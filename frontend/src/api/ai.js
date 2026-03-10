/**
 * MiniRock v2.0 - AI 分析 API
 * AI评估和分析相关接口
 */

class AIAPI {
  constructor(client) {
    this.client = client;
    this.basePath = '/ai';
  }

  /**
   * AI持仓体检
   * @param {Array} holdings - 持仓数据
   * @returns {Promise<Object>} AI分析报告
   */
  async analyzeHoldings(holdings) {
    if (!Array.isArray(holdings) || holdings.length === 0) {
      return this.getDefaultAnalysis();
    }

    try {
      const result = await this.client.post(`${this.basePath}/analyze`, {
        holdings: holdings.map(h => ({
          symbol: h.symbol,
          name: h.name,
          quantity: h.quantity,
          avgCost: h.avgCost,
          currentPrice: h.close || h.currentPrice
        }))
      });

      return this.normalizeAnalysisResult(result);
    } catch (error) {
      console.error('[AIAPI] Analysis failed:', error);
      // 返回默认分析结果，不抛错
      return this.getDefaultAnalysis();
    }
  }

  /**
   * 单只股票AI评分
   * @param {string} symbol - 股票代码
   * @returns {Promise<Object>} 评分结果
   */
  async getStockScore(symbol) {
    if (!symbol) {
      return null;
    }

    try {
      const result = await this.client.get(`${this.basePath}/score/${symbol}`);
      return {
        symbol,
        score: result.score || 50,
        recommendation: result.recommendation || '观望',
        factors: result.factors || {}
      };
    } catch (error) {
      console.error(`[AIAPI] Failed to get score for ${symbol}:`, error);
      // 返回基础评分
      return {
        symbol,
        score: 50,
        recommendation: '观望',
        factors: {}
      };
    }
  }

  /**
   * 批量获取AI评分
   * @param {string[]} symbols - 股票代码数组
   * @returns {Promise<Array>} 评分数组
   */
  async getBatchScores(symbols) {
    if (!Array.isArray(symbols) || symbols.length === 0) {
      return [];
    }

    try {
      const result = await this.client.post(`${this.basePath}/scores`, {
        symbols
      });

      return result.scores || [];
    } catch (error) {
      console.error('[AIAPI] Failed to get batch scores:', error);
      // 返回基础评分
      return symbols.map(symbol => ({
        symbol,
        score: 50,
        recommendation: '观望',
        factors: {}
      }));
    }
  }

  /**
   * 生成投资建议
   * @param {Object} params - 参数
   * @returns {Promise<Object>} 建议
   */
  async generateAdvice(params = {}) {
    try {
      const result = await this.client.post(`${this.basePath}/advice`, params);
      return {
        advice: result.advice || [],
        risks: result.risks || [],
        opportunities: result.opportunities || []
      };
    } catch (error) {
      console.error('[AIAPI] Failed to generate advice:', error);
      return {
        advice: ['建议关注市场动态'],
        risks: [],
        opportunities: []
      };
    }
  }

  /**
   * 规范化分析结果
   * @private
   */
  normalizeAnalysisResult(result) {
    return {
      totalScore: result.totalScore || result.score || 50,
      riskLevel: result.riskLevel || 'medium',
      technicalScore: result.technicalScore || 50,
      fundamentalScore: result.fundamentalScore || 50,
      riskScore: result.riskScore || 50,
      diversityScore: result.diversityScore || 50,
      suggestions: result.suggestions || result.advice || [],
      alerts: result.alerts || result.risks || [],
      timestamp: result.timestamp || Date.now()
    };
  }

  /**
   * 获取默认分析结果
   * @private
   */
  getDefaultAnalysis() {
    return {
      totalScore: 50,
      riskLevel: 'medium',
      technicalScore: 50,
      fundamentalScore: 50,
      riskScore: 50,
      diversityScore: 50,
      suggestions: ['暂无分析数据'],
      alerts: [],
      timestamp: Date.now()
    };
  }

  /**
   * 计算本地AI评分（无需API，客户端计算）
   * @param {Object} stock - 股票数据
   * @returns {Object} 评分结果
   */
  calculateLocalScore(stock) {
    if (!stock) {
      return { score: 50, recommendation: '观望' };
    }

    const changePercent = parseFloat(stock.pct_chg || stock.change || 0);
    let score = 50;

    // 基于涨跌幅计算基础分
    if (changePercent > 5) score += 15;
    else if (changePercent > 2) score += 10;
    else if (changePercent > 0) score += 5;
    else if (changePercent < -5) score -= 15;
    else if (changePercent < -2) score -= 10;
    else if (changePercent < 0) score -= 5;

    // 波动率调整
    const volatility = Math.abs(changePercent);
    if (volatility > 8) score -= 5;
    else if (volatility > 5) score -= 2;

    // 限制范围
    score = Math.max(0, Math.min(100, score));

    return {
      score: score,
      recommendation: score >= 70 ? '推荐' : score >= 50 ? '观望' : '谨慎'
    };
  }
}

// 创建实例
const aiAPI = new AIAPI(apiClient);

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { AIAPI, aiAPI };
} else {
  window.AIAPI = AIAPI;
  window.aiAPI = aiAPI;
}
