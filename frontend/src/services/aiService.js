/**
 * MiniRock v2.0 - AI 分析服务
 * 封装AI分析相关业务逻辑
 */

class AIService {
  constructor() {
    this.analysisCache = new Map();
    this.lastAnalysis = null;
  }

  /**
   * 分析持仓组合
   * @param {Array} holdings - 持仓数据（带实时价格）
   * @returns {Promise<Object>} 分析报告
   */
  async analyzePortfolio(holdings) {
    if (!holdings || holdings.length === 0) {
      return this.getEmptyAnalysis();
    }

    // 检查缓存
    const cacheKey = this.getCacheKey(holdings);
    if (this.analysisCache.has(cacheKey)) {
      const cached = this.analysisCache.get(cacheKey);
      if (Date.now() - cached.timestamp < 300000) { // 5分钟缓存
        return cached.data;
      }
    }

    try {
      // 尝试调用后端AI API
      const apiResult = await aiAPI.analyzeHoldings(holdings);
      
      // 如果API返回有效结果，使用API结果
      if (apiResult && apiResult.totalScore > 0) {
        const analysis = this.enrichAnalysis(apiResult, holdings);
        this.cacheAnalysis(cacheKey, analysis);
        this.lastAnalysis = analysis;
        return analysis;
      }
    } catch (error) {
      console.warn('[AIService] API analysis failed, using local calculation:', error);
    }

    // 本地计算分析结果
    const localAnalysis = this.calculateLocalAnalysis(holdings);
    this.cacheAnalysis(cacheKey, localAnalysis);
    this.lastAnalysis = localAnalysis;
    
    return localAnalysis;
  }

  /**
   * 本地计算分析
   * @private
   */
  calculateLocalAnalysis(holdings) {
    const scores = holdings.map(h => ({
      ...h,
      aiScore: h.aiScore || aiAPI.calculateLocalScore(h).score
    }));

    // 计算各项指标
    const technicalScore = this.calculateTechnicalScore(scores);
    const fundamentalScore = this.calculateFundamentalScore(scores);
    const riskScore = this.calculateRiskScore(scores);
    const diversityScore = this.calculateDiversityScore(scores);
    
    const totalScore = Math.round(
      (technicalScore + fundamentalScore + riskScore + diversityScore) / 4
    );

    // 生成建议
    const suggestions = this.generateSuggestions(scores, totalScore);
    const risks = this.identifyRisks(scores);

    return {
      totalScore,
      riskLevel: totalScore >= 70 ? 'low' : totalScore >= 50 ? 'medium' : 'high',
      technicalScore,
      fundamentalScore,
      riskScore,
      diversityScore,
      holdings: scores,
      suggestions,
      risks,
      timestamp: Date.now(),
      isLocal: true
    };
  }

  /**
   * 计算技术面评分
   * @private
   */
  calculateTechnicalScore(holdings) {
    if (holdings.length === 0) return 50;
    
    const avgChange = holdings.reduce((sum, h) => {
      return sum + (h.pct_chg || 0);
    }, 0) / holdings.length;

    let score = 50;
    if (avgChange > 2) score += 20;
    else if (avgChange > 0) score += 10;
    else if (avgChange < -2) score -= 20;
    else if (avgChange < 0) score -= 10;

    return Math.max(0, Math.min(100, score));
  }

  /**
   * 计算基本面评分
   * @private
   */
  calculateFundamentalScore(holdings) {
    if (holdings.length === 0) return 50;
    
    // 基于盈亏情况评分
    const profitableCount = holdings.filter(h => (h.profit || 0) > 0).length;
    const ratio = profitableCount / holdings.length;
    
    return Math.round(50 + ratio * 40);
  }

  /**
   * 计算风险评分
   * @private
   */
  calculateRiskScore(holdings) {
    if (holdings.length === 0) return 50;

    // 计算波动率
    const volatilities = holdings.map(h => Math.abs(h.pct_chg || 0));
    const avgVolatility = volatilities.reduce((a, b) => a + b, 0) / volatilities.length;
    
    // 波动率越高，风险评分越低
    let score = 100 - avgVolatility * 3;
    
    // 持仓集中度风险
    const totalValue = holdings.reduce((sum, h) => sum + ((h.close || 0) * h.quantity), 0);
    const maxHolding = holdings.reduce((max, h) => {
      const value = (h.close || 0) * h.quantity;
      return value > max ? value : max;
    }, 0);
    
    if (maxHolding / totalValue > 0.5) {
      score -= 15; // 单只股票占比超50%，扣分
    }

    return Math.max(0, Math.min(100, score));
  }

  /**
   * 计算分散度评分
   * @private
   */
  calculateDiversityScore(holdings) {
    if (holdings.length === 0) return 50;
    if (holdings.length < 3) return 40;
    if (holdings.length < 5) return 60;
    if (holdings.length < 10) return 80;
    return 90;
  }

  /**
   * 生成建议
   * @private
   */
  generateSuggestions(holdings, totalScore) {
    const suggestions = [];

    // 根据总评分给出建议
    if (totalScore >= 70) {
      suggestions.push({ type: 'good', text: '整体持仓表现良好，建议继续持有' });
    } else if (totalScore >= 50) {
      suggestions.push({ type: 'info', text: '持仓整体平稳，可关注市场变化' });
    } else {
      suggestions.push({ type: 'warning', text: '建议关注持仓风险，考虑调整策略' });
    }

    // 针对个股的建议
    const lowScoreStocks = holdings.filter(h => (h.aiScore || 50) < 40);
    if (lowScoreStocks.length > 0) {
      suggestions.push({
        type: 'warning',
        text: `${lowScoreStocks.length}只股票AI评分较低，建议关注`
      });
    }

    // 盈亏建议
    const lossStocks = holdings.filter(h => (h.profit || 0) < 0);
    if (lossStocks.length > holdings.length * 0.5) {
      suggestions.push({
        type: 'warning',
        text: '超过半数的持仓处于亏损状态，建议重新评估'
      });
    }

    return suggestions;
  }

  /**
   * 识别风险
   * @private
   */
  identifyRisks(holdings) {
    const risks = [];

    // 高波动风险
    const highVolatility = holdings.filter(h => Math.abs(h.pct_chg || 0) > 5);
    if (highVolatility.length > 0) {
      risks.push({
        type: 'volatility',
        level: 'high',
        text: `${highVolatility.length}只股票今日波动超过5%`,
        stocks: highVolatility.map(h => h.symbol)
      });
    }

    // 连续亏损风险
    const lossStocks = holdings.filter(h => (h.profitPercent || 0) < -10);
    if (lossStocks.length > 0) {
      risks.push({
        type: 'loss',
        level: 'medium',
        text: `${lossStocks.length}只股票亏损超过10%`,
        stocks: lossStocks.map(h => h.symbol)
      });
    }

    return risks;
  }

  /**
   * 获取个股AI评分
   * @param {string} symbol - 股票代码
   * @param {Object} stockData - 股票数据
   * @returns {Object} 评分结果
   */
  getStockScore(symbol, stockData) {
    return aiAPI.calculateLocalScore(stockData);
  }

  /**
   * 批量获取AI评分
   * @param {Array} stocks - 股票列表
   * @returns {Array} 评分列表
   */
  getBatchScores(stocks) {
    return stocks.map(stock => ({
      symbol: stock.symbol,
      ...this.getStockScore(stock.symbol, stock)
    }));
  }

  /**
   * 获取上次分析结果
   */
  getLastAnalysis() {
    return this.lastAnalysis;
  }

  /**
   * 清空缓存
   */
  clearCache() {
    this.analysisCache.clear();
  }

  /**
   * 生成缓存key
   * @private
   */
  getCacheKey(holdings) {
    const symbols = holdings.map(h => h.symbol).sort().join(',');
    return `analysis:${symbols}`;
  }

  /**
   * 缓存分析结果
   * @private
   */
  cacheAnalysis(key, data) {
    this.analysisCache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  /**
   * 丰富分析结果
   * @private
   */
  enrichAnalysis(apiResult, holdings) {
    return {
      ...apiResult,
      holdings,
      timestamp: Date.now(),
      isLocal: false
    };
  }

  /**
   * 获取空分析结果
   * @private
   */
  getEmptyAnalysis() {
    return {
      totalScore: 0,
      riskLevel: 'medium',
      technicalScore: 0,
      fundamentalScore: 0,
      riskScore: 0,
      diversityScore: 0,
      holdings: [],
      suggestions: [{ type: 'info', text: '暂无持仓数据' }],
      risks: [],
      timestamp: Date.now(),
      isEmpty: true
    };
  }
}

// 创建单例
const aiService = new AIService();

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { AIService, aiService };
} else {
  window.AIService = AIService;
  window.aiService = aiService;
}
