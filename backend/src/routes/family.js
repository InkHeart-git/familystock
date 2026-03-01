const express = require('express');

const router = express.Router();

// 获取家庭组信息
router.get('/', async (req, res) => {
  try {
    const userId = req.user.userId;
    
    // TODO: 从数据库获取
    const family = {
      id: 'f001',
      name: '张家投资组合',
      members: [
        { id: 'u001', name: '张三', role: 'admin' },
        { id: 'u002', name: '李四', role: 'member' }
      ],
      createdAt: '2024-01-01'
    };

    res.json(family);
  } catch (error) {
    console.error('获取家庭组错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

// 获取家庭成员
router.get('/members', async (req, res) => {
  try {
    const userId = req.user.userId;
    
    const members = [
      { id: 'u001', name: '张三', email: 'zhang@example.com', role: 'admin' },
      { id: 'u002', name: '李四', email: 'li@example.com', role: 'member' }
    ];

    res.json({ members });
  } catch (error) {
    console.error('获取成员错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

// 邀请成员
router.post('/invite', async (req, res) => {
  try {
    const { email } = req.body;
    
    // TODO: 发送邀请邮件
    res.json({ message: '邀请已发送', email });
  } catch (error) {
    console.error('邀请错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

// 获取家庭共享自选池
router.get('/watchlist', async (req, res) => {
  try {
    const watchlist = [
      { symbol: '000001.SZ', name: '平安银行', addedBy: '张三', addedAt: '2024-01-01' },
      { symbol: '000002.SZ', name: '万科A', addedBy: '李四', addedAt: '2024-01-02' }
    ];

    res.json({ watchlist });
  } catch (error) {
    console.error('获取共享池错误:', error);
    res.status(500).json({ error: '服务器错误' });
  }
});

module.exports = router;
