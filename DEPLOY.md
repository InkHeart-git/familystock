# FamilyStock 部署指南

## 🚀 快速开始

### 1. 复制项目到绿联NAS

```bash
# 在Windows PowerShell中运行
$NAS_IP = "你的NASIP"
scp -r C:\Users\Administrator\.openclaw\workspace\projects\FamilyStock\* root@${NAS_IP}:/volume1/docker/familystock/
```

### 2. SSH到NAS启动服务

```bash
ssh root@你的NASIP
cd /volume1/docker/familystock

# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件配置API密钥
vi .env
```

### 3. 配置 .env 文件

```bash
# 数据库配置
DB_USER=familystock
DB_PASSWORD=你的强密码
DB_NAME=familystock

# JWT密钥
JWT_SECRET=随机长字符串

# API密钥（用于AI分析和股票数据）
OPENAI_API_KEY=sk-xxx
ALPHA_VANTAGE_API_KEY=xxx
TUSHARE_TOKEN=xxx
```

### 4. 启动服务

```bash
# 创建数据目录
mkdir -p data/postgres data/redis data/uploads

# 启动所有服务
docker-compose -f docker-compose.nas.yml up -d

# 查看日志
docker-compose -f docker-compose.nas.yml logs -f
```

### 5. 验证部署

```bash
# 检查容器状态
docker-compose -f docker-compose.nas.yml ps

# 测试API
curl http://localhost:5000/health
```

---

## 🌐 外网访问配置

见 `docs/EXTERNAL_ACCESS.md`

**推荐方案：Cloudflare Tunnel**

1. 访问 https://one.dash.cloudflare.com
2. 创建 Tunnel，获取 token
3. 在 `.env` 中添加：`CF_TUNNEL_TOKEN=你的token`
4. 启动 tunnel 容器

---

## 📁 项目结构

```
familystock/
├── docker-compose.nas.yml    # NAS专用配置
├── .env                      # 环境变量（需创建）
├── data/                     # 数据持久化
│   ├── postgres/
│   ├── redis/
│   └── uploads/
├── backend/                  # Node.js后端
├── frontend/                 # React前端
└── docs/                     # 文档
```

---

## 🔧 常用命令

```bash
# 查看日志
docker-compose -f docker-compose.nas.yml logs -f backend
docker-compose -f docker-compose.nas.yml logs -f frontend

# 重启服务
docker-compose -f docker-compose.nas.yml restart

# 停止服务
docker-compose -f docker-compose.nas.yml down

# 完全删除（包括数据！）
docker-compose -f docker-compose.nas.yml down -v

# 更新镜像
docker-compose -f docker-compose.nas.yml pull
docker-compose -f docker-compose.nas.yml up -d
```

---

## 🛡️ 安全建议

1. **修改默认密码**：`DB_PASSWORD` 和 `JWT_SECRET`
2. **使用HTTPS**：配置 Cloudflare Tunnel 或 Nginx SSL
3. **限制访问**：如可能，限制特定IP访问
4. **定期备份**：
   ```bash
   # 备份数据库
   docker exec familystock-db pg_dump -U familystock familystock > backup.sql
   ```

---

## 📱 访问地址

| 服务 | 内网地址 | 外网地址（配置后） |
|------|----------|-------------------|
| 前端 | http://NAS_IP:3000 | https://familystock.你的域名.com |
| API | http://NAS_IP:5000 | https://familystock.你的域名.com/api |
