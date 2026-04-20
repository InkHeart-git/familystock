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
                    allocated_quantity INTEGER DEFAULT 0
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
            # 同事务内 DELETE + INSERT：删除旧意向（含 coordinated=1 的分配结果），
            # 重新注册时触发新一轮协调，保证每个 ai+sym 在每个窗口期只竞争一次
            conn.execute(
                "DELETE FROM ai_buy_intentions WHERE ai_id=? AND symbol=?",
                (ai_id, symbol)
            )
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
            allocated = self._coordinate_intentions(symbol)
            return allocated.get(ai_id, quantity)  # 未触发协调时返回原始数量
        finally:
            conn.close()

    def _coordinate_intentions(self, symbol: str) -> dict:
        """
        核心协调逻辑：检测并协调该股票的买入意向冲突。
        每次调用都基于当前窗口内所有未分配的意向重新计算（无状态标记）。

        返回: {ai_id: allocated_qty}
        """
        now = time.time()
        window_start = now - INTENTION_WINDOW_SECONDS

        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            intentions = conn.execute(
                """SELECT ai_id, ai_name, quantity, price, score, is_empty, timestamp
                   FROM ai_buy_intentions
                   WHERE symbol=? AND timestamp>=?
                   ORDER BY is_empty DESC, score DESC, timestamp ASC""",
                (symbol, window_start)
            ).fetchall()
        finally:
            conn.close()

        if not intentions:
            return {}

        count = len(intentions)

        if count <= CONGESTION_THRESHOLD:
            # 没有拥挤：各自全额购买
            return {row["ai_id"]: row["quantity"] for row in intentions}

        # ── 拥挤：需要协调分配 ────────────────────────────
        logger.warning(f"[Coordinator] ⚠️ {symbol} 拥挤度预警: {count}个AI同时想买！")

        total_quantity = sum(r["quantity"] for r in intentions)
        empty = [r for r in intentions if r["is_empty"]]
        holding = [r for r in intentions if not r["is_empty"]]

        # 总预算的 80%（留20%余地）
        budget_qty = int(total_quantity * 0.8)

        # 两轮分配：第一轮空仓AI保底，第二轮持仓AI按比例
        allocated = {}
        remaining = budget_qty

        # 第一轮：空仓AI保底（意向的 60%，最少1股）
        for row in empty:
            qty = max(1, int(row["quantity"] * 0.6))
            qty = min(qty, remaining)
            allocated[row["ai_id"]] = qty
            remaining -= qty

        # 第二轮：持仓AI分配（若有剩余，按剩余比例）
        if holding and remaining > 0:
            for row in holding:
                qty = max(1, int(row["quantity"] * 0.3))
                qty = min(qty, remaining // max(1, len(holding)))
                allocated[row["ai_id"]] = qty
                remaining -= qty

        # 第三轮：剩余数量给空仓AI补到其原始数量（不能超过原始数量）
        if remaining > 0 and empty:
            for row in empty:
                ai_id = row["ai_id"]
                cap = row["quantity"]
                allocated_qty = allocated.get(ai_id, 0)
                if allocated_qty < cap:
                    extra = min(cap - allocated_qty, remaining)
                    allocated[ai_id] = allocated_qty + extra
                    remaining -= extra

        # 写入分配结果到 DB（使用单独的连接，避免事务冲突）
        db = sqlite3.connect(self.db_path)
        try:
            for ai_id, qty in allocated.items():
                db.execute(
                    "UPDATE ai_buy_intentions SET allocated_quantity=? "
                    "WHERE symbol=? AND ai_id=? AND timestamp>=?",
                    (qty, symbol, ai_id, window_start)
                )
            db.commit()
        finally:
            db.close()

        for row in intentions:
            qty = allocated.get(row["ai_id"], 1)
            print(f"[Coordinator]   {row['ai_name']} → 分配 {qty}股 (原意向{row['quantity']}股)")

        return allocated

    def get_allocated_quantity(self, ai_id: str, symbol: str) -> int:
        """查询某个AI在某个股票上的最终可买数量（来自DB）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT allocated_quantity FROM ai_buy_intentions
                   WHERE ai_id=? AND symbol=?
                   ORDER BY timestamp DESC LIMIT 1""",
                (ai_id, symbol)
            ).fetchone()
            return row["allocated_quantity"] if row else 0
        finally:
            conn.close()

    def get_latest_intention_quantity(self, ai_id: str, symbol: str) -> int:
        """查询某AI某股的原始意向数量（注册时的数量）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT quantity FROM ai_buy_intentions
                   WHERE ai_id=? AND symbol=?
                   ORDER BY timestamp DESC LIMIT 1""",
                (ai_id, symbol)
            ).fetchone()
            return row["quantity"] if row else 0
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
            conn.row_factory = sqlite3.Row
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
