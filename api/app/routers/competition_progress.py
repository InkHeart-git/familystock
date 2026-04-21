"""
赛季进度可视化 API
- AI收益排行实时榜单
- 算法评分命中率追踪
- 每日操作热力图
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/competition", tags=["赛季进度"])

DB_PATH = "/var/www/ai-god-of-stocks/ai_god.db"


# ============== 数据模型 ==============

class AIRankItem(BaseModel):
    """AI收益排行单项"""
    rank: int
    ai_id: int
    ai_name: str
    emoji: str
    total_value: float
    cash: float
    holdings_value: float
    profit: float
    profit_rate: float
    seed_capital: float


class ScoreHitItem(BaseModel):
    """评分命中追踪单项"""
    ai_id: int
    ai_name: str
    symbol: str
    name: str
    buy_date: str
    buy_price: float
    buy_score: int
    current_price: Optional[float]
    day5_price: Optional[float]
    day5_return: Optional[float]
    current_return: Optional[float]


class HeatmapCell(BaseModel):
    """热力图单元格"""
    date: str
    ai_id: int
    ai_name: str
    symbol: str
    action: str
    quantity: int
    price: float


class DailyHeatmap(BaseModel):
    """每日操作热力图"""
    date: str
    trades: list[HeatmapCell]
    ai_summary: dict  # ai_id -> {buys: n, sells: n}


# ============== 工具函数 ==============

def get_db():
    """获取数据库连接"""
    return sqlite3.connect(DB_PATH)


def get_ai_info(conn, ai_id: int) -> dict:
    """获取AI角色信息"""
    cursor = conn.execute(
        "SELECT id, name, emoji, style FROM ai_characters WHERE id = ?",
        (str(ai_id),)
    )
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "name": row[1], "emoji": row[2] or "🤖", "style": row[3]}
    return {"id": str(ai_id), "name": f"AI-{ai_id}", "emoji": "🤖", "style": ""}


# ============== API 端点 ==============

@router.get("/leaderboard", response_model=list[AIRankItem])
def get_leaderboard():
    """
    获取AI收益排行实时榜单
    按总资产降序排列
    """
    conn = get_db()
    try:
        cursor = conn.execute("""
            SELECT 
                p.ai_id,
                p.cash,
                p.total_value,
                p.seed_capital,
                p.updated_at
            FROM ai_portfolios p
            ORDER BY p.total_value DESC
        """)
        
        ranks = []
        for rank, row in enumerate(cursor.fetchall(), 1):
            ai_id = row[0]
            ai_info = get_ai_info(conn, ai_id)
            cash = row[1]
            total_value = row[2]
            seed_capital = row[3] or total_value  # 如果没有种子资金，用当前总资产
            holdings_value = total_value - cash
            profit = total_value - seed_capital
            profit_rate = (profit / seed_capital * 100) if seed_capital > 0 else 0
            
            ranks.append(AIRankItem(
                rank=rank,
                ai_id=ai_id,
                ai_name=ai_info["name"],
                emoji=ai_info["emoji"],
                total_value=round(total_value, 2),
                cash=round(cash, 2),
                holdings_value=round(holdings_value, 2),
                profit=round(profit, 2),
                profit_rate=round(profit_rate, 2)
            ))
        
        return ranks
    finally:
        conn.close()


@router.get("/score-tracking", response_model=list[ScoreHitItem])
def get_score_tracking(days: int = 30):
    """
    获取算法评分命中率追踪
    追踪买入后5日收益 vs 评分相关性
    
    Args:
        days: 追踪最近多少天的买入记录
    """
    conn = get_db()
    try:
        # 获取最近days天内的BUY交易记录
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        cursor = conn.execute("""
            SELECT 
                t.ai_id,
                t.symbol,
                t.name,
                t.price as buy_price,
                t.score,
                t.created_at
            FROM ai_trades t
            WHERE t.action = 'BUY'
            AND t.created_at >= ?
            ORDER BY t.created_at DESC
        """, (cutoff,))
        
        # 从 tushare 或行情API 获取后续价格（这里先用占位）
        results = []
        for row in cursor.fetchall():
            ai_id = row[0]
            symbol = row[1]
            name = row[2]
            buy_price = row[3]
            buy_score = row[4]
            buy_date = row[5]
            
            ai_info = get_ai_info(conn, ai_id)
            
            # 这里需要调用行情API获取后续价格
            # 暂时返回基本信息，后续接入MiniRock行情
            results.append(ScoreHitItem(
                ai_id=ai_id,
                ai_name=ai_info["name"],
                symbol=symbol,
                name=name,
                buy_date=buy_date,
                buy_price=buy_price,
                buy_score=buy_score,
                current_price=None,
                day5_price=None,
                day5_return=None,
                current_return=None
            ))
        
        return results
    finally:
        conn.close()


@router.get("/heatmap/daily", response_model=list[DailyHeatmap])
def get_daily_heatmap(days: int = 7):
    """
    获取每日操作热力图
    显示哪些股票被哪些AI买卖
    
    Args:
        days: 显示最近多少天
    """
    conn = get_db()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        cursor = conn.execute("""
            SELECT 
                DATE(created_at) as trade_date,
                ai_id,
                symbol,
                action,
                quantity,
                price
            FROM ai_trades
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """, (cutoff,))
        
        # 按日期分组
        daily_data = defaultdict(lambda: {"trades": [], "ai_summary": defaultdict(lambda: {"buys": 0, "sells": 0})})
        
        for row in cursor.fetchall():
            trade_date = row[0]
            ai_id = row[1]
            symbol = row[2]
            action = row[3]
            quantity = row[4]
            price = row[5]
            
            ai_info = get_ai_info(conn, ai_id)
            
            cell = HeatmapCell(
                date=trade_date,
                ai_id=ai_id,
                ai_name=ai_info["name"],
                symbol=symbol,
                name="",  # 可后续补充
                action=action,
                quantity=quantity,
                price=price
            )
            
            daily_data[trade_date]["trades"].append(cell)
            if action == "BUY":
                daily_data[trade_date]["ai_summary"][ai_id]["buys"] += 1
            elif action == "SELL":
                daily_data[trade_date]["ai_summary"][ai_id]["sells"] += 1
        
        # 转换为响应格式
        result = []
        for date in sorted(daily_data.keys(), reverse=True):
            data = daily_data[date]
            # 转换 ai_summary 的 key 为字符串（JSON兼容性）
            ai_summary_str = {str(k): v for k, v in data["ai_summary"].items()}
            result.append(DailyHeatmap(
                date=date,
                trades=data["trades"],
                ai_summary=ai_summary_str
            ))
        
        return result
    finally:
        conn.close()


@router.get("/summary")
def get_competition_summary():
    """
    获取赛季总览数据
    """
    conn = get_db()
    try:
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total_trades,
                COUNT(DISTINCT ai_id) as ai_count,
                COUNT(DISTINCT symbol) as stock_count,
                MIN(created_at) as first_trade,
                MAX(created_at) as last_trade
            FROM ai_trades
        """)
        row = cursor.fetchone()

        today = datetime.now().strftime("%Y-%m-%d")
        cursor = conn.execute("""
            SELECT COUNT(*) FROM ai_trades WHERE DATE(created_at) = ?
        """, (today,))
        today_trades = cursor.fetchone()[0]

        return {
            "total_trades": row[0],
            "ai_count": row[1],
            "stock_count": row[2],
            "first_trade": row[3],
            "last_trade": row[4],
            "today_trades": today_trades,
            "season_start": "2026-04-19",
            "update_time": datetime.now().isoformat()
        }
    finally:
        conn.close()


# ============== Phase 4.6: 赛季积分体系 ==============

class AIScoringItem(BaseModel):
    """AI积分单项"""
    ai_id: int
    ai_name: str
    emoji: str
    # 综合积分
    total_score: float       # 综合积分 (0-100)
    total_score_rank: int     # 综合排名
    # 子项积分
    return_score: float      # 收益率分 (0-100, 权重60%)
    return_rate: float       # 累计收益率%
    return_rate_rank: int     # 收益率排名
    winrate_score: float      # 胜率分 (0-100, 权重25%)
    win_count: int            # 盈利笔数
    total_closed: int         # 已平仓总笔数
    win_rate: float          # 胜率%
    winrate_rank: int         # 胜率排名
    accuracy_score: float     # 评分准确分 (0-100, 权重15%)
    high_rating_hits: int      # 高评分买入→盈利次数
    high_rating_total: int    # 高评分买入总次数
    rating_accuracy: float    # 评分命中率%
    accuracy_rank: int         # 评分准确排名


@router.get("/scoring", response_model=list[AIScoringItem])
def get_competition_scoring():
    """
    赛季积分体系 API (Phase 4.6)

    综合积分 = 收益率分(60%) + 胜率分(25%) + 评分准确分(15%)

    收益率分：按 ai_portfolios.total_value 计算累计收益率，
             在所有AI中归一化到0-100分段
    胜率分：按已平仓交易中盈利占比计算
    评分准确分：买入评分>=70的高评分交易，后5日收益为正的比例
    """
    conn = get_db()
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        # 用于算收益率的基准日（赛季第一天）
        season_start = "2026-04-19"

        # ---- 1. 获取各AI收益率数据 ----
        cursor = conn.execute("""
            SELECT
                p.ai_id,
                p.cash,
                p.total_value,
                p.seed_capital,
                p.updated_at
            FROM ai_portfolios p
        """)
        portfolio_data = {}
        for row in cursor.fetchall():
            ai_id = row[0]
            cash = row[1]
            total_value = row[2]
            seed_capital = row[3] or 1000000.0
            profit_rate = (total_value - seed_capital) / seed_capital * 100 if seed_capital > 0 else 0.0
            portfolio_data[ai_id] = {
                "cash": cash,
                "total_value": total_value,
                "seed_capital": seed_capital,
                "profit_rate": profit_rate,
            }

        # ---- 2. 获取各AI胜率数据（已平仓的 SELL/CLEARED 交易） ----
        cursor = conn.execute("""
            SELECT
                ai_id,
                COUNT(*) as total_closed,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_count
            FROM ai_trades
            WHERE action IN ('SELL', 'CLEARED')
            GROUP BY ai_id
        """)
        winrate_data = {}
        for row in cursor.fetchall():
            ai_id = row[0]
            total_closed = row[1] or 0
            win_count = row[2] or 0
            win_rate = (win_count / total_closed * 100) if total_closed > 0 else 0.0
            winrate_data[ai_id] = {
                "total_closed": total_closed,
                "win_count": win_count,
                "win_rate": win_rate,
            }

        # ---- 3. 获取各AI评分准确数据（买入评分>=70，追踪后5日） ----
        # 从 ai_trades 取高评分买入记录
        cursor = conn.execute("""
            SELECT
                ai_id,
                COUNT(*) as total_high,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as hits
            FROM ai_trades
            WHERE action = 'BUY'
              AND score >= 70
            GROUP BY ai_id
        """)
        accuracy_data = {}
        for row in cursor.fetchall():
            ai_id = row[0]
            total_high = row[1] or 0
            hits = row[2] or 0
            accuracy = (hits / total_high * 100) if total_high > 0 else 0.0
            accuracy_data[ai_id] = {
                "high_rating_total": total_high,
                "high_rating_hits": hits,
                "rating_accuracy": accuracy,
            }

        # ---- 4. 收集所有AI ID（从 ai_characters） ----
        cursor = conn.execute("SELECT id, name, emoji FROM ai_characters")
        ai_chars = {str(row[0]): {"name": row[1], "emoji": row[2] or "🤖"} for row in cursor.fetchall()}

        # ---- 5. 计算所有AI的原始分 ----
        all_ai_ids = set(list(portfolio_data.keys()) +
                         list(winrate_data.keys()) +
                         list(accuracy_data.keys()))

        raw_scores = {}
        for ai_id in all_ai_ids:
            p = portfolio_data.get(ai_id, {"profit_rate": 0.0})
            w = winrate_data.get(ai_id, {"win_rate": 0.0, "win_count": 0, "total_closed": 0})
            a = accuracy_data.get(ai_id, {"rating_accuracy": 0.0, "high_rating_hits": 0, "high_rating_total": 0})

            raw_scores[ai_id] = {
                "return_rate": p["profit_rate"],
                "win_rate": w["win_rate"],
                "win_count": w["win_count"],
                "total_closed": w["total_closed"],
                "rating_accuracy": a["rating_accuracy"],
                "high_rating_hits": a["high_rating_hits"],
                "high_rating_total": a["high_rating_total"],
            }

        # ---- 6. 归一化：每个维度单独排名再映射到0-100 ----
        def rank_normalize(values_dict):
            """返回 {ai_id: norm_score}，归一化到0-100"""
            sorted_ais = sorted(values_dict.keys(), key=lambda x: values_dict[x], reverse=True)
            n = len(sorted_ais)
            result = {}
            for rank, ai_id in enumerate(sorted_ais, 1):
                result[ai_id] = round((n - rank) / max(n - 1, 1) * 100, 2) if n > 1 else 100.0
            return result

        return_scores = {ai_id: v["return_rate"] for ai_id, v in raw_scores.items()}
        winrate_scores = {ai_id: v["win_rate"] for ai_id, v in raw_scores.items()}
        accuracy_scores = {ai_id: v["rating_accuracy"] for ai_id, v in raw_scores.items()}

        norm_return = rank_normalize(return_scores)
        norm_winrate = rank_normalize(winrate_scores)
        norm_accuracy = rank_normalize(accuracy_scores)

        # ---- 7. 计算综合积分 ----
        results = []
        for ai_id in all_ai_ids:
            ret_s = norm_return.get(ai_id, 0.0)
            win_s = norm_winrate.get(ai_id, 0.0)
            acc_s = norm_accuracy.get(ai_id, 0.0)
            total_s = round(ret_s * 0.60 + win_s * 0.25 + acc_s * 0.15, 2)

            info = ai_chars.get(str(ai_id), {"name": f"AI-{ai_id}", "emoji": "🤖"})
            results.append({
                "ai_id": ai_id,
                "ai_name": info["name"],
                "emoji": info["emoji"],
                "total_score": total_s,
                "return_score": round(ret_s, 2),
                "return_rate": round(raw_scores[ai_id]["return_rate"], 2),
                "winrate_score": round(win_s, 2),
                "win_count": raw_scores[ai_id]["win_count"],
                "total_closed": raw_scores[ai_id]["total_closed"],
                "win_rate": round(raw_scores[ai_id]["win_rate"], 2),
                "accuracy_score": round(acc_s, 2),
                "high_rating_hits": raw_scores[ai_id]["high_rating_hits"],
                "high_rating_total": raw_scores[ai_id]["high_rating_total"],
                "rating_accuracy": round(raw_scores[ai_id]["rating_accuracy"], 2),
                "raw": raw_scores[ai_id],
            })

        # 按综合积分降序
        results.sort(key=lambda x: x["total_score"], reverse=True)

        # 填排名
        for rank, item in enumerate(results, 1):
            item["total_score_rank"] = rank

        # 填各子项排名
        def assign_sub_rank(items, key):
            sorted_items = sorted(items, key=lambda x: x[key if key != "return_rate" else "return_score"], reverse=True)
            for r, it in enumerate(sorted_items, 1):
                it[key if key != "return_rate" else "return_score_rank"] = r

        # 分别按子项排序获取各子项排名
        for sub_key, score_key in [("return_score", "return_rate"),
                                    ("winrate_score", "win_rate"),
                                    ("accuracy_score", "rating_accuracy")]:
            sorted_by_sub = sorted(results, key=lambda x: x[sub_key], reverse=True)
            for r, it in enumerate(sorted_by_sub, 1):
                it[sub_key + "_rank"] = r

        # 最终输出（去掉 raw 临时字段）
        output = []
        for item in results:
            ai_id = item.pop("ai_id")
            raw = item.pop("raw")
            output.append(AIScoringItem(**item))

        return output
    finally:
        conn.close()
