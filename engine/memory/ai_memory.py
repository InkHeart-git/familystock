"""
记忆系统 - AI个人记忆 + 跨AI共享上下文
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("Memory")


@dataclass
class MemoryItem:
    """记忆条目"""
    key: str
    value: Any
    category: str        # "holding", "trade", "post", "market", "social"
    importance: int       # 1-10, 重要性
    created_at: float
    expires_at: Optional[float] = None  # TTL，None=永不过期


class AIMemory:
    """
    单个AI的记忆系统
    持久化到SQLite，内存中缓存热点
    """
    
    def __init__(self, ai_id: str, db_path: str):
        self.ai_id = ai_id
        self.db_path = db_path
        self._cache: Dict[str, MemoryItem] = {}
        self._cache_loaded = False
        self._init_db()
    
    def _init_db(self):
        """初始化记忆表"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                importance INTEGER DEFAULT 5,
                created_at REAL NOT NULL,
                expires_at REAL,
                UNIQUE(ai_id, key)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_memory_ai_id 
            ON ai_memory(ai_id, category)
        """)
        conn.commit()
        conn.close()
    
    def remember(self, key: str, value: Any, category: str = "general", 
                 importance: int = 5, ttl_seconds: Optional[int] = None):
        """写入记忆"""
        now = time.time()
        expires = now + ttl_seconds if ttl_seconds else None
        
        item = MemoryItem(
            key=key, value=value, category=category,
            importance=importance, created_at=now, expires_at=expires
        )
        self._cache[key] = item
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO ai_memory 
            (ai_id, key, value, category, importance, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (self.ai_id, key, json.dumps(value), category, importance, now, expires))
        conn.commit()
        conn.close()
    
    def recall(self, key: str, default=None) -> Any:
        """读取记忆"""
        if key in self._cache:
            item = self._cache[key]
            if item.expires_at and time.time() > item.expires_at:
                del self._cache[key]
                return default
            return item.value
        
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT value, expires_at FROM ai_memory 
            WHERE ai_id=? AND key=? AND (expires_at IS NULL OR expires_at > ?)
        """, (self.ai_id, key, time.time())).fetchone()
        conn.close()
        
        if row:
            value = json.loads(row[0])
            self._cache[key] = MemoryItem(
                key=key, value=value, category="",
                importance=5, created_at=0,
                expires_at=row[1]
            )
            return value
        
        return default
    
    def get_recent_posts(self, limit: int = 10) -> List[Dict]:
        """获取最近发帖记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT post_id, title, content, post_type, created_at 
            FROM ai_posts 
            WHERE ai_id=? 
            ORDER BY created_at DESC LIMIT ?
        """, (self.ai_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    def record_post(self, post_type: str, content: str):
        """记录发帖到记忆"""
        self.remember(
            key=f"post_{int(time.time())}",
            value={"type": post_type, "content": content[:100]},
            category="post",
            importance=3,
            ttl_seconds=86400 * 7  # 7天过期
        )
    
    def get_holdings(self) -> List[Dict]:
        """获取持仓"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT symbol, name, quantity, avg_cost, current_price, updated_at
            FROM ai_holdings WHERE ai_id=? AND quantity > 0
        """, (self.ai_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    def get_cash(self) -> float:
        """获取现金"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT cash FROM ai_portfolios 
            WHERE ai_id=? ORDER BY updated_at DESC LIMIT 1
        """, (self.ai_id,)).fetchone()
        conn.close()
        return float(row[0]) if row else 1000000.0
    
    def get_market_impression(self, symbol: str) -> Optional[str]:
        """获取对某股票的市场印象（从记忆中）"""
        return self.recall(f"impression_{symbol}")
    
    def set_market_impression(self, symbol: str, impression: str):
        """设置市场印象"""
        self.remember(
            key=f"impression_{symbol}",
            value=impression,
            category="market",
            importance=7,
            ttl_seconds=86400 * 30  # 30天
        )
    
    def get_posts_today_count(self) -> int:
        """今日发帖数"""
        conn = sqlite3.connect(self.db_path)
        today = datetime.now().strftime("%Y-%m-%d")
        count = conn.execute("""
            SELECT COUNT(*) FROM ai_posts 
            WHERE ai_id=? AND date(created_at)=?
        """, (self.ai_id, today)).fetchone()[0]
        conn.close()
        return count
    
    def get_recent_trades(self, limit: int = 5) -> List[Dict]:
        """获取最近交易（从记忆反推）"""
        # 从最近的帖子内容中提取交易记录
        posts = self.get_recent_posts(limit)
        trades = []
        for p in posts:
            content = p.get("content", "")
            # 简单解析：包含"买入""卖出"关键词的帖子
            if "买入" in content or "卖出" in content or "加仓" in content or "减仓" in content:
                trades.append(p)
        return trades

    def get_context_for_llm(self, max_tokens: int = 800) -> str:
        """
        为 LLM 调用生成记忆上下文
        将 AI 的历史记录压缩成 LLM 可处理的文本摘要
        """
        from datetime import datetime, timedelta

        lines = ["【AI记忆上下文】"]
        remaining = max_tokens

        # 1. 今日交易摘要（优先）
        today_trades = self.get_recent_trades(limit=10)
        if today_trades:
            trade_lines = ["## 今日交易"]
            for t in today_trades[:5]:
                ts = t.get("created_at", "")
                content = t.get("content", "")[:100]
                trade_lines.append(f"- [{ts}] {content}")
            trade_text = "\n".join(trade_lines)
            if len(trade_text) < remaining:
                lines.append(trade_text)
                remaining -= len(trade_text)

        # 2. 持仓状态（从记忆读取）
        holdings = self.recall("current_holdings")
        if holdings and remaining > 100:
            lines.append(f"## 当前持仓: {holdings}")
            remaining -= 100

        # 3. 最近发帖风格（用于保持一致性）
        recent = self.get_recent_posts(limit=3)
        if recent and remaining > 80:
            lines.append("## 最近发帖")
            for p in recent[:2]:
                content = p.get("content", "")[:80]
                lines.append(f"- {content}...")
            remaining -= 200

        # 4. 重要记忆（按 importance 过滤）
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT key, value, importance, category
            FROM ai_memory
            WHERE ai_id=? AND importance >= 7
            ORDER BY importance DESC LIMIT 10
        """, (self.ai_id,)).fetchall()
        conn.close()

        if rows and remaining > 150:
            lines.append("## 重要记忆")
            for row in rows[:5]:
                key = row["key"]
                val = str(row["value"])[:60]
                lines.append(f"- {key}: {val}")

        return "\n".join(lines)

    def save_holdings_summary(self, holdings: List[Dict], cash: float):
        """保存持仓摘要到记忆（每次交易后调用）"""
        summary = {
            "holdings": holdings,
            "cash": cash,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.remember("current_holdings", summary, category="portfolio", importance=8)
        # 同时更新持仓成本（用于后续参考）
        for h in holdings:
            key = f"cost_{h['symbol']}"
            self.remember(key, h.get("avg_cost", 0), category="portfolio", importance=7)



class SharedContext:
    """
    跨AI共享上下文
    用于AI间社交互动（围观、嘲讽、回复）
    """
    
    _instance = None
    _lock = False
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        self._cache: Dict[str, List[Dict]] = {}  # ai_id -> recent posts
        self._interactions: List[Dict] = []
        self._last_sync = 0
        self.db_path = "/var/www/ai-god-of-stocks/ai_god.db"
    
    def sync_other_ai_posts(self, my_ai_id: str, minutes: int = 120) -> List[Dict]:
        """同步其他AI的最近帖子"""
        now = time.time()
        if now - self._last_sync < 30:  # 30秒内不重复同步
            return self._cache.get(f"other_{my_ai_id}", [])
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        since = datetime.fromtimestamp(now - minutes * 60).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute("""
            SELECT post_id, ai_id, title, content, post_type, created_at, ai_name
            FROM ai_posts 
            WHERE ai_id != ? AND created_at >= ?
            ORDER BY created_at DESC LIMIT 50
        """, (my_ai_id, since)).fetchall()
        conn.close()
        
        posts = [dict(r) for r in rows]
        self._cache[f"other_{my_ai_id}"] = posts
        self._last_sync = now
        return posts
    
    def get_recent_other_ai_posts(self, my_ai_id: str, minutes: int = 120) -> List[Dict]:
        return self.sync_other_ai_posts(my_ai_id, minutes)
    
    def record_interaction(
        self, from_ai_id: str, to_ai_id: str, 
        to_post_id: str, content: str
    ):
        """记录一次社交互动"""
        self._interactions.append({
            "from": from_ai_id,
            "to": to_ai_id,
            "post": to_post_id,
            "content": content[:100],
            "at": time.time()
        })
        # 保留最近100条
        self._interactions = self._interactions[-100:]
    
    def get_interaction_count(self, ai_id: str, minutes: int = 60) -> int:
        """最近N分钟互动次数"""
        since = time.time() - minutes * 60
        return sum(1 for i in self._interactions if i["at"] > since and (
            i["from"] == ai_id or i["to"] == ai_id
        ))
