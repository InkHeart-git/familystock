/**
 * MiniRock 公共 JavaScript
 * 版本: 1.0.0
 * 用途: 统一所有页面的交互逻辑
 */

// ==================== 配置 ====================
const API_CONFIG = {
  baseURL: '/api'
};

// ==================== 工具函数 ====================

/**
 * 显示 Toast 提示
 * @param {string} message - 提示内容
 * @param {string} type - 类型: success/error/warning/info
 * @param {number} duration - 显示时长(毫秒)
 */
function showToast(message, type = 'info', duration = 3000) {
  // 移除已存在的 toast
  const existingToast = document.querySelector('.toast');
  if (existingToast) {
    existingToast.remove();
  }
  
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  
  // 触发显示动画
  requestAnimationFrame(() => {
    toast.classList.add('show');
  });
  
  // 自动隐藏
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/**
 * 格式化数字为价格
 * @param {number} num - 数字
 * @param {number} decimals - 小数位数
 */
function formatPrice(num, decimals = 2) {
  if (num === null || num === undefined || isNaN(num)) return '--';
  return num.toFixed(decimals);
}

/**
 * 格式化百分比
 * @param {number} num - 数字
 */
function formatPercent(num) {
  if (num === null || num === undefined || isNaN(num)) return '--';
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}%`;
}

/**
 * 格式化大数字 (万/亿)
 * @param {number} num - 数字
 */
function formatAmount(num) {
  if (num === null || num === undefined || isNaN(num)) return '--';
  if (num >= 100000000) {
    return (num / 100000000).toFixed(2) + '亿';
  } else if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万';
  }
  return num.toFixed(2);
}

/**
 * 获取当前登录用户
 */
function getCurrentUser() {
  try {
    const userStr = localStorage.getItem('minirock_user');
    return userStr ? JSON.parse(userStr) : null;
  } catch (e) {
    return null;
  }
}

/**
 * 获取用户ID
 */
function getUserId() {
  const user = getCurrentUser();
  return user?.phone || user?.id || 'demo_user';
}

/**
 * 检查是否已同意风险提示
 */
function hasAgreedRisk() {
  return localStorage.getItem('minirock_risk_agreed') === 'true';
}

/**
 * 设置已同意风险提示
 */
function setRiskAgreed() {
  localStorage.setItem('minirock_risk_agreed', 'true');
}

/**
 * 显示风险提示弹窗
 * @param {Function} onConfirm - 确认后的回调
 */
function showRiskModal(onConfirm) {
  // 检查是否已同意
  if (hasAgreedRisk()) {
    if (onConfirm) onConfirm();
    return;
  }
  
  // 创建弹窗
  const modal = document.createElement('div');
  modal.className = 'risk-modal active';
  modal.id = 'riskModal';
  modal.innerHTML = `
    <div class="risk-modal-content">
      <div class="risk-modal-icon">⚠️</div>
      <div class="risk-modal-title">投资风险提示</div>
      <div class="risk-modal-text">
        <p>1. 本模拟平台仅供学习和体验，不构成任何投资建议。</p>
        <p>2. 股市有风险，投资需谨慎。过往业绩不代表未来表现。</p>
        <p>3. 请根据自身风险承受能力谨慎决策，切勿盲目跟风。</p>
        <p>4. 模拟交易盈亏均为虚拟数据，不影响实际资产。</p>
      </div>
      <label class="risk-modal-checkbox">
        <input type="checkbox" id="riskCheckbox">
        <span>我已充分了解并自愿承担投资风险</span>
      </label>
      <button class="risk-modal-btn" id="riskConfirmBtn" disabled>我已了解，进入平台</button>
    </div>
  `;
  
  document.body.appendChild(modal);
  
  // 绑定事件
  const checkbox = modal.querySelector('#riskCheckbox');
  const confirmBtn = modal.querySelector('#riskConfirmBtn');
  
  checkbox.addEventListener('change', () => {
    confirmBtn.disabled = !checkbox.checked;
  });
  
  confirmBtn.addEventListener('click', () => {
    if (checkbox.checked) {
      setRiskAgreed();
      modal.classList.remove('active');
      setTimeout(() => {
        modal.remove();
        if (onConfirm) onConfirm();
      }, 300);
    }
  });
  
  // 点击遮罩关闭
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      // 可选：点击遮罩不关闭，强制用户选择
    }
  });
}

/**
 * 创建底部导航栏
 * @param {string} activePage - 当前活动页面: home/market/watchlist/me
 */
function createBottomNav(activePage = 'home') {
  const nav = document.createElement('div');
  nav.className = 'bottom-nav';
  nav.innerHTML = `
    <div class="nav-items">
      <a href="/minirock-v2.html" class="nav-item ${activePage === 'home' ? 'active' : ''}">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
        <span>首页</span>
      </a>
      <a href="/market.html" class="nav-item ${activePage === 'market' ? 'active' : ''}">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
        <span>行情</span>
      </a>
      <a href="/watchlist.html" class="nav-item ${activePage === 'watchlist' ? 'active' : ''}">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
        </svg>
        <span>自选</span>
      </a>
      <a href="/portfolio.html" class="nav-item ${activePage === 'portfolio' ? 'active' : ''}">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        <span>我的</span>
      </a>
    </div>
  `;
  return nav;
}

/**
 * 创建顶部导航栏
 * @param {Object} options - 配置选项
 * @param {string} options.title - 标题
 * @param {boolean} options.showBack - 是否显示返回按钮
 * @param {string} options.backUrl - 返回链接
 * @param {Array} options.actions - 右侧操作按钮
 */
function createHeader(options = {}) {
  const { title = 'MiniRock', showBack = false, backUrl = '/', actions = [] } = options;
  
  const header = document.createElement('div');
  header.className = 'app-header';
  
  let actionsHtml = '';
  if (actions.length > 0) {
    actionsHtml = actions.map(action => `
      <button class="nav-icon" onclick="${action.onClick}" title="${action.title || ''}">
        ${action.icon}
      </button>
    `).join('');
  }
  
  header.innerHTML = `
    <div class="top-nav">
      ${showBack ? `
        <a href="${backUrl}" class="back-button">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          <span>返回</span>
        </a>
      ` : `<div class="app-title">${title}</div>`}
      <div class="nav-actions">
        ${actionsHtml}
      </div>
    </div>
  `;
  
  return header;
}

/**
 * API 请求封装
 * @param {string} url - 请求路径
 * @param {Object} options - fetch 选项
 */
async function apiRequest(url, options = {}) {
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json'
    }
  };
  
  const mergedOptions = { ...defaultOptions, ...options };
  
  try {
    const response = await fetch(`${API_CONFIG.baseURL}${url}`, mergedOptions);
    
    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('API请求失败:', error);
    showToast('请求失败，请稍后重试', 'error');
    throw error;
  }
}

/**
 * 防抖函数
 * @param {Function} fn - 要执行的函数
 * @param {number} delay - 延迟时间
 */
function debounce(fn, delay = 300) {
  let timer = null;
  return function(...args) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * 节流函数
 * @param {Function} fn - 要执行的函数
 * @param {number} limit - 限制时间
 */
function throttle(fn, limit = 300) {
  let inThrottle = false;
  return function(...args) {
    if (!inThrottle) {
      fn.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// ==================== 初始化 ====================

/**
 * 初始化页面
 * @param {Object} options - 初始化选项
 */
function initPage(options = {}) {
  const { showRisk = true, onRiskConfirm } = options;
  
  // 页面加载完成后执行
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      if (showRisk) {
        showRiskModal(onRiskConfirm);
      }
    });
  } else {
    if (showRisk) {
      showRiskModal(onRiskConfirm);
    }
  }
}

// 导出到全局
window.MiniRock = {
  showToast,
  formatPrice,
  formatPercent,
  formatAmount,
  getCurrentUser,
  getUserId,
  hasAgreedRisk,
  setRiskAgreed,
  showRiskModal,
  createBottomNav,
  createHeader,
  apiRequest,
  debounce,
  throttle,
  initPage,
  API_CONFIG
};
