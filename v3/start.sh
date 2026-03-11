#!/bin/bash
# FamilyStock V3 启动脚本

echo "=============================================="
echo "FamilyStock AI推演预警系统 V3"
echo "=============================================="

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误: Python3 未安装"
    exit 1
fi

# 安装依赖
echo "正在检查依赖..."
pip3 install flask flask-cors loguru -q

# 创建日志目录
mkdir -p /var/www/familystock/v3/logs

# 启动API服务器
echo ""
echo "启动 API 服务器..."
echo "访问地址: http://43.160.193.165:8080"
echo ""

cd /var/www/familystock/v3
python3 server_v3.py