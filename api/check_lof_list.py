#!/usr/bin/env python3
"""
检查LOF列表，看看166008是否存在
"""

import tushare as ts
import mysql.connector

# Tushare Pro配置
ts.set_token('f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735')
pro = ts.pro_api()

# 获取LOF
print("获取LOF列表...")
df = pro.fund_basic(exchange='', list_status='L', fund_type='LOF')
print(f"总共有 {len(df)} 只LOF")

# 搜索代码包含166
print("\n搜索代码 166xxx:")
result = df[df['ts_code'].str.startswith('166', na=False)]
print(f"找到 {len(result)} 只:")
print(result[['ts_code', 'name', 'fund_type', 'market']])

# 搜索名称包含"中欧"
print("\n搜索名称包含 '中欧':")
result = df[df['name'].str.contains('中欧', na=False)]
print(f"找到 {len(result)} 只:")
print(result[['ts_code', 'name', 'fund_type', 'market']])
