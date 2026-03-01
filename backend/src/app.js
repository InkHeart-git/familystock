const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const morgan = require('morgan');
const dotenv = require('dotenv');

dotenv.config();

const authRoutes = require('./routes/auth');
const stockRoutes = require('./routes/stocks');
const watchlistRoutes = require('./routes/watchlist');
const analysisRoutes = require('./routes/analysis');
const familyRoutes = require('./routes/family');
const { errorHandler } = require('./middleware/errorHandler');
const { auth } = require('./middleware/auth');

const app = express();

// 安全中间件
app.use(helmet());
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:3000',
  credentials: true
}));

// 速率限制
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15分钟
  max: 100 // 每个IP限制100个请求
});
app.use('/api/', limiter);

// 日志
app.use(morgan('combined'));

// 解析JSON
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// 健康检查
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// API路由
app.use('/api/auth', authRoutes);
app.use('/api/stocks', stockRoutes);
app.use('/api/watchlist', auth, watchlistRoutes);
app.use('/api/analysis', auth, analysisRoutes);
app.use('/api/family', auth, familyRoutes);

// API文档
app.get('/api/docs', (req, res) => {
  res.json({
    name: 'FamilyStock API',
    version: '1.0.0',
    endpoints: {
      auth: {
        'POST /api/auth/register': '用户注册',
        'POST /api/auth/login': '用户登录',
        'POST /api/auth/logout': '用户登出',
        'GET /api/auth/me': '获取当前用户信息'
      },
      stocks: {
        'GET /api/stocks/search?q={query}': '搜索股票',
        'GET /api/stocks/:symbol': '获取股票详情',
        'GET /api/stocks/:symbol/quote': '获取实时行情',
        'GET /api/stocks/:symbol/history': '获取历史数据'
      },
      watchlist: {
        'GET /api/watchlist': '获取自选股列表',
        'POST /api/watchlist': '添加自选股',
        'DELETE /api/watchlist/:symbol': '删除自选股'
      },
      analysis: {
        'POST /api/analysis/filter': 'AI股票筛选',
        'POST /api/analysis/report': '财报解读',
        'POST /api/analysis/news': '新闻分析'
      },
      family: {
        'GET /api/family': '获取家庭组信息',
        'GET /api/family/members': '获取家庭成员',
        'POST /api/family/invite': '邀请成员',
        'GET /api/family/watchlist': '获取家庭共享自选池'
      }
    }
  });
});

// 错误处理
app.use(errorHandler);

// 404处理
app.use((req, res) => {
  res.status(404).json({ error: 'Not Found', path: req.path });
});

module.exports = app;
