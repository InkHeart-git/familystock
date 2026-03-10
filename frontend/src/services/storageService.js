/**
 * MiniRock v2.0 - 存储服务
 * 统一封装 localStorage 操作
 */

class StorageService {
  constructor() {
    this.prefix = 'minirock_';
    this.cache = new Map();
    this.memoryFallback = new Map(); // 用于无痕模式
    
    // 检测是否支持 localStorage
    this.isSupported = this.checkStorageSupport();
  }

  /**
   * 检测存储支持
   * @private
   */
  checkStorageSupport() {
    try {
      const test = '__storage_test__';
      localStorage.setItem(test, test);
      localStorage.removeItem(test);
      return true;
    } catch (e) {
      console.warn('[StorageService] localStorage not supported, using memory fallback');
      return false;
    }
  }

  /**
   * 生成完整key
   * @private
   */
  getKey(key) {
    return `${this.prefix}${key}`;
  }

  /**
   * 设置数据
   * @param {string} key - 键名
   * @param {any} value - 值
   * @param {Object} options - 选项
   */
  set(key, value, options = {}) {
    const { expires = null, compress = false } = options;
    
    const data = {
      value,
      timestamp: Date.now(),
      expires: expires ? Date.now() + expires : null
    };

    const fullKey = this.getKey(key);

    try {
      if (this.isSupported) {
        localStorage.setItem(fullKey, JSON.stringify(data));
      } else {
        this.memoryFallback.set(fullKey, data);
      }
      
      this.cache.set(fullKey, data);
      return true;
    } catch (error) {
      // 存储空间不足
      if (error.name === 'QuotaExceededError') {
        console.warn('[StorageService] Storage quota exceeded, clearing old data');
        this.clearExpired();
        // 重试一次
        try {
          localStorage.setItem(fullKey, JSON.stringify(data));
          this.cache.set(fullKey, data);
          return true;
        } catch (e) {
          console.error('[StorageService] Failed to save after cleanup:', e);
        }
      }
      
      console.error('[StorageService] Save failed:', error);
      return false;
    }
  }

  /**
   * 获取数据
   * @param {string} key - 键名
   * @param {any} defaultValue - 默认值
   * @returns {any} 值
   */
  get(key, defaultValue = null) {
    const fullKey = this.getKey(key);

    // 先检查缓存
    if (this.cache.has(fullKey)) {
      const cached = this.cache.get(fullKey);
      if (!cached.expires || cached.expires > Date.now()) {
        return cached.value;
      }
    }

    // 从存储读取
    try {
      let data;
      
      if (this.isSupported) {
        const stored = localStorage.getItem(fullKey);
        if (!stored) return defaultValue;
        data = JSON.parse(stored);
      } else {
        data = this.memoryFallback.get(fullKey);
        if (!data) return defaultValue;
      }

      // 检查过期
      if (data.expires && data.expires <= Date.now()) {
        this.remove(key);
        return defaultValue;
      }

      // 更新缓存
      this.cache.set(fullKey, data);
      return data.value;

    } catch (error) {
      console.error('[StorageService] Get failed:', error);
      return defaultValue;
    }
  }

  /**
   * 移除数据
   * @param {string} key - 键名
   */
  remove(key) {
    const fullKey = this.getKey(key);
    
    try {
      if (this.isSupported) {
        localStorage.removeItem(fullKey);
      } else {
        this.memoryFallback.delete(fullKey);
      }
      this.cache.delete(fullKey);
      return true;
    } catch (error) {
      console.error('[StorageService] Remove failed:', error);
      return false;
    }
  }

  /**
   * 清空所有数据
   */
  clear() {
    try {
      if (this.isSupported) {
        // 只清除前缀匹配的数据
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const key = localStorage.key(i);
          if (key && key.startsWith(this.prefix)) {
            localStorage.removeItem(key);
          }
        }
      }
      
      this.memoryFallback.clear();
      this.cache.clear();
      return true;
    } catch (error) {
      console.error('[StorageService] Clear failed:', error);
      return false;
    }
  }

  /**
   * 获取所有key
   */
  keys() {
    const keys = [];
    
    try {
      if (this.isSupported) {
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key.startsWith(this.prefix)) {
            keys.push(key.slice(this.prefix.length));
          }
        }
      } else {
        for (const key of this.memoryFallback.keys()) {
          if (key.startsWith(this.prefix)) {
            keys.push(key.slice(this.prefix.length));
          }
        }
      }
    } catch (error) {
      console.error('[StorageService] Keys failed:', error);
    }
    
    return keys;
  }

  /**
   * 获取存储大小
   */
  getSize() {
    try {
      let size = 0;
      
      if (this.isSupported) {
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key.startsWith(this.prefix)) {
            size += localStorage.getItem(key).length * 2; // UTF-16
          }
        }
      } else {
        for (const [key, value] of this.memoryFallback) {
          if (key.startsWith(this.prefix)) {
            size += JSON.stringify(value).length * 2;
          }
        }
      }
      
      return {
        bytes: size,
        kb: (size / 1024).toFixed(2),
        mb: (size / 1024 / 1024).toFixed(2)
      };
    } catch (error) {
      console.error('[StorageService] GetSize failed:', error);
      return { bytes: 0, kb: '0.00', mb: '0.00' };
    }
  }

  /**
   * 清除过期数据
   */
  clearExpired() {
    try {
      const now = Date.now();
      let cleared = 0;
      
      if (this.isSupported) {
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const key = localStorage.key(i);
          if (key && key.startsWith(this.prefix)) {
            try {
              const data = JSON.parse(localStorage.getItem(key));
              if (data.expires && data.expires <= now) {
                localStorage.removeItem(key);
                this.cache.delete(key);
                cleared++;
              }
            } catch (e) {
              // 无效数据，删除
              localStorage.removeItem(key);
              cleared++;
            }
          }
        }
      }
      
      // 清理内存回退
      for (const [key, data] of this.memoryFallback) {
        if (key.startsWith(this.prefix)) {
          if (data.expires && data.expires <= now) {
            this.memoryFallback.delete(key);
            this.cache.delete(key);
            cleared++;
          }
        }
      }
      
      console.log(`[StorageService] Cleared ${cleared} expired items`);
      return cleared;
    } catch (error) {
      console.error('[StorageService] ClearExpired failed:', error);
      return 0;
    }
  }

  /**
   * 导出所有数据
   */
  export() {
    const data = {};
    
    try {
      if (this.isSupported) {
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key.startsWith(this.prefix)) {
            const shortKey = key.slice(this.prefix.length);
            data[shortKey] = this.get(shortKey);
          }
        }
      } else {
        for (const [key, value] of this.memoryFallback) {
          if (key.startsWith(this.prefix)) {
            const shortKey = key.slice(this.prefix.length);
            data[shortKey] = value.value;
          }
        }
      }
    } catch (error) {
      console.error('[StorageService] Export failed:', error);
    }
    
    return data;
  }

  /**
   * 导入数据
   */
  import(data) {
    try {
      for (const [key, value] of Object.entries(data)) {
        this.set(key, value);
      }
      return true;
    } catch (error) {
      console.error('[StorageService] Import failed:', error);
      return false;
    }
  }
}

// 创建单例
const storageService = new StorageService();

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { StorageService, storageService };
} else {
  window.StorageService = StorageService;
  window.storageService = storageService;
}
