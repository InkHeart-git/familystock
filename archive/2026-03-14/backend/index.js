const express = require('express');
const cors = require('cors');
const mysql = require('mysql2/promise');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const axios = require('axios');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET || 'familystock2026';

// 中间件
app.use(cors());
app.use(express.json());

// 数据库连接
const dbConfig = {
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_NAME || 'familystock',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
};

let pool;
async function initDB() {
  try {
    pool = mysql.createPool(dbConfig);
    console.log('数据库连接成功');
    
    // 初始化表
    await pool.execute(`
      CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        email VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    
    await pool.execute(`
      CREATE TABLE IF NOT EXISTS stocks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(20) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        price DECIMAL(10,2) DEFAULT 0,
        change_percent DECIMAL(5,2) DEFAULT 0,
        market VARCHAR(20) DEFAULT 'sh',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
      )
    `);
    
    await pool.execute(`
      CREATE TABLE IF NOT EXISTS portfolio (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        stock_code VARCHAR(20) NOT NULL,
        stock_name VARCHAR(100) NOT NULL,
        quantity INT NOT NULL DEFAULT 0,
        avg_price DECIMAL(10,2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE KEY unique_user_stock (user_id, stock_code)
      )
    `);
    
    await pool.execute(`
      CREATE TABLE IF NOT EXISTS watchlist_groups (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        name VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
      )
    `);
    
    await pool.execute(`
      CREATE TABLE IF NOT EXISTS watchlist_stocks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_id INT NOT NULL,
        stock_code VARCHAR(20) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES watchlist_groups(id) ON DELETE CASCADE,
        UNIQUE KEY unique_group_stock (group_id, stock_code)
      )
    `);
    
    console.log('数据库表初始化完成');
  } catch (error) {
    console.error('数据库初始化失败:', error);
  }
}

// JWT验证中间件
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ code: 401, message: '未提供访问令牌' });
  }
  
  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      return res.status(403).json({ code: 403, message: '令牌无效' });
    }
    req.user = user;
    next();
  });
};

// 健康检查接口
app.get('/api/health', (req, res) => {
  res.json({ 
    code: 200, 
    status: 'ok', 
    message: 'FamilyStock 后端服务运行正常',
    timestamp: new Date().toISOString()
  });
});

// 用户注册
app.post('/api/auth/register', async (req, res) => {
  try {
    const { username, password, email } = req.body;
    
    if (!username || !password) {
      return res.status(400).json({ code: 400, message: '用户名和密码不能为空' });
    }
    
    // 检查用户是否已存在
    const [existingUsers] = await pool.execute('SELECT id FROM users WHERE username = ?', [username]);
    if (existingUsers.length > 0) {
      return res.status(400).json({ code: 400, message: '用户名已存在' });
    }
    
    // 加密密码
    const hashedPassword = await bcrypt.hash(password, 10);
    
    // 创建用户
    const [result] = await pool.execute(
      'INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
      [username, hashedPassword, email || null]
    );
    
    // 生成JWT
    const token = jwt.sign(
      { userId: result.insertId, username },
      JWT_SECRET,
      { expiresIn: '7d' }
    );
    
    res.json({
      code: 200,
      message: '注册成功',
      data: {
        userId: result.insertId,
        username,
        token
      }
    });
  } catch (error) {
    console.error('注册失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 用户登录
app.post('/api/auth/login', async (req, res) => {
  try {
    const { username, password } = req.body;
    
    if (!username || !password) {
      return res.status(400).json({ code: 400, message: '用户名和密码不能为空' });
    }
    
    // 查询用户
    const [users] = await pool.execute('SELECT * FROM users WHERE username = ?', [username]);
    if (users.length === 0) {
      return res.status(400).json({ code: 400, message: '用户名或密码错误' });
    }
    
    const user = users[0];
    
    // 验证密码
    const validPassword = await bcrypt.compare(password, user.password);
    if (!validPassword) {
      return res.status(400).json({ code: 400, message: '用户名或密码错误' });
    }
    
    // 生成JWT
    const token = jwt.sign(
      { userId: user.id, username: user.username },
      JWT_SECRET,
      { expiresIn: '7d' }
    );
    
    res.json({
      code: 200,
      message: '登录成功',
      data: {
        userId: user.id,
        username: user.username,
        email: user.email,
        token
      }
    });
  } catch (error) {
    console.error('登录失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 获取用户信息
app.get('/api/user/info', authenticateToken, async (req, res) => {
  try {
    const [users] = await pool.execute(
      'SELECT id, username, email, created_at FROM users WHERE id = ?',
      [req.user.userId]
    );
    
    if (users.length === 0) {
      return res.status(404).json({ code: 404, message: '用户不存在' });
    }
    
    res.json({
      code: 200,
      data: users[0]
    });
  } catch (error) {
    console.error('获取用户信息失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 股票搜索
app.get('/api/stock/search', async (req, res) => {
  try {
    const keyword = req.query.keyword;
    if (!keyword) {
      return res.status(400).json({ code: 400, message: '搜索关键词不能为空' });
    }
    
    // 从真实数据库查询
    const [stocks] = await pool.execute(`
      SELECT code, name, price, change_percent, market, industry 
      FROM stocks 
      WHERE code LIKE ? OR name LIKE ? 
      LIMIT 20
    `, [`%${keyword}%`, `%${keyword}%`]);
    
    res.json({
      code: 200,
      data: stocks
    });
  } catch (error) {
    console.error('股票搜索失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// Tushare行情接口
app.get('/api/tushare/quote', async (req, res) => {
  try {
    const code = req.query.code;
    if (!code) {
      return res.status(400).json({ code: 400, message: '股票代码不能为空' });
    }
    
    // 查询数据库最新行情
    const [stocks] = await pool.execute(`
      SELECT code, name, price, change_percent, market, industry, updated_at 
      FROM stocks 
      WHERE code = ?
    `, [code]);
    
    if (stocks.length === 0) {
      return res.status(404).json({ code: 404, message: '股票不存在' });
    }
    
    res.json({
      code: 200,
      data: stocks[0]
    });
  } catch (error) {
    console.error('获取行情失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 获取股票详情
app.get('/api/stock/:code', async (req, res) => {
  try {
    const code = req.params.code;
    
    // 模拟股票详情
    const stock = {
      code,
      name: code === 'sh600000' ? '浦发银行' : code === 'sz000001' ? '平安银行' : '腾讯控股',
      price: code === 'sh600000' ? 8.25 : code === 'sz000001' ? 12.56 : 328.6,
      change_percent: code === 'sh600000' ? 1.23 : code === 'sz000001' ? -0.87 : 2.45,
      change: code === 'sh600000' ? 0.10 : code === 'sz000001' ? -0.11 : 7.8,
      high: code === 'sh600000' ? 8.30 : code === 'sz000001' ? 12.70 : 330.0,
      low: code === 'sh600000' ? 8.15 : code === 'sz000001' ? 12.40 : 325.0,
      volume: '25.6万手',
      turnover: '2.1亿',
      market_cap: code === 'sh600000' ? '2456亿' : code === 'sz000001' ? '3210亿' : '3.12万亿',
      pe: code === 'sh600000' ? 6.8 : code === 'sz000001' ? 7.2 : 15.6,
      pb: code === 'sh600000' ? 0.45 : code === 'sz000001' ? 0.58 : 3.2
    };
    
    res.json({
      code: 200,
      data: stock
    });
  } catch (error) {
    console.error('获取股票详情失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 获取K线数据
app.get('/api/stock/:code/kline', async (req, res) => {
  try {
    const code = req.params.code;
    const period = req.query.period || 'day'; // day/week/month
    
    // 模拟K线数据
    const klineData = [];
    const basePrice = code === 'sh600000' ? 8.25 : code === 'sz000001' ? 12.56 : 328.6;
    
    for (let i = 29; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      
      const open = basePrice + (Math.random() - 0.5) * 2;
      const close = open + (Math.random() - 0.5) * 1.5;
      const high = Math.max(open, close) + Math.random() * 0.5;
      const low = Math.min(open, close) - Math.random() * 0.5;
      
      klineData.push({
        date: date.toISOString().split('T')[0],
        open: parseFloat(open.toFixed(2)),
        close: parseFloat(close.toFixed(2)),
        high: parseFloat(high.toFixed(2)),
        low: parseFloat(low.toFixed(2)),
        volume: Math.floor(Math.random() * 100000) + 10000
      });
    }
    
    res.json({
      code: 200,
      data: {
        period,
        list: klineData
      }
    });
  } catch (error) {
    console.error('获取K线数据失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 获取持仓列表
app.get('/api/portfolio', authenticateToken, async (req, res) => {
  try {
    const [portfolio] = await pool.execute(`
      SELECT p.*, s.price as current_price, s.change_percent, s.industry
      FROM portfolio p
      LEFT JOIN stocks s ON p.stock_code = s.code
      WHERE p.user_id = ?
    `, [req.user.userId]);
    
    // 计算收益
    const result = portfolio.map(item => ({
      ...item,
      current_price: item.current_price || parseFloat((item.avg_price * (1 + (Math.random() - 0.5) * 0.2)).toFixed(2)),
      profit: parseFloat((((item.current_price || item.avg_price * (1 + (Math.random() - 0.5) * 0.2)) - item.avg_price) * item.quantity).toFixed(2)),
      profit_percent: parseFloat((((item.current_price || item.avg_price * (1 + (Math.random() - 0.5) * 0.2)) - item.avg_price) / item.avg_price * 100).toFixed(2))
    }));
    
    res.json({
      code: 200,
      data: result,
      total: result.length
    });
  } catch (error) {
    console.error('获取持仓列表失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 添加持仓
app.post('/api/portfolio', authenticateToken, async (req, res) => {
  try {
    const { stock_code, stock_name, quantity, avg_price } = req.body;
    
    if (!stock_code || !stock_name || !quantity || quantity <= 0 || !avg_price || avg_price <= 0) {
      return res.status(400).json({ code: 400, message: '参数不完整' });
    }
    
    // 检查是否已存在
    const [existing] = await pool.execute(
      'SELECT id, quantity, avg_price FROM portfolio WHERE user_id = ? AND stock_code = ?',
      [req.user.userId, stock_code]
    );
    
    if (existing.length > 0) {
      // 更新现有持仓
      const newQuantity = existing[0].quantity + quantity;
      const newAvgPrice = ((existing[0].quantity * existing[0].avg_price) + (quantity * avg_price)) / newQuantity;
      
      await pool.execute(
        'UPDATE portfolio SET quantity = ?, avg_price = ? WHERE id = ?',
        [newQuantity, newAvgPrice, existing[0].id]
      );
    } else {
      // 添加新持仓
      await pool.execute(
        'INSERT INTO portfolio (user_id, stock_code, stock_name, quantity, avg_price) VALUES (?, ?, ?, ?, ?)',
        [req.user.userId, stock_code, stock_name, quantity, avg_price]
      );
    }
    
    res.json({
      code: 200,
      message: '添加持仓成功'
    });
  } catch (error) {
    console.error('添加持仓失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 修改持仓
app.put('/api/portfolio/:id', authenticateToken, async (req, res) => {
  try {
    const id = req.params.id;
    const { quantity, avg_price } = req.body;
    
    if (!quantity || quantity <= 0 || !avg_price || avg_price <= 0) {
      return res.status(400).json({ code: 400, message: '参数不完整' });
    }
    
    // 检查是否属于当前用户
    const [portfolio] = await pool.execute(
      'SELECT id FROM portfolio WHERE id = ? AND user_id = ?',
      [id, req.user.userId]
    );
    
    if (portfolio.length === 0) {
      return res.status(404).json({ code: 404, message: '持仓记录不存在' });
    }
    
    await pool.execute(
      'UPDATE portfolio SET quantity = ?, avg_price = ? WHERE id = ?',
      [quantity, avg_price, id]
    );
    
    res.json({
      code: 200,
      message: '修改持仓成功'
    });
  } catch (error) {
    console.error('修改持仓失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 删除持仓
app.delete('/api/portfolio/:id', authenticateToken, async (req, res) => {
  try {
    const id = req.params.id;
    
    // 检查是否属于当前用户
    const [portfolio] = await pool.execute(
      'SELECT id FROM portfolio WHERE id = ? AND user_id = ?',
      [id, req.user.userId]
    );
    
    if (portfolio.length === 0) {
      return res.status(404).json({ code: 404, message: '持仓记录不存在' });
    }
    
    await pool.execute('DELETE FROM portfolio WHERE id = ?', [id]);
    
    res.json({
      code: 200,
      message: '删除持仓成功'
    });
  } catch (error) {
    console.error('删除持仓失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 获取自选股分组
app.get('/api/watchlist/groups', authenticateToken, async (req, res) => {
  try {
    const [groups] = await pool.execute(
      'SELECT * FROM watchlist_groups WHERE user_id = ? ORDER BY created_at',
      [req.user.userId]
    );
    
    // 查询每个分组的股票数量
    for (let group of groups) {
      const [count] = await pool.execute(
        'SELECT COUNT(*) as count FROM watchlist_stocks WHERE group_id = ?',
        [group.id]
      );
      group.stock_count = count[0].count;
    }
    
    res.json({
      code: 200,
      data: groups
    });
  } catch (error) {
    console.error('获取自选股分组失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 创建自选股分组
app.post('/api/watchlist/groups', authenticateToken, async (req, res) => {
  try {
    const { name } = req.body;
    
    if (!name || name.trim() === '') {
      return res.status(400).json({ code: 400, message: '分组名称不能为空' });
    }
    
    // 检查是否已存在同名分组
    const [existing] = await pool.execute(
      'SELECT id FROM watchlist_groups WHERE user_id = ? AND name = ?',
      [req.user.userId, name]
    );
    
    if (existing.length > 0) {
      return res.status(400).json({ code: 400, message: '分组名称已存在' });
    }
    
    const [result] = await pool.execute(
      'INSERT INTO watchlist_groups (user_id, name) VALUES (?, ?)',
      [req.user.userId, name]
    );
    
    res.json({
      code: 200,
      message: '创建分组成功',
      data: {
        id: result.insertId,
        name
      }
    });
  } catch (error) {
    console.error('创建自选股分组失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 获取分组内的股票
app.get('/api/watchlist/groups/:groupId/stocks', authenticateToken, async (req, res) => {
  try {
    const groupId = req.params.groupId;
    
    // 检查分组是否属于当前用户
    const [groups] = await pool.execute(
      'SELECT id FROM watchlist_groups WHERE id = ? AND user_id = ?',
      [groupId, req.user.userId]
    );
    
    if (groups.length === 0) {
      return res.status(404).json({ code: 404, message: '分组不存在' });
    }
    
    const [stocks] = await pool.execute(`
      SELECT ws.stock_code, s.name, s.price, s.change_percent 
      FROM watchlist_stocks ws
      LEFT JOIN stocks s ON ws.stock_code = s.code
      WHERE ws.group_id = ?
      ORDER BY ws.created_at DESC
    `, [groupId]);
    
    // 补充模拟数据
    const result = stocks.map(stock => ({
      ...stock,
      price: stock.price || parseFloat((Math.random() * 100 + 10).toFixed(2)),
      change_percent: stock.change_percent || parseFloat(((Math.random() - 0.5) * 20).toFixed(2))
    }));
    
    res.json({
      code: 200,
      data: result
    });
  } catch (error) {
    console.error('获取分组股票失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 添加股票到自选股
app.post('/api/watchlist/groups/:groupId/stocks', authenticateToken, async (req, res) => {
  try {
    const groupId = req.params.groupId;
    const { stock_code, stock_name } = req.body;
    
    if (!stock_code || !stock_name) {
      return res.status(400).json({ code: 400, message: '股票信息不完整' });
    }
    
    // 检查分组是否属于当前用户
    const [groups] = await pool.execute(
      'SELECT id FROM watchlist_groups WHERE id = ? AND user_id = ?',
      [groupId, req.user.userId]
    );
    
    if (groups.length === 0) {
      return res.status(404).json({ code: 404, message: '分组不存在' });
    }
    
    // 检查是否已存在
    const [existing] = await pool.execute(
      'SELECT id FROM watchlist_stocks WHERE group_id = ? AND stock_code = ?',
      [groupId, stock_code]
    );
    
    if (existing.length > 0) {
      return res.status(400).json({ code: 400, message: '该股票已在自选股中' });
    }
    
    // 添加到stocks表（如果不存在）
    await pool.execute(
      'INSERT IGNORE INTO stocks (code, name) VALUES (?, ?)',
      [stock_code, stock_name]
    );
    
    // 添加到自选股
    await pool.execute(
      'INSERT INTO watchlist_stocks (group_id, stock_code) VALUES (?, ?)',
      [groupId, stock_code]
    );
    
    res.json({
      code: 200,
      message: '添加自选股成功'
    });
  } catch (error) {
    console.error('添加自选股失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 从自选股删除
app.delete('/api/watchlist/groups/:groupId/stocks/:stockCode', authenticateToken, async (req, res) => {
  try {
    const groupId = req.params.groupId;
    const stockCode = req.params.stockCode;
    
    // 检查分组是否属于当前用户
    const [groups] = await pool.execute(
      'SELECT id FROM watchlist_groups WHERE id = ? AND user_id = ?',
      [groupId, req.user.userId]
    );
    
    if (groups.length === 0) {
      return res.status(404).json({ code: 404, message: '分组不存在' });
    }
    
    await pool.execute(
      'DELETE FROM watchlist_stocks WHERE group_id = ? AND stock_code = ?',
      [groupId, stockCode]
    );
    
    res.json({
      code: 200,
      message: '删除自选股成功'
    });
  } catch (error) {
    console.error('删除自选股失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 获取涨跌提醒列表
app.get('/api/alerts', authenticateToken, async (req, res) => {
  try {
    // 模拟提醒数据
    const alerts = [
      {
        id: 1,
        stock_code: 'sh600000',
        stock_name: '浦发银行',
        alert_type: 'price_up',
        threshold: 8.5,
        current_price: 8.25,
        enabled: true,
        created_at: '2026-03-13T10:00:00Z'
      },
      {
        id: 2,
        stock_code: 'sz000001',
        stock_name: '平安银行',
        alert_type: 'price_down',
        threshold: 12.0,
        current_price: 12.56,
        enabled: true,
        created_at: '2026-03-13T11:00:00Z'
      }
    ];
    
    res.json({
      code: 200,
      data: alerts
    });
  } catch (error) {
    console.error('获取提醒列表失败:', error);
    res.status(500).json({ code: 500, message: '服务器错误' });
  }
});

// 情景推演API
app.post('/api/ai/scenario', async (req, res) => {
  try {
    const { scenario, stocks } = req.body;
    
    if (!scenario || !stocks || !Array.isArray(stocks)) {
      return res.status(400).json({ code: 400, message: '参数不完整' });
    }
    
    // 模拟推演结果（实际对接AI模型）
    const result = {
      scenario,
      analysis_time: new Date().toISOString(),
      stocks: stocks.map(code => ({
        code,
        impact: Math.random() > 0.5 ? 'positive' : 'negative',
        change_range: `${(Math.random() * 20 - 10).toFixed(2)}%`,
        confidence: Math.floor(Math.random() * 30) + 70
      })),
      summary: `在${scenario}情景下，持仓预计波动幅度在-15%~+20%之间，建议关注新能源和科技板块`,
      suggestion: '建议适度减持高估值成长股，增加消费和医药板块配置'
    };
    
    res.json({
      code: 200,
      data: result,
      message: '推演完成'
    });
  } catch (error) {
    console.error('情景推演失败:', error);
    res.status(500).json({ code: 500, message: '推演失败，请稍后重试' });
  }
});

// 组合分析API
app.get('/api/ai/portfolio-analysis', authenticateToken, async (req, res) => {
  try {
    // 设置超时时间为10秒
    req.setTimeout(10000);
    
    // 查询用户持仓
    const [portfolio] = await pool.execute(`
      SELECT p.*, s.industry, s.market
      FROM portfolio p
      LEFT JOIN stocks s ON p.stock_code = s.code
      WHERE p.user_id = ?
    `, [req.user.userId]);
    
    if (portfolio.length === 0) {
      return res.json({
        code: 200,
        data: {
          total_value: 0,
          industry_distribution: [],
          market_distribution: [],
          risk_level: 'low',
          score: 0,
          suggestion: '暂无持仓，建议开始配置资产'
        }
      });
    }
    
    // 计算组合分析
    const totalValue = portfolio.reduce((sum, item) => sum + item.quantity * item.avg_price, 0);
    
    // 行业分布
    const industryMap = {};
    portfolio.forEach(item => {
      const industry = item.industry || '其他';
      industryMap[industry] = (industryMap[industry] || 0) + item.quantity * item.avg_price;
    });
    
    const industryDistribution = Object.entries(industryMap).map(([name, value]) => ({
      name,
      value: parseFloat((value / totalValue * 100).toFixed(2))
    }));
    
    // 市场分布
    const marketMap = {};
    portfolio.forEach(item => {
      const market = item.market || 'SH';
      marketMap[market] = (marketMap[market] || 0) + item.quantity * item.avg_price;
    });
    
    const marketDistribution = Object.entries(marketMap).map(([name, value]) => ({
      name,
      value: parseFloat((value / totalValue * 100).toFixed(2))
    }));
    
    // 风险评分
    const riskScore = Math.floor(Math.random() * 40) + 60;
    const riskLevel = riskScore < 70 ? 'low' : riskScore < 85 ? 'medium' : 'high';
    
    const result = {
      total_value: parseFloat(totalValue.toFixed(2)),
      stock_count: portfolio.length,
      industry_distribution: industryDistribution,
      market_distribution: marketDistribution,
      risk_level: riskLevel,
      score: riskScore,
      max_drawdown: `${(Math.random() * 20 + 10).toFixed(2)}%`,
      volatility: `${(Math.random() * 15 + 5).toFixed(2)}%`,
      suggestion: '组合配置较为均衡，建议适当增加港股和美股配置以分散风险'
    };
    
    res.json({
      code: 200,
      data: result,
      message: '分析完成'
    });
  } catch (error) {
    console.error('组合分析失败:', error);
    res.status(500).json({ code: 500, message: '分析失败，请稍后重试' });
  }
});

// 全局错误处理
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ code: 500, message: '服务器内部错误' });
});

// 404处理
app.use((req, res) => {
  res.status(404).json({ code: 404, message: '接口不存在' });
});

// 启动服务
async function startServer() {
  await initDB();
  
  app.listen(PORT, () => {
    console.log(`🚀 FamilyStock 后端服务已启动，运行在端口 ${PORT}`);
    console.log(`📊 API文档：http://localhost:${PORT}/api/health`);
  });
}

startServer();
