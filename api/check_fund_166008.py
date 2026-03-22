#!/usr/bin/env python3
"""
检查中欧强债 (166008) 的基本信息
"""

import tushare as ts
import mysql.connector

# Tushare Pro配置
ts.set_token('f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735')
pro = ts.pro_api()

# 查询这只基金
print("查询 166008...")
df = pro.fund_basic(ts_code='', name='中欧强债')
print(df)

print("\n--- 查询所有包含 166008 的...")
df_all = pro.fund_basic()
df_166008 = df_all[df_all['ts_code'].str.contains('166008', na=False)]
print(df_166008)
