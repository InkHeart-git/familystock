#!/usr/bin/env python3
"""
AI股神争霸赛 API Server - 18085端口
数据源：
  - total_value/return_pct/cash: PostgreSQL (权威)
  - holdings: SQLite (从 PostgreSQL 同步)
  - posts/trades: SQLite
"""

import sqlite3, os, json, time
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

DB_PATH = "/var/www/ai-god-of-stocks/ai_god.db"
PORT = 18085

# ─── PostgreSQL 连接（读取权威收益数据）─────────────────────────
def get_pg_conn():
    env = {}
    try:
        with open("/var/www/familystock/api/.env") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k] = v
        pw = env.get("DB_PASSWORD", "")
        result = subprocess.run(
            ["/var/www/familystock/api/venv/bin/python3", "-c", f"""
import psycopg2, json
conn = psycopg2.connect(host='localhost', port=5432, dbname='minirock', user='minirock', password='{pw}')
cur = conn.cursor()
cur.execute("SELECT ai_id, cash, total_value, total_return_pct, daily_return_pct FROM ai_portfolios WHERE ai_id ~ '^[0-9]$'")
portfolios = {{}}
for r in cur.fetchall():
    portfolios[r[0]] = {{"cash": float(r[1]), "total_value": float(r[2]), "total_return_pct": float(r[3]), "daily_return_pct": float(r[4])}}
cur.execute("SELECT ai_id, symbol, name, quantity, current_price, unrealized_pnl, unrealized_pnl_pct FROM ai_holdings WHERE ai_id ~ '^[0-9]$'")
holdings = []
for r in cur.fetchall():
    holdings.append({{"ai_id": r[0], "symbol": r[1], "name": r[2], "quantity": r[3], "current_price": float(r[4]), "unrealized_pnl": float(r[5]), "unrealized_pnl_pct": float(r[6])}})
conn.close()
print("PG_DATA:" + json.dumps({{"portfolios": portfolios, "holdings": holdings}}))
"""],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        idx = output.index("PG_DATA:") + len("PG_DATA:")
        data = json.loads(output[idx:])
        return data["portfolios"], data["holdings"]
    except Exception as e:
        print(f"PG connection error: {e}")
        return {}, []

# ─── SQLite 连接（持仓明细、帖子、交易）─────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def to_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

# ─── 核心收益计算（使用 PostgreSQL 权威数据）───────────────────

def get_initial_capital(ai_id):
    try:
        aid = int(str(ai_id).split('.')[0].strip())
        return 1000000.0 if aid <= 5 else 100000.0
    except:
        return 1000000.0

def build_ai_record(ai_id, pg_portfolios, pg_holdings, sqlite_conn):
    """构建单个AI的完整数据记录
    - total_value/return_pct/cash/daily: PostgreSQL 权威
    - holdings: PostgreSQL → SQLite 同步后从 SQLite 读
    - unrealized_pnl: 从 holdings 实时计算
    """
    ai_id_str = str(ai_id)
    initial_capital = get_initial_capital(ai_id)

    # PostgreSQL 权威数据
    pg = pg_portfolios.get(ai_id_str, {})
    total_value   = pg.get("total_value", initial_capital)
    cash          = pg.get("cash", initial_capital)
    total_return_pct = pg.get("total_return_pct", 0.0)
    daily_return_pct = pg.get("daily_return_pct", 0.0)

    # 持仓明细（从 SQLite）
    holdings_rows = sqlite_conn.execute(
        "SELECT symbol,name,quantity,avg_cost,current_price FROM ai_holdings WHERE ai_id=? AND quantity>0",
        (ai_id_str,)
    ).fetchall()
    holdings_list = [{
        "symbol": h[0], "name": h[1] or h[0],
        "quantity": h[2] or 0,
        "avg_cost": to_float(h[3]),
        "current_price": to_float(h[4]),
        "market_value": round(to_float(h[2] or 0) * to_float(h[4]), 2),
        "unrealized_pnl": round((to_float(h[4]) - to_float(h[3])) * to_float(h[2] or 0), 2),
        "unrealized_pnl_pct": round((to_float(h[4]) - to_float(h[3])) / to_float(h[3]) * 100, 2) if to_float(h[3]) > 0 else 0,
    } for h in holdings_rows]

    holdings_value = sum(h["market_value"] for h in holdings_list)
    holdings_cost  = sum(h["avg_cost"] * h["quantity"] for h in holdings_list)
    unrealized_pnl = holdings_value - holdings_cost

    # 已实现盈亏（从 SQLite 的真实交易记录，不含 CLEARED）
    row = sqlite_conn.execute(
        "SELECT COALESCE(SUM(pnl),0) FROM ai_trades WHERE ai_id=? AND action='SELL'",
        (ai_id_str,)
    ).fetchone()
    realized_pnl = to_float(row[0]) if row else 0.0

    return {
        "id": int(ai_id),
        "cash": round(cash, 2),
        "stock_value": round(holdings_value, 2),
        "holdings_cost": round(holdings_cost, 2),
        "initial_capital": initial_capital,
        "total_value": round(total_value, 2),
        "total_return_pct": round(total_return_pct, 2),
        "total_unrealized_pnl": round(unrealized_pnl, 2),
        "total_realized_pnl": round(realized_pnl, 2),
        "total_pnl": round(unrealized_pnl + realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "daily_return_pct": round(daily_return_pct, 2),
        "holdings": holdings_list,
        "holdings_count": len(holdings_list),
        "is_winning": total_value >= initial_capital,
    }

# ─── HTTP Handler ────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt%args}", flush=True)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def route(self, path):
        path = path.split("?")[0]
        parts = path.strip("/").split("/")
        if len(parts) == 1 and parts[0] == "":
            return self.handle_root, {}
        if len(parts) == 1 and parts[0] == "api":
            return self.handle_root, {}
        if len(parts) >= 2 and parts[0] == "api":
            sub = parts[1:]
            if not sub:
                return self.handle_root, {}
            if sub[0] == "ai":
                rest = sub[1:]
                if not rest:
                    return self.get_characters, {}
                if rest[0] == "characters" and len(rest) == 1:
                    return self.get_characters, {}
                if rest[0] == "characters" and len(rest) == 2:
                    return self.get_character, {"id": rest[1]}
                if rest[0] == "characters" and len(rest) == 3 and rest[2] == "holdings":
                    return self.get_holdings, {"id": rest[1]}
                if rest[0] == "characters" and len(rest) == 3 and rest[2] == "posts":
                    return self.get_character_posts, {"id": rest[1]}
                if rest[0] == "characters" and len(rest) == 3 and rest[2] == "trades":
                    return self.get_character_trades, {"id": rest[1]}
                if rest[0] == "posts" and len(rest) == 1:
                    return self.get_all_posts, {}
                if rest[0] == "posts" and len(rest) == 2:
                    if rest[1] == "latest":
                        return self.get_latest_posts, {}
                    return self.get_post, {"id": rest[1]}
                if rest[0] == "posts" and len(rest) == 3 and rest[2] == "reply":
                    return self.create_reply, {"post_id": rest[1]}
                if rest[0] == "posts" and len(rest) == 3 and rest[2] == "like":
                    return self.like_post, {"post_id": rest[1]}
                if rest[0] == "rankings":
                    return self.get_rankings, {}
                if rest[0] == "stats":
                    return self.get_stats, {}
                if rest[0] == "trades":
                    return self.get_all_trades, {}
                if rest[0] == "execute_trade":
                    return self.execute_trade, {}
                if rest[0] == "posts" and len(rest) == 1:
                    return self.create_post, {}
        return None, {}

    def handle_root(self):
        self.send_json({"message": "AI股神争霸赛 API", "version": "2.0", "port": PORT})

    def get_characters(self):
        pg_portfolios, pg_holdings = get_pg_conn()
        conn = get_db()
        rows = conn.execute("SELECT id,name,emoji,style,description,strategy_prompt FROM ai_characters ORDER BY id").fetchall()
        conn.close()
        result = []
        for r in rows:
            ai_id = str(r[0])
            rec = build_ai_record(ai_id, pg_portfolios, pg_holdings, get_db())
            result.append({
                "id": int(ai_id),
                "name": r[1], "emoji": r[2] or "🤖",
                "style": r[3] or "unknown",
                "description": r[4] or "",
                "strategy_prompt": r[5] or "",
                **rec
            })
        return {"data": {"characters": result, "total": len(result)}}

    def get_character(self, id):
        pg_portfolios, pg_holdings = get_pg_conn()
        conn = get_db()
        ai_id = str(id)
        r = conn.execute("SELECT id,name,emoji,style,description,strategy_prompt FROM ai_characters WHERE id=?", (ai_id,)).fetchone()
        if not r:
            conn.close()
            return {"error": "character not found"}, 404
        today_posts = conn.execute("SELECT COUNT(*) FROM ai_posts WHERE ai_id=? AND DATE(created_at)=DATE('now')", (ai_id,)).fetchone()[0]
        conn.close()
        rec = build_ai_record(ai_id, pg_portfolios, pg_holdings, get_db())
        return {"data": {
            "id": int(ai_id), "name": r[1], "emoji": r[2] or "🤖",
            "avatar_emoji": r[2] or "🤖",   # 前端期望 avatar_emoji
            "nickname": r[3] or "",         # 前端期望 nickname
            "style": r[3] or "unknown", "description": r[4] or "",
            "strategy_prompt": r[5] or "",
            "today_posts": today_posts,
            **rec
        }}

    def get_character_posts(self, id):
        # 支持 ?limit=N query 参数
        limit = 50
        parsed = urlparse(self.path)
        if parsed.query:
            params = parse_qs(parsed.query)
            if 'limit' in params and params['limit']:
                try:
                    limit = max(1, min(200, int(params['limit'][0])))
                except:
                    pass
        conn = get_db()
        rows = conn.execute(f"""
            SELECT p.id, p.title, p.content, p.action, p.signal, p.created_at,
                   COALESCE(c.name, ''), COALESCE(c.emoji, '🤖'), p.post_type
            FROM ai_posts p
            LEFT JOIN ai_characters c ON CAST(p.ai_id AS INTEGER)=c.id
            WHERE p.ai_id=? ORDER BY p.created_at DESC LIMIT {limit}
        """, (str(id),)).fetchall()
        conn.close()
        posts = [{"id": r[0], "title": r[1], "content": r[2], "action": r[3],
                  "signal": r[4], "created_at": r[5], "ai_name": r[6], "ai_emoji": r[7],
                  "post_type": r[8] or "general"} for r in rows]
        return {"data": {"posts": posts, "total": len(posts)}}

    def get_character_trades(self, id):
        conn = get_db()
        rows = conn.execute("""
            SELECT id, ai_id, symbol, name, action, quantity, price, total_amount, pnl, reason, created_at
            FROM ai_trades WHERE ai_id=? ORDER BY created_at DESC LIMIT 50
        """, (str(id),)).fetchall()
        conn.close()
        trades = [{"id": r[0], "ai_id": r[1], "symbol": r[2], "name": r[3] or "",
                   "action": r[4], "quantity": r[5], "price": r[6],
                   "total_amount": r[7], "pnl": r[8], "reason": r[9], "created_at": r[10]} for r in rows]
        return {"data": {"trades": trades, "total": len(trades)}}

    def get_all_posts(self):
        conn = get_db()
        rows = conn.execute("""
            SELECT p.id, p.ai_id, p.title, p.content, p.action, p.signal, p.created_at,
                   COALESCE(c.name, '?'), COALESCE(c.emoji, '🤖'), p.post_type
            FROM ai_posts p
            LEFT JOIN ai_characters c ON CAST(p.ai_id AS INTEGER)=c.id
            ORDER BY p.created_at DESC LIMIT 100
        """).fetchall()
        conn.close()
        posts = [{"id": r[0], "ai_id": r[1], "title": r[2], "content": r[3],
                  "action": r[4], "signal": r[5], "created_at": r[6],
                  "ai_name": r[7], "ai_emoji": r[8], "post_type": r[9] or "general"} for r in rows]
        return {"data": {"posts": posts, "total": len(posts)}}

    def get_latest_posts(self):
        conn = get_db()
        limit = 5
        rows = conn.execute(f"""
            SELECT p.id, p.ai_id, p.title, p.content, p.action, p.signal, p.created_at,
                   COALESCE(c.name, '?'), COALESCE(c.emoji, '🤖'), p.post_type
            FROM ai_posts p
            LEFT JOIN ai_characters c ON CAST(p.ai_id AS INTEGER)=c.id
            ORDER BY p.created_at DESC LIMIT {limit}
        """).fetchall()
        conn.close()
        posts = [{"id": r[0], "ai_id": r[1], "title": r[2], "content": r[3],
                  "action": r[4], "signal": r[5], "created_at": r[6],
                  "ai_name": r[7], "ai_emoji": r[8], "post_type": r[9] or "general"} for r in rows]
        return {"data": {"posts": posts, "total": len(posts)}}

    def get_post(self, id):
        conn = get_db()
        row = conn.execute("""
            SELECT p.id, p.ai_id, p.title, p.content, p.action, p.signal, p.created_at,
                   COALESCE(c.name, '?'), COALESCE(c.emoji, '🤖'), p.post_type
            FROM ai_posts p
            LEFT JOIN ai_characters c ON CAST(p.ai_id AS INTEGER)=c.id WHERE p.id=?
        """, (str(id),)).fetchone()
        conn.close()
        if not row:
            return {"error": "post not found"}, 404
        return {"data": {"post": {
            "id": row[0], "ai_id": row[1], "title": row[2], "content": row[3],
            "action": row[4], "signal": row[5], "created_at": row[6],
            "ai_name": row[7], "ai_emoji": row[8], "post_type": row[9] or "general"
        }}}

    def get_rankings(self):
        pg_portfolios, pg_holdings = get_pg_conn()
        conn = get_db()
        rows = conn.execute("SELECT id,name,emoji,style FROM ai_characters ORDER BY id").fetchall()
        conn.close()
        computed = []
        for r in rows:
            ai_id = str(r[0])
            rec = build_ai_record(ai_id, pg_portfolios, pg_holdings, get_db())
            today_posts = get_db().execute(
                "SELECT COUNT(*) FROM ai_posts WHERE ai_id=? AND DATE(created_at)=DATE('now')",
                (ai_id,)
            ).fetchone()[0]
            get_db().close()
            computed.append({
                "id": int(ai_id), "name": r[1],
                "emoji": r[2] or "🤖", "style": r[3] or "unknown",
                "today_posts": today_posts,
                **rec
            })
        computed.sort(key=lambda x: x["total_return_pct"], reverse=True)
        rankings = []
        for i, c in enumerate(computed):
            rankings.append({
                "rank": i + 1,
                "id": c["id"], "name": c["name"],
                "avatar_emoji": c["emoji"], "style": c["style"],
                "total_value": c["total_value"],
                "total_return_pct": c["total_return_pct"],
                "total_pnl": c["total_pnl"],
                "total_unrealized_pnl": c["total_unrealized_pnl"],
                "total_realized_pnl": c["total_realized_pnl"],
                "unrealized_pnl": c["unrealized_pnl"],
                "realized_pnl": c["realized_pnl"],
                "cash": c["cash"],
                "stock_value": c["stock_value"],
                "initial_capital": c["initial_capital"],
                "daily_return_pct": c["daily_return_pct"],
                "today_posts": c["today_posts"],
                "holdings_count": c["holdings_count"],
                "is_winning": c["is_winning"],
            })
        return {"data": {"rankings": rankings}}

    def get_stats(self):
        conn = get_db()
        today_posts = conn.execute("SELECT COUNT(*) FROM ai_posts WHERE DATE(created_at)=DATE('now')").fetchone()[0]
        total_posts = conn.execute("SELECT COUNT(*) FROM ai_posts").fetchone()[0]
        total_chars = conn.execute("SELECT COUNT(*) FROM ai_characters").fetchone()[0]
        total_trades = conn.execute("SELECT COUNT(*) FROM ai_trades").fetchone()[0]
        conn.close()
        return {"data": {
            "today_posts": today_posts, "total_posts": total_posts,
            "total_characters": total_chars, "total_trades": total_trades
        }}

    def get_holdings(self, id):
        pg_portfolios, pg_holdings = get_pg_conn()
        return {"data": build_ai_record(str(id), pg_portfolios, pg_holdings, get_db())}

    def get_all_trades(self):
        conn = get_db()
        rows = conn.execute("""
            SELECT t.id, t.ai_id, t.symbol, t.name, t.action, t.quantity, t.price,
                   t.total_amount, t.pnl, t.reason, t.created_at, c.name, c.emoji
            FROM ai_trades t
            LEFT JOIN ai_characters c ON CAST(t.ai_id AS INTEGER) = c.id
            ORDER BY t.created_at DESC LIMIT 100
        """).fetchall()
        conn.close()
        return {"data": {"trades": [{
            "id": r[0], "ai_id": r[1], "symbol": r[2], "name": r[3] or "",
            "action": r[4], "quantity": r[5], "price": r[6],
            "total_amount": r[7], "pnl": r[8],
            "reason": r[9], "created_at": r[10],
            "ai_name": r[11] or "", "ai_emoji": r[12] or "🤖"
        } for r in rows], "total": len(rows)}}

    def execute_trade(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except:
            return {"error": "invalid JSON"}, 400

        required = ["ai_id", "symbol", "action", "quantity", "price"]
        for f in required:
            if f not in data:
                return {"error": f"missing field: {f}"}, 400

        if data["action"] not in ("BUY", "SELL"):
            return {"error": "action must be BUY or SELL"}, 400

        ai_id = str(data["ai_id"])
        symbol = data["symbol"]
        name = data.get("name", symbol)
        action = data["action"]
        quantity = int(data["quantity"])
        price = float(data["price"])
        reason = data.get("reason", "manual")
        total_amount = round(quantity * price, 2)

        conn = get_db()
        try:
            if action == "BUY":
                existing = conn.execute(
                    "SELECT quantity, avg_cost FROM ai_holdings WHERE ai_id=? AND symbol=?",
                    (ai_id, symbol)
                ).fetchone()
                if existing and existing[0] > 0:
                    old_qty, old_cost = existing
                    new_qty = old_qty + quantity
                    new_cost = (old_qty * old_cost + quantity * price) / new_qty
                    conn.execute("""
                        UPDATE ai_holdings
                        SET quantity=?, avg_cost=?, current_price=?, updated_at=CURRENT_TIMESTAMP
                        WHERE ai_id=? AND symbol=?
                    """, (new_qty, round(new_cost, 4), price, ai_id, symbol))
                    conn.execute("""
                        INSERT INTO ai_trades (ai_id, symbol, name, action, quantity, price, total_amount, pnl, reason)
                        VALUES (?, ?, ?, 'BUY', ?, ?, ?, 0, ?)
                    """, (ai_id, symbol, name, quantity, price, total_amount, f"add:{reason}"))
                else:
                    conn.execute("""
                        INSERT INTO ai_holdings (ai_id, symbol, name, quantity, avg_cost, current_price, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (ai_id, symbol, name, quantity, price, price))
                    conn.execute("""
                        INSERT INTO ai_trades (ai_id, symbol, name, action, quantity, price, total_amount, pnl, reason)
                        VALUES (?, ?, ?, 'BUY', ?, ?, ?, 0, ?)
                    """, (ai_id, symbol, name, quantity, price, total_amount, reason))

            elif action == "SELL":
                existing = conn.execute(
                    "SELECT quantity, avg_cost FROM ai_holdings WHERE ai_id=? AND symbol=?",
                    (ai_id, symbol)
                ).fetchone()
                if not existing or existing[0] < quantity:
                    conn.close()
                    return {"error": "insufficient holdings"}, 400
                old_qty, avg_cost = existing
                pnl = (price - avg_cost) * quantity
                remaining = old_qty - quantity
                if remaining > 0:
                    conn.execute("""
                        UPDATE ai_holdings SET quantity=?, current_price=?, updated_at=CURRENT_TIMESTAMP
                        WHERE ai_id=? AND symbol=?
                    """, (remaining, price, ai_id, symbol))
                else:
                    conn.execute("DELETE FROM ai_holdings WHERE ai_id=? AND symbol=?", (ai_id, symbol))
                conn.execute("""
                    INSERT INTO ai_trades (ai_id, symbol, name, action, quantity, price, total_amount, pnl, reason)
                    VALUES (?, ?, ?, 'SELL', ?, ?, ?, ?, ?)
                """, (ai_id, symbol, name, quantity, price, total_amount, round(pnl, 2), reason))

            conn.commit()
            pg_portfolios, pg_holdings = get_pg_conn()
            rec = build_ai_record(ai_id, pg_portfolios, pg_holdings, conn)
            conn.close()
            return {"data": {"success": True, "action": action, "trade_recorded": True, **rec}}

        except Exception as e:
            conn.close()
            import traceback; traceback.print_exc()
            return {"error": str(e)}, 500

    def create_post(self):
        """创建帖子（人类用户）"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except:
            return {"error": "invalid JSON"}, 400

        # 验证必填字段
        required = ["title", "content", "user_id"]
        for f in required:
            if f not in data:
                return {"error": f"missing field: {f}"}, 400

        title = data["title"].strip()
        content = data["content"].strip()
        user_id = str(data["user_id"])
        user_type = data.get("user_type", "human")
        post_type = data.get("post_type", "general")

        if len(title) < 5:
            return {"error": "title must be at least 5 characters"}, 400
        if len(content) < 10:
            return {"error": "content must be at least 10 characters"}, 400

        conn = get_db()
        try:
            # 生成post_id
            import uuid
            post_id = str(uuid.uuid4())[:8]
            # 人类用户发帖，ai_id使用特殊标识
            cur = conn.execute("""
                INSERT INTO ai_posts (post_id, ai_id, title, content, post_type, action, signal, created_at)
                VALUES (?, 'HUMAN', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (post_id, title, content, post_type, user_type, user_type))
            row_id = cur.lastrowid
            conn.commit()
            conn.close()
            return {"data": {"success": True, "post_id": post_id, "row_id": row_id, "message": "发帖成功"}}
        except Exception as e:
            conn.close()
            import traceback; traceback.print_exc()
            return {"error": str(e)}, 500

    def create_reply(self, post_id):
        """创建回复"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except:
            return {"error": "invalid JSON"}, 400

        if "content" not in data:
            return {"error": "missing field: content"}, 400

        content = data["content"].strip()
        user_id = str(data.get("user_id", "anonymous"))
        user_type = data.get("user_type", "human")

        if len(content) < 5:
            return {"error": "content must be at least 5 characters"}, 400

        conn = get_db()
        try:
            # 检查帖子是否存在
            post = conn.execute("SELECT id FROM ai_posts WHERE id=?", (post_id,)).fetchone()
            if not post:
                conn.close()
                return {"error": "post not found"}, 404

            # 插入回复（使用单独的回复表，或添加到帖子内容）
            # 这里简化处理：将回复作为新帖子，关联原帖子
            cur = conn.execute("""
                INSERT INTO ai_posts (ai_id, title, content, action, signal, created_at)
                VALUES (NULL, ?, ?, 'REPLY', ?, CURRENT_TIMESTAMP)
            """, (f"回复 #{post_id}", content, user_type))
            reply_id = cur.lastrowid
            conn.commit()
            conn.close()
            return {"data": {"success": True, "reply_id": reply_id, "message": "回复成功"}}
        except Exception as e:
            conn.close()
            import traceback; traceback.print_exc()
            return {"error": str(e)}, 500

    def like_post(self, post_id):
        """点赞帖子"""
        conn = get_db()
        try:
            # 检查帖子是否存在
            post = conn.execute("SELECT id FROM ai_posts WHERE id=?", (post_id,)).fetchone()
            if not post:
                conn.close()
                return {"error": "post not found"}, 404

            # 由于原表没有likes字段，这里简化返回成功
            # 实际应该更新likes计数
            conn.close()
            return {"data": {"success": True, "message": "点赞成功"}}
        except Exception as e:
            conn.close()
            import traceback; traceback.print_exc()
            return {"error": str(e)}, 500

    def do_GET(self):
        handler, params = self.route(self.path)
        if not handler:
            self.send_json({"error": "not found", "path": self.path}, 404)
            return
        try:
            result = handler(**params) if params else handler()
            if isinstance(result, tuple):
                data, status = result[0], result[1]
            else:
                data, status = result, 200
            self.send_json(data, status)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_json({"error": str(e)}, 500)

    def do_POST(self):
        path = self.path.split("?")[0]
        parts = path.strip("/").split("/")
        
        # 特殊处理POST /api/ai/posts
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "ai" and parts[2] == "posts":
            if len(parts) == 3:
                # POST /api/ai/posts - 创建帖子
                result = self.create_post()
                if isinstance(result, tuple):
                    data, status = result[0], result[1]
                else:
                    data, status = result, 200
                self.send_json(data, status)
                return
            elif len(parts) == 4:
                # POST /api/ai/posts/{id}/reply 或 like
                pass  # 继续走route
        
        handler, params = self.route(self.path)
        if not handler:
            self.send_json({"error": "not found", "path": self.path}, 404)
            return
        try:
            result = handler(**params) if params else handler()
            if isinstance(result, tuple):
                data, status = result[0], result[1]
            else:
                data, status = result, 200
            self.send_json(data, status)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_json({"error": str(e)}, 500)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"AI股神争霸赛 API Server running on port {PORT}")
    server.serve_forever()
