/**
 * MiniRock v2.0 - 统一 API Client
 * 所有网络请求必须通过此 client
 */

class APIClient {
  constructor() {
    this.baseURL = CONFIG.API.BASE_URL;
    this.timeout = CONFIG.API.TIMEOUT;
    this.retryCount = CONFIG.API.RETRY_COUNT;
    this.retryDelay = CONFIG.API.RETRY_DELAY;
    this.cache = new Map();
    
    // 请求拦截器
    this.interceptors = {
      request: [],
      response: [],
      error: []
    };
    
    console.log('[API] Client initialized, baseURL:', this.baseURL);
  }

  /**
   * 添加请求拦截器
   */
  addRequestInterceptor(fn) {
    this.interceptors.request.push(fn);
  }

  /**
   * 添加响应拦截器
   */
  addResponseInterceptor(fn) {
    this.interceptors.response.push(fn);
  }

  /**
   * 添加错误拦截器
   */
  addErrorInterceptor(fn) {
    this.interceptors.error.push(fn);
  }

  /**
   * 生成缓存 key
   */
  getCacheKey(url, params) {
    return `${url}:${JSON.stringify(params || {})}`;
  }

  /**
   * 检查缓存
   */
  getFromCache(key) {
    const cached = this.cache.get(key);
    if (!cached) return null;
    
    if (Date.now() - cached.timestamp > CONFIG.API.CACHE_TTL) {
      this.cache.delete(key);
      return null;
    }
    
    return cached.data;
  }

  /**
   * 设置缓存
   */
  setCache(key, data) {
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  /**
   * 清除缓存
   */
  clearCache() {
    this.cache.clear();
  }

  /**
   * 核心请求方法
   */
  async request(endpoint, options = {}) {
    const { 
      method = 'GET', 
      params = null, 
      body = null, 
      useCache = false,
      headers = {} 
    } = options;

    let url = `${this.baseURL}${endpoint}`;
    
    // 添加查询参数
    if (params) {
      const queryString = new URLSearchParams(params).toString();
      url += `?${queryString}`;
    }

    // 检查缓存
    const cacheKey = this.getCacheKey(url, params);
    if (useCache && method === 'GET') {
      const cached = this.getFromCache(cacheKey);
      if (cached) {
        console.log('[API] Cache hit:', endpoint);
        return cached;
      }
    }

    // 请求配置
    const fetchOptions = {
      method,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...headers
      }
    };

    if (body) {
      fetchOptions.body = JSON.stringify(body);
    }

    // 执行请求拦截器
    let finalOptions = fetchOptions;
    for (const interceptor of this.interceptors.request) {
      finalOptions = await interceptor(finalOptions) || finalOptions;
    }

    // 执行请求（带重试）
    let lastError;
    for (let attempt = 0; attempt < this.retryCount; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);
        
        finalOptions.signal = controller.signal;
        
        console.log(`[API] Request ${attempt + 1}/${this.retryCount}:`, method, url);
        const response = await fetch(url, finalOptions);
        
        clearTimeout(timeoutId);

        // 检查 HTTP 状态
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        // 解析响应
        const data = await response.json();

        // 执行响应拦截器
        let finalData = data;
        for (const interceptor of this.interceptors.response) {
          finalData = await interceptor(finalData) || finalData;
        }

        // 缓存响应
        if (useCache && method === 'GET') {
          this.setCache(cacheKey, finalData);
        }

        return finalData;

      } catch (error) {
        lastError = error;
        console.warn(`[API] Attempt ${attempt + 1} failed:`, error.message);
        
        if (attempt < this.retryCount - 1) {
          await this.delay(this.retryDelay * (attempt + 1));
        }
      }
    }

    // 所有重试失败
    console.error('[API] All retries failed:', lastError);
    
    // 执行错误拦截器
    for (const interceptor of this.interceptors.error) {
      await interceptor(lastError);
    }

    throw lastError;
  }

  /**
   * GET 请求
   */
  async get(endpoint, params = null, options = {}) {
    return this.request(endpoint, { 
      method: 'GET', 
      params, 
      ...options 
    });
  }

  /**
   * POST 请求
   */
  async post(endpoint, body = null, options = {}) {
    return this.request(endpoint, { 
      method: 'POST', 
      body, 
      ...options 
    });
  }

  /**
   * PUT 请求
   */
  async put(endpoint, body = null, options = {}) {
    return this.request(endpoint, { 
      method: 'PUT', 
      body, 
      ...options 
    });
  }

  /**
   * DELETE 请求
   */
  async delete(endpoint, options = {}) {
    return this.request(endpoint, { 
      method: 'DELETE', 
      ...options 
    });
  }

  /**
   * 延迟
   */
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// 创建单例
const apiClient = new APIClient();

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { APIClient, apiClient };
} else {
  window.APIClient = APIClient;
  window.apiClient = apiClient;
}
