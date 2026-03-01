const errorHandler = (err, req, res, next) => {
  console.error('错误:', err);

  // 处理已知的错误类型
  if (err.name === 'ValidationError') {
    return res.status(400).json({
      error: '验证错误',
      message: err.message
    });
  }

  if (err.name === 'UnauthorizedError') {
    return res.status(401).json({
      error: '未授权',
      message: '无效的认证令牌'
    });
  }

  if (err.code === 'P2002') {
    // Prisma 唯一约束冲突
    return res.status(409).json({
      error: '数据冲突',
      message: '记录已存在'
    });
  }

  // 默认错误响应
  res.status(err.status || 500).json({
    error: err.message || '服务器内部错误',
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
};

module.exports = { errorHandler };
