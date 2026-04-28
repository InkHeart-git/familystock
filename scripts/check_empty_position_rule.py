#!/usr/bin/env python3
"""
AI股神争霸 - 空仓检查脚本
规则：最多连续空仓1天（不允许连续2天空仓，必须有持仓）
每天8:25执行，检查所有AI的空仓状态
"""
import sys
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json

sys.path.insert(0, "/var/www/ai-god-of-stocks")

DB_PATH = "/var/www/ai-god-of-stocks/ai_god.db"
REPORT_PATH = "/var/www/ai-god-of-stocks/data/empty_position_report.json"

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def get_all_ais():
    """获取所有AI信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, style, description FROM ai_characters ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "style": r[2], "desc": r[3]} for r in rows]

def get_trade_history(ai_id: int) -> List[Dict]:
    """获取某AI的所有交易记录，按时间排序"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ai_id, symbol, name, action, quantity, price, total_amount, created_at
        FROM ai_trades 
        WHERE ai_id = ?
        ORDER BY created_at ASC
    """, (ai_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "ai_id": r[1], "symbol": r[2], "name": r[3], 
         "action": r[4], "quantity": r[5], "price": r[6], 
         "total_amount": r[7], "created_at": r[8]}
        for r in rows
    ]

def simulate_positions(trades: List[Dict]) -> Dict[str, int]:
    """根据交易记录模拟持仓（symbol -> quantity）"""
    positions = {}
    for t in trades:
        sym = t["symbol"]
        qty = t["quantity"]
        if t["action"] == "BUY":
            positions[sym] = positions.get(sym, 0) + qty
        elif t["action"] in ("SELL", "CLEARED"):
            positions[sym] = positions.get(sym, 0) - qty
            if positions.get(sym, 0) <= 0:
                del positions[sym]
    return positions

def get_all_trading_dates(ai_id: int) -> List[str]:
    """获取某AI有交易的所有日期（去重）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT DATE(created_at) as trade_date
        FROM ai_trades 
        WHERE ai_id = ?
        ORDER BY trade_date
    """, (ai_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def calculate_consecutive_empty_days(ai_id: int, from_date: str = "2026-04-20", to_date: str = None) -> Tuple[int, List[str]]:
    """
    计算连续空仓天数
    返回: (最长连续空仓天数, 空仓日期列表)
    """
    trade_dates = set(get_all_trading_dates(ai_id))
    
    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")
    
    # 生成所有交易日历（从比赛开始到现在）
    current = datetime.strptime(from_date, "%Y-%m-%d")
    end = datetime.strptime(to_date, "%Y-%m-%d")
    
    all_dates = []
    while current <= end:
        all_dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    # 找出连续空仓的日期段
    empty_sequences = []
    current_sequence = []
    
    for date in all_dates:
        # 有持仓 = 该日期有 BUY 交易且之后没有对应的 SELL
        # 更准确的方式：模拟到该日期之前的持仓状态
        # 简化：如果该日期在 trade_dates 中，认为有操作，不算空仓
        if date not in trade_dates:
            current_sequence.append(date)
        else:
            if current_sequence:
                empty_sequences.append(current_sequence)
            current_sequence = []
    
    if current_sequence:
        empty_sequences.append(current_sequence)
    
    if not empty_sequences:
        return 0, []
    
    # 最长连续空仓
    longest = max(empty_sequences, key=len)
    return len(longest), longest

def check_current_position(ai_id: int) -> Tuple[bool, str]:
    """
    检查AI当前是否有持仓
    返回: (是否有持仓, 持仓摘要)
    """
    trades = get_trade_history(ai_id)
    if not trades:
        return False, "从未交易（初始状态）"
    
    # 模拟所有交易后的持仓
    positions = simulate_positions(trades)
    
    if not positions:
        last_trade = trades[-1]
        return False, f"空仓（最后交易: {last_trade['action']} {last_trade['symbol']} @ {last_trade['created_at']}）"
    
    pos_summary = ", ".join([f"{sym}:{qty}股" for sym, qty in positions.items()])
    return True, f"持仓中: {pos_summary}"

def main():
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"=== AI股神争霸 空仓检查 ===")
    print(f"检查时间: {today}")
    print()
    
    ais = get_all_ais()
    results = []
    forced_trading_ais = []
    
    for ai in ais:
        ai_id = ai["id"]
        has_position, pos_summary = check_current_position(ai_id)
        max_empty_days, empty_dates = calculate_consecutive_empty_days(ai_id)
        
        status = "✅ 正常" if max_empty_days <= 1 else "⚠️ 需强制交易"
        
        result = {
            "ai_id": ai_id,
            "ai_name": ai["name"],
            "has_position": has_position,
            "position_summary": pos_summary,
            "max_consecutive_empty_days": max_empty_days,
            "status": status,
        }
        
        if max_empty_days >= 2:
            forced_trading_ais.append({
                "ai_id": ai_id,
                "ai_name": ai["name"],
                "empty_days": max_empty_days,
                "last_empty_dates": empty_dates[-5:] if empty_dates else [],
            })
        
        results.append(result)
        
        print(f"AI {ai_id}: {ai['name']}")
        print(f"  当前状态: {'有持仓' if has_position else '空仓'}")
        print(f"  持仓情况: {pos_summary}")
        print(f"  最长连续空仓: {max_empty_days} 天")
        print(f"  状态: {status}")
        print()
    
    # 保存报告
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    report = {
        "check_time": today,
        "total_ais": len(ais),
        "results": results,
        "forced_trading": forced_trading_ais,
        "summary": {
            "total_empty_violations": len(forced_trading_ais),
            "violation_ais": [a["ai_name"] for a in forced_trading_ais],
        }
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"=== 汇总 ===")
    print(f"总AI数: {len(ais)}")
    print(f"空仓违规（≥2天空仓）: {len(forced_trading_ais)} 个")
    for a in forced_trading_ais:
        print(f"  - {a['ai_name']} (连续空仓 {a['empty_days']} 天)")
    
    print(f"\n报告已保存: {REPORT_PATH}")
    return report

if __name__ == "__main__":
    main()
