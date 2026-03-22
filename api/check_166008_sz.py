#!/usr/bin/env python3
"""
查询 166008.SZ 是否存在于 stock_basic
"""

import tushare as ts
import pandas as pd

# Tushare Pro配置
ts.set_token('f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735')
pro = ts.pro_api()

# 深交所查询
print("查询深交所上市证券...")
df = pro.stock_basic(exchange='SZSE', list_status='L')
print(f"深交所总共 {len(df)} 只")

# 搜索166008
result = df[df['symbol'] == '166008']
print(f"\n找到 symbol=166008: {len(result)} 条")
if len(result) > 0:
    print(result)

# 搜索名称包含中欧强债
result = df[df['name'].str.contains('中欧强债', na=False)]
print(f"\n找到名称包含'中欧强债': {len(result)} 条")
if len(result) > 0:
    print(result)

# 搜索代码开头166
result = df[df['symbol'].str.startswith('166', na=False)]
print(f"\n找到symbol开头 166: {len(result)} 条")
print(result[['symbol', 'name', 'ts_code']].head(20))
