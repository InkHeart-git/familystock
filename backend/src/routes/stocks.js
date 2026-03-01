const express = require('express');

const router = express.Router();

// 搜索股票
router.get('/search', async (req, res) => {
  try {
    const { q } = req.query;
    if (!q) {
      return res.status(400).json({ error: '请提供搜索关键词' });
    }

    // TODO: 接入Tushare/AkShare搜索
    // 临时返回模拟数据
    const mockStocks = [
      { symbol: '000001.SZ', name: '平安银行', exchange: 'SZSE' },
      { symbol: '000002.SZ', name: '万科A', exchange: 'SZSE' },
      { symbol: '600000.SH', name: '浦发银行', exchange: 'SSE' }
    ].filter(s => s.name.includes(q) || s.symbol.includes(q));

    res.json({ stocks: mockStocks });
  } catch (error) {
    console.error('搜索错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

// 获取股票详情
router.get('/:symbol', async (req, res) => {
  try {
    const { symbol } = req.params;
    
    // TODO: 从数据库或API获取详情
    const mockDetail = {
      symbol,
      name: '平安银行',
      exchange: 'SZSE',
      industry: '银行',
      marketCap: '2000亿',
      pe: 5.2,
      pb: 0.8,
      roe: '12%'
    };

    res.json(mockDetail);
  } catch (error) {
    console.error('获取详情错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

// 获取实时行情
router.get('/:symbol/quote', async (req, res) => {
  try {
    const { symbol } = req.params;
    
    // TODO: 从API获取实时行情
    const mockQuote = {
      symbol,
      price: 12.35,
      change: 0.25,
      changePercent: 2.07,
      volume: 1250000,
      high: 12.50,
      low: 12.10,
      open: 12.10,
      prevClose: 12.10,
      timestamp: new Date().toISOString()
    };

    res.json(mockQuote);
  } catch (error) {
    console.error('获取行情错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

// 获取历史数据
router.get('/:symbol/history', async (req, res) => {
  try {
    const { symbol } = req.params;
    const { period = '1d' } = req.query;
    
    // TODO: 从API获取历史数据
    const mockHistory = [
      { date: '2024-01-01', open: 12.0, high: 12.3, low: 11.9, close: 12.1, volume: 1000000 },
      { date: '2024-01-02', open: 12.1, high: 12.4, low: 12.0, close: 12.2, volume: 1200000 },
      { date: '2024-01-03', open: 12.2, high: 12.5, low: 12.1, close: 12.35, volume: 1250000 }
    ];

    res.json({ symbol, period, data: mockHistory });
  } catch (error) {
    console.error('获取历史数据错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

module.exports = router;
