/**
 * MiniRock API Service - 生产版本
 * 前端API服务层 - 对接方舟后端接口
 * 更新时间: 2026-03-14 11:45
 */

const API_CONFIG = {
  baseURL: '/api',
  timeout: 10000
};

// API请求封装
async function apiRequest(endpoint, options = {}) {
  const url = `${API_CONFIG.baseURL}${endpoint}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || `API错误: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('请求超时，请检查网络');
    }
    console.error(`API请求失败: ${endpoint}`, error);
    throw error;
  }
}

// ==================== 股票搜索API ====================
const StockAPI = {
  // 搜索股票（代码/名称/拼音）
  async search(keyword, limit = 10) {
    if (!keyword || keyword.length < 1) return { results: [] };
    return await apiRequest(`/tushare/search?q=${encodeURIComponent(keyword)}&limit=${limit}`);
  },
  
  // 获取股票行情
  async getQuote(symbol) {
    return await apiRequest(`/tushare/quote?symbol=${symbol}`);
  },
  
  // 批量获取行情
  async getBatchQuotes(symbols) {
    if (!symbols || symbols.length === 0) return [];
    return await apiRequest('/tushare/quote/batch', {
      method: 'POST',
      body: JSON.stringify({ symbols })
    });
  }
};

// ==================== 持仓管理API ====================
const PortfolioAPI = {
  // 获取持仓列表
  async getHoldings() {
    return await apiRequest('/portfolio');
  },
  
  // 添加持仓
  async addHolding(data) {
    return await apiRequest('/portfolio/holdings?user_id=demo_user', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  
  // 更新持仓
  async updateHolding(id, data) {
    return await apiRequest(`/portfolio/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  },
  
  // 删除持仓
  async deleteHolding(id) {
    return await apiRequest(`/portfolio/${id}`, {
      method: 'DELETE'
    });
  }
};

// ==================== 自选股API ====================
const WatchlistAPI = {
  // 获取自选股列表
  async getWatchlist() {
    return await apiRequest('/watchlist');
  },
  
  // 添加自选股
  async addToWatchlist(symbol) {
    return await apiRequest('/watchlist', {
      method: 'POST',
      body: JSON.stringify({ symbol })
    });
  },
  
  // 删除自选股
  async removeFromWatchlist(symbol) {
    return await apiRequest(`/watchlist/${symbol}`, {
      method: 'DELETE'
    });
  }
};

// ==================== 情景推演API ====================
const ScenarioAPI = {
  // 投资情景推演
  async simulate(portfolioData, marketScenario) {
    return await apiRequest('/scenario/simulate', {
      method: 'POST',
      body: JSON.stringify({
        portfolio: portfolioData,
        scenario: marketScenario || 'neutral'
      })
    });
  }
};

// ==================== 认证API ====================
const AuthAPI = {
  // 登录
  async login(credentials) {
    const result = await apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials)
    });
    if (result.token) {
      localStorage.setItem('minirock_token', result.token);
    }
    return result;
  },
  
  // 注册
  async register(data) {
    return await apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  
  // 发送验证码
  async sendVerifyCode(phone) {
    return await apiRequest('/auth/verify-code', {
      method: 'POST',
      body: JSON.stringify({ phone })
    });
  },
  
  // 获取token
  getToken() {
    return localStorage.getItem('minirock_token');
  },
  
  // 退出登录
  logout() {
    localStorage.removeItem('minirock_token');
    localStorage.removeItem('disclaimerAgreed');
  }
};

// 导出API模块
window.MiniRockAPI = {
  config: API_CONFIG,
  request: apiRequest,
  Stock: StockAPI,
  Portfolio: PortfolioAPI,
  Watchlist: WatchlistAPI,
  Scenario: ScenarioAPI,
  Auth: AuthAPI
};

// 页面加载完成后初始化
console.log('✅ MiniRock API Service 加载完成');
console.log('可用API:', Object.keys(window.MiniRockAPI));