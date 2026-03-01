const express = require('express');

const router = express.Router();

// 获取自选股列表
router.get('/', async (req, res) => {
  try {
    const userId = req.user.userId;
    
    // TODO: 从数据库获取
    const watchlist = [
      { symbol: '000001.SZ', name: '平安银行', addedAt: '2024-01-01' },
      { symbol: '000002.SZ', name: '万科A', addedAt: '2024-01-02' }
    ];

    res.json({ watchlist });
  } catch (error) {
    console.error('获取自选股错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

// 添加自选股
router.post('/', async (req, res) => {
  try {
    const userId = req.user.userId;
    const { symbol, name } = req.body;

    // TODO: 保存到数据库
    res.status(201).json({ message: '添加成功', symbol, name });
  } catch (error) {
    console.error('添加自选股错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

// 删除自选股
router.delete('/:symbol', async (req, res) => {
  try {
    const userId = req.user.userId;
    const { symbol } = req.params;

    // TODO: 从数据库删除
    res.json({ message: '删除成功', symbol });
  } catch (error) {
    console.error('删除自选股错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

module.exports = router;
