#!/bin/bash
# 重启API服务脚本

cd /var/www/familystock/api

# 停止现有服务
pkill -f 'uvicorn.*8006' 2>/dev/null
sleep 3

# 清除缓存
rm -rf app/__pycache__ app/routers/__pycache__

# 启动新服务
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8006 --workers 2 > logs/api.log 2>&1 &

sleep 2
echo "API服务已重启"
echo "测试: curl http://localhost:8006/api/portfolio/holdings"
