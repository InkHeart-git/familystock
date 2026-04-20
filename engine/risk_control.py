"""
Phase 3.3 + 3.4: 账户风控模块
- 仓位上限：单股≤20%仓位，总仓位≤150%
- 现金充足性：买入金额不能超过可用现金
- 单日止损：亏损>3%暂停该AI交易30分钟
"""

import sqlite3
import logging
import time
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger("RiskControl")

# 单股最大仓位比例
MAX_SINGLE_POSITION_PCT = 0.20  # 20%
# 总仓位上限（相对初始资金）
MAX_TOTAL_POSITION_PCT = 1.50   # 150%


class RiskController:
    """
    账户级风控检查器。
    所有交易执行前必须经过 check_trade() 检查。
    """

    def __init__(self, db_path: str = "/var/www/ai-god-of-stocks/ai_god.db"):
        self.db_path = db_path
        self._pause_until: Optional[float] = None  # pause until timestamp

    def check_trade(
        self,
        ai_id: str,
        action: str,      # "BUY" or "SELL"
        symbol: str,
        quantity: int,
        price: float,
    ) -> Tuple[bool, str]:
        """
        检查交易是否允许执行。
        返回 (允许, 原因)。不允许时原因说明触发了哪条规则。
        """
        if self._is_paused():
            return False, f"风控暂停中，暂停至 {datetime.fromtimestamp(self._pause_until)}"

        if action.upper() != "BUY":
            return True, "SELL无需风控检查"

        # ── 规则1: 仓位上限检查 ────────────────────────────
        allowed, reason = self._check_position_limit(ai_id, symbol, quantity, price)
        if not allowed:
            return False, reason

        # ── 规则2: 现金充足性检查 ──────────────────────────
        allowed, reason = self._check_cash_sufficient(ai_id, quantity, price)
        if not allowed:
            return False, reason

        return True, "通过"

    def _is_paused(self) -> bool:
        """检查是否处于暂停期"""
        if self._pause_until and time.time() < self._pause_until:
            return True
        self._pause_until = None
        return False

    def _check_position_limit(
        self, ai_id: str, symbol: str, quantity: int, price: float
    ) -> Tuple[bool, str]:
        """规则1: 单股仓位≤20%，总仓位≤150%"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row

            # 获取初始资金（ai_portfolios 的第一条记录）
            init_row = conn.execute(
                "SELECT total_value FROM ai_portfolios WHERE ai_id=? ORDER BY updated_at ASC LIMIT 1",
                (ai_id,)
            ).fetchone()
            initial_capital = float(init_row["total_value"]) if init_row else 1000000.0

            # 当前总资产和现金
            current = conn.execute(
                "SELECT cash, total_value FROM ai_portfolios WHERE ai_id=? ORDER BY updated_at DESC LIMIT 1",
                (ai_id,)
            ).fetchone()
            if not current:
                return True, "无portfolio记录，跳过"

            current_cash = float(current["cash"])
            current_total = float(current["total_value"])

            # 当前各持仓市值
            holdings = conn.execute(
                "SELECT symbol, quantity, avg_cost FROM ai_holdings WHERE ai_id=? AND quantity>0",
                (ai_id,)
            ).fetchall()

            # 计算当前各持仓市值
            current_positions_value = 0.0
            position_by_symbol = {}
            for h in holdings:
                sym = h["symbol"]
                # 用 avg_cost 估算当前市值（未更新 current_price 时用 avg_cost）
                val = h["quantity"] * (h["avg_cost"] or 0)
                current_positions_value += val
                position_by_symbol[sym] = val

            # 本次买入金额
            buy_amount = quantity * price

            # 新增后总持仓市值
            new_total_position_value = current_positions_value + buy_amount

            # 检查单股仓位（如果已持有该股，需要累加）
            existing_value = position_by_symbol.get(symbol, 0.0)
            new_single_value = existing_value + buy_amount
            single_pct = new_single_value / initial_capital
            if single_pct > MAX_SINGLE_POSITION_PCT:
                return False, (
                    f"单股仓位超限: {symbol} "
                    f"当前{existing_value/initial_capital:.1%}+本次{buy_amount/initial_capital:.1%}"
                    f"={single_pct:.1%} > {MAX_SINGLE_POSITION_PCT:.0%}上限"
                )

            # 检查总仓位
            new_total_pct = new_total_position_value / initial_capital
            if new_total_pct > MAX_TOTAL_POSITION_PCT:
                return False, (
                    f"总仓位超限: {new_total_pct:.1%} > {MAX_TOTAL_POSITION_PCT:.0%}上限"
                )

            return True, "仓位检查通过"

        finally:
            conn.close()

    def _check_cash_sufficient(
        self, ai_id: str, quantity: int, price: float
    ) -> Tuple[bool, str]:
        """规则3: 现金是否充足"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT cash FROM ai_portfolios WHERE ai_id=? ORDER BY updated_at DESC LIMIT 1",
                (ai_id,)
            ).fetchone()
            cash = float(row["cash"]) if row else 1000000.0
            cost = quantity * price
            if cost > cash:
                return False, f"资金不足: 需要{cost:.2f}，只有{cash:.2f}"
            return True, "现金充足"
        finally:
            conn.close()

    def check_daily_loss(self, ai_id: str) -> Tuple[bool, str]:
        """
        规则3: 单日亏损>3%则暂停该AI交易30分钟。
        检查当前总资产相对初始资金的亏损幅度。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row

            # 今日开盘时总资产（用 ai_portfolios 最早记录，或者 ai_trades 第一条的时间戳）
            today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")

            # 今日第一笔买入前的 total_value 作为今日初始
            first_trade = conn.execute(
                """SELECT created_at FROM ai_trades
                   WHERE ai_id=? AND action='BUY' AND created_at>=?
                   ORDER BY created_at ASC LIMIT 1""",
                (ai_id, today_start)
            ).fetchone()

            if first_trade:
                # 取这笔交易前的 total_value
                trade_time = first_trade["created_at"]
                prev = conn.execute(
                    """SELECT total_value FROM ai_portfolios
                       WHERE ai_id=? AND updated_at<=?
                       ORDER BY updated_at DESC LIMIT 1""",
                    (ai_id, trade_time)
                ).fetchone()
                initial_today = float(prev["total_value"]) if prev else None
            else:
                initial_today = None

            # 如果无法确定今日初始，用昨日收盘或初始资金
            if not initial_today:
                # 用 ai_portfolios 第一条（初始资金）
                init_row = conn.execute(
                    "SELECT total_value FROM ai_portfolios WHERE ai_id=? ORDER BY updated_at ASC LIMIT 1",
                    (ai_id,)
                ).fetchone()
                initial_today = float(init_row["total_value"]) if init_row else 1000000.0

            # 当前总资产
            current = conn.execute(
                "SELECT total_value FROM ai_portfolios WHERE ai_id=? ORDER BY updated_at DESC LIMIT 1",
                (ai_id,)
            ).fetchone()
            current_total = float(current["total_value"]) if current else initial_today

            loss_pct = (initial_today - current_total) / initial_today
            if loss_pct > 0.03:
                self._trigger_pause()
                return False, (
                    f"单日亏损{loss_pct:.2%} > 3%红线，"
                    f"暂停{ai_id}交易30分钟（暂停至 {datetime.fromtimestamp(self._pause_until).strftime('%H:%M')}）"
                )
            return True, f"亏损{loss_pct:.2%}，在安全范围内"

        finally:
            conn.close()

    def _trigger_pause(self):
        """触发30分钟交易暂停"""
        self._pause_until = time.time() + 1800  # 30分钟
        self._daily_loss_triggered = True
        self._daily_loss_time = time.time()
        logger.warning(f"风控触发: 单日亏损>3%，暂停所有交易至 {datetime.fromtimestamp(self._pause_until)}")

    def is_trading_paused(self) -> bool:
        """供外部查询是否暂停"""
        return self._is_paused()

    def get_pause_remaining_seconds(self) -> int:
        """剩余暂停时间（秒）"""
        if self._pause_until and time.time() < self._pause_until:
            return int(self._pause_until - time.time())
        return 0


# 全局单例（所有AI共享一个风控器）
_risk_controller: Optional[RiskController] = None

def get_risk_controller(db_path: str = "/var/www/ai-god-of-stocks/ai_god.db") -> RiskController:
    global _risk_controller
    if _risk_controller is None:
        _risk_controller = RiskController(db_path)
    return _risk_controller
