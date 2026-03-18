#!/bin/bash
# 定时同步脚本
# 每小时执行一次

cd /var/www/familystock/api

# 同步Tushare Pro股票基础数据
python3 sync_tushare_pro.py >> /var/log/familystock/sync_stock.log 2>&1

# 同步新闻（每分钟只能调用1次Tushare新闻接口）
python3 -c "
import tushare as ts
import time
ts.set_token('f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735')
pro = ts.pro_api()
try:
    df = pro.news(limit=100)
    print(f'获取到{len(df)}条新闻')
except Exception as e:
    print(f'获取新闻失败: {e}')
" >> /var/log/familystock/sync_news.log 2>&1

echo "[$(date)] 同步完成" >> /var/log/familystock/cron.log
