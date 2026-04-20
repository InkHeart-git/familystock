"""
Phase 4.3: 多脑协调模块
- 板块拥挤度检测：多个AI同时想买同一只股时，按比例分配数量
- 空仓优先权：空仓AI优先于持仓AI分配热门股票
- 决策意图追踪：记录近期所有AI的买入意向，协调冲突
"""

import sqlite3
import logging
import time
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger("MultiBrainCoordinator")

# 协调窗口：最近多少秒内的买入意向视为"同时"
INTENTION_WINDOW_SECONDS = 120  # 2分钟内多个AI想买 = 冲突

# 拥挤度阈值：超过这个数量的AI想买同一股，触发分配
CONGESTION_THRESHOLD = 2  # 2个以上AI想买同一股 → 分配

# 单个AI在拥挤时最多能买的比例
MAX_SHARE_IN_CONGESTION = 0.5  # 50%：最多占意向总量的50%


@dataclass
class BuyIntention:
    """一个AI的买入意向"""
    ai_id: str
    ai_name: str
    symbol: str
    name: str
    quantity: int      # 原始想要的数量
    price: float
    score: int         # MiniRock 评分（越高越优先）
    is_empty: bool     # 是否当前空仓
    timestamp: float


class MultiBrainCoordinator:
    """
    多脑协调器（全局单例）。
    负责：
    1. 记录各AI的买入意向（临时表）
    2. 检测板块拥挤度
    3. 协调冲突，给出"实际可买数量"
    """

    def __init__(self, db_path: str = "/var/www/ai-god-of-stocks/ai_god.db"):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        """确保协调临时表存在"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_buy_intentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ai_id TEXT NOT NULL,
                    ai_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    score INTEGER DEFAULT 0,
                    is_empty INTEGER DEFAULT 0,
                    timestamp REAL NOT NULL,
                    allocated_quantity INTEGER,
                    coordinated INTEGER DEFAULT 0,
                    UNIQUE(ai_id, symbol)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_intentions_symbol
                ON ai_buy_intentions(symbol, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_intentions_timestamp
                ON ai_buy_intentions(timestamp)
            """)
            conn.commit()
        finally:
            conn.close()

    def register_intention(
        self,
        ai_id: str,
        ai_name: str,
        symbol: str,
        name: str,
        quantity: int,
        price: float,
        score: int = 0,
        is_empty: bool = False,
    ) -> int:
        """
        注册一个买入意向。
        如果该 ai+symbol 已有未协调的意向，先删除再写入（更新）。
        返回该AI在该股票上的"协调后数量"（可能与原始数量相同或减少）。
        """
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        try:
            # 删除该AI对该股的旧意向（未协调的）
            conn.execute(
                "DELETE FROM ai_buy_intentions WHERE ai_id=? AND symbol=? AND coordinated=0",
                (ai_id, symbol)
            )
            # 写入新意向
            conn.execute(
                """INSERT INTO ai_buy_intentions
                   (ai_id, ai_name, symbol, name, quantity, price, score, is_empty, timestamp, allocated_quantity, coordinated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (ai_id, ai_name, symbol, name, quantity, price, score, int(is_empty), now, quantity)
            )
            conn.commit()
            logger.info(
                f"[Coordinator] {ai_name} 注册买入意向: {symbol} {quantity}股 @{price} "
                f"(评分{score}, {'空仓' if is_empty else '持仓中'})"
            )
            # 触发协调，并返回当前AI的分配数量
            self._coordinate_intentions(symbol, conn=conn)
            allocated_qty = self.get_allocated_quantity(ai_id, symbol)
            return allocated_qty
        finally:
            conn.close()

    def _coordinate_intentions(self, symbol: str, conn: sqlite3.Connection) -> int:
        """
        核心协调逻辑：检测并协调该股票的买入意向冲突。
        策略：
        1. 收集窗口期内所有未协调的意向
        2. 如果意向数 > CONGESTION_THRESHOLD，触发分配
        3. 空仓AI优先：空仓AI总数量先除以总数量，得到分配比例
        4. 每人最多 MAX_SHARE_IN_CONGESTION
        """
        now = time.time()
        window_start = now - INTENTION_WINDOW_SECONDS

        intentions = conn.execute(
            """SELECT ai_id, ai_name, quantity, score, is_empty, timestamp
               FROM ai_buy_intentions
               WHERE symbol=? AND timestamp>=? AND coordinated=0
               ORDER BY is_empty DESC, score DESC, timestamp ASC""",
            (symbol, window_start)
        ).fetchall()

        if not intentions:
            return 0

        count = len(intentions)

        if count <= CONGESTION_THRESHOLD:
            # 没有拥挤：各自买各自的数量
            for row in intentions:
                conn.execute(
                    "UPDATE ai_buy_intentions SET allocated_quantity=? WHERE ai_id=? AND symbol=?",
                    (row["quantity"], row["ai_id"], symbol)
                )
            conn.commit()
            return intentions[0]["quantity"] if intentions else 0

        # ── 拥挤：需要协调分配 ────────────────────────────
        logger.warning(f"[Coordinator] ⚠️ {symbol} 拥挤度预警: {count}个AI同时想买！")

        # 计算总原始数量和总买入金额
        total_quantity = sum(r["quantity"] for r in intentions)
        total_amount = sum(r["quantity"] * r["price"] for r in intentions)

        # 分离空仓AI和持仓AI
        empty = [r for r in intentions if r["is_empty"]]
        holding = [r for r in intentions if not r["is_empty"]]

        # 分配逻辑：空仓AI优先（空仓=需要建立头寸）
        # 总分配预算 = 各AI原始数量的 80%（留20%余地）
        budget_qty = int(total_quantity * 0.8)

        # 第一轮：空仓AI优先分配（每只空仓AI至少分到其意向的50%）
        allocated = {}
        remaining_budget = budget_qty

        for row in (empty + holding):
            ai_id = row["ai_id"]
            orig_qty = row["quantity"]
            is_empty_ai = row["is_empty"]

            # 每个AI最多占 MAX_SHARE_IN_CONGESTION
            max_allowed = int(budget_qty * MAX_SHARE_IN_CONGESTION)

            if is_empty_ai:
                # 空仓AI：优先分配，最少保底 orig_qty * 50%
                allocated_qty = max(int(orig_qty * 0.5), min(orig_qty, remaining_budget // (len(empty + holding))))
            else:
                # 持仓AI：空仓分完后有剩余才给，最多 orig_qty * 30%
                allocated_qty = max(int(orig_qty * 0.3), min(orig_qty, remaining_budget // (len(holding) + 1)))

            allocated_qty = min(allocated_qty, max_allowed)
            allocated_qty = min(allocated_qty, remaining_budget)
            allocated[ai_id] = max(1, allocated_qty)  # 至少1股
            remaining_budget -= allocated_qty

        # 写入分配结果
        for row in intentions:
            ai_id = row["ai_id"]
            qty = allocated.get(ai_id, 1)
            conn.execute(
                "UPDATE ai_buy_intentions SET allocated_quantity=?, coordinated=1 "
                "WHERE ai_id=? AND symbol=?",
                (qty, ai_id, symbol)
            )
            logger.info(f"[Coordinator]   {row['ai_name']} → 分配 {qty}股 (原意向{row['quantity']}股)")

        conn.commit()

        # 返回当前AI的分配数量（通过 ai_id 查询）
        # 注：这个方法是被调用的AI传入的，所以返回在外层处理
        return 0  # 协调完成后，由 get_allocated_quantity() 查询

    def get_allocated_quantity(self, ai_id: str, symbol: str) -> int:
        """
        查询某个AI在某个股票上的最终可买数量。
        在 register_intention() 之后调用。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                """SELECT allocated_quantity FROM ai_buy_intentions
                   WHERE ai_id=? AND symbol=? AND coordinated=1
                   ORDER BY timestamp DESC LIMIT 1""",
                (ai_id, symbol)
            ).fetchone()
            return row["allocated_quantity"] if row else 0
        finally:
            conn.close()

    def get_congestion_info(self, symbol: str) -> dict:
        """
        获取某股票的当前拥挤度信息（用于发帖/预警）。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            now = time.time()
            window_start = now - INTENTION_WINDOW_SECONDS
            intentions = conn.execute(
                """SELECT ai_name, quantity, score, is_empty
                   FROM ai_buy_intentions
                   WHERE symbol=? AND timestamp>=? AND coordinated=0
                   ORDER BY is_empty DESC, score DESC""",
                (symbol, window_start)
            ).fetchall()
            total = len(intentions)
            return {
                "symbol": symbol,
                "congestion_count": total,
                "is_congested": total > CONGESTION_THRESHOLD,
                "ai_names": [r["ai_name"] for r in intentions],
                "total_quantity": sum(r["quantity"] for r in intentions),
            }
        finally:
            conn.close()

    def cleanup_old_intentions(self):
        """
        定期清理过期意向（只保留窗口期内的）。
        由 scheduler 定时调用。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            now = time.time()
            window_start = now - INTENTION_WINDOW_SECONDS * 3  # 窗口的3倍
            deleted = conn.execute(
                "DELETE FROM ai_buy_intentions WHERE timestamp < ?",
                (window_start,)
            ).rowcount
            if deleted > 0:
                logger.info(f"[Coordinator] 清理过期意向 {deleted} 条")
            conn.commit()
        finally:
            conn.close()


# 全局单例
_coordinator: Optional[MultiBrainCoordinator] = None

def get_coordinator(db_path: str = "/var/www/ai-god-of-stocks/ai_god.db") -> MultiBrainCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = MultiBrainCoordinator(db_path)
    return _coordinator
