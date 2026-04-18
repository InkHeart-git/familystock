"""
QVeris 实时行情模块
用于替代 akshare / family_stock.db 的陈旧数据源
数据来源: 同花顺 iFinD Level-2 (QVeris 89%成功率)
"""

import os
import json
import sqlite3
import httpx
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "ai_god.db")
LOG_PATH = os.path.join(BASE_DIR, "..", "logs", "qveris_price.log")

# QVeris API 配置
QVERIS_BASE = "https://qveris.ai/api/v1"
SEARCH_ID = "b3d4a11d-f156-43d6-90ce-2fdb0b86521a"
TOOL_ID = "ths_ifind.real_time_quotation.v1"


def get_qveris_key() -> str:
    """读取 QVeris API Key"""
    with open("/etc/environment") as f:
        for line in f:
            if "QVERIS_API_KEY" in line:
                return line.split("=")[1].strip().strip('"')
    raise ValueError("QVERIS_API_KEY not found in /etc/environment")


def get_db_path() -> str:
    return os.path.join(os.path.dirname(BASE_DIR), "ai_god.db")


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def ts_code(symbol: str) -> str:
    """给股票代码加上 SH/SZ/BJ 后缀"""
    symbol = symbol.strip()
    if "." in symbol:
        return symbol
    if symbol.startswith(("6", "5", "9", "7", "8")):
        return f"{symbol}.SH"
    if symbol.startswith(("0", "3", "2")):
        return f"{symbol}.SZ"
    if symbol.startswith(("4", "8")):
        return f"{symbol}.BJ"
    return f"{symbol}.SH"


def ts_code_to_symbol(ts: str) -> str:
    """把 300750.SH → 300750"""
    return ts.split(".")[0]


async def fetch_realtime_prices(symbols: List[str]) -> Dict[str, dict]:
    """
    通过 QVeris 实时行情 API 获取多个股票的实时价格
    返回: { "300750": { "price": 443.03, "change_pct": -2.41, "volume": ... }, ... }
    """
    key = get_qveris_key()
    codes = ",".join(ts_code(s) for s in symbols)

    log(f"QVeris 请求 ({len(symbols)} 只股票): {codes[:80]}...")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{QVERIS_BASE}/tools/execute",
            params={"tool_id": TOOL_ID},
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "search_id": SEARCH_ID,
                "parameters": {"codes": codes},
                "max_response_size": 81920,
            },
        )

    data = resp.json()
    if not data.get("success"):
        log(f"QVeris 请求失败: {data.get('error_message', 'unknown')}")
        return {}

    raw = data.get("result", {})
    status = raw.get("status_code")
    if status != 200:
        log(f"QVeris 行情返回错误: status={status}")
        return {}

    # data 格式: [[[{stock_info}]], [[{stock_info}]], ...]
    results = {}
    stock_data_list = raw.get("data", [])
    for stock_arr in stock_data_list:
        if not stock_arr:
            continue
        # stock_arr 是 [[{...}]] 或 [{...}]
        inner = stock_arr[0] if stock_arr else {}
        if isinstance(inner, list):
            inner = inner[0] if inner else {}
        if not isinstance(inner, dict):
            continue

        thscode = inner.get("thscode", "")
        symbol = ts_code_to_symbol(thscode)
        results[symbol] = {
            "name": inner.get("name", ""),
            "price": inner.get("latest_price") or inner.get("latest") or inner.get("close"),
            "open": inner.get("open"),
            "high": inner.get("high"),
            "low": inner.get("low"),
            "pre_close": inner.get("preClose"),
            "change": inner.get("change"),
            "change_pct": inner.get("changeRatio"),
            "volume": inner.get("volume"),
            "amount": inner.get("amount"),
            "trade_status": inner.get("tradeStatus", ""),
            "trade_time": inner.get("tradeTime", "") or inner.get("time", ""),
        }
        log(f"  {symbol}: ¥{results[symbol]['price']} ({results[symbol]['change_pct']:+.2f}%)")

    return results


async def update_holdings_prices() -> int:
    """
    更新 ai_holdings 表中所有持仓的 current_price
    返回: 更新了多少只股票
    """
    db = get_db_path()

    # 读取所有有持仓的股票
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT symbol FROM ai_holdings WHERE quantity > 0")
    symbols = [row[0] for row in cur.fetchall()]
    conn.close()

    if not symbols:
        log("无持仓，跳过价格更新")
        return 0

    log(f"开始更新 {len(symbols)} 只持仓股票...")
    prices = await fetch_realtime_prices(symbols)

    if not prices:
        log("未能获取任何价格数据")
        return 0

    # 更新数据库
    updated = 0
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for symbol, info in prices.items():
        price = info.get("price")
        if price is None:
            continue
        cur.execute(
            "UPDATE ai_holdings SET current_price=?, updated_at=? WHERE symbol=? AND quantity > 0",
            (price, now, symbol),
        )
        updated += cur.rowcount

    conn.commit()
    conn.close()
    log(f"价格更新完成: {updated} 只股票")
    return updated


async def update_portfolio_values() -> int:
    """
    重新计算每个 AI 的总持仓市值并更新 ai_portfolios.total_value
    返回: 更新了多少个账户
    """
    db = get_db_path()
    conn = sqlite3.connect(db)
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT ai_id FROM ai_holdings")
    ai_ids = [row[0] for row in cur.fetchall()]

    updated = 0
    for ai_id in ai_ids:
        cur.execute(
            "SELECT COALESCE(cash, 1000000.0) FROM ai_portfolios WHERE ai_id=? ORDER BY updated_at DESC LIMIT 1",
            (ai_id,),
        )
        row = cur.fetchone()
        cash = row[0] if row else 1000000.0

        cur.execute(
            "SELECT COALESCE(SUM(quantity * current_price), 0) FROM ai_holdings WHERE ai_id=? AND quantity > 0",
            (ai_id,),
        )
        holdings_value = cur.fetchone()[0] or 0.0
        total_value = cash + holdings_value

        cur.execute(
            "UPDATE ai_portfolios SET total_value=?, updated_at=? WHERE ai_id=?",
            (total_value, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ai_id),
        )
        if cur.rowcount > 0:
            updated += 1

    conn.commit()
    conn.close()
    log(f"账户价值更新完成: {updated} 个账户")
    return updated


async def full_refresh() -> dict:
    """
    完整刷新: 获取实时价格 → 更新持仓 → 重算账户
    返回统计信息
    """
    t0 = datetime.now()
    stocks = await update_holdings_prices()
    portfolios = await update_portfolio_values()
    elapsed = (datetime.now() - t0).total_seconds()
    log(f"完整刷新完成 ({elapsed:.1f}s): {stocks}只股票, {portfolios}个账户")
    return {"stocks": stocks, "portfolios": portfolios, "elapsed_s": elapsed}


# 同步包装器 (供 cron / PM Brain 调用)
def sync_full_refresh():
    return asyncio.run(full_refresh())


if __name__ == "__main__":
    result = sync_full_refresh()
    print(json.dumps(result, indent=2, ensure_ascii=False))
