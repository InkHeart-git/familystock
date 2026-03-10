/**
 * MiniRock v2.0 - 工具函数
 * 格式化、验证等通用工具
 */

const Utils = {
  /**
   * 格式化价格
   * @param {number} price - 价格
   * @param {string} currency - 货币: CNY/USD
   * @param {number} decimals - 小数位
   * @returns {string} 格式化后的价格
   */
  formatPrice(price, currency = 'CNY', decimals = 2) {
    const num = parseFloat(price);
    if (isNaN(num)) return currency === 'CNY' ? '¥0.00' : '$0.00';
    
    const formatted = num.toFixed(decimals);
    return currency === 'CNY' ? `¥${formatted}` : `$${formatted}`;
  },

  /**
   * 格式化涨跌幅
   * @param {number} percent - 百分比
   * @param {boolean} withSign - 是否带符号
   * @returns {string} 格式化后的百分比
   */
  formatChange(percent, withSign = true) {
    const num = parseFloat(percent);
    if (isNaN(num)) return withSign ? '+0.00%' : '0.00%';
    
    const formatted = Math.abs(num).toFixed(2);
    if (!withSign) return `${formatted}%`;
    
    const sign = num >= 0 ? '+' : '-';
    return `${sign}${formatted}%`;
  },

  /**
   * 格式化成交量
   * @param {number} volume - 成交量
   * @returns {string} 格式化后的成交量
   */
  formatVolume(volume) {
    const num = parseInt(volume) || 0;
    
    if (num >= 100000000) {
      return (num / 100000000).toFixed(2) + '亿';
    } else if (num >= 10000) {
      return (num / 10000).toFixed(2) + '万';
    }
    return num.toString();
  },

  /**
   * 格式化市值
   * @param {number} marketCap - 市值
   * @returns {string} 格式化后的市值
   */
  formatMarketCap(marketCap) {
    const num = parseFloat(marketCap) || 0;
    
    if (num >= 1000000000000) {
      return (num / 1000000000000).toFixed(2) + '万亿';
    } else if (num >= 100000000) {
      return (num / 100000000).toFixed(2) + '亿';
    } else if (num >= 10000) {
      return (num / 10000).toFixed(2) + '万';
    }
    return num.toFixed(2);
  },

  /**
   * 格式化日期时间
   * @param {Date|number|string} date - 日期
   * @param {string} format - 格式
   * @returns {string} 格式化后的日期
   */
  formatDate(date, format = 'YYYY-MM-DD HH:mm') {
    const d = new Date(date);
    if (isNaN(d.getTime())) return '-';

    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hour = String(d.getHours()).padStart(2, '0');
    const minute = String(d.getMinutes()).padStart(2, '0');
    const second = String(d.getSeconds()).padStart(2, '0');

    return format
      .replace('YYYY', year)
      .replace('MM', month)
      .replace('DD', day)
      .replace('HH', hour)
      .replace('mm', minute)
      .replace('ss', second);
  },

  /**
   * 获取涨跌颜色类名
   * @param {number} value - 数值
   * @returns {string} 颜色类名
   */
  getChangeClass(value) {
    const num = parseFloat(value);
    if (num > 0) return 'change-up';
    if (num < 0) return 'change-down';
    return 'change-neutral';
  },

  /**
   * 获取AI评分颜色类名
   * @param {number} score - 分数
   * @returns {string} 颜色类名
   */
  getScoreClass(score) {
    const num = parseInt(score) || 0;
    if (num >= 70) return 'score-high';
    if (num >= 50) return 'score-medium';
    return 'score-low';
  },

  /**
   * 获取AI评分文字
   * @param {number} score - 分数
   * @returns {string} 评分文字
   */
  getScoreText(score) {
    const num = parseInt(score) || 0;
    if (num >= 70) return '推荐';
    if (num >= 50) return '观望';
    return '谨慎';
  },

  /**
   * 验证股票代码
   * @param {string} symbol - 股票代码
   * @returns {boolean} 是否有效
   */
  isValidSymbol(symbol) {
    if (!symbol || typeof symbol !== 'string') return false;
    const clean = symbol.trim();
    // A股代码: 600/601/603/688/000/002/300 开头，6位数字
    return /^[036]\d{5}$/.test(clean) || /^\d{6}$/.test(clean);
  },

  /**
   * 防抖函数
   * @param {Function} fn - 原函数
   * @param {number} delay - 延迟时间
   * @returns {Function} 防抖后的函数
   */
  debounce(fn, delay = 300) {
    let timer = null;
    return function(...args) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        fn.apply(this, args);
      }, delay);
    };
  },

  /**
   * 节流函数
   * @param {Function} fn - 原函数
   * @param {number} limit - 限制时间
   * @returns {Function} 节流后的函数
   */
  throttle(fn, limit = 300) {
    let inThrottle = false;
    return function(...args) {
      if (!inThrottle) {
        fn.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  },

  /**
   * 生成唯一ID
   * @returns {string} 唯一ID
   */
  generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  },

  /**
   * 深拷贝
   * @param {Object} obj - 原对象
   * @returns {Object} 拷贝后的对象
   */
  deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (Array.isArray(obj)) return obj.map(item => this.deepClone(item));
    
    const cloned = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        cloned[key] = this.deepClone(obj[key]);
      }
    }
    return cloned;
  },

  /**
   * 计算盈亏
   * @param {number} current - 当前价
   * @param {number} cost - 成本价
   * @param {number} quantity - 数量
   * @returns {Object} 盈亏信息
   */
  calculateProfit(current, cost, quantity) {
    const currentNum = parseFloat(current) || 0;
    const costNum = parseFloat(cost) || 0;
    const qty = parseInt(quantity) || 0;
    
    const profit = (currentNum - costNum) * qty;
    const profitPercent = costNum > 0 ? ((currentNum - costNum) / costNum) * 100 : 0;
    
    return {
      profit,
      profitPercent,
      formattedProfit: this.formatPrice(profit),
      formattedPercent: this.formatChange(profitPercent)
    };
  },

  /**
   * 延迟
   * @param {number} ms - 毫秒
   * @returns {Promise}
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
};

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = Utils;
} else {
  window.Utils = Utils;
}
