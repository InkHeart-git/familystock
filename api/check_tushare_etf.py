#!/usr/bin/env python3
"""
检查Tushare返回的数据，确认ETF是否真的在列表中
"""

import tushare as ts
import pandas as pd

# Tushare Pro配置
ts.set_token('f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735')
pro = ts.pro_api()

# 获取上交所数据
print("获取上交所数据...")
df = pro.stock_basic(exchange='SSE', list_status='L')
print(f"总条数: {len(df)}")
print(f"列名: {list(df.columns)}")
print("\n前10条数据:")
print(df.head(10)[['ts_code', 'symbol', 'name', 'list_date']])

# 搜索包含ETF的
print("\n搜索包含ETF的...")
etf_df = df[df['name'].str.contains('ETF', na=False, case=False)]
print(f"找到 {len(etf_df)} 只ETF")
if len(etf_df) > 0:
    print(etf_df[['ts_code', 'symbol', 'name']].head(10))

# 搜索包含LOF的
print("\n搜索包含LOF的...")
lof_df = df[df['name'].str.contains('LOF', na=False, case=False)]
print(f"找到 {len(lof_df)} 只LOF")

# 搜索包含债券的
print("\n搜索包含'债'的...")
bond_df = df[df['name'].str.contains('债', na=False)]
print(f"找到 {len(bond_df)} 只债券相关")
