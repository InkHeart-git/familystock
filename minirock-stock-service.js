// MiniRock Stock Data Service
// 支持Tushare API和双价格显示

const API_BASE_URL = window.location.origin.includes('localhost') 
    ? 'http://localhost:8080/api/v3'
    : 'http://43.160.193.165/api/v3';

// 汇率配置（简化版，实际应从API获取）
const EXCHANGE_RATE = {
    CNY_TO_USD: 0.138,  // 1人民币 = 0.138美元
    USD_TO_CNY: 7.25    // 1美元 = 7.25人民币
};

/**
 * 获取单只股票数据
 */
async function getStockData(symbol) {
    try {
        // 调用后端Tushare API
        const response = await fetch(`${API_BASE_URL}/tushare/quote/${symbol}`);
        if (!response.ok) {
            throw new Error('API请求失败');
        }
        const data = await response.json();
        
        // 添加双价格
        return {
            ...data,
            localPrice: data.close,
            localCurrency: 'CNY',
            usdPrice: (data.close * EXCHANGE_RATE.CNY_TO_USD).toFixed(2),
            usdCurrency: 'USD'
        };
    } catch (error) {
        console.error('获取股票数据失败:', error);
        // API失败时返回null，不显示假数据
        return null;
    }
}

/**
 * 批量获取股票数据
 */
async function getMultipleStocks(symbols) {
    try {
        const symbolStr = symbols.join(',');
        const response = await fetch(`${API_BASE_URL}/tushare/batch?symbols=${symbolStr}`);
        if (!response.ok) {
            throw new Error('API请求失败');
        }
        const result = await response.json();
        
        // 添加双价格
        return result.stocks.map(stock => ({
            ...stock,
            localPrice: stock.close,
            localCurrency: 'CNY',
            usdPrice: (stock.close * EXCHANGE_RATE.CNY_TO_USD).toFixed(2),
            usdCurrency: 'USD'
        }));
    } catch (error) {
        console.error('批量获取失败:', error);
        // API失败时返回null
        return null;
    }
}

/**
 * 搜索股票
 */
async function searchStocks(keyword) {
    try {
        const response = await fetch(`${API_BASE_URL}/tushare/search?keyword=${encodeURIComponent(keyword)}`);
        if (!response.ok) {
            throw new Error('搜索失败');
        }
        const result = await response.json();
        return result.results || [];
    } catch (error) {
        console.error('搜索失败:', error);
        return [];
    }
}

/**
 * 计算AI评分（简化版）
 */
function calculateAIScore(changePercent) {
    let score = 50;
    
    if (changePercent > 5) score += 15;
    else if (changePercent > 2) score += 10;
    else if (changePercent > 0) score += 5;
    else if (changePercent < -5) score -= 15;
    else if (changePercent < -2) score -= 10;
    else if (changePercent < 0) score -= 5;
    
    const volatility = Math.abs(changePercent);
    if (volatility > 8) score -= 5;
    
    score = Math.max(0, Math.min(100, score));
    
    return {
        score: score,
        recommendation: score >= 70 ? '推荐' : score >= 50 ? '观望' : '谨慎'
    };
}

/**
 * 生成模拟数据（fallback）
 */
function generateMockStockData(symbol) {
    const basePrices = {
        '600519': 1680, '000858': 145, '000568': 168,
        '000651': 35, '000725': 3.8, '002230': 48,
        '002415': 32, '002594': 245, '300750': 198
    };
    
    // 使用全局的 STOCK_NAME_MAP 获取名称，支持所有A股和ETF
    const stockName = (typeof STOCK_NAME_MAP !== 'undefined' && STOCK_NAME_MAP[symbol]) 
        ? STOCK_NAME_MAP[symbol] 
        : symbol;
    
    const basePrice = basePrices[symbol] || 50;
    const changePercent = (Math.random() * 6 - 3).toFixed(2);
    const price = (basePrice * (1 + changePercent / 100)).toFixed(2);
    
    const aiScore = calculateAIScore(parseFloat(changePercent));
    
    return {
        symbol: symbol,
        name: stockName,
        close: parseFloat(price),
        open: parseFloat((basePrice * (1 + (Math.random() * 2 - 1) / 100)).toFixed(2)),
        high: parseFloat((basePrice * 1.02).toFixed(2)),
        low: parseFloat((basePrice * 0.98).toFixed(2)),
        pct_chg: parseFloat(changePercent),
        volume: Math.floor(Math.random() * 1000000),
        market: 'A股',
        currency: 'CNY',
        localPrice: parseFloat(price),
        localCurrency: 'CNY',
        usdPrice: (parseFloat(price) * EXCHANGE_RATE.CNY_TO_USD).toFixed(2),
        usdCurrency: 'USD',
        aiScore: aiScore.score,
        recommendation: aiScore.recommendation,
        isMock: true
    };
}

/**
 * 格式化价格显示
 */
function formatPrice(price, currency) {
    if (currency === 'CNY') {
        return '¥' + parseFloat(price).toFixed(2);
    } else if (currency === 'USD') {
        return '$' + parseFloat(price).toFixed(2);
    }
    return price;
}

/**
 * 格式化涨跌幅
 */
function formatChange(percent) {
    const sign = percent >= 0 ? '+' : '';
    return `${sign}${percent.toFixed(2)}%`;
}

/**
 * 获取AI评分样式类
 */
function getAIScoreClass(score) {
    if (score >= 70) return '';
    if (score >= 50) return 'warning';
    return 'danger';
}

/**
 * 获取涨跌幅样式类
 */
function getChangeClass(percent) {
    if (percent > 0) return 'change-up';
    if (percent < 0) return 'change-down';
    return '';
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getStockData,
        getMultipleStocks,
        searchStocks,
        calculateAIScore,
        formatPrice,
        formatChange,
        getAIScoreClass,
        getChangeClass
    };
}
