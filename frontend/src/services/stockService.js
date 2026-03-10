/**
 * MiniRock v2.0 - 股票数据服务
 * 业务逻辑层，封装股票相关操作
 */

class StockService {
  constructor() {
    this.holdings = [];
    this.watchlist = [];
    this.priceCache = new Map();
    this.subscribers = new Map();
    this.updateInterval = null;
  }

  /**
   * 初始化服务
   */
  async init() {
    // 从本地存储加载持仓
    this.loadFromStorage();
    
    // 启动定时更新
    this.startAutoUpdate();
    
    console.log('[StockService] Initialized');
  }

  /**
   * 添加持仓
   * @param {Object} holding - 持仓信息
   * @returns {boolean} 是否成功
   */
  addHolding(holding) {
    if (!holding.symbol || !holding.quantity || !holding.avgCost) {
      console.error('[StockService] Invalid holding data');
      return false;
    }

    // 检查是否已存在
    const existingIndex = this.holdings.findIndex(h => h.symbol === holding.symbol);
    
    if (existingIndex >= 0) {
      // 更新现有持仓
      this.holdings[existingIndex] = {
        ...this.holdings[existingIndex],
        quantity: holding.quantity,
        avgCost: holding.avgCost,
        updatedAt: Date.now()
      };
    } else {
      // 添加新持仓
      this.holdings.push({
        symbol: holding.symbol,
        name: holding.name || holding.symbol,
        quantity: parseInt(holding.quantity),
        avgCost: parseFloat(holding.avgCost),
        addedAt: Date.now(),
        updatedAt: Date.now()
      });
    }

    this.saveToStorage();
    this.notifySubscribers('holdings', this.holdings);
    
    return true;
  }

  /**
   * 移除持仓
   * @param {string} symbol - 股票代码
   * @returns {boolean} 是否成功
   */
  removeHolding(symbol) {
    const index = this.holdings.findIndex(h => h.symbol === symbol);
    if (index >= 0) {
      this.holdings.splice(index, 1);
      this.saveToStorage();
      this.notifySubscribers('holdings', this.holdings);
      return true;
    }
    return false;
  }

  /**
   * 获取持仓列表（带实时价格）
   * @returns {Promise<Array>} 持仓列表
   */
  async getHoldingsWithPrice() {
    if (this.holdings.length === 0) {
      return [];
    }

    const symbols = this.holdings.map(h => h.symbol);
    
    try {
      // 批量获取实时价格
      const priceData = await stockAPI.getBatchQuotes(symbols);
      
      if (!priceData || priceData.length === 0) {
        // API失败，返回持仓但不带价格
        return this.holdings.map(h => ({
          ...h,
          close: null,
          pct_chg: 0,
          aiScore: 50,
          profit: 0,
          profitPercent: 0
        }));
      }

      // 合并持仓和价格数据
      return this.holdings.map(holding => {
        const price = priceData.find(p => p.symbol === holding.symbol);
        const currentPrice = price ? price.close : holding.avgCost;
        const aiScore = price ? aiAPI.calculateLocalScore(price).score : 50;
        
        // 计算盈亏
        const profitCalc = Utils.calculateProfit(
          currentPrice,
          holding.avgCost,
          holding.quantity
        );

        return {
          ...holding,
          ...price,
          name: holding.name || price?.name || holding.symbol,
          aiScore,
          profit: profitCalc.profit,
          profitPercent: profitCalc.profitPercent,
          formattedProfit: profitCalc.formattedProfit,
          formattedPercent: profitCalc.formattedPercent
        };
      });
    } catch (error) {
      console.error('[StockService] Failed to get holdings price:', error);
      return this.holdings.map(h => ({
        ...h,
        close: null,
        pct_chg: 0,
        aiScore: 50,
        profit: 0,
        profitPercent: 0,
        error: true
      }));
    }
  }

  /**
   * 计算总资产
   * @returns {Promise<Object>} 资产统计
   */
  async calculateAssets() {
    const holdings = await this.getHoldingsWithPrice();
    
    let totalValue = 0;
    let totalCost = 0;
    let dailyChange = 0;
    
    holdings.forEach(h => {
      const marketValue = (h.close || h.avgCost) * h.quantity;
      const costValue = h.avgCost * h.quantity;
      
      totalValue += marketValue;
      totalCost += costValue;
      dailyChange += marketValue * (h.pct_chg || 0) / 100;
    });

    const totalProfit = totalValue - totalCost;
    const totalProfitPercent = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;

    return {
      totalValue,
      totalCost,
      totalProfit,
      totalProfitPercent,
      dailyChange,
      holdingsCount: holdings.length,
      formattedValue: Utils.formatPrice(totalValue),
      formattedProfit: Utils.formatPrice(totalProfit),
      formattedPercent: Utils.formatChange(totalProfitPercent),
      formattedDaily: Utils.formatChange(totalCost > 0 ? (dailyChange / totalCost) * 100 : 0)
    };
  }

  /**
   * 搜索股票
   * @param {string} keyword - 关键词
   * @returns {Promise<Array>} 搜索结果
   */
  async searchStocks(keyword) {
    if (!keyword || keyword.trim().length === 0) {
      return [];
    }

    // 先搜索本地数据库
    const localResults = this.searchLocalDatabase(keyword);
    
    try {
      // 再搜索API
      const apiResults = await stockAPI.search(keyword);
      
      // 合并结果（去重）
      const seen = new Set(localResults.map(r => r.symbol));
      const merged = [...localResults];
      
      apiResults.forEach(r => {
        if (!seen.has(r.symbol)) {
          merged.push(r);
        }
      });
      
      return merged.slice(0, 10); // 最多10条
    } catch (error) {
      console.error('[StockService] Search failed:', error);
      return localResults.slice(0, 10);
    }
  }

  /**
   * 搜索本地股票数据库
   * @private
   */
  searchLocalDatabase(keyword) {
    const results = [];
    const upperKeyword = keyword.toUpperCase();
    
    // 如果全局有股票数据库
    if (typeof STOCK_NAME_MAP !== 'undefined') {
      for (const [symbol, name] of Object.entries(STOCK_NAME_MAP)) {
        if (symbol.includes(upperKeyword) || name.includes(keyword)) {
          results.push({ symbol, name });
          if (results.length >= 10) break;
        }
      }
    }
    
    return results;
  }

  /**
   * 添加到自选
   * @param {string} symbol - 股票代码
   * @param {string} name - 股票名称
   */
  addToWatchlist(symbol, name) {
    if (!this.watchlist.find(w => w.symbol === symbol)) {
      this.watchlist.push({ symbol, name, addedAt: Date.now() });
      this.saveToStorage();
      this.notifySubscribers('watchlist', this.watchlist);
    }
  }

  /**
   * 从自选移除
   * @param {string} symbol - 股票代码
   */
  removeFromWatchlist(symbol) {
    const index = this.watchlist.findIndex(w => w.symbol === symbol);
    if (index >= 0) {
      this.watchlist.splice(index, 1);
      this.saveToStorage();
      this.notifySubscribers('watchlist', this.watchlist);
    }
  }

  /**
   * 启动自动更新
   * @private
   */
  startAutoUpdate() {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
    }

    this.updateInterval = setInterval(() => {
      if (this.holdings.length > 0) {
        this.getHoldingsWithPrice().then(data => {
          this.notifySubscribers('priceUpdate', data);
        });
      }
    }, CONFIG.APP.UPDATE_INTERVAL);
  }

  /**
   * 停止自动更新
   */
  stopAutoUpdate() {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
      this.updateInterval = null;
    }
  }

  /**
   * 订阅数据变化
   * @param {string} event - 事件名
   * @param {Function} callback - 回调函数
   */
  subscribe(event, callback) {
    if (!this.subscribers.has(event)) {
      this.subscribers.set(event, []);
    }
    this.subscribers.get(event).push(callback);
  }

  /**
   * 取消订阅
   */
  unsubscribe(event, callback) {
    if (this.subscribers.has(event)) {
      const callbacks = this.subscribers.get(event);
      const index = callbacks.indexOf(callback);
      if (index >= 0) {
        callbacks.splice(index, 1);
      }
    }
  }

  /**
   * 通知订阅者
   * @private
   */
  notifySubscribers(event, data) {
    if (this.subscribers.has(event)) {
      this.subscribers.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('[StockService] Subscriber error:', error);
        }
      });
    }
  }

  /**
   * 从本地存储加载
   * @private
   */
  loadFromStorage() {
    try {
      const holdingsData = localStorage.getItem('minirock_holdings');
      const watchlistData = localStorage.getItem('minirock_watchlist');
      
      if (holdingsData) {
        this.holdings = JSON.parse(holdingsData);
      }
      if (watchlistData) {
        this.watchlist = JSON.parse(watchlistData);
      }
    } catch (error) {
      console.error('[StockService] Failed to load from storage:', error);
    }
  }

  /**
   * 保存到本地存储
   * @private
   */
  saveToStorage() {
    try {
      localStorage.setItem('minirock_holdings', JSON.stringify(this.holdings));
      localStorage.setItem('minirock_watchlist', JSON.stringify(this.watchlist));
    } catch (error) {
      console.error('[StockService] Failed to save to storage:', error);
    }
  }
}

// 创建单例
const stockService = new StockService();

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { StockService, stockService };
} else {
  window.StockService = StockService;
  window.stockService = stockService;
}
