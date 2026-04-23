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
    conn.row_factory = sqlite3.Row
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
                    if rest2[0] == "comments":
                        return self.get_competition_comments, {}
                    if rest2[0] == "my-comments" and len(rest2) >= 2:
                        return self.get_competition_my_comments, {"user_id": rest2[1]}
                    # Phase 3.3: 互动积分
                    if rest2[0] == "interaction":
                        if len(rest2) >= 2 and rest2[1] == "ranking":
                            return self.get_interaction_ranking, {}
                        if len(rest2) >= 3 and rest2[1] == "me":
                            return self.get_interaction_me, {"user_id": rest2[2]}
                    # Phase 1 收尾：赛季管理
                    if rest2[0] == "seasons":
                        return self.get_competition_seasons, {}
                    if rest2[0] == "checkin":
                        return self.post_daily_checkin, {}
                    if rest2[0] == "reset-season":
                        return self.post_competition_reset_season, {}
                if rest[0] == "news":
                    return self.get_news_market, {}
                if rest[0] == "my-votes" and len(rest) >= 2:
                    return self.get_competition_my_votes, {"user_id": rest[1]}
                if rest[0] == "trades":
                    return self.get_all_trades, {}
                if rest[0] == "execute_trade":
                    return self.execute_trade, {}
                if rest[0] == "posts" and len(rest) == 1:
                    return self.create_post, {}
                # Phase 2: 真人论坛
                if rest[0] == "forum":
                    rest2 = rest[1:]
                    # 精确路由优先（长路径在前）
                    if len(rest2) >= 3 and rest2[0] == "posts" and rest2[2] == "replies":
                        return self.get_forum_replies, {"post_id": rest2[1]}
                    if len(rest2) >= 2 and rest2[0] == "posts" and rest2[1] == "new":
                        return self.create_forum_post, {}
                    if len(rest2) >= 2 and rest2[0] == "posts":
                        return self.get_forum_post, {"post_id": rest2[1]}
                    if not rest2 or rest2[0] == "posts":
                        return self.get_forum_posts, {}
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
                if len(rest) >= 2 and rest[0] == "prediction-stats":
                    return self.get_prediction_stats, {"ai_id": rest[1]}
                # Phase 3.2: 中级竞猜 - 区间押注统计
                if len(rest) >= 2 and rest[0] == "range-stats":
                    return self.get_range_stats, {"ai_id": rest[1]}
                if rest[0] == "my-votes" and len(rest) >= 2:
                    return self.get_competition_my_votes, {"user_id": rest[1]}
                if rest[0] == "vote-results":
                    return self.get_competition_vote_results, {}
                if rest[0] == "comments":
                    return self.get_competition_comments, {}
                if rest[0] == "my-comments" and len(rest) >= 2:
                    return self.get_competition_my_comments, {"user_id": rest[1]}
                # Phase 3.3: 互动积分
                if rest[0] == "interaction":
                    if len(rest) >= 2 and rest[1] == "ranking":
                        return self.get_interaction_ranking, {}
                    if len(rest) >= 3 and rest[1] == "me":
                        return self.get_interaction_me, {"user_id": rest[2]}
                # Phase 1 收尾：赛季管理
                if rest[0] == "seasons":
                    return self.get_competition_seasons, {}
                if rest[0] == "checkin":
                    return self.post_daily_checkin, {}
                if rest[0] == "reset-season":
                    return self.post_competition_reset_season, {}
            if sub[0] == "news":
                return self.get_news_market, {}
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

    # ========== 信息市场 API ==========
    def get_news_market(self):
        """信息市场 - GET /api/news?type=xxx&page=1&limit=20"""
        import sqlite3 as sq3
        
        # 解析参数
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        news_type = params.get('type', ['all'])[0]
        page = max(1, int(params.get('page', [1])[0]))
        limit = min(50, max(1, int(params.get('limit', [20])[0])))
        offset = (page - 1) * limit
        
        # 映射type到过滤条件
        NEWS_DB = '/var/www/familystock/api/data/family_stock.db'
        
        # 构建WHERE条件
        where_clauses = []
        params = []
        
        if news_type == 'finance':
            where_clauses.append("source_platform IN (?, ?)")
            params.extend(['cls', 'ths'])
        elif news_type == 'social':
            where_clauses.append("source_platform IN (?, ?)")
            params.extend(['weibo', 'douyin'])
        elif news_type == 'black':
            # 黑天鹅监控：event_type 为风险类型
            where_clauses.append("event_type IN (?, ?, ?, ?)")
            params.extend(['black_swan', 'gray_rhinoceros', 'macro_risk', 'sector_risk'])
        elif news_type == 'blogger':
            where_clauses.append("source_platform = ?")
            params.append('bilibili')
        # 'all': 不加过滤条件
        
        where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
        
        try:
            conn = sq3.connect(NEWS_DB, timeout=30)
            conn.execute('PRAGMA journal_mode=WAL')
            
            # 统计
            total = conn.execute(f'SELECT COUNT(*) FROM news WHERE {where_sql}', params).fetchone()[0]
            rows = conn.execute(
                f'''SELECT id, title, content, source, source_platform, published_at,
                          sentiment, event_type, keywords, category, url, blogger_source
                   FROM news WHERE {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?''',
                params + [limit, offset]
            ).fetchall()
            
            conn.close()
            
            items = []
            for row in rows:
                items.append({
                    'id': row[0],
                    'title': row[1] or '',
                    'content': (row[2] or '')[:200],
                    'source': row[3] or '',
                    'source_platform': row[4] or '',
                    'published_at': row[5] or '',
                    'sentiment': round(float(row[6] or 0), 2),
                    'event_type': row[7] or 'normal',
                    'keywords': row[8] or '',
                    'category': row[9] or '',
                    'url': row[10] or '',
                    'blogger_source': row[11] or ''
                })
            
            return {'data': {
                'list': items,
                'total': total,
                'page': page,
                'limit': limit,
                'pages': (total + limit - 1) // limit,
                'type': news_type
            }}
            
        except Exception as e:
            return {'data': {'list': [], 'total': 0, 'page': page, 'limit': limit, 'pages': 0, 'type': news_type, 'error': str(e)}}

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
            # 获取所有AI（即使无持仓也要显示，支持预测空仓AI次日涨跌）
            rows = conn.execute("""
                SELECT c.id, c.name, c.emoji, c.style,
                       h.symbol, h.name AS stock_name, h.current_price,
                       h.quantity, h.avg_cost
                FROM ai_characters c
                LEFT JOIN ai_holdings h ON CAST(h.ai_id AS INTEGER) = c.id AND h.current_price > 0
                ORDER BY c.id
            """).fetchall()

            items = []
            for r in rows:
                aid = r[0]
                items.append({
                    "ai_id": aid, "ai_name": r[1], "ai_emoji": r[2] or "🤖",
                    "symbol": r[4], "stock_name": r[5], "current_price": float(r[6] or 0),
                    "quantity": r[7], "avg_cost": float(r[8] or 0)
                })

            # 按AI分组
            ai_groups = {}
            for item in items:
                aid = item["ai_id"]
                if aid not in ai_groups:
                    ai_groups[aid] = {"ai_id": aid, "ai_name": item["ai_name"],
                                      "ai_emoji": item["ai_emoji"], "holdings": []}
                if item["symbol"]:  # 只添加有symbol的持仓
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

        required = ["user_id", "ai_id"]
        vote_type_check = data.get("vote_type", "direction")
        if vote_type_check == "direction" and "direction" not in data:
            return {"error": "missing field: direction"}, 400
        if vote_type_check not in ("direction", "range"):
            return {"error": "vote_type must be 'direction' or 'range'"}, 400

        user_id = str(data["user_id"]).strip()
        ai_id = int(data["ai_id"])
        vote_type = data.get("vote_type", "direction")
        range_type = data.get("range_type", None)
        stock_symbol = data.get("stock_symbol", None)
        stock_name = data.get("stock_name", stock_symbol or "")

        if vote_type == "range":
            valid_ranges = ("below_minus5", "minus5_to_0", "0_to_5", "above_5")
            if range_type not in valid_ranges:
                return {"error": "range_type must be one of: below_minus5, minus5_to_0, 0_to_5, above_5"}, 400
            direction = "up"  # placeholder - range stored in range_type column
        elif vote_type == "direction":
            direction = data["direction"]
            if direction not in ("up", "down"):
                return {"error": "direction must be 'up' or 'down'"}, 400
        else:
            return {"error": "vote_type must be 'direction' or 'range'"}, 400

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
                INSERT INTO user_votes (user_id, user_phone, ai_id, ai_name, stock_symbol, stock_name, direction, vote_date, settled, vote_type, range_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(user_id, ai_id, stock_symbol, vote_date) DO UPDATE SET
                    direction=excluded.direction,
                    vote_type=excluded.vote_type,
                    range_type=excluded.range_type,
                    created_at=datetime('now', '+8 hours')
            """, (user_id, user_phone, ai_id, ai_name, stock_symbol, stock_name, direction, today, vote_type, range_type))
            conn.commit()

            if vote_type == "range":
                labels = {"below_minus5": "跌幅>5%", "minus5_to_0": "跌0~5%", "0_to_5": "涨0~5%", "above_5": "涨幅>5%"}
                msg = f"区间预测已提交: {ai_name} {labels.get(range_type, range_type)}"
            else:
                msg = f"方向预测已提交: {ai_name} {'涨' if direction=='up' else '跌'}"
            return {"data": {"success": True, "message": msg, "vote_date": today}}
        finally:
            conn.close()

    def get_competition_my_votes(self, user_id=None):
        """获取用户的投票历史
        支持 user_id=openid 或 phone（自动映射到 openid）
        """
        uid = user_id or "unknown"
        conn = get_db()
        try:
            # phone→openid 映射：先查 user_votes（phone存这里），再查 user_interaction_points
            uid_for_interaction = uid
            uid_for_votes = uid
            if uid and not uid.startswith("ou_"):
                # 从 votes 表找到该 phone 对应的 openid（user_id 字段存 openid）
                row = conn.execute(
                    "SELECT DISTINCT user_id FROM user_votes WHERE user_phone=? AND user_id LIKE 'ou_%' LIMIT 1",
                    (uid,)
                ).fetchone()
                if row:
                    uid_for_interaction = row[0]  # openid → 查 user_interaction_points
                    uid_for_votes = uid          # phone   → 查 user_votes
                else:
                    # votes表也没有openid，fallback：直接用phone查interaction_points
                    uid_for_interaction = uid
                    uid_for_votes = uid

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
            """, (uid_for_votes,)).fetchall()

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
            vote_points = sum(v["points_earned"] for v in votes if v["points_earned"])

            # 合并 user_interaction_points.total_score（含签到/道具等积分）
            interaction = conn.execute(
                "SELECT COALESCE(total_score,0) FROM user_interaction_points WHERE user_id=?",
                (uid_for_interaction,)
            ).fetchone()
            interaction_points = interaction[0] if interaction else 0
            total_points = vote_points + interaction_points

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

    def get_competition_seasons(self):
        """获取所有赛季列表"""
        conn = get_db()
        try:
            cur = conn.execute("SELECT * FROM ai_seasons ORDER BY id DESC")
            rows = cur.fetchall()
            seasons = []
            for r in rows:
                seasons.append({
                    "id": r["id"],
                    "season_id": r["season_id"],
                    "start_date": r["start_date"],
                    "end_date": r["end_date"],
                    "champion_ai_id": r["champion_ai_id"],
                    "created_at": r["created_at"]
                })
            return {"data": {"seasons": seasons, "count": len(seasons)}}
        except Exception as e:
            return {"error": str(e)}

    def post_competition_reset_season(self):
        """重置赛季：存档当前数据 → 清空持仓/交易 → 生成新赛季ID"""
        conn = get_db()
        try:
            import json as _json
            # 1. 读取当前赛季信息（如果有的话）
            cur = conn.execute("SELECT season_id FROM ai_seasons ORDER BY id DESC LIMIT 1")
            last_season = cur.fetchone()
            current_season_id = last_season["season_id"] if last_season else "2026_Q1"

            # 2. 读取当前持仓快照用于存档
            cur = conn.execute("""
                SELECT p.ai_id, c.name as ai_name, p.cash, p.total_value,
                       (SELECT GROUP_CONCAT(h.symbol || ':' || h.quantity || ':' || h.avg_cost)
                        FROM ai_holdings h WHERE h.ai_id = p.ai_id) as holdings
                FROM ai_portfolios p
                JOIN ai_characters c ON c.id = p.ai_id
            """)
            portfolio_snapshot = []
            for r in cur.fetchall():
                portfolio_snapshot.append({
                    "ai_id": r["ai_id"],
                    "ai_name": r["ai_name"],
                    "cash": r["cash"],
                    "total_value": r["total_value"],
                    "holdings": r["holdings"]
                })

            # 读取排行榜快照
            cur = conn.execute("""
                SELECT p.ai_id, c.name as ai_name, p.total_value, p.cash,
                       ROUND((p.total_value - p.cash) / p.cash * 100, 2) as profit_rate,
                       p.updated_at
                FROM ai_portfolios p
                JOIN ai_characters c ON c.id = p.ai_id
                ORDER BY (p.total_value - p.cash) / p.cash DESC
            """)
            rankings_snapshot = []
            for r in cur.fetchall():
                rankings_snapshot.append({
                    "ai_id": r["ai_id"],
                    "ai_name": r["ai_name"],
                    "total_value": r["total_value"],
                    "cash": r["cash"],
                    "profit_rate": r["profit_rate"],
                    "updated_at": r["updated_at"]
                })

            # 确定冠军
            champion_id = rankings_snapshot[0]["ai_id"] if rankings_snapshot else None

            # 3. 生成新赛季ID
            import re
            m = re.search(r'(\d{4})_Q(\d)', current_season_id)
            if m:
                year, quarter = int(m.group(1)), int(m.group(2))
                if quarter == 4:
                    year += 1; quarter = 1
                else:
                    quarter += 1
                new_season_id = f"{year}_Q{quarter}"
            else:
                new_season_id = "2026_Q2"

            new_start = datetime.now().strftime("%Y-%m-%d")

            # 4. 写入历史存档
            archive_data = _json.dumps({
                "rankings": rankings_snapshot,
                "portfolios": portfolio_snapshot,
                "stats": {
                    "total_ais": len(portfolio_snapshot),
                    "top_profit_rate": rankings_snapshot[0]["profit_rate"] if rankings_snapshot else 0
                }
            }, ensure_ascii=False)

            # 5. 写入新赛季记录
            conn.execute("""
                INSERT INTO ai_seasons (season_id, start_date, champion_ai_id, final_data)
                VALUES (?, ?, ?, ?)
            """, (new_season_id, new_start, champion_id, archive_data))

            # 6. 清空持仓和交易记录
            conn.execute("DELETE FROM ai_holdings")
            conn.execute("DELETE FROM ai_trades")

            # 7. 重置持仓（去重 + 按 ai_id 分组重置）
            # 删除每个 ai_id 的重复行，只保留 id 最小的那条
            conn.execute("""
                DELETE FROM ai_portfolios WHERE id NOT IN (
                    SELECT MIN(id) FROM ai_portfolios GROUP BY ai_id
                )
            """)
            # 重置A组(1-5)为100万，B组(6-10)为10万
            conn.execute("""
                UPDATE ai_portfolios
                SET cash = CASE WHEN CAST(ai_id AS INTEGER) BETWEEN 1 AND 5 THEN 1000000.0 ELSE 100000.0 END,
                    total_value = cash,
                    seed_capital = cash,
                    updated_at = ?
                WHERE 1=1
            """, (datetime.now().isoformat(),))

            conn.commit()

            return {"data": {
                "message": "赛季重置成功",
                "archived_season": current_season_id,
                "new_season_id": new_season_id,
                "champion": champion_id,
                "ai_count": len(portfolio_snapshot)
            }}

        except Exception as e:
            conn.rollback()
            return {"error": str(e)}

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

    # ─── Phase 2: 真人论坛 ───────────────────────────────────────

    def get_forum_posts(self):
        """获取真人帖子列表"""
        conn = get_db()
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            category = params.get("category", [None])[0]
            related_ai = params.get("ai", [None])[0]
            limit = int(params.get("limit", ["50"])[0])
            offset = int(params.get("offset", ["0"])[0])

            query = "SELECT * FROM forum_posts WHERE 1=1"
            args = []
            if category:
                query += " AND category=?"
                args.append(category)
            if related_ai:
                query += " AND related_ai_id=?"
                args.append(related_ai)
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            args.extend([limit, offset])

            cur = conn.execute(query, args)
            rows = cur.fetchall()
            posts = []
            for r in rows:
                posts.append({
                    "id": r["id"],
                    "post_id": r["post_id"],
                    "user_id": r["user_id"],
                    "user_name": r["user_name"],
                    "title": r["title"],
                    "content": r["content"],
                    "category": r["category"],
                    "related_ai_id": r["related_ai_id"],
                    "related_symbol": r["related_symbol"],
                    "views": r["views"],
                    "likes": r["likes"],
                    "replies": r["replies"],
                    "created_at": r["created_at"]
                })
            total = conn.execute("SELECT COUNT(*) FROM forum_posts").fetchone()[0]
            return {"data": {"posts": posts, "total": total, "offset": offset, "limit": limit}}
        except Exception as e:
            import traceback; traceback.print_exc()
            return {"error": str(e)}

    def create_forum_post(self):
        """真人发布帖子"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except:
            return {"error": "invalid JSON"}, 400

        required = ["title", "content", "user_id"]
        for f in required:
            if f not in data:
                return {"error": f"missing field: {f}"}, 400

        title = data["title"].strip()
        content = data["content"].strip()
        if len(title) < 5:
            return {"error": "title must be at least 5 chars"}, 400
        if len(content) < 10:
            return {"error": "content must be at least 10 chars"}, 400

        conn = get_db()
        try:
            import uuid
            post_id = str(uuid.uuid4())[:8]
            cur = conn.execute("""
                INSERT INTO forum_posts (post_id, user_id, user_name, user_phone, title, content,
                    category, related_ai_id, related_symbol, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '+8 hours'))
            """, (post_id, str(data["user_id"]), data.get("user_name", ""),
                  data.get("user_phone", ""), title, content,
                  data.get("category", "general"),
                  data.get("related_ai_id"), data.get("related_symbol")))
            row_id = cur.lastrowid
            conn.commit()
            conn.close()
            return {"data": {"success": True, "post_id": post_id, "row_id": row_id}}
        except Exception as e:
            conn.rollback()
            conn.close()
            import traceback; traceback.print_exc()
            return {"error": str(e)}, 500

    def get_forum_post(self, post_id):
        """获取帖子详情"""
        conn = get_db()
        try:
            row = conn.execute("SELECT * FROM forum_posts WHERE id=? OR post_id=?", (post_id, post_id)).fetchone()
            if not row:
                return {"error": "post not found"}, 404
            # views++
            conn.execute("UPDATE forum_posts SET views=views+1 WHERE id=?", (row["id"],))
            conn.commit()
            return {"data": {
                "id": row["id"],
                "post_id": row["post_id"],
                "user_id": row["user_id"],
                "user_name": row["user_name"],
                "title": row["title"],
                "content": row["content"],
                "category": row["category"],
                "related_ai_id": row["related_ai_id"],
                "related_symbol": row["related_symbol"],
                "views": row["views"] + 1,
                "likes": row["likes"],
                "replies": row["replies"],
                "created_at": row["created_at"]
            }}
        except Exception as e:
            return {"error": str(e)}

    def get_forum_replies(self, post_id):
        """获取某帖子的所有 AI 回复"""
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT * FROM forum_replies
                WHERE post_id = ?
                ORDER BY created_at ASC
            """, (post_id,)).fetchall()
            replies = []
            for r in rows:
                replies.append({
                    "id": r["id"],
                    "post_id": r["post_id"],
                    "ai_id": r["ai_id"],
                    "ai_name": r["ai_name"],
                    "content": r["content"],
                    "created_at": r["created_at"]
                })
            return {"data": {"replies": replies, "count": len(replies)}}
        except Exception as e:
            return {"error": str(e)}

    # ─── Phase 3.2: 用户评论 ───────────────────────────────────────

    def get_comments(self, target_id=None):
        """获取评论列表

        GET /api/comments              - 所有评论（最新）
        GET /api/comments/{target_id}  - 指定目标的评论
        GET /api/comments/latest       - 最新评论
        """
        conn = get_db()
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            limit = 50
            if 'limit' in params and params['limit']:
                try:
                    limit = max(1, min(200, int(params['limit'][0])))
                except:
                    pass

            if target_id == "latest":
                rows = conn.execute(f"""
                    SELECT c.id, c.user_id, c.user_name, c.user_phone, c.ai_id, c.ai_name,
                           c.target_type, c.target_id, c.content, c.parent_id, c.likes,
                           c.created_at, p.title
                    FROM user_comments c
                    LEFT JOIN ai_posts p ON c.target_id = p.post_id
                    ORDER BY c.created_at DESC LIMIT {limit}
                """).fetchall()
            elif target_id:
                rows = conn.execute(f"""
                    SELECT c.id, c.user_id, c.user_name, c.user_phone, c.ai_id, c.ai_name,
                           c.target_type, c.target_id, c.content, c.parent_id, c.likes,
                           c.created_at, p.title
                    FROM user_comments c
                    LEFT JOIN ai_posts p ON c.target_id = p.post_id
                    WHERE c.target_id=? OR c.target_id=?
                    ORDER BY c.created_at DESC LIMIT {limit}
                """, (str(target_id), f"post_{target_id}")).fetchall()
            else:
                rows = conn.execute(f"""
                    SELECT c.id, c.user_id, c.user_name, c.user_phone, c.ai_id, c.ai_name,
                           c.target_type, c.target_id, c.content, c.parent_id, c.likes,
                           c.created_at, p.title
                    FROM user_comments c
                    LEFT JOIN ai_posts p ON c.target_id = p.post_id
                    ORDER BY c.created_at DESC LIMIT {limit}
                """).fetchall()

            comments = []
            for r in rows:
                comments.append({
                    "id": r[0], "user_id": r[1], "user_name": r[2] or "匿名用户",
                    "user_phone": r[3][-4:] if r[3] and len(r[3]) >= 4 else r[3] or "",
                    "ai_id": r[4], "ai_name": r[5],
                    "target_type": r[6], "target_id": r[7],
                    "content": r[8], "parent_id": r[9], "likes": r[10] or 0,
                    "created_at": r[11], "post_title": r[12]
                })

            # 按parent_id组织回复
            root_comments = [c for c in comments if c["parent_id"] is None]
            replies_map = {}
            for c in comments:
                if c["parent_id"]:
                    replies_map.setdefault(c["parent_id"], []).append(c)
            for c in root_comments:
                c["replies"] = replies_map.get(c["id"], [])

            return {"data": {"comments": root_comments, "total": len(comments)}}
        finally:
            conn.close()

    def get_latest_comments(self):
        """获取最新评论"""
        return self.get_comments(target_id="latest")

    def get_competition_comments(self):
        """获取AI股神争霸可评论内容列表（帖子+交易）

        GET /api/competition/comments
        Query params: ai_id, type (post/trade/all), limit, offset
        """
        conn = get_db()
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            limit = min(int(params.get("limit", ["20"])[0]) if params.get("limit") else 20, 50)
            offset = int(params.get("offset", ["0"])[0]) if params.get("offset") else 0
            ai_filter = params.get("ai_id", [None])[0]
            content_type = params.get("type", ["all"])[0]

            items = []

            # 获取AI帖子（可评论的）
            if content_type in ("all", "post"):
                post_sql = """
                    SELECT p.id, p.post_id, p.ai_id, p.ai_name, p.post_type, p.title,
                           p.content, p.created_at, p.likes
                    FROM ai_posts p
                """
                post_params = []
                if ai_filter:
                    post_sql += " WHERE p.ai_id = ?"
                    post_params.append(str(ai_filter))
                post_sql += " ORDER BY p.created_at DESC LIMIT ? OFFSET ?"
                post_params.extend([limit, offset])
                post_rows = conn.execute(post_sql, post_params).fetchall()
                for row in post_rows:
                    items.append({
                        "id": row[1],  # post_id (TEXT, 可用于API)
                        "db_id": row[0],  # INTEGER主键
                        "ai_id": row[2], "ai_name": row[3],
                        "type": "post", "post_type": row[4], "title": row[5] or "",
                        "content": row[6][:200] if row[6] else "",
                        "created_at": row[7], "likes": row[8] or 0,
                        "comment_count": conn.execute(
                            "SELECT COUNT(*) FROM user_comments WHERE target_type='post' AND target_id=?",
                            (str(row[1]),)
                        ).fetchone()[0]
                    })

            # 获取AI交易（可评论的）
            if content_type in ("all", "trade"):
                trade_sql = """
                    SELECT t.id, t.ai_id, c.name, t.symbol, t.name as stock_name,
                           t.action, t.price, t.quantity, t.created_at
                    FROM ai_trades t
                    JOIN ai_characters c ON t.ai_id = c.id
                """
                trade_params = []
                if ai_filter:
                    trade_sql += " WHERE t.ai_id = ?"
                    trade_params.append(str(ai_filter))
                else:
                    trade_sql += " WHERE 1=1"
                trade_sql += " ORDER BY t.created_at DESC LIMIT ? OFFSET ?"
                trade_params.extend([limit, offset])
                trade_rows = conn.execute(trade_sql, trade_params).fetchall()
                for row in trade_rows:
                    items.append({
                        "id": str(row[0]), "ai_id": row[1], "ai_name": row[2],
                        "type": "trade", "symbol": row[3], "stock_name": row[4],
                        "action": row[5], "price": row[6], "quantity": row[7],
                        "created_at": row[8],
                        "comment_count": conn.execute(
                            "SELECT COUNT(*) FROM user_comments WHERE target_type='trade' AND target_id=?",
                            (str(row[0]),)
                        ).fetchone()[0]
                    })

            # 按时间排序
            items.sort(key=lambda x: x["created_at"], reverse=True)

            return {"data": {"items": items[:limit], "total": len(items), "limit": limit, "offset": offset}}
        finally:
            conn.close()

    def get_competition_my_comments(self, user_id):
        """获取用户在AI股神争霸的评论记录

        GET /api/competition/my-comments/{user_id}
        """
        conn = get_db()
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            limit = min(int(params.get("limit", ["30"])[0]) if params.get("limit") else 30, 100)
            offset = int(params.get("offset", ["0"])[0]) if params.get("offset") else 0

            rows = conn.execute("""
                SELECT c.id, c.user_id, c.user_name, c.user_phone, c.ai_id, c.ai_name,
                       c.target_type, c.target_id, c.content, c.parent_id, c.likes,
                       c.created_at,
                       CASE WHEN c.target_type = 'post' THEN p.title
                            WHEN c.target_type = 'trade' THEN t.name || ' ' || t.action
                            ELSE '' END as target_title
                FROM user_comments c
                LEFT JOIN ai_posts p ON c.target_type = 'post' AND c.target_id = CAST(p.post_id AS TEXT)
                LEFT JOIN ai_trades t ON c.target_type = 'trade' AND c.target_id = CAST(t.id AS TEXT)
                WHERE c.user_id = ?
                ORDER BY c.created_at DESC LIMIT ? OFFSET ?
            """, (str(user_id), limit, offset)).fetchall()

            comments = []
            for r in rows:
                comments.append({
                    "id": r[0], "user_id": r[1], "user_name": r[2] or "匿名用户",
                    "user_phone": r[3][-4:] if r[3] and len(r[3]) >= 4 else r[3] or "",
                    "ai_id": r[4], "ai_name": r[5],
                    "target_type": r[6], "target_id": r[7],
                    "content": r[8], "parent_id": r[9], "likes": r[10] or 0,
                    "created_at": r[11], "target_title": r[12] or ""
                })

            total = conn.execute(
                "SELECT COUNT(*) FROM user_comments WHERE user_id = ?", (str(user_id),)
            ).fetchone()[0]

            return {"data": {"comments": comments, "total": total, "limit": limit, "offset": offset}}
        finally:
            conn.close()

    def compute_user_points(self, user_id):
        """根据投票+评论数据计算用户积分，保存到 user_interaction_scores 表 (Phase 3.3)

        积分规则:
        - 投票积分 = 准确率×100 (最多100分)
        - 评论积分 = min(comment_count×2, 50) + min(likes_received×1, 30) + min(replies×3, 20)
        - 总分 = vote_score×50% + comment_score×50%
        - 等级: 0=新手, 1=活跃, 2=专家, 3=大师, 4=传奇
        """
        conn = get_db()
        try:
            user_id_str = str(user_id)

            # 投票准确率（settle_date IS NOT NULL 表示已结算）
            pred = conn.execute("""
                SELECT COUNT(*), SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END)
                FROM prediction_results WHERE user_id=? AND settle_date IS NOT NULL
            """, (user_id_str,)).fetchone()
            total_votes = pred[0] or 0
            correct_votes = pred[1] or 0
            vote_accuracy = (correct_votes / total_votes * 100) if total_votes > 0 else 0.0
            vote_score = vote_accuracy  # 准确率×100

            # 评论积分
            comment_count = conn.execute(
                "SELECT COUNT(*) FROM user_comments WHERE user_id=?", (user_id_str,)
            ).fetchone()[0]
            likes_received = conn.execute(
                "SELECT COALESCE(SUM(likes), 0) FROM user_comments WHERE user_id=?", (user_id_str,)
            ).fetchone()[0] or 0
            replies_received = conn.execute(
                "SELECT COUNT(*) FROM user_comments WHERE parent_id IS NOT NULL AND user_id=?", (user_id_str,)
            ).fetchone()[0]

            comment_score = min(comment_count * 2, 50) + min(likes_received, 30) + min(replies_received * 3, 20)

            # 总分和等级
            total_score = vote_score * 0.5 + comment_score * 0.5
            level = 0
            if total_score >= 80: level = 4
            elif total_score >= 60: level = 3
            elif total_score >= 40: level = 2
            elif total_score >= 20: level = 1

            # 用户信息
            row = conn.execute(
                "SELECT user_name, user_phone FROM user_comments WHERE user_id=? LIMIT 1",
                (user_id_str,)
            ).fetchone()
            user_name = row[0] if row else ""
            user_phone = row[1] if row else user_id_str

            # UPSERT
            conn.execute("""
                INSERT INTO user_interaction_scores
                    (user_id, user_name, user_phone, total_votes, correct_votes, vote_accuracy,
                     vote_score, comment_count, likes_received, replies_received, comment_score,
                     total_score, level, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '+8 hours'))
                ON CONFLICT(user_id) DO UPDATE SET
                    user_name=excluded.user_name, user_phone=excluded.user_phone,
                    total_votes=excluded.total_votes, correct_votes=excluded.correct_votes,
                    vote_accuracy=excluded.vote_accuracy, vote_score=excluded.vote_score,
                    comment_count=excluded.comment_count, likes_received=excluded.likes_received,
                    replies_received=excluded.replies_received, comment_score=excluded.comment_score,
                    total_score=excluded.total_score, level=excluded.level,
                    updated_at=excluded.updated_at
            """, (user_id_str, user_name, user_phone, total_votes, correct_votes, vote_accuracy,
                  vote_score, comment_count, likes_received, replies_received, comment_score,
                  total_score, level))
            conn.commit()
            return {"data": {"total_score": round(total_score, 1), "vote_score": round(vote_score, 1),
                             "comment_score": comment_score, "level": level}}
        finally:
            conn.close()

    def get_interaction_ranking(self):
        """获取用户互动积分排行榜 (Phase 3.3)

        GET /api/competition/interaction/ranking
        Query: limit, offset
        """
        conn = get_db()
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            limit = min(int(params.get("limit", ["20"])[0]) if params.get("limit") else 20, 100)
            offset = int(params.get("offset", ["0"])[0]) if params.get("offset") else 0

            rows = conn.execute("""
                SELECT user_id, user_name, user_phone, total_votes, correct_votes,
                       vote_accuracy, vote_score, comment_count, likes_received,
                       comment_score, total_score, level, updated_at
                FROM user_interaction_scores
                ORDER BY total_score DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()

            level_names = ["新手", "活跃", "专家", "大师", "传奇"]
            items = []
            for rank, row in enumerate(rows, start=offset + 1):
                items.append({
                    "rank": rank,
                    "user_id": row[0],
                    "user_name": row[1] or "匿名用户",
                    "user_phone": (row[2][-4:] if row[2] and len(row[2]) >= 4 else row[2] or ""),
                    "total_votes": row[3] or 0,
                    "correct_votes": row[4] or 0,
                    "vote_accuracy": round(row[5] or 0, 1),
                    "vote_score": round(row[6] or 0, 1),
                    "comment_count": row[7] or 0,
                    "likes_received": row[8] or 0,
                    "comment_score": row[9] or 0,
                    "total_score": round(row[10] or 0, 1),
                    "level": row[11] or 0,
                    "level_name": level_names[row[11] or 0],
                    "updated_at": row[12] or ""
                })

            total = conn.execute("SELECT COUNT(*) FROM user_interaction_scores").fetchone()[0]
            return {"data": {"items": items, "total": total, "limit": limit, "offset": offset}}
        finally:
            conn.close()

    def get_interaction_me(self, user_id):
        """获取指定用户的互动积分详情 (Phase 3.3)

        GET /api/competition/interaction/me/{user_id}
        """
        conn = get_db()
        try:
            # 先计算最新积分
            calc_result = self.compute_user_points(str(user_id))

            # 再读取
            row = conn.execute("""
                SELECT user_id, user_name, user_phone, total_votes, correct_votes,
                       vote_accuracy, vote_score, comment_count, likes_received,
                       replies_received, comment_score, total_score, level, updated_at
                FROM user_interaction_scores WHERE user_id=?
            """, (str(user_id),)).fetchone()

            if not row:
                return {"data": {"user_id": str(user_id), "total_score": 0, "level_name": "新手", "items": []}}

            level_names = ["新手", "活跃", "专家", "大师", "传奇"]
            rank_row = conn.execute("""
                SELECT COUNT(*) + 1 FROM user_interaction_scores
                WHERE total_score > ?
            """, (row[11] or 0,)).fetchone()

            return {"data": {
                "rank": rank_row[0],
                "user_id": row[0],
                "user_name": row[1] or "匿名用户",
                "user_phone": (row[2][-4:] if row[2] and len(row[2]) >= 4 else row[2] or ""),
                "total_votes": row[3] or 0,
                "correct_votes": row[4] or 0,
                "vote_accuracy": round(row[5] or 0, 1),
                "vote_score": round(row[6] or 0, 1),
                "comment_count": row[7] or 0,
                "likes_received": row[8] or 0,
                "replies_received": row[9] or 0,
                "comment_score": row[10] or 0,
                "total_score": round(row[11] or 0, 1),
                "level": row[12] or 0,
                "level_name": level_names[row[12] or 0],
                "updated_at": row[13] or ""
            }}
        finally:
            conn.close()

    def calc_interaction_score(self):
        """重新计算所有用户积分 (Phase 3.3)

        POST /api/competition/interaction/calc
        可选body: {user_id} - 仅重算指定用户
        """
        conn = get_db()
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            data = json.loads(body) if body != "{}" else {}
            target_user = data.get("user_id")

            if target_user:
                result = self.compute_user_points(str(target_user))
                return {"data": {"recalculated": 1, **result.get("data", {})}}
            else:
                # 重算所有有活动的用户
                user_ids = conn.execute("""
                    SELECT DISTINCT user_id FROM user_comments
                    UNION SELECT DISTINCT user_id FROM user_votes
                """).fetchall()
                count = 0
                for (uid,) in user_ids:
                    self.compute_user_points(str(uid))
                    count += 1
                return {"data": {"recalculated": count}}
        except Exception as e:
            return {"error": str(e)}, 500
        finally:
            conn.close()

    def post_daily_checkin(self):
        """每日签到（Phase 3.3）
        POST /api/competition/checkin
        Body: {user_id, user_name}
        连续签到奖励：1天=10分，7天=20分，30天=50分
        """
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except:
            return {"error": "invalid JSON"}, 400

        user_id = str(data.get("user_id", ""))
        user_name = data.get("user_name", "")
        if not user_id:
            return {"error": "user_id required"}, 400

        conn = get_db()
        try:
            today = datetime.now().strftime("%Y-%m-%d")

            # 查找上次签到记录
            row = conn.execute("""
                SELECT last_active_date, streak_days, daily_visits
                FROM user_interaction_points WHERE user_id=?
            """, (user_id,)).fetchone()

            if row and row["last_active_date"]:
                last_date = row["last_active_date"]
                prev_streak = row["streak_days"] or 0
                prev_visits = row["daily_visits"] or 0

                # 昨天已签到 → 连续+1
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                if last_date == yesterday:
                    new_streak = prev_streak + 1
                    already_checked_in = (last_date == today)
                elif last_date == today:
                    already_checked_in = True
                    new_streak = prev_streak
                else:
                    new_streak = 1
                    already_checked_in = False
            else:
                new_streak = 1
                already_checked_in = False
                prev_visits = 0

            if already_checked_in:
                return {"data": {
                    "message": "今日已签到",
                    "streak_days": new_streak,
                    "points_earned": 0,
                    "already_checked_in": True
                }}

            # 计算积分
            if new_streak >= 30:
                points = 50
            elif new_streak >= 7:
                points = 20
            else:
                points = 10

            new_visits = prev_visits + 1

            # 查现有积分
            existing = conn.execute("SELECT COALESCE(total_score, 0) as s FROM user_interaction_points WHERE user_id=?", (user_id,)).fetchone()
            existing_score = existing["s"] if existing else 0

            # 计算新总分
            new_total_score = existing_score + points
            new_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # UPSERT
            conn.execute("""
                INSERT INTO user_interaction_points
                    (user_id, user_name, daily_visits, streak_days, last_active_date, total_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    daily_visits = excluded.daily_visits,
                    streak_days = excluded.streak_days,
                    last_active_date = excluded.last_active_date,
                    total_score = excluded.total_score,
                    updated_at = excluded.updated_at
            """, (user_id, user_name, new_visits, new_streak, today, new_total_score, new_updated_at))

            conn.commit()
            return {"data": {
                "message": f"签到成功！连续 {new_streak} 天",
                "streak_days": new_streak,
                "points_earned": points,
                "total_streak": new_streak,
                "already_checked_in": False
            }}
        except Exception as e:
            conn.rollback()
            import traceback; traceback.print_exc()
            return {"error": str(e)}, 500
        finally:
            conn.close()

    def get_range_stats(self, ai_id):
        """区间押注分布（Phase 3.2 中级竞猜）
        GET /api/competition/range-stats/{ai_id}
        """
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT range_type, COUNT(*) as cnt
                FROM user_votes
                WHERE ai_id=? AND vote_type='range' AND range_type IS NOT NULL
                GROUP BY range_type
            """, (int(ai_id),)).fetchall()
            total = sum(r[1] for r in rows)
            distribution = {}
            for rt in ("below_minus5", "minus5_to_0", "0_to_5", "above_5"):
                cnt = next((r[1] for r in rows if r[0] == rt), 0)
                distribution[rt] = {
                    "count": cnt,
                    "pct": round(cnt / total * 100, 1) if total > 0 else 0
                }
            return {"data": {
                "ai_id": str(ai_id),
                "total_range_votes": total,
                "distribution": distribution
            }}
        finally:
            conn.close()

    def get_prediction_stats(self, ai_id):
        """竞猜可视化数据（Phase 3.2）

        GET /api/competition/prediction-stats/{ai_id}
        返回：该AI的押注分布、参与人数趋势、历史准确率
        """
        conn = get_db()
        try:
            # 押注分布
            total_votes = conn.execute("""
                SELECT COUNT(*) FROM user_votes WHERE ai_id=?
            """, (ai_id,)).fetchone()[0] or 0

            up_count = conn.execute("""
                SELECT COUNT(*) FROM user_votes WHERE ai_id=? AND direction='up'
            """, (ai_id,)).fetchone()[0] or 0

            down_count = total_votes - up_count

            # 近7天押注趋势
            trend_rows = conn.execute("""
                SELECT vote_date, COUNT(*) as cnt,
                       SUM(CASE WHEN direction='up' THEN 1 ELSE 0 END) as up_cnt
                FROM user_votes
                WHERE ai_id=? AND vote_date >= date('now', '-7 days')
                GROUP BY vote_date
                ORDER BY vote_date ASC
            """, (ai_id,)).fetchall()
            trend = [{
                "date": r["vote_date"],
                "total": r["cnt"],
                "up": r["up_cnt"],
                "down": r["cnt"] - r["up_cnt"]
            } for r in trend_rows]

            # 历史准确率（settle_date IS NOT NULL = 已结算）
            settled = conn.execute("""
                SELECT COUNT(*) as total, SUM(is_correct) as correct
                FROM prediction_results WHERE ai_id=? AND settle_date IS NOT NULL
            """, (ai_id,)).fetchone()

            accuracy = 0.0
            if settled and settled["total"] and settled["total"] > 0:
                accuracy = round(settled["correct"] / settled["total"] * 100, 1)

            return {"data": {
                "ai_id": ai_id,
                "total_votes": total_votes,
                "up_votes": up_count,
                "down_votes": down_count,
                "up_pct": round(up_count / total_votes * 100, 1) if total_votes > 0 else 0,
                "down_pct": round(down_count / total_votes * 100, 1) if total_votes > 0 else 0,
                "trend_7d": trend,
                "historical_accuracy": accuracy,
                "settled_count": settled["total"] if settled else 0
            }}
        except Exception as e:
            import traceback; traceback.print_exc()
            return {"error": str(e)}
        finally:
            conn.close()

    def get_user_leaderboard(self):
        """获取用户互动积分排行榜

        GET /api/competition/user-leaderboard
        Query: limit, offset
        """
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        limit = min(int(params.get("limit", ["20"])[0]) if params.get("limit") else 20, 100)
        offset = int(params.get("offset", ["0"])[0]) if params.get("offset") else 0

        conn = get_db()
        try:
            # 先同步所有人的积分
            all_users = conn.execute("SELECT DISTINCT user_id FROM user_comments UNION SELECT DISTINCT user_id FROM prediction_results").fetchall()
            for (uid,) in all_users:
                try:
                    self.compute_user_points(uid)
                except:
                    pass

            rows = conn.execute("""
                SELECT user_id, user_name, user_phone, total_score,
                       prediction_points, prediction_total, prediction_correct,
                       comment_count, like_received, streak_days, updated_at
                FROM user_interaction_points
                ORDER BY total_score DESC, updated_at ASC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()

            # 计算排名
            rank_rows = conn.execute("""
                SELECT user_id FROM user_interaction_points
                ORDER BY total_score DESC
            """).fetchall()
            rank_map = {uid: i + 1 for i, (uid,) in enumerate(rank_rows)}

            items = []
            for r in rows:
                uid = r[0]
                rank = rank_map.get(uid, offset + len(items) + 1)
                items.append({
                    "rank": rank,
                    "user_id": uid,
                    "user_name": r[1] or "匿名用户",
                    "user_phone": (r[2][-4:] if r[2] and len(r[2]) >= 4 else r[2]) if r[2] else "",
                    "total_score": r[3] or 0,
                    "prediction_points": r[4] or 0,
                    "prediction_total": r[5] or 0,
                    "prediction_correct": r[6] or 0,
                    "prediction_accuracy": round(r[6] / r[5] * 100, 1) if (r[5] or 0) > 0 else 0,
                    "comment_count": r[7] or 0,
                    "like_received": r[8] or 0,
                    "streak_days": r[9] or 0,
                    "updated_at": r[10]
                })

            total = conn.execute("SELECT COUNT(*) FROM user_interaction_points").fetchone()[0]
            return {"data": {"items": items, "total": total, "limit": limit, "offset": offset}}
        finally:
            conn.close()

    def create_competition_comment(self):
        """创建AI股神争霸评论

        POST /api/competition/comment
        Body: {user_id, user_name, user_phone, ai_id, ai_name, target_type, target_id, content, parent_id}
        """
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except:
            return {"error": "invalid JSON"}, 400

        required = ["content", "user_id", "target_type", "target_id"]
        for f in required:
            if f not in data:
                return {"error": f"missing field: {f}"}, 400

        content = data["content"].strip()
        if len(content) < 2:
            return {"error": "content too short (min 2 chars)"}, 400
        if len(content) > 500:
            return {"error": "content too long (max 500 chars)"}, 400

        user_id = str(data["user_id"])
        user_name = data.get("user_name", "")
        user_phone = data.get("user_phone", user_id if len(user_id) >= 11 else "")
        ai_id = data.get("ai_id")
        ai_name = data.get("ai_name", "")
        target_type = data.get("target_type", "general")
        target_id = str(data["target_id"])
        parent_id = data.get("parent_id")

        if target_type not in ("post", "trade", "ai", "prediction", "general"):
            return {"error": "invalid target_type"}, 400

        conn = get_db()
        try:
            cur = conn.execute("""
                INSERT INTO user_comments
                    (user_id, user_name, user_phone, ai_id, ai_name, target_type, target_id, content, parent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, user_name, user_phone, ai_id, ai_name, target_type, target_id, content, parent_id))
            comment_id = cur.lastrowid
            conn.commit()
            return {"data": {"id": comment_id, "message": "Comment created"}}, 200
        except Exception as e:
            import traceback; traceback.print_exc()
            return {"error": str(e)}, 500
        finally:
            conn.close()

    def create_comment(self):
        """创建评论

        POST /api/comments
        Body: {user_id, user_name, ai_id, ai_name, target_type, target_id, content, parent_id}
        """
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except:
            return {"error": "invalid JSON"}, 400

        required = ["content", "user_id"]
        for f in required:
            if f not in data:
                return {"error": f"missing field: {f}"}, 400

        content = data["content"].strip()
        if len(content) < 2:
            return {"error": "content too short (min 2 chars)"}, 400
        if len(content) > 500:
            return {"error": "content too long (max 500 chars)"}, 400

        user_id = str(data["user_id"])
        user_name = data.get("user_name", "")
        user_phone = data.get("user_phone", user_id if len(user_id) >= 11 else "")
        ai_id = data.get("ai_id")
        ai_name = data.get("ai_name", "")
        target_type = data.get("target_type", "general")
        target_id = data.get("target_id", "")
        parent_id = data.get("parent_id")

        if target_type not in ("post", "ai", "prediction", "general"):
            return {"error": "invalid target_type"}, 400

        conn = get_db()
        try:
            cur = conn.execute("""
                INSERT INTO user_comments
                    (user_id, user_name, user_phone, ai_id, ai_name, target_type, target_id, content, parent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, user_name, user_phone, ai_id, ai_name, target_type, target_id, content, parent_id))
            comment_id = cur.lastrowid
            conn.commit()

            # 更新 ai_posts 的回复计数
            if target_type == "post" and target_id:
                conn.execute("UPDATE ai_posts SET replies = replies + 1 WHERE post_id=?", (str(target_id),))
                conn.commit()

            conn.close()
            return {"data": {"success": True, "id": comment_id, "message": "评论已发布"}}
        except Exception as e:
            conn.close()
            import traceback; traceback.print_exc()
            return {"error": str(e)}, 500

    def like_comment(self, id):
        """点赞评论

        GET /api/comments/{id}/like
        """
        conn = get_db()
        try:
            row = conn.execute("SELECT id, likes FROM user_comments WHERE id=?", (int(id),)).fetchone()
            if not row:
                conn.close()
                return {"error": "comment not found"}, 404

            new_likes = (row[1] or 0) + 1
            conn.execute("UPDATE user_comments SET likes=? WHERE id=?", (new_likes, int(id)))
            conn.commit()
            conn.close()
            return {"data": {"success": True, "id": int(id), "likes": new_likes}}
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

        # 特殊处理POST /api/competition/comment
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "competition" and parts[2] == "comment":
            result = self.create_competition_comment()
            if isinstance(result, tuple):
                data, status = result[0], result[1]
            else:
                data, status = result, 200
            self.send_json(data, status)
            return

        # 特殊处理POST /api/competition/interaction/calc
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "competition" and parts[2] == "interaction" and parts[3] == "calc":
            result = self.calc_interaction_score()
            if isinstance(result, tuple):
                data, status = result[0], result[1]
            else:
                data, status = result, 200
            self.send_json(data, status)
            return

        # 特殊处理POST /api/competition/comments/like
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "competition" and parts[2] == "comments" and parts[3] == "like":
            # POST /api/competition/comments/like {id}
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            try:
                data = json.loads(body)
                cid = int(data.get("id", 0))
                if cid <= 0:
                    self.send_json({"error": "missing comment id"}, 400)
                    return
                conn = get_db()
                try:
                    row = conn.execute("SELECT id, likes FROM user_comments WHERE id=?", (cid,)).fetchone()
                    if not row:
                        self.send_json({"error": "comment not found"}, 404)
                        return
                    new_likes = (row[1] or 0) + 1
                    conn.execute("UPDATE user_comments SET likes=? WHERE id=?", (new_likes, cid))
                    conn.commit()
                    self.send_json({"data": {"success": True, "id": cid, "likes": new_likes}})
                finally:
                    conn.close()
            except Exception as e:
                self.send_json({"error": str(e)}, 400)
            return

        # 特殊处理POST /api/comments
        if len(parts) >= 2 and parts[0] == "api" and parts[1] == "comments":
            if len(parts) == 2:
                result = self.create_comment()
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
