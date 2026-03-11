#!/bin/bash
# FamilyStock AI推演预警系统启动脚本
# 参考贝莱德阿拉丁系统设计

echo "======================================"
echo "FamilyStock AI推演预警系统 V3"
echo "参考贝莱德阿拉丁(Aladdin)系统设计"
echo "======================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3"
    exit 1
fi

# 安装依赖
echo "[1/4] 检查依赖..."
pip3 install -q flask flask-cors requests loguru jieba snownlp numpy 2>/dev/null || true

# 创建日志目录
mkdir -p /var/www/familystock/api/logs

# 启动API服务器
echo "[2/4] 启动API服务器..."
cd /var/www/familystock/api

# 停止已有的服务
pkill -f "server_v3.py" 2>/dev/null || true
sleep 1

# 启动新服务
nohup python3 server_v3.py > /var/www/familystock/api/logs/server.log 2>&1 &

# 等待服务启动
sleep 3

# 检查服务状态
if curl -s http://localhost:8080/ > /dev/null; then
    echo "[3/4] API服务器启动成功!"
    echo "  - API地址: http://localhost:8080"
    echo "  - 文档: http://localhost:8080/"
else
    echo "[3/4] 警告: API服务器可能未正常启动"
    echo "  请检查日志: /var/www/familystock/api/logs/server.log"
fi

# 显示状态
echo "[4/4] 系统状态:"
echo "  - 前端页面: /var/www/familystock/index_v3.html"
echo "  - API服务: http://localhost:8080"
echo "  - 日志目录: /var/www/familystock/api/logs/"
echo ""
echo "API端点:"
echo "  - GET  /api/v3/dashboard       风险仪表盘"
echo "  - GET  /api/v3/alerts/active   活跃预警"
echo "  - GET  /api/v3/pipeline/status 流水线状态"
echo "  - POST /api/v3/pipeline/run    手动触发流水线"
echo ""
echo "系统已启动，流水线将每5分钟自动运行一次"
echo "======================================"
