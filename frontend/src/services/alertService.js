/**
 * MiniRock v2.0 - 预警服务
 * 实时监控持仓并提供预警功能
 */

class AlertService {
  constructor() {
    this.alerts = [];
    this.triggeredAlerts = new Map();
    this.settings = this.getDefaultSettings();
    this.checkInterval = null;
    this.isRunning = false;
    this.subscribers = [];
    
    this.loadSettings();
  }

  /**
   * 获取默认设置
   * @private
   */
  getDefaultSettings() {
    return {
      enabled: true,
      priceDrop: true,
      priceRise: true,
      aiScoreAlert: true,
      volumeAlert: false,
      soundEnabled: true,
      pushEnabled: false,
      thresholds: {
        priceDrop: -10,      // 跌幅10%预警
        priceRise: 20,       // 涨幅20%预警
        aiScoreLow: 40,      // AI评分低于40
        volumeMultiplier: 3  // 成交量放大3倍
      }
    };
  }

  /**
   * 初始化服务
   */
  init() {
    if (this.isRunning) return;
    
    this.isRunning = true;
    this.startMonitoring();
    console.log('[AlertService] Initialized');
  }

  /**
   * 启动监控
   */
  startMonitoring() {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
    }

    this.checkInterval = setInterval(() => {
      if (this.settings.enabled) {
        this.checkAlerts();
      }
    }, CONFIG.ALERT.CHECK_INTERVAL);
  }

  /**
   * 停止监控
   */
  stopMonitoring() {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
    this.isRunning = false;
  }

  /**
   * 检查预警条件
   */
  async checkAlerts() {
    const holdings = await stockService.getHoldingsWithPrice();
    const newAlerts = [];

    for (const stock of holdings) {
      const alerts = this.checkStockAlerts(stock);
      newAlerts.push(...alerts);
    }

    if (newAlerts.length > 0) {
      this.processNewAlerts(newAlerts);
    }
  }

  /**
   * 检查单只股票预警
   * @private
   */
  checkStockAlerts(stock) {
    const alerts = [];
    const profitPercent = stock.profitPercent || 0;
    const aiScore = stock.aiScore || 50;

    // 暴跌预警
    if (this.settings.priceDrop && profitPercent <= this.settings.thresholds.priceDrop) {
      alerts.push({
        id: `${stock.symbol}_drop_${Date.now()}`,
        type: 'danger',
        icon: '📉',
        title: '暴跌预警',
        message: `${stock.name}(${stock.symbol}) 跌幅超 ${Math.abs(profitPercent).toFixed(1)}%`,
        symbol: stock.symbol,
        timestamp: Date.now()
      });
    }

    // 暴涨预警
    if (this.settings.priceRise && profitPercent >= this.settings.thresholds.priceRise) {
      alerts.push({
        id: `${stock.symbol}_rise_${Date.now()}`,
        type: 'success',
        icon: '📈',
        title: '暴涨预警',
        message: `${stock.name}(${stock.symbol}) 涨幅超 ${profitPercent.toFixed(1)}%`,
        symbol: stock.symbol,
        timestamp: Date.now()
      });
    }

    // AI评分预警
    if (this.settings.aiScoreAlert && aiScore <= this.settings.thresholds.aiScoreLow) {
      alerts.push({
        id: `${stock.symbol}_ai_${Date.now()}`,
        type: 'warning',
        icon: '🤖',
        title: 'AI评分预警',
        message: `${stock.name}(${stock.symbol}) AI评分降至 ${aiScore}`,
        symbol: stock.symbol,
        timestamp: Date.now()
      });
    }

    return alerts;
  }

  /**
   * 处理新预警
   * @private
   */
  processNewAlerts(alerts) {
    for (const alert of alerts) {
      // 检查冷却期
      const lastTriggered = this.triggeredAlerts.get(alert.symbol);
      if (lastTriggered && Date.now() - lastTriggered < CONFIG.ALERT.COOLDOWN) {
        continue;
      }

      // 记录触发时间
      this.triggeredAlerts.set(alert.symbol, Date.now());

      // 添加到预警列表
      this.alerts.unshift({
        ...alert,
        read: false
      });

      // 通知订阅者
      this.notifySubscribers(alert);

      // 播放声音
      if (this.settings.soundEnabled) {
        this.playAlertSound(alert.type);
      }
    }

    // 保存预警历史
    this.saveAlerts();
  }

  /**
   * 播放预警声音
   * @private
   */
  playAlertSound(type) {
    // 简单的 beep 声音
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      if (type === 'danger') {
        oscillator.frequency.value = 880; // 高频
        gainNode.gain.value = 0.3;
      } else if (type === 'warning') {
        oscillator.frequency.value = 660; // 中频
        gainNode.gain.value = 0.2;
      } else {
        oscillator.frequency.value = 440; // 低频
        gainNode.gain.value = 0.1;
      }

      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.1);
    } catch (error) {
      console.warn('[AlertService] Failed to play sound:', error);
    }
  }

  /**
   * 获取所有预警
   */
  getAlerts(options = {}) {
    const { unreadOnly = false, type = null, limit = 50 } = options;
    
    let filtered = this.alerts;
    
    if (unreadOnly) {
      filtered = filtered.filter(a => !a.read);
    }
    
    if (type) {
      filtered = filtered.filter(a => a.type === type);
    }
    
    return filtered.slice(0, limit);
  }

  /**
   * 获取未读预警数量
   */
  getUnreadCount() {
    return this.alerts.filter(a => !a.read).length;
  }

  /**
   * 标记为已读
   */
  markAsRead(alertId) {
    const alert = this.alerts.find(a => a.id === alertId);
    if (alert) {
      alert.read = true;
      this.saveAlerts();
    }
  }

  /**
   * 标记全部为已读
   */
  markAllAsRead() {
    this.alerts.forEach(a => a.read = true);
    this.saveAlerts();
  }

  /**
   * 清除预警
   */
  clearAlerts() {
    this.alerts = [];
    this.saveAlerts();
  }

  /**
   * 更新设置
   */
  updateSettings(newSettings) {
    this.settings = { ...this.settings, ...newSettings };
    this.saveSettings();
  }

  /**
   * 获取设置
   */
  getSettings() {
    return { ...this.settings };
  }

  /**
   * 订阅预警通知
   */
  subscribe(callback) {
    this.subscribers.push(callback);
  }

  /**
   * 取消订阅
   */
  unsubscribe(callback) {
    const index = this.subscribers.indexOf(callback);
    if (index >= 0) {
      this.subscribers.splice(index, 1);
    }
  }

  /**
   * 通知订阅者
   * @private
   */
  notifySubscribers(alert) {
    this.subscribers.forEach(callback => {
      try {
        callback(alert);
      } catch (error) {
        console.error('[AlertService] Subscriber error:', error);
      }
    });
  }

  /**
   * 保存设置
   * @private
   */
  saveSettings() {
    try {
      localStorage.setItem('minirock_alert_settings', JSON.stringify(this.settings));
    } catch (error) {
      console.error('[AlertService] Failed to save settings:', error);
    }
  }

  /**
   * 加载设置
   * @private
   */
  loadSettings() {
    try {
      const saved = localStorage.getItem('minirock_alert_settings');
      if (saved) {
        this.settings = { ...this.getDefaultSettings(), ...JSON.parse(saved) };
      }
    } catch (error) {
      console.error('[AlertService] Failed to load settings:', error);
    }
  }

  /**
   * 保存预警历史
   * @private
   */
  saveAlerts() {
    try {
      // 只保存最近100条
      const toSave = this.alerts.slice(0, 100);
      localStorage.setItem('minirock_alerts', JSON.stringify(toSave));
    } catch (error) {
      console.error('[AlertService] Failed to save alerts:', error);
    }
  }

  /**
   * 加载预警历史
   * @private
   */
  loadAlerts() {
    try {
      const saved = localStorage.getItem('minirock_alerts');
      if (saved) {
        this.alerts = JSON.parse(saved);
      }
    } catch (error) {
      console.error('[AlertService] Failed to load alerts:', error);
    }
  }
}

// 创建单例
const alertService = new AlertService();

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { AlertService, alertService };
} else {
  window.AlertService = AlertService;
  window.alertService = alertService;
}
