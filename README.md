# FamilyStock - 家庭智能选股平台

🏠 为家庭打造的AI驱动股票投资分析平台

## 功能特性

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

### AI与数据
- **大模型**: Kimi API / OpenAI / Claude
- **数据源**: AkShare / Tushare

### 部署
- **容器化**: Docker + Docker Compose
- **反向代理**: Nginx

## 项目结构

```
FamilyStock/
├── frontend/          # React前端应用
│   ├── src/
│   │   ├── components/   # 可复用组件
│   │   ├── pages/        # 页面组件
│   │   ├── services/     # API服务
│   │   ├── store/        # 状态管理
│   │   └── utils/        # 工具函数
│   └── package.json
├── backend/           # Node.js后端服务
│   ├── src/
│   │   ├── routes/       # 路由定义
│   │   ├── controllers/  # 控制器
│   │   ├── models/       # 数据模型
│   │   ├── services/     # 业务逻辑
│   │   └── utils/        # 工具函数
│   └── package.json
├── database/          # 数据库迁移
├── docker/            # Docker配置
├── docs/              # 项目文档
└── nginx/             # Nginx配置
```

## 快速开始

### 环境要求
- Docker 24.x
- Docker Compose 2.x
- Node.js 20+ (本地开发)

### Docker部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/InkHeart-git/familystock.git
cd familystock

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件配置你的API密钥

# 3. 启动所有服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f
```

访问地址：
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

## 核心功能

### 1. 用户系统
- 用户注册/登录
- JWT认证
- 家庭组成员管理
- 权限控制

### 2. 股票数据
- 实时行情获取
- 历史数据查询
- 股票搜索
- 数据可视化

### 3. AI分析
- 智能股票筛选
- 财报解读
- 新闻情感分析
- 投资建议生成

### 4. 自选股管理
- 个人自选列表
- 家庭共享池
- 分组管理
- 价格提醒

## 开发计划

| 周次 | 任务 | 状态 |
|------|------|------|
| 第1周 | 环境搭建、数据库设计 | ✅ 已完成 |
| 第2周 | 数据接口对接 | 🚧 进行中 |
| 第3周 | 前端基础页面 | ⏳ 待开始 |
| 第4周 | 股票筛选器 | ⏳ 待开始 |
| 第5周 | AI分析功能 | ⏳ 待开始 |
| 第6周 | 测试优化 | ⏳ 待开始 |

## 文档

- [API文档](docs/API.md)
- [架构设计](docs/ARCHITECTURE.md)
- [部署指南](DEPLOY.md)

## 许可证

MIT License

---

*项目启动时间：2026-03-01*  
*当前版本：v1.0.0-dev*
