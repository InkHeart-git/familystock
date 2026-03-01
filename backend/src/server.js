const app = require('./app');
const { PrismaClient } = require('@prisma/client');
const Redis = require('ioredis');

const PORT = process.env.PORT || 5000;

// 初始化Prisma客户端
const prisma = new PrismaClient();

// 初始化Redis客户端
const redis = new Redis({
  host: process.env.REDIS_HOST || 'localhost',
  port: process.env.REDIS_PORT || 6379,
  password: process.env.REDIS_PASSWORD || undefined,
  retryStrategy: (times) => {
    const delay = Math.min(times * 50, 2000);
    return delay;
  }
});

// 全局存储实例
global.prisma = prisma;
global.redis = redis;

// 优雅关闭
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, closing gracefully...');
  await prisma.$disconnect();
  await redis.quit();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('SIGINT received, closing gracefully...');
  await prisma.$disconnect();
  await redis.quit();
  process.exit(0);
});

// 启动服务器
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`📚 API docs: http://localhost:${PORT}/api/docs`);
  console.log(`💓 Health check: http://localhost:${PORT}/health`);
});
