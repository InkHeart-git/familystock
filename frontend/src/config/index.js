/**
 * MiniRock v2.0 - 全局配置
 * 集中管理所有配置项，禁止硬编码
 */

const CONFIG = {
  // 应用信息
  APP: {
    NAME: 'MiniRock',
    VERSION: '2.0.0',
    DESCRIPTION: 'AI投资助手',
    UPDATE_INTERVAL: 30000,  // 30秒刷新
    DEFAULT_CURRENCY: 'CNY'
  },

  // API 配置 - 使用 8080 端口 (server_v3.py)
  API: {
    BASE_URL: (() => {
      const host = window.location.hostname;
      // 本地开发
      if (host === 'localhost' || host === '127.0.0.1') {
        return 'http://localhost:8080/api/v3';
      }
      // 生产环境
      return `http://${host}:8080/api/v3`;
    })(),
    TIMEOUT: 10000,           // 10秒超时
    RETRY_COUNT: 3,           // 重试次数
    RETRY_DELAY: 1000,        // 重试间隔
    CACHE_TTL: 60000          // 缓存1分钟
  },

  // Tushare 配置
  TUSHARE: {
    TOKEN: 'f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735',
    RATE_LIMIT: 2000          // 每分钟调用次数限制
  },

  // 汇率配置
  EXCHANGE: {
    CNY_TO_USD: 0.138,
    USD_TO_CNY: 7.25,
    UPDATE_INTERVAL: 3600000  // 1小时更新
  },

  // 预警配置
  ALERT: {
    CHECK_INTERVAL: 60000,    // 1分钟检查一次
    COOLDOWN: 300000,         // 5分钟冷却
    THRESHOLDS: {
      PRICE_DROP: -10,        // 跌幅10%预警
      PRICE_RISE: 20,         // 涨幅20%预警
      AI_SCORE_LOW: 40,       // AI评分低于40预警
      VOLUME_SPIKE: 3         // 成交量放大3倍预警
    }
  },

  // UI 配置
  UI: {
    // 颜色
    COLORS: {
      BG_PRIMARY: '#0a0a0f',
      BG_SECONDARY: '#1a1a2e',
      BG_CARD: '#16213e',
      TEXT_PRIMARY: '#ffffff',
      TEXT_SECONDARY: '#8892b0',
      TEXT_MUTED: '#64748b',
      UP: '#ff6b6b',           // 红涨
      DOWN: '#51cf66',         // 绿跌
      BLUE: '#3b82f6',
      PURPLE: '#8b5cf6',
      YELLOW: '#f59e0b'
    },
    
    // 动画
    ANIMATION: {
      FAST: 150,
      NORMAL: 300,
      SLOW: 500
    },
    
    // 间距
    SPACING: {
      XS: 4,
      SM: 8,
      MD: 16,
      LG: 24,
      XL: 32,
      XXL: 48
    }
  },

  // 股票配置
  STOCK: {
    DEFAULT_HOLDINGS: [],     // 默认持仓
    MAX_HOLDINGS: 50,         // 最大持仓数量
    PRICE_DECIMALS: 2,        // 价格小数位
    PCT_DECIMALS: 2           // 百分比小数位
  },

  // 开发配置
  DEV: {
    DEBUG: false,             // 调试模式
    MOCK: false,              // 禁止使用假数据
    LOG_LEVEL: 'error'        // 日志级别
  }
};

// 冻结配置，防止运行时修改
Object.freeze(CONFIG);
Object.freeze(CONFIG.APP);
Object.freeze(CONFIG.API);
Object.freeze(CONFIG.TUSHARE);
Object.freeze(CONFIG.EXCHANGE);
Object.freeze(CONFIG.ALERT);
Object.freeze(CONFIG.UI);
Object.freeze(CONFIG.UI.COLORS);
Object.freeze(CONFIG.UI.ANIMATION);
Object.freeze(CONFIG.UI.SPACING);
Object.freeze(CONFIG.STOCK);
Object.freeze(CONFIG.DEV);

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CONFIG;
} else {
  window.CONFIG = CONFIG;
}
