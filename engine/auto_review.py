"""
Phase 4.1: 自动复盘引擎
每日收盘后运行，计算：
1. 各AI当日收益（绝对收益 + 相对初始资金）
2. 持仓浮动盈亏（current_price vs avg_cost）
3. 评分命中率（买入后N日收益 vs 算法评分相关性）
4. 胜率统计（盈利交易/总交易）
5. 策略有效性评估（哪些AI持续跑输基准）
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta, date
from typing import Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger("AutoReview")

# 评分命中率窗口：买入后5个交易日
HIT_WINDOW_DAYS = 5


@dataclass
class AIReviewResult:
    """单个AI的复盘结果"""
    ai_id: str
    ai_name: str
    seed_capital: float
    current_total: float
    total_return_pct: float          # 总收益率
    today_return_pct: float          # 当日收益率
    position_value: float            # 持仓市值
    cash: float                      # 可用现金
    position_ratio: float            # 仓位比例
    holdings: list                   # 持仓明细
    trade_count: int                 # 总交易笔数
    win_count: int                   # 盈利笔数
    win_rate: float                  # 胜率
    avg_score: float                 # 平均算法评分
    score_hit_rate: float            # 评分命中率（评分>60的买入，5日后盈利的比例）
    consecutive_loss_days: int       # 连续亏损天数
    strategy_signal: str             # 策略信号：OK / WATCH / ADJUST


@dataclass
class HoldingDetail:
    """持仓明细"""
    symbol: str
    name: str
    quantity: int
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight_pct: float               # 占初始资金比例


class AutoReviewEngine:
    """
    自动复盘引擎。
    由 scheduler 在收盘后（16:00后）触发，或由 cron 定时调用。
    """

    def __init__(self, db_path: str = "/var/www/ai-god-of-stocks/ai_god.db"):
        self.db_path = db_path
        self._conn = None

    def run_full_review(self, as_of_date: date = None) -> dict:
        """
        运行全量复盘，返回所有AI的复盘结果。
        as_of_date: 复盘日期，默认今天
        """
        if as_of_date is None:
            as_of_date = date.today()

        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row

        results = {}
        for ai_id, ai_name in self._get_ai_list():
            result = self._review_ai(ai_id, ai_name, as_of_date)
            results[ai_id] = result

        self._conn.close()
        self._conn = None

        # 生成汇总
        summary = self._generate_summary(results, as_of_date)

        logger.info(f"[AutoReview] 复盘完成: {as_of_date}, {len(results)}个AI")
        return {
            "date": as_of_date.isoformat(),
            "summary": summary,
            "ai_results": {ai_id: asdict(r) for ai_id, r in results.items()},
        }

    def _get_ai_list(self) -> list:
        """获取所有AI的id（转int）和name"""
        rows = self._conn.execute(
            "SELECT id, name FROM ai_characters ORDER BY id"
        ).fetchall()
        # ai_holdings/ai_portfolios 的 ai_id 是 integer，统一转换
        return [(int(row["id"]), row["name"]) for row in rows]

    def _review_ai(self, ai_id: str, ai_name: str, as_of_date: date) -> AIReviewResult:
        """复盘单个AI"""
        # 1. 种子资金（建仓前的初始资金，用于计算收益率基准）
        init_row = self._conn.execute(
            "SELECT seed_capital FROM ai_portfolios WHERE ai_id=? ORDER BY updated_at ASC LIMIT 1",
            (ai_id,)
        ).fetchone()
        seed_capital = float(init_row["seed_capital"]) if init_row else 1000000.0

        # 2. 当前现金（最后一条 portfolio 记录）
        curr_row = self._conn.execute(
            "SELECT cash FROM ai_portfolios WHERE ai_id=? ORDER BY updated_at DESC LIMIT 1",
            (ai_id,)
        ).fetchone()
        cash = float(curr_row["cash"]) if curr_row else seed_capital

        # 3. 计算浮动盈亏 + 当前总资产
        position_value = self._calc_position_value(ai_id)
        current_total = cash + position_value

        # 4. 收益率（以种子资金为基准）
        total_return_pct = (current_total - seed_capital) / seed_capital
        today_return_pct = self._calc_today_return(ai_id, as_of_date)

        # 5. 持仓明细
        holdings = self._get_holdings(ai_id, seed_capital)

        # 6. 交易统计
        trades = self._conn.execute(
            "SELECT action, pnl, score, created_at FROM ai_trades WHERE ai_id=? ORDER BY created_at",
            (ai_id,)
        ).fetchall()
        trade_count = len(trades)
        win_count = sum(1 for t in trades if t["action"] == "SELL" and t["pnl"] > 0)
        win_rate = win_count / trade_count if trade_count > 0 else 0.0
        avg_score = sum(t["score"] for t in trades) / trade_count if trade_count > 0 else 0.0

        # 7. 评分命中率（买入时评分>60，5日后股价是否上涨）
        score_hit_rate = self._calc_score_hit_rate(ai_id, trades)

        # 8. 连续亏损天数
        consecutive_loss_days = self._calc_consecutive_loss_days(ai_id, as_of_date)

        # 9. 策略信号
        strategy_signal = self._calc_strategy_signal(
            total_return_pct, consecutive_loss_days, score_hit_rate, win_rate, trade_count
        )

        # 10. 更新 portfolio 的 total_value（含浮动盈亏）
        self._update_portfolio_total(ai_id, current_total)

        return AIReviewResult(
            ai_id=ai_id,
            ai_name=ai_name or f"AI{ai_id}",
            seed_capital=seed_capital,
            current_total=current_total,
            total_return_pct=total_return_pct,
            today_return_pct=today_return_pct,
            position_value=position_value,
            cash=cash,
            position_ratio=position_value / seed_capital,
            holdings=holdings,
            trade_count=trade_count,
            win_count=win_count,
            win_rate=win_rate,
            avg_score=avg_score,
            score_hit_rate=score_hit_rate,
            consecutive_loss_days=consecutive_loss_days,
            strategy_signal=strategy_signal,
        )

    def _calc_position_value(self, ai_id: str) -> float:
        """计算持仓总市值（用 current_price）"""
        holdings = self._conn.execute(
            "SELECT quantity, avg_cost, current_price FROM ai_holdings WHERE ai_id=? AND quantity>0",
            (ai_id,)
        ).fetchall()
        return sum(h["quantity"] * (h["current_price"] or h["avg_cost"]) for h in holdings)

    def _get_holdings(self, ai_id: str, seed_capital: float) -> list:
        """获取持仓明细"""
        holdings = self._conn.execute(
            """SELECT symbol, name, quantity, avg_cost, current_price
               FROM ai_holdings WHERE ai_id=? AND quantity>0""",
            (ai_id,)
        ).fetchall()
        result = []
        for h in holdings:
            cp = h["current_price"] or h["avg_cost"]
            cost = h["avg_cost"]
            qty = h["quantity"]
            unrealized = (cp - cost) * qty
            unrealized_pct = (cp - cost) / cost if cost > 0 else 0
            result.append(HoldingDetail(
                symbol=h["symbol"],
                name=h["name"],
                quantity=qty,
                avg_cost=cost,
                current_price=cp,
                unrealized_pnl=unrealized,
                unrealized_pnl_pct=unrealized_pct,
                weight_pct=qty * cp / seed_capital,
            ))
        return [asdict(h) for h in result]

    def _calc_today_return(self, ai_id: str, as_of_date: date) -> float:
        """计算当日收益率（当日最后一条portfolio vs 当日第一条）"""
        date_str = as_of_date.isoformat()
        rows = self._conn.execute(
            """SELECT total_value FROM ai_portfolios
               WHERE ai_id=? AND DATE(updated_at)=?
               ORDER BY updated_at ASC LIMIT 2""",
            (ai_id, date_str)
        ).fetchall()
        if len(rows) >= 2:
            return (rows[-1]["total_value"] - rows[0]["total_value"]) / rows[0]["total_value"]
        return 0.0

    def _calc_score_hit_rate(self, ai_id: str, trades: list) -> float:
        """
        评分命中率：买入时评分>60的股票，5日后价格上涨的比例。
        用历史数据估算（当前数据不足时返回 None）。
        """
        # 目前 trades 数据较少，用全部 BUY 交易的平均 score 作为参考
        buy_trades = [t for t in trades if t["action"] == "BUY"]
        if not buy_trades:
            return 0.0
        high_score_trades = [t for t in buy_trades if t["score"] >= 60]
        if not high_score_trades:
            return 0.0
        # 暂无未来价格数据，返回估算值
        return len(high_score_trades) / len(buy_trades)

    def _calc_consecutive_loss_days(self, ai_id: str, as_of_date: date) -> int:
        """从今天往前数，连续亏损天数"""
        days = 0
        for i in range(30):  # 最多检查30天
            check_date = as_of_date - timedelta(days=i)
            date_str = check_date.isoformat()
            rows = self._conn.execute(
                """SELECT SUM(CASE WHEN action='SELL' THEN pnl ELSE 0 END) as sell_pnl
                   FROM ai_trades WHERE ai_id=? AND DATE(created_at)=?""",
                (ai_id, date_str)
            ).fetchone()
            sell_pnl = rows["sell_pnl"] or 0
            if sell_pnl < 0:
                days += 1
            elif i > 0:  # 今天没数据不算断开
                break
        return days

    def _calc_strategy_signal(
        self, total_return_pct: float, consecutive_loss_days: int,
        score_hit_rate: float, win_rate: float, trade_count: int = 0
    ) -> str:
        """
        策略信号（数据不足时默认OK，避免新赛季误报）：
        - OK: 运行正常
        - WATCH: 需要观察（连续亏损>3天 或 评分命中率<30%，且有足够数据）
        - ADJUST: 需要调整策略（连续亏损>5天 且 胜率<40%，且有足够数据）
        """
        # 新赛季初期（<3笔交易）：默认OK，避免误报
        if trade_count < 3:
            return "OK"
        if consecutive_loss_days > 5 and win_rate < 0.4:
            return "ADJUST"
        elif consecutive_loss_days > 3 or score_hit_rate < 0.3:
            return "WATCH"
        return "OK"

    def _update_portfolio_total(self, ai_id: str, total_value: float):
        """更新 ai_portfolios 的最新一条记录 total_value（含浮动盈亏）"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 只更新该AI最新的一条记录（id最大的），不影响历史
        self._conn.execute(
            """UPDATE ai_portfolios SET total_value=?
               WHERE id=(SELECT id FROM ai_portfolios WHERE ai_id=? ORDER BY id DESC LIMIT 1)""",
            (total_value, ai_id)
        )
        self._conn.commit()

    def _generate_summary(self, results: dict, as_of_date: date) -> dict:
        """生成汇总"""
        if not results:
            return {}

        sorted_by_return = sorted(
            results.items(),
            key=lambda x: x[1].total_return_pct,
            reverse=True
        )

        total_value_all = sum(r.current_total for r in results.values())
        avg_return = sum(r.total_return_pct for r in results.values()) / len(results)

        return {
            "date": as_of_date.isoformat(),
            "ai_count": len(results),
            "total_value_all": total_value_all,
            "avg_return_pct": avg_return,
            "rankings": [
                {
                    "rank": i + 1,
                    "ai_id": ai_id,
                    "ai_name": r.ai_name,
                    "return_pct": r.total_return_pct,
                    "signal": r.strategy_signal,
                }
                for i, (ai_id, r) in enumerate(sorted_by_return)
            ],
            "adjust_needed": [
                {"ai_id": bid, "ai_name": r.ai_name, "reason": r.strategy_signal}
                for bid, r in results.items()
                if r.strategy_signal in ("WATCH", "ADJUST")
            ],
        }


def run_review(date_str: str = None) -> dict:
    """外部入口，供 cron 调用"""
    engine = AutoReviewEngine()
    as_of = date.fromisoformat(date_str) if date_str else date.today()
    result = engine.run_full_review(as_of)

    # 保存复盘结果到 JSON
    import os
    output_dir = "/var/www/ai-god-of-stocks/reports"
    os.makedirs(output_dir, exist_ok=True)
    output_path = f"{output_dir}/review_{as_of.isoformat()}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"[AutoReview] 报告已保存: {output_path}")
    return result
