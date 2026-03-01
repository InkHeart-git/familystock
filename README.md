# FamilyStock - 家庭AI选股系统

> 🏠 为家庭打造的智能股票投资分析平台

## 项目简介

FamilyStock 是一个面向家庭用户的AI驱动股票分析平台，帮助家庭成员：
- 📊 AI智能股票筛选和分析
- 📰 财报/新闻AI深度解读  
- 👨‍👩‍👧‍👦 家庭共享自选股池
- 📈 实时行情数据追踪

## 技术栈

### 前端
- **框架**: React 18 + Vite
- **样式**: Tailwind CSS
- **状态管理**: Zustand
- **图表**: Recharts
- **HTTP客户端**: Axios

### 后端
- **运行时**: Node.js 20
- **框架**: Express.js
- **数据库**: PostgreSQL 16
- **缓存**: Redis
- **ORM**: Prisma

### AI服务
- **大模型**: OpenAI GPT-4 / Claude / 国内大模型API
- **向量数据库**: Pinecone (可选)

### 部署
- **容器化**: Docker + Docker Compose
- **反向代理**: Nginx
- **监控**: Prometheus + Grafana (可选)

## 快速开始

### 环境要求
- Docker 24.x
- Docker Compose 2.x
- Node.js 20+ (本地开发)

### 启动服务

```bash
# 1. 克隆项目
cd projects/FamilyStock

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件配置你的API密钥

# 3. 启动所有服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f
```

服务启动后访问：
- 前端: http://localhost:3000
- 后端API: http://localhost:5000/api
- API文档: http://localhost:5000/api/docs

### 本地开发

```bash
# 后端开发
cd backend
npm install
npm run dev

# 前端开发 (新终端)
cd frontend
npm install
npm run dev
```

## 项目结构

```
FamilyStock/
├── frontend/           # React前端应用
│   ├── src/
│   │   ├── components/ # 可复用组件
│   │   ├── pages/      # 页面组件
│   │   ├── services/   # API服务
│   │   ├── store/      # 状态管理
│   │   └── utils/      # 工具函数
│   └── public/
├── backend/            # Node.js后端服务
│   ├── src/
│   │   ├── routes/     # 路由定义
│   │   ├── controllers/# 控制器
│   │   ├── models/     # 数据模型
│   │   ├── services/   # 业务逻辑
│   │   ├── middleware/ # 中间件
│   │   └── utils/      # 工具函数
│   └── tests/
├── database/           # 数据库迁移和种子
│   └── migrations/
├── docs/              # 项目文档
├── nginx/             # Nginx配置
└── docker-compose.yml # Docker编排
```

## 功能模块

### 1. 用户系统
- [x] 用户注册/登录
- [x] JWT认证
- [x] 家庭组成员管理
- [x] 权限控制

### 2. 股票数据
- [x] 实时行情获取
- [x] 历史数据查询
- [x] 股票搜索
- [x] 数据可视化

### 3. AI分析
- [x] 智能股票筛选
- [x] 财报解读
- [x] 新闻情感分析
- [x] 投资建议生成

### 4. 自选股池
- [x] 个人自选列表
- [x] 家庭共享池
- [x] 分组管理
- [x] 价格提醒

## API文档

详见 [docs/API.md](./docs/API.md)

## 数据库设计

详见 [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md#数据库设计)

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 许可证

MIT License - 详见 [LICENSE](./LICENSE)

## 更新日志

详见 [CHANGELOG.md](./CHANGELOG.md)
