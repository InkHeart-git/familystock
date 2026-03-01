#!/bin/bash
# NAS 部署脚本 - deploy-to-nas.sh

set -e

NAS_IP="${1:-你的NASIP}"
NAS_USER="${2:-root}"
REMOTE_PATH="/volume1/docker/familystock"

echo "🚀 部署 FamilyStock 到绿联 NAS..."
echo "NAS地址: $NAS_IP"
echo "远程路径: $REMOTE_PATH"

# 1. 在NAS上创建目录
echo "📁 创建远程目录..."
ssh $NAS_USER@$NAS_IP "mkdir -p $REMOTE_PATH"

# 2. 传输项目文件（排除node_modules和.git）
echo "📦 传输项目文件..."
rsync -avz --exclude='node_modules' --exclude='.git' --exclude='data' \
  ./ $NAS_USER@$NAS_IP:$REMOTE_PATH/

# 3. 创建环境变量文件（如果不存在）
echo "⚙️  检查环境配置..."
ssh $NAS_USER@$NAS_IP "cd $REMOTE_PATH && [ ! -f .env ] && cp .env.example .env && echo '请编辑 .env 文件配置API密钥' || echo '.env 已存在'"

# 4. 创建数据目录
echo "💾 创建数据目录..."
ssh $NAS_USER@$NAS_IP "mkdir -p $REMOTE_PATH/data/postgres $REMOTE_PATH/data/redis $REMOTE_PATH/data/uploads"

# 5. 启动服务
echo "🐳 启动Docker服务..."
ssh $NAS_USER@$NAS_IP "cd $REMOTE_PATH && docker-compose -f docker-compose.nas.yml up -d"

# 6. 检查状态
echo "🔍 检查服务状态..."
sleep 5
ssh $NAS_USER@$NAS_IP "cd $REMOTE_PATH && docker-compose -f docker-compose.nas.yml ps"

echo ""
echo "✅ 部署完成！"
echo "本地访问: http://$NAS_IP:3000"
echo "API地址: http://$NAS_IP:5000/api"
echo ""
echo "查看日志: ssh $NAS_USER@$NAS_IP 'cd $REMOTE_PATH && docker-compose logs -f'"
