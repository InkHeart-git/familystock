import re

# Read file
with open("tushare.py", "r") as f:
    lines = f.readlines()

# Delete old function (lines 161-227, 0-indexed: 160-227)
new_lines = lines[:161] + lines[228:]

# New function
new_func = '''@router_tushare.get("/index")
async def get_index_quotes():
    """Get index quotes from index_quotes table"""
    try:
        import sqlite3
        
        indices = [
            {"ts_code": "000001.SH", "name": "上证指数"},
            {"ts_code": "399001.SZ", "name": "深证成指"},
            {"ts_code": "399006.SZ", "name": "创业板指"},
        ]
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        results = []
        for idx in indices:
            cursor.execute("SELECT * FROM index_quotes WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 1", (idx["ts_code"],))
            row = cursor.fetchone()
            
            if row and row["close"]:
                results.append({
                    "name": idx["name"],
                    "ts_code": idx["ts_code"],
                    "close": float(row["close"]),
                    "pct_chg": float(row["pct_chg"] or 0),
                    "source": "local_db"
                })
            else:
                results.append({
                    "name": idx["name"],
                    "ts_code": idx["ts_code"],
                    "close": 0,
                    "pct_chg": 0,
                    "source": "unavailable"
                })
        
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

'''

new_lines.insert(161, new_func)

with open("tushare.py", "w") as f:
    f.writelines(new_lines)

print("Done")
