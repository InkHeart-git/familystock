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
                if rest[0] == "competition":
                    rest2 = rest[1:]
                    if not rest2 or rest2[0] == "leaderboard":
                        return self.get_competition_leaderboard, {}
                    if rest2[0] == "heatmap":
                        return self.get_competition_heatmap, {}
                    if rest2[0] == "score-tracking":
                        return self.get_score_tracking, {}
                    if rest2[0] == "summary":
                        return self.get_competition_summary, {}
                    if rest2[0] == "scoring":
                        return self.get_competition_scoring, {}
                    if rest2[0] == "social":
                        return self.get_competition_social, {}
                    if rest2[0] == "predictions":
                        return self.get_competition_predictions, {}
                    if rest2[0] == "my-votes" and len(rest2) >= 2:
                        return self.get_competition_my_votes, {"user_id": rest2[1]}
                    if rest2[0] == "vote" and len(rest2) == 1:
                        return self.post_competition_vote, {}
                    if rest2[0] == "vote-results":
                        return self.get_competition_vote_results, {}
                    if rest2[0] == "settle":
                        return self.settle_predictions, {}
                if rest[0] == "my-votes" and len(rest) >= 2:
                    return self.get_competition_my_votes, {"user_id": rest[1]}
                if rest[0] == "trades":
                    return self.get_all_trades, {}
                if rest[0] == "execute_trade":
                    return self.execute_trade, {}
                if rest[0] == "posts" and len(rest) == 1:
                    return self.create_post, {}
            if sub[0] == "competition":
                rest = sub[1:]
                if not rest or rest[0] == "leaderboard":
                    return self.get_competition_leaderboard, {}
                if rest[0] == "heatmap":
                    return self.get_competition_heatmap, {}
                if rest[0] == "score-tracking":
                    return self.get_score_tracking, {}
                if rest[0] == "summary":
                    return self.get_competition_summary, {}
                if rest[0] == "scoring":
                    return self.get_competition_scoring, {}
                if rest[0] == "social":
                    return self.get_competition_social, {}
                if rest[0] == "predictions":
                    return self.get_competition_predictions, {}
                if rest[0] == "my-votes" and len(rest) >= 2:
                    return self.get_competition_my_votes, {"user_id": rest[1]}
                if rest[0] == "vote-results":
                    return self.get_competition_vote_results, {}
            if sub[0] == "my-votes" and len(sub) >= 2:
                return self.get_competition_my_votes, {"user_id": sub[1]}
            if sub[0] == "settle":
                return self.settle_predictions, {}
            if sub[0] == "stats":
                return self.get_stats, {}
            if sub[0] == "trades":
                return self.get_all_trades, {}
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

    def get_ai_info(self, conn, ai_id):
        """获取AI角色信息"""
        row = conn.execute(
            "SELECT id, name, emoji, style FROM ai_characters WHERE id = ?",
            (str(ai_id),)
        ).fetchone()
        if row:
            return {"id": row[0], "name": row[1], "emoji": row[2] or "🤖", "style": row[3]}
        return {"id": str(ai_id), "name": f"AI-{ai_id}", "emoji": "🤖", "style": ""}

    def get_competition_leaderboard(self):
        """AI收益排行实时榜单"""
        pg_portfolios, _ = get_pg_conn()
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT DISTINCT ai_id, cash, total_value, seed_capital
                FROM ai_portfolios
                GROUP BY ai_id
                ORDER BY total_value DESC
            """).fetchall()

            rankings = []
            for rank, row in enumerate(rows, 1):
                ai_id = row[0]
                ai_info = self.get_ai_info(conn, ai_id)
                cash = row[1] or 0
                total_value = row[2] or 0
                seed_capital = row[3] or total_value
                holdings_value = total_value - cash
                profit = total_value - seed_capital
                profit_rate = (profit / seed_capital * 100) if seed_capital > 0 else 0

                rankings.append({
                    "rank": rank,
                    "ai_id": ai_id,
                    "ai_name": ai_info["name"],
                    "emoji": ai_info["emoji"],
                    "total_value": round(total_value, 2),
                    "cash": round(cash, 2),
                    "holdings_value": round(holdings_value, 2),
                    "profit": round(profit, 2),
                    "profit_rate": round(profit_rate, 2),
                    "seed_capital": seed_capital
                })

            return {"data": {"rankings": rankings}}
        finally:
            conn.close()

    def get_competition_heatmap(self):
        """每日操作热力图"""
        conn = get_db()
        try:
            # 获取最近7天的交易数据
            rows = conn.execute("""
                SELECT DISTINCT
                    DATE(created_at) as trade_date,
                    ai_id,
                    symbol,
                    action,
                    quantity,
                    price
                FROM ai_trades
                WHERE created_at >= DATE('now', '-7 days')
                ORDER BY created_at DESC
            """).fetchall()

            # 按日期分组
            daily_data = {}
            for row in rows:
                trade_date = row[0]
                if trade_date not in daily_data:
                    daily_data[trade_date] = {"trades": [], "ai_summary": {}}

                ai_id = row[1]
                ai_info = self.get_ai_info(conn, ai_id)
                action = row[3]

                cell = {
                    "ai_id": ai_id,
                    "ai_name": ai_info["name"],
                    "symbol": row[2],
                    "action": action,
                    "quantity": row[4],
                    "price": row[5]
                }
                daily_data[trade_date]["trades"].append(cell)

                if ai_id not in daily_data[trade_date]["ai_summary"]:
                    daily_data[trade_date]["ai_summary"][ai_id] = {"buys": 0, "sells": 0}
                if action == "BUY":
                    daily_data[trade_date]["ai_summary"][ai_id]["buys"] += 1
                elif action == "SELL":
                    daily_data[trade_date]["ai_summary"][ai_id]["sells"] += 1

            # 转换为列表格式
            result = []
            for date in sorted(daily_data.keys(), reverse=True):
                result.append({
                    "date": date,
                    "trades": daily_data[date]["trades"],
                    "ai_summary": daily_data[date]["ai_summary"]
                })

            return {"data": {"heatmap": result}}
        finally:
            conn.close()

    def get_score_tracking(self):
        """算法评分命中率追踪"""
        conn = get_db()
        try:
            # 获取最近30天的BUY交易记录
            rows = conn.execute("""
                SELECT
                    ai_id,
                    symbol,
                    name,
                    price as buy_price,
                    score,
                    created_at as buy_date
                FROM ai_trades
                WHERE action = 'BUY'
                AND created_at >= DATE('now', '-30 days')
                ORDER BY created_at DESC
            """).fetchall()

            results = []
            for row in rows:
                ai_id = row[0]
                ai_info = self.get_ai_info(conn, ai_id)
                results.append({
                    "ai_id": ai_id,
                    "ai_name": ai_info["name"],
                    "symbol": row[1],
                    "name": row[2] or "",
                    "buy_price": row[3],
                    "buy_score": row[4],
                    "buy_date": row[5],
                    "day5_price": None,  # 需要后续接入行情API
                    "day5_return": None,
                    "current_price": None,
                    "current_return": None
                })

            return {"data": {"tracking": results}}
        finally:
            conn.close()

    def get_competition_summary(self):
        """赛季总览数据"""
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
            today_trades = conn.execute(
                "SELECT COUNT(*) FROM ai_trades WHERE DATE(created_at) = ?", (today,)
            ).fetchone()[0]

            return {"data": {
                "total_trades": row[0],
                "ai_count": row[1],
                "stock_count": row[2],
                "first_trade": row[3],
                "last_trade": row[4],
                "today_trades": today_trades,
                "season_start": "2026-04-19",
                "update_time": datetime.now().isoformat()
            }}
        finally:
            conn.close()

    def get_competition_scoring(self):
        """
        赛季积分体系 (Phase 4.6)
        综合积分 = 收益率分(60%) + 胜率分(25%) + 评分准确分(15%)
        归一化方式：按排名映射到 0-100 分段
        """
        conn = get_db()
        try:
            # ---- 1. 收益率数据 ----
            p_rows = conn.execute("""
                SELECT ai_id, cash, total_value, seed_capital
                FROM ai_portfolios
            """).fetchall()
            portfolio_data = {}
            for row in p_rows:
                ai_id = row[0]
                seed = row[3] or 1000000.0
                profit_rate = (row[2] - seed) / seed * 100 if seed > 0 else 0.0
                portfolio_data[ai_id] = {"profit_rate": profit_rate}

            # ---- 2. 胜率数据 ----
            w_rows = conn.execute("""
                SELECT ai_id,
                    COUNT(*) as total_closed,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_count
                FROM ai_trades
                WHERE action IN ('SELL', 'CLEARED')
                GROUP BY ai_id
            """).fetchall()
            winrate_data = {}
            for row in w_rows:
                total_closed = row[1] or 0
                win_count = row[2] or 0
                winrate_data[row[0]] = {
                    "total_closed": total_closed,
                    "win_count": win_count,
                    "win_rate": (win_count / total_closed * 100) if total_closed > 0 else 0.0,
                }

            # ---- 3. 评分准确数据 ----
            a_rows = conn.execute("""
                SELECT ai_id,
                    COUNT(*) as total_high,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as hits
                FROM ai_trades
                WHERE action = 'BUY' AND score >= 70
                GROUP BY ai_id
            """).fetchall()
            accuracy_data = {}
            for row in a_rows:
                total_high = row[1] or 0
                hits = row[2] or 0
                accuracy_data[row[0]] = {
                    "high_rating_total": total_high,
                    "high_rating_hits": hits,
                    "rating_accuracy": (hits / total_high * 100) if total_high > 0 else 0.0,
                }

            # ---- 4. AI 角色信息 ----
            char_rows = conn.execute("SELECT id, name, emoji FROM ai_characters").fetchall()
            ai_chars = {str(r[0]): {"name": r[1], "emoji": r[2] or "🤖"} for r in char_rows}

            # ---- 5. 收集所有 AI ----
            all_ais = set(list(portfolio_data.keys()) +
                          list(winrate_data.keys()) +
                          list(accuracy_data.keys()))

            # ---- 6. 归一化函数 ----
            def rank_normalize(values_dict):
                sorted_ais = sorted(values_dict.keys(), key=lambda x: values_dict[x], reverse=True)
                n = len(sorted_ais)
                result = {}
                for rank, ai_id in enumerate(sorted_ais, 1):
                    result[ai_id] = round((n - rank) / max(n - 1, 1) * 100, 2) if n > 1 else 100.0
                return result

            return_vals = {ai: portfolio_data.get(ai, {"profit_rate": 0.0})["profit_rate"] for ai in all_ais}
            winrate_vals = {ai: winrate_data.get(ai, {"win_rate": 0.0})["win_rate"] for ai in all_ais}
            accuracy_vals = {ai: accuracy_data.get(ai, {"rating_accuracy": 0.0})["rating_accuracy"] for ai in all_ais}

            norm_return = rank_normalize(return_vals)
            norm_winrate = rank_normalize(winrate_vals)
            norm_accuracy = rank_normalize(accuracy_vals)

            # ---- 7. 计算综合积分 ----
            results = []
            for ai_id in all_ais:
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
                    "return_rate": round(return_vals.get(ai_id, 0.0), 2),
                    "winrate_score": round(win_s, 2),
                    "win_count": winrate_data.get(ai_id, {}).get("win_count", 0),
                    "total_closed": winrate_data.get(ai_id, {}).get("total_closed", 0),
                    "win_rate": round(winrate_vals.get(ai_id, 0.0), 2),
                    "accuracy_score": round(acc_s, 2),
                    "high_rating_hits": accuracy_data.get(ai_id, {}).get("high_rating_hits", 0),
                    "high_rating_total": accuracy_data.get(ai_id, {}).get("high_rating_total", 0),
                    "rating_accuracy": round(accuracy_vals.get(ai_id, 0.0), 2),
                })

            # 按综合积分降序并填排名
            results.sort(key=lambda x: x["total_score"], reverse=True)
            for rank, item in enumerate(results, 1):
                item["total_score_rank"] = rank

            return {"data": {"rankings": results}}
        finally:
            conn.close()

    def get_competition_social(self):
        """
        AI 社交互动数据 (Phase 4.8)
        双数据源：
        - bbs_posts (post_type=global/watch/summary) → 真实社交事件
        - ai_posts content 关键词推断 → 算法推断互动关系
        关系类型：jeer(嘲讽) / support(站台) / watch(围观) / rivalry(对手)
        """
        conn = get_db()
        try:
            import re
            mention_pat = re.compile(r'@(.{2,14})')

            # 收集所有 AI 角色信息
            ai_chars = {}
            for r in conn.execute("SELECT id, name, emoji FROM ai_characters").fetchall():
                ai_chars[str(r[0])] = {"name": r[1], "emoji": r[2] or "🤖"}

            # ── 数据源1: bbs_posts (真实社交) ─────────────────────────
            bbs_rows = conn.execute("""
                SELECT id, ai_id, ai_name, post_type, content, signal, timestamp
                FROM bbs_posts
                ORDER BY timestamp DESC
                LIMIT 200
            """).fetchall()

            # post_type → 关系类型映射
            type_map = {"global": "watch", "watch": "watch", "summary": "support"}

            # (src_id, tgt_id) → list[event]
            relations = {}
            social_events = []

            for r in bbs_rows:
                pid, src_id, src_name, ptype, content, signal, ts = r
                if not content:
                    continue
                src_id = str(src_id)
                rel_type = type_map.get(ptype, "watch")

                # 提取 @mention
                mentions = mention_pat.findall(content)
                targets = []
                for mentioned in mentions:
                    for aid, ainfo in ai_chars.items():
                        if aid != src_id and (
                            mentioned.strip() in ainfo["name"]
                            or ainfo["name"].replace("（", "(").replace("）", ")") in mentioned
                        ):
                            targets.append(aid)

                # 全局广播型（无特定target）→ 围观事件
                if not targets and ptype in ("global", "watch"):
                    social_events.append({
                        "post_id": pid,
                        "src_id": src_id,
                        "src_name": src_name or f"AI-{src_id}",
                        "src_emoji": ai_chars.get(src_id, {}).get("emoji", "🤖"),
                        "content": re.sub(r'[#*📊📈💰]+', '', content)[:200],
                        "type": rel_type,
                        "signal": signal or "",
                        "target_id": None,
                        "target_name": None,
                        "created_at": ts
                    })

                # 定向提及 → 关系
                for tgt_id in set(targets):
                    key = (src_id, tgt_id)
                    if key not in relations:
                        relations[key] = []
                    relations[key].append({
                        "post_id": pid,
                        "type": rel_type,
                        "content": re.sub(r'[#*📊📈💰]+', '', content)[:150],
                        "created_at": ts
                    })

            # ── 数据源2: ai_posts 关键词推断 ─────────────────────────
            # 收益率相似 → rivalry (对手盘)
            p_rows = conn.execute("""
                SELECT DISTINCT ai_id, total_value, seed_capital
                FROM ai_portfolios
            """).fetchall()
            perf = {}
            for row in p_rows:
                seed = row[2] or 1000000.0
                perf[str(row[0])] = (row[1] - seed) / seed * 100 if seed > 0 else 0.0

            # 持仓重叠 → rivalry
            h_rows = conn.execute("""
                SELECT ai_id, symbol FROM ai_holdings
            """).fetchall()
            holdings = {}
            for r in h_rows:
                aid = str(r[0])
                if aid not in holdings:
                    holdings[aid] = set()
                holdings[aid].add(r[1])

            rivalry_pairs = set()
            ai_list = list(holdings.keys())
            for i in range(len(ai_list)):
                for j in range(i + 1, len(ai_list)):
                    a1, a2 = ai_list[i], ai_list[j]
                    overlap = holdings[a1] & holdings[a2]
                    if overlap:
                        rivalry_pairs.add(tuple(sorted([a1, a2])))
                        # 双向 rivalry 关系
                        for (src, tgt) in [(a1, a2), (a2, a1)]:
                            key = (src, tgt)
                            if key not in relations:
                                relations[key] = []
                            relations[key].append({
                                "post_id": None,
                                "type": "rivalry",
                                "content": f"双方均持仓 {', '.join(overlap)}",
                                "created_at": None
                            })

            # ── 构建关系图 ───────────────────────────────────────────
            graph = []
            for (src_id, tgt_id), events in relations.items():
                src_info = ai_chars.get(src_id, {"name": f"AI-{src_id}", "emoji": "🤖"})
                tgt_info = ai_chars.get(tgt_id, {"name": f"AI-{tgt_id}", "emoji": "🤖"})
                types = list(set(e["type"] for e in events))
                valid_events = [e for e in events if e["created_at"]]
                latest = max((e["created_at"] for e in valid_events), default=None)
                graph.append({
                    "src_id": src_id,
                    "src_name": src_info["name"],
                    "src_emoji": src_info["emoji"],
                    "tgt_id": tgt_id,
                    "tgt_name": tgt_info["name"],
                    "tgt_emoji": tgt_info["emoji"],
                    "interaction_count": len(events),
                    "types": types,
                    "dominant_type": max(set(t for t in types), default="watch"),
                    "latest_at": latest,
                    "sample_content": next((e["content"] for e in events if e["content"]), "")[:80]
                })

            graph.sort(key=lambda x: x["interaction_count"], reverse=True)

            # ── 每AI统计 ─────────────────────────────────────────────
            ai_stats = {}
            for src_id in ai_chars:
                outgoing = sum(1 for (s, _), evs in relations.items() if s == src_id for _ in evs)
                incoming = sum(1 for (_, t), evs in relations.items() if t == src_id for _ in evs)
                jeer = sum(1 for (s, _), evs in relations.items() if s == src_id for e in evs if e["type"] == "jeer")
                support = sum(1 for (s, _), evs in relations.items() if s == src_id for e in evs if e["type"] == "support")
                ai_stats[src_id] = {
                    "ai_id": src_id,
                    "ai_name": ai_chars[src_id]["name"],
                    "emoji": ai_chars[src_id]["emoji"],
                    "outgoing": outgoing,
                    "incoming": incoming,
                    "jeer_count": jeer,
                    "support_count": support,
                    "total_interactions": outgoing + incoming
                }

            stats_list = sorted(ai_stats.values(), key=lambda x: x["total_interactions"], reverse=True)

            return {
                "data": {
                    "relations": graph,
                    "events": social_events[:30],
                    "ai_stats": stats_list,
                    "update_time": datetime.now().isoformat()
                }
            }
        finally:
            conn.close()

    def get_holdings(self, id):
        pg_portfolios, pg_holdings = get_pg_conn()
        return {"data": build_ai_record(str(id), pg_portfolios, pg_holdings, get_db())}

    # ─── Phase 3: 用户投票预测 ────────────────────────────────────

    def get_competition_predictions(self):
        """获取当日可投票的AI持仓股票列表"""
        conn = get_db()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            # 获取各AI当前持仓股（从ai_holdings）
            rows = conn.execute("""
                SELECT DISTINCT h.ai_id, c.name, c.emoji,
                       h.symbol, h.name AS stock_name, h.current_price,
                       h.quantity, h.avg_cost
                FROM ai_holdings h
                JOIN ai_characters c ON CAST(h.ai_id AS INTEGER) = c.id
                WHERE h.quantity > 0 AND h.current_price > 0
                ORDER BY h.ai_id
            """).fetchall()

            items = []
            for r in rows:
                # 检查用户是否已投票
                items.append({
                    "ai_id": r[0], "ai_name": r[1], "ai_emoji": r[2] or "🤖",
                    "symbol": r[3], "stock_name": r[4], "current_price": float(r[5]),
                    "quantity": r[6], "avg_cost": float(r[7])
                })

            # 按AI分组
            ai_groups = {}
            for item in items:
                aid = item["ai_id"]
                if aid not in ai_groups:
                    ai_groups[aid] = {"ai_id": aid, "ai_name": item["ai_name"],
                                      "ai_emoji": item["ai_emoji"], "holdings": []}
                ai_groups[aid]["holdings"].append({
                    "symbol": item["symbol"], "stock_name": item["stock_name"],
                    "current_price": item["current_price"], "quantity": item["quantity"],
                    "avg_cost": item["avg_cost"]
                })

            return {"data": {"ais": list(ai_groups.values()), "total": len(items),
                              "date": today}}
        finally:
            conn.close()

    def post_competition_vote(self):
        """提交投票预测"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except:
            return {"error": "invalid JSON"}, 400

        required = ["user_id", "ai_id", "direction"]
        for f in required:
            if f not in data:
                return {"error": f"missing field: {f}"}, 400

        user_id = str(data["user_id"]).strip()
        ai_id = int(data["ai_id"])
        direction = data["direction"]
        stock_symbol = data.get("stock_symbol", None)
        stock_name = data.get("stock_name", stock_symbol or "")

        if direction not in ("up", "down"):
            return {"error": "direction must be 'up' or 'down'"}, 400

        # user_phone 从 user_id 推断（手机号格式）
        user_phone = user_id if len(user_id) >= 11 else "unknown"

        conn = get_db()
        try:
            # 验证AI存在
            ai = conn.execute("SELECT name FROM ai_characters WHERE id=?", (ai_id,)).fetchone()
            if not ai:
                return {"error": "AI not found"}, 404
            ai_name = ai[0]

            today = datetime.now().strftime("%Y-%m-%d")

            # UPSERT（允许同一用户对同一AI同一股票每天多次改票）
            conn.execute("""
                INSERT INTO user_votes (user_id, user_phone, ai_id, ai_name, stock_symbol, stock_name, direction, vote_date, settled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(user_id, ai_id, stock_symbol, vote_date) DO UPDATE SET
                    direction=excluded.direction,
                    created_at=datetime('now', '+8 hours')
            """, (user_id, user_phone, ai_id, ai_name, stock_symbol, stock_name, direction, today))
            conn.commit()

            return {"data": {"success": True, "message": f"预测已提交: {ai_name} {'涨' if direction=='up' else '跌'}", "vote_date": today}}
        finally:
            conn.close()

    def get_competition_my_votes(self, user_id=None):
        """获取用户的投票历史"""
        uid = user_id or "unknown"
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT v.id, v.ai_id, v.ai_name, v.stock_symbol, v.stock_name,
                       v.direction, v.vote_date, v.settled,
                       r.is_correct, r.points_earned, r.settle_date
                FROM user_votes v
                LEFT JOIN prediction_results r ON
                    r.user_id=v.user_id AND r.ai_id=v.ai_id
                    AND r.stock_symbol=v.stock_symbol AND r.vote_date=v.vote_date
                WHERE v.user_id=?
                ORDER BY v.vote_date DESC, v.created_at DESC
                LIMIT 50
            """, (uid,)).fetchall()

            votes = [{
                "id": r[0], "ai_id": r[1], "ai_name": r[2],
                "stock_symbol": r[3], "stock_name": r[4],
                "direction": r[5], "vote_date": r[6], "settled": bool(r[7]),
                "is_correct": r[8], "points_earned": r[9] or 0,
                "settle_date": r[10]
            } for r in rows]

            # 统计
            total = len(votes)
            correct = sum(1 for v in votes if v["settled"] and v["is_correct"] == 1)
            total_points = sum(v["points_earned"] for v in votes if v["points_earned"])

            return {"data": {"votes": votes, "total": total, "correct": correct,
                              "accuracy": round(correct/total*100, 1) if total > 0 else 0,
                              "total_points": total_points}}
        finally:
            conn.close()

    def get_competition_vote_results(self):
        """获取往期预测结算结果（所有用户）"""
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT user_id, user_phone, ai_id, ai_name, stock_symbol, stock_name,
                       direction, vote_date, settle_date, is_correct, points_earned
                FROM prediction_results
                ORDER BY settle_date DESC, created_at DESC
                LIMIT 100
            """).fetchall()

            results = [{
                "user_id": r[0], "user_phone": r[1][-4:] if len(r[1]) >= 4 else r[1],
                "ai_id": r[2], "ai_name": r[3],
                "stock_symbol": r[4], "stock_name": r[5],
                "direction": r[6], "vote_date": r[7], "settle_date": r[8],
                "is_correct": bool(r[9]), "points_earned": r[10]
            } for r in rows]

            return {"data": {"results": results, "total": len(results)}}
        finally:
            conn.close()

    def settle_predictions(self):
        """每日收盘后结算预测（可由cron调用）
        逻辑：读取上一交易日的未结算投票，对比收盘价涨跌，写入prediction_results
        """
        conn = get_db()
        try:
            # 找上一交易日（周一到周五）
            today = datetime.now()
            weekday = today.weekday()  # 0=Mon, 4=Fri
            if weekday == 0:  # 周一 → 取上周五
                last_trade = (today - timedelta(days=3)).strftime("%Y-%m-%d")
            else:
                last_trade = (today - timedelta(days=1)).strftime("%Y-%m-%d")

            unsettled = conn.execute("""
                SELECT v.id, v.user_id, v.user_phone, v.ai_id, v.ai_name,
                       v.stock_symbol, v.stock_name, v.direction, v.vote_date
                FROM user_votes v
                WHERE v.settled=0 AND v.vote_date < ?
            """, (last_trade,)).fetchall()

            if not unsettled:
                return {"data": {"message": "no unsettled votes", "count": 0}}

            settled = 0
            for v in unsettled:
                vid, uid, uphone, aid, aname, sym, sname, direction, vdate = v
                if not sym:
                    conn.execute("UPDATE user_votes SET settled=1 WHERE id=?", (vid,))
                    settled += 1
                    continue

                # 获取收盘价（从quotes表取）
                price_row = conn.execute("""
                    SELECT close FROM quotes
                    WHERE ts_code=? AND trade_date<=?
                    ORDER BY trade_date DESC LIMIT 1
                """, (sym, last_trade)).fetchone()

                prev_row = conn.execute("""
                    SELECT close FROM quotes
                    WHERE ts_code=? AND trade_date<? AND trade_date<=?
                    ORDER BY trade_date DESC LIMIT 1
                """, (sym, last_trade, vdate)).fetchone()

                if price_row and prev_row:
                    close = float(price_row[0])
                    prev = float(prev_row[0])
                    stock_up = 1 if close > prev else 0
                    is_correct = 1 if stock_up == (1 if direction == "up" else 0) else 0
                    points = 10 if is_correct else 0
                else:
                    stock_up = None
                    is_correct = 0
                    points = 0

                conn.execute("""
                    INSERT INTO prediction_results
                        (user_id, user_phone, ai_id, ai_name, stock_symbol, stock_name,
                         direction, vote_date, settle_date, stock_close_up, is_correct, points_earned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (uid, uphone, aid, aname, sym, sname, direction, vdate, last_trade, stock_up, is_correct, points))

                conn.execute("UPDATE user_votes SET settled=1 WHERE id=?", (vid,))
                settled += 1

            conn.commit()
            return {"data": {"message": "settled", "count": settled}}
        finally:
            conn.close()

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

        # 特殊处理POST /api/competition/vote
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "competition" and parts[2] == "vote":
            result = self.post_competition_vote()
            if isinstance(result, tuple):
                data, status = result[0], result[1]
            else:
                data, status = result, 200
            self.send_json(data, status)
            return

        # 特殊处理POST /api/competition/settle
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "competition" and parts[2] == "settle":
            result = self.settle_predictions()
            if isinstance(result, tuple):
                data, status = result[0], result[1]
            else:
                data, status = result, 200
            self.send_json(data, status)
            return

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
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"AI股神争霸赛 API Server running on port {PORT}")
    server.serve_forever()
