/**
 * MiniRock Alert System
 * 实时预警系统
 */

// 预警配置
const ALERT_CONFIG = {
    // 预警阈值
    thresholds: {
        priceDrop: -10,      // 跌幅超10%预警
        priceRise: 20,       // 涨幅超20%预警
        aiScoreLow: 40,      // AI评分低于40预警
        volumeSpike: 3       // 成交量放大3倍预警
    },
    // 检查间隔（毫秒）
    checkInterval: 60000,  // 1分钟检查一次
    // 预警冷却时间（毫秒）
    cooldown: 300000       // 5分钟内不重复预警同一股票
};

// 预警状态
let alertSystemState = {
    isRunning: false,
    lastCheck: null,
    triggeredAlerts: new Map(), // 记录已触发的预警
    userSettings: {
        enabled: true,
        priceDrop: true,
        priceRise: true,
        aiScoreAlert: true,
        soundEnabled: true
    }
};

/**
 * 初始化预警系统
 */
function initAlertSystem() {
    if (alertSystemState.isRunning) return;
    
    console.log('🚨 MiniRock 预警系统已启动');
    alertSystemState.isRunning = true;
    
    // 立即检查一次
    checkAlerts();
    
    // 定时检查
    setInterval(() => {
        if (alertSystemState.userSettings.enabled) {
            checkAlerts();
        }
    }, ALERT_CONFIG.checkInterval);
    
    // 显示预警提示
    showAlertToast('预警系统已开启', 'success');
}

/**
 * 检查预警
 */
async function checkAlerts() {
    if (!holdings || holdings.length === 0) return;
    
    alertSystemState.lastCheck = new Date();
    const newAlerts = [];
    
    for (const stock of holdings) {
        const profitPct = ((stock.close - stock.avgCost) / stock.avgCost * 100);
        const aiScore = calculateAIScore(stock.pct_chg).score;
        
        // 检查各项预警条件
        const alerts = [];
        
        // 1. 暴跌预警
        if (alertSystemState.userSettings.priceDrop && profitPct <= ALERT_CONFIG.thresholds.priceDrop) {
            alerts.push({
                id: `${stock.symbol}_drop`,
                type: 'danger',
                icon: '📉',
                title: '暴跌预警',
                message: `${stock.name}(${stock.symbol}) 亏损达 ${Math.abs(profitPct).toFixed(1)}%`,
                stock: stock,
                value: profitPct,
                timestamp: Date.now()
            });
        }
        
        // 2. 暴涨预警
        if (alertSystemState.userSettings.priceRise && profitPct >= ALERT_CONFIG.thresholds.priceRise) {
            alerts.push({
                id: `${stock.symbol}_rise`,
                type: 'warning',
                icon: '📈',
                title: '止盈提醒',
                message: `${stock.name}(${stock.symbol}) 盈利达 ${profitPct.toFixed(1)}%`,
                stock: stock,
                value: profitPct,
                timestamp: Date.now()
            });
        }
        
        // 3. AI评分预警
        if (alertSystemState.userSettings.aiScoreAlert && aiScore <= ALERT_CONFIG.thresholds.aiScoreLow) {
            alerts.push({
                id: `${stock.symbol}_score`,
                type: 'warning',
                icon: '🤖',
                title: 'AI评分预警',
                message: `${stock.name}(${stock.symbol}) AI评分仅 ${aiScore}，技术面转弱`,
                stock: stock,
                value: aiScore,
                timestamp: Date.now()
            });
        }
        
        // 过滤已冷却的预警
        for (const alert of alerts) {
            if (!isAlertInCooldown(alert.id)) {
                newAlerts.push(alert);
                recordAlert(alert);
            }
        }
    }
    
    // 显示新预警
    if (newAlerts.length > 0) {
        displayAlerts(newAlerts);
    }
    
    return newAlerts;
}

/**
 * 检查预警是否在冷却期
 */
function isAlertInCooldown(alertId) {
    const lastTriggered = alertSystemState.triggeredAlerts.get(alertId);
    if (!lastTriggered) return false;
    
    return (Date.now() - lastTriggered) < ALERT_CONFIG.cooldown;
}

/**
 * 记录预警触发
 */
function recordAlert(alert) {
    alertSystemState.triggeredAlerts.set(alert.id, Date.now());
    
    // 保存到本地存储
    try {
        const history = JSON.parse(localStorage.getItem('minirock_alerts') || '[]');
        history.push({
            ...alert,
            date: new Date().toISOString()
        });
        // 只保留最近100条
        if (history.length > 100) history.shift();
        localStorage.setItem('minirock_alerts', JSON.stringify(history));
    } catch (e) {
        console.error('保存预警历史失败:', e);
    }
}

/**
 * 显示预警
 */
function displayAlerts(alerts) {
    // 播放提示音（如果开启）
    if (alertSystemState.userSettings.soundEnabled) {
        playAlertSound();
    }
    
    // 显示预警弹窗
    alerts.forEach((alert, index) => {
        setTimeout(() => {
            showAlertNotification(alert);
        }, index * 500);
    });
    
    // 更新预警角标
    updateAlertBadge(alerts.length);
}

/**
 * 显示预警通知
 */
function showAlertNotification(alert) {
    const notification = document.createElement('div');
    notification.className = `alert-notification ${alert.type}`;
    notification.innerHTML = `
        <div class="alert-notification-icon">${alert.icon}</div>
        <div class="alert-notification-content">
            <div class="alert-notification-title">${alert.title}</div>
            <div class="alert-notification-message">${alert.message}</div>
            <div class="alert-notification-time">${new Date().toLocaleTimeString('zh-CN')}</div>
        </div>
        <button class="alert-notification-close" onclick="this.parentElement.remove()">✕</button>
    `;
    
    // 添加到页面
    let container = document.getElementById('alertNotifications');
    if (!container) {
        container = document.createElement('div');
        container.id = 'alertNotifications';
        container.className = 'alert-notifications-container';
        document.body.appendChild(container);
    }
    
    container.appendChild(notification);
    
    // 自动移除
    setTimeout(() => {
        notification.classList.add('hiding');
        setTimeout(() => notification.remove(), 300);
    }, 8000);
}

/**
 * 播放提示音
 */
function playAlertSound() {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    } catch (e) {
        console.log('播放提示音失败:', e);
    }
}

/**
 * 更新预警角标
 */
function updateAlertBadge(count) {
    let badge = document.getElementById('alertBadge');
    if (!badge) {
        // 在导航栏添加角标
        const navItems = document.querySelectorAll('.nav-item');
        const settingsNav = navItems[2]; // 设置按钮
        if (settingsNav) {
            badge = document.createElement('span');
            badge.id = 'alertBadge';
            badge.className = 'nav-badge';
            settingsNav.appendChild(badge);
        }
    }
    
    if (badge) {
        const currentCount = parseInt(badge.textContent) || 0;
        badge.textContent = currentCount + count;
        badge.style.display = 'inline-flex';
        
        // 闪烁效果
        badge.classList.add('pulse');
        setTimeout(() => badge.classList.remove('pulse'), 1000);
    }
}

/**
 * 显示预警设置
 */
function showAlertSettings() {
    const modal = document.createElement('div');
    modal.className = 'ai-modal show';
    modal.id = 'alertSettingsModal';
    modal.innerHTML = `
        <div class="ai-modal-content">
            <div class="ai-result-header">
                <button class="ai-close-btn" onclick="document.getElementById('alertSettingsModal').remove()">✕</button>
                <h3>⚙️ 预警设置</h3>
            </div>
            <div class="ai-result-body">
                <div class="alert-settings-list">
                    <div class="alert-setting-item">
                        <div class="setting-info">
                            <div class="setting-title">启用预警</div>
                            <div class="setting-desc">开启/关闭所有预警功能</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" id="alertMasterSwitch" ${alertSystemState.userSettings.enabled ? 'checked' : ''} onchange="toggleAlertSetting('enabled', this.checked)">
                            <span class="switch-slider"></span>
                        </label>
                    </div>
                    
                    <div class="alert-setting-item">
                        <div class="setting-info">
                            <div class="setting-title">📉 跌幅预警</div>
                            <div class="setting-desc">亏损超10%时提醒</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" ${alertSystemState.userSettings.priceDrop ? 'checked' : ''} onchange="toggleAlertSetting('priceDrop', this.checked)">
                            <span class="switch-slider"></span>
                        </label>
                    </div>
                    
                    <div class="alert-setting-item">
                        <div class="setting-info">
                            <div class="setting-title">📈 止盈提醒</div>
                            <div class="setting-desc">盈利超20%时提醒</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" ${alertSystemState.userSettings.priceRise ? 'checked' : ''} onchange="toggleAlertSetting('priceRise', this.checked)">
                            <span class="switch-slider"></span>
                        </label>
                    </div>
                    
                    <div class="alert-setting-item">
                        <div class="setting-info">
                            <div class="setting-title">🤖 AI评分预警</div>
                            <div class="setting-desc">AI评分低于40时提醒</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" ${alertSystemState.userSettings.aiScoreAlert ? 'checked' : ''} onchange="toggleAlertSetting('aiScoreAlert', this.checked)">
                            <span class="switch-slider"></span>
                        </label>
                    </div>
                    
                    <div class="alert-setting-item">
                        <div class="setting-info">
                            <div class="setting-title">🔔 提示音</div>
                            <div class="setting-desc">预警时播放提示音</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" ${alertSystemState.userSettings.soundEnabled ? 'checked' : ''} onchange="toggleAlertSetting('soundEnabled', this.checked)">
                            <span class="switch-slider"></span>
                        </label>
                    </div>
                </div>
                
                <div class="ai-section" style="margin-top: 20px;">
                    <h4>📝 预警历史</h4>
                    <div id="alertHistoryList" class="alert-history-list">
                        <div class="loading-text">加载中...</div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    loadAlertHistory();
}

/**
 * 切换预警设置
 */
function toggleAlertSetting(key, value) {
    alertSystemState.userSettings[key] = value;
    
    // 保存到本地存储
    try {
        localStorage.setItem('minirock_alert_settings', JSON.stringify(alertSystemState.userSettings));
    } catch (e) {
        console.error('保存设置失败:', e);
    }
    
    showAlertToast(`${key === 'enabled' ? '预警系统' : '设置'}已${value ? '开启' : '关闭'}`, 'info');
}

/**
 * 加载预警历史
 */
function loadAlertHistory() {
    const listEl = document.getElementById('alertHistoryList');
    if (!listEl) return;
    
    try {
        const history = JSON.parse(localStorage.getItem('minirock_alerts') || '[]');
        
        if (history.length === 0) {
            listEl.innerHTML = '<div class="empty-state-small">暂无预警记录</div>';
            return;
        }
        
        // 显示最近10条
        listEl.innerHTML = history.slice(-10).reverse().map(item => `
            <div class="alert-history-item ${item.type}">
                <div class="alert-history-icon">${item.icon}</div>
                <div class="alert-history-content">
                    <div class="alert-history-title">${item.title}</div>
                    <div class="alert-history-message">${item.message}</div>
                    <div class="alert-history-date">${new Date(item.date).toLocaleString('zh-CN')}</div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        listEl.innerHTML = '<div class="empty-state-small">加载失败</div>';
    }
}

/**
 * 显示预警Toast
 */
function showAlertToast(message, type = 'info') {
    if (typeof showToast === 'function') {
        showToast(message, type);
    } else {
        console.log(`[${type}] ${message}`);
    }
}

/**
 * 加载设置
 */
function loadAlertSettings() {
    try {
        const saved = localStorage.getItem('minirock_alert_settings');
        if (saved) {
            alertSystemState.userSettings = { ...alertSystemState.userSettings, ...JSON.parse(saved) };
        }
    } catch (e) {
        console.error('加载设置失败:', e);
    }
}

// 页面加载时初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        loadAlertSettings();
        // 延迟启动预警系统
        setTimeout(initAlertSystem, 2000);
    });
} else {
    loadAlertSettings();
    setTimeout(initAlertSystem, 2000);
}

// 导出
try {
    window.AlertSystem = {
        init: initAlertSystem,
        check: checkAlerts,
        showSettings: showAlertSettings,
        toggleSetting: toggleAlertSetting
    };
} catch (e) {
    console.log('AlertSystem loaded');
}
