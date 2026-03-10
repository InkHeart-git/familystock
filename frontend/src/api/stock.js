/**
 * MiniRock v2.0 - 股票相关 API
 * 所有股票数据请求统一入口
 */

class StockAPI {
  constructor(client) {
    this.client = client;
    this.basePath = '/tushare';
  }

  /**
   * 获取单只股票实时行情
   * @param {string} symbol - 股票代码 (如: 600519)
   * @returns {Promise<Object>} 股票数据
   */
  async getQuote(symbol) {
    if (!symbol) {
      throw new Error('Symbol is required');
    }
    
    // 清理代码格式
    const cleanSymbol = symbol.toString().trim();
    
    try {
      const data = await this.client.get(`${this.basePath}/quote/${cleanSymbol}`);
      
      // 添加双价格显示
      return this.enrichWithDualPrice(data);
    } catch (error) {
      console.error(`[StockAPI] Failed to get quote for ${cleanSymbol}:`, error);
      // API失败返回null，不返回假数据
      return null;
    }
  }

  /**
   * 批量获取股票行情
   * @param {string[]} symbols - 股票代码数组
   * @returns {Promise<Array>} 股票数据数组
   */
  async getBatchQuotes(symbols) {
    if (!Array.isArray(symbols) || symbols.length === 0) {
      return [];
    }

    // 限制批量数量
    const MAX_BATCH = 50;
    if (symbols.length > MAX_BATCH) {
      console.warn(`[StockAPI] Batch size limited to ${MAX_BATCH}`);
      symbols = symbols.slice(0, MAX_BATCH);
    }

    try {
      const symbolStr = symbols.join(',');
      const result = await this.client.get(`${this.basePath}/batch`, { 
        symbols: symbolStr 
      });

      // 处理响应格式
      const stocks = result.stocks || result || [];
      
      // 为每只股票添加双价格
      return stocks.map(stock => this.enrichWithDualPrice(stock));
    } catch (error) {
      console.error('[StockAPI] Failed to get batch quotes:', error);
      return null;
    }
  }

  /**
   * 搜索股票
   * @param {string} keyword - 搜索关键词
   * @returns {Promise<Array>} 搜索结果
   */
  async search(keyword) {
    if (!keyword || keyword.trim().length === 0) {
      return [];
    }

    try {
      const result = await this.client.get(`${this.basePath}/search`, {
        keyword: keyword.trim()
      });

      return result.results || result || [];
    } catch (error) {
      console.error('[StockAPI] Search failed:', error);
      return [];
    }
  }

  /**
   * 获取K线数据
   * @param {string} symbol - 股票代码
   * @param {string} period - 周期: day/week/month
   * @param {number} limit - 数量限制
   * @returns {Promise<Array>} K线数据
   */
  async getKLine(symbol, period = 'day', limit = 100) {
    if (!symbol) {
      throw new Error('Symbol is required');
    }

    try {
      const result = await this.client.get(`${this.basePath}/kline/${symbol}`, {
        period,
        limit
      });

      return result.data || result || [];
    } catch (error) {
      console.error(`[StockAPI] Failed to get K-line for ${symbol}:`, error);
      return null;
    }
  }

  /**
   * 获取股票基本面数据
   * @param {string} symbol - 股票代码
   * @returns {Promise<Object>} 基本面数据
   */
  async getFundamentals(symbol) {
    if (!symbol) {
      throw new Error('Symbol is required');
    }

    try {
      return await this.client.get(`${this.basePath}/fundamentals/${symbol}`);
    } catch (error) {
      console.error(`[StockAPI] Failed to get fundamentals for ${symbol}:`, error);
      return null;
    }
  }

  /**
   * 获取市场指数
   * @returns {Promise<Array>} 指数数据
   */
  async getMarketIndices() {
    const indices = ['000001.SH', '399001.SZ', '399006.SZ'];
    
    try {
      const results = await this.getBatchQuotes(indices);
      return results || [];
    } catch (error) {
      console.error('[StockAPI] Failed to get market indices:', error);
      return [];
    }
  }

  /**
   * 为股票数据添加双价格显示
   * @private
   */
  enrichWithDualPrice(stock) {
    if (!stock) return null;

    const { EXCHANGE } = CONFIG;
    const close = parseFloat(stock.close || 0);

    return {
      ...stock,
      // 本地价格 (CNY)
      localPrice: close,
      localCurrency: 'CNY',
      localSymbol: '¥',
      
      // 美元价格
      usdPrice: close > 0 ? (close * EXCHANGE.CNY_TO_USD).toFixed(2) : '0.00',
      usdCurrency: 'USD',
      usdSymbol: '$',
      
      // 格式化后的价格
      formattedLocal: this.formatPrice(close, 'CNY'),
      formattedUSD: close > 0 ? this.formatPrice(close * EXCHANGE.CNY_TO_USD, 'USD') : '$0.00'
    };
  }

  /**
   * 格式化价格
   * @private
   */
  formatPrice(price, currency) {
    const num = parseFloat(price);
    if (isNaN(num)) return currency === 'CNY' ? '¥0.00' : '$0.00';
    
    const formatted = num.toFixed(2);
    return currency === 'CNY' ? `¥${formatted}` : `$${formatted}`;
  }
}

// 创建实例
const stockAPI = new StockAPI(apiClient);

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { StockAPI, stockAPI };
} else {
  window.StockAPI = StockAPI;
  window.stockAPI = stockAPI;
}
