/**
 * MiniRock AI Analysis Service
 * AI评估和预警服务
 */

const AI_API_BASE = window.location.origin.includes('localhost') 
    ? 'http://localhost:8080/api/v3'
    : 'http://43.160.193.165:8080/api/v3';

// 分析状态
let aiAnalysisState = {
    isAnalyzing: false,
    progress: 0,
    currentStep: '',
    result: null
};

/**
 * AI持仓体检 - 带进度动画
 */
async function performAICheckWithAnimation() {
    if (aiAnalysisState.isAnalyzing) return;
    
    aiAnalysisState.isAnalyzing = true;
    aiAnalysisState.progress = 0;
    
    // 显示AI分析弹窗
    showAIAnalysisModal();
    
    // 模拟分析步骤
    const steps = [
        { progress: 10, text: '正在获取市场数据...', duration: 800 },
        { progress: 25, text: '分析技术面指标...', duration: 1000 },
        { progress: 45, text: '评估基本面数据...', duration: 1000 },
        { progress: 65, text: '计算AI评分模型...', duration: 1200 },
        { progress: 80, text: '生成风险预警...', duration: 800 },
        { progress: 95, text: '优化投资建议...', duration: 600 },
        { progress: 100, text: '分析完成！', duration: 300 }
    ];
    
    for (const step of steps) {
        await updateAIProgress(step.progress, step.text);
        await sleep(step.duration);
    }
    
    // 执行真实分析
    try {
        const result = await performRealAIAnalysis();
        aiAnalysisState.result = result;
        showAIAnalysisResult(result);
    } catch (error) {
        console.error('AI分析失败:', error);
        showAIAnalysisError();
    }
    
    aiAnalysisState.isAnalyzing = false;
}

/**
 * 执行真实AI分析
 */
async function performRealAIAnalysis() {
    // 构建持仓数据
    const holdingsData = holdings.map(h => ({
        symbol: h.symbol,
        name: h.name,
        quantity: h.quantity,
        avg_cost: h.avgCost,
        current_price: h.close,
        profit_pct: ((h.close - h.avgCost) / h.avgCost * 100),
        ai_score: calculateAIScore(h.pct_chg).score,
        market_value: h.close * h.quantity
    }));
    
    // 计算各项评分
    const technicalScore = calculateTechnicalScore(holdingsData);
    const riskScore = calculateRiskScore(holdingsData);
    const diversityScore = calculateDiversityScore(holdingsData);
    const totalScore = Math.round((technicalScore + riskScore + diversityScore) / 3);
    
    // 生成建议
    const suggestions = generateSuggestions(holdingsData, totalScore);
    
    // 检测预警
    const alerts = detectAlerts(holdingsData);
    
    return {
        totalScore,
        technicalScore,
        riskScore,
        diversityScore,
        holdings: holdingsData,
        suggestions,
        alerts,
        timestamp: new Date().toISOString()
    };
}

/**
 * 计算技术面评分
 */
function calculateTechnicalScore(holdings) {
    if (holdings.length === 0) return 50;
    
    let totalScore = 0;
    holdings.forEach(h => {
        let score = 50;
        const profitPct = h.profit_pct;
        
        // 盈利加分
        if (profitPct > 20) score += 20;
        else if (profitPct > 10) score += 15;
        else if (profitPct > 0) score += 10;
        else if (profitPct > -10) score -= 5;
        else score -= 15;
        
        // AI评分加权
        score = score * 0.6 + h.ai_score * 0.4;
        
        totalScore += Math.max(0, Math.min(100, score));
    });
    
    return Math.round(totalScore / holdings.length);
}

/**
 * 计算风险评分
 */
function calculateRiskScore(holdings) {
    if (holdings.length === 0) return 50;
    
    // 检查是否有高风险持仓
    const highRiskCount = holdings.filter(h => h.profit_pct < -10).length;
    const concentratedRisk = holdings.length > 0 && 
        (holdings[0].market_value / holdings.reduce((a, b) => a + b.market_value, 0)) > 0.5;
    
    let score = 70;
    score -= highRiskCount * 15;
    if (concentratedRisk) score -= 10;
    
    return Math.max(0, Math.min(100, score));
}

/**
 * 计算分散度评分
 */
function calculateDiversityScore(holdings) {
    if (holdings.length === 0) return 0;
    if (holdings.length === 1) return 30;
    if (holdings.length === 2) return 50;
    if (holdings.length >= 3) return 70 + Math.min(30, holdings.length * 5);
    return 50;
}

/**
 * 生成投资建议
 */
function generateSuggestions(holdings, totalScore) {
    const suggestions = [];
    
    // 基于总评分
    if (totalScore >= 80) {
        suggestions.push({ type: 'good', text: '整体组合表现优秀，可继续保持' });
    } else if (totalScore >= 60) {
        suggestions.push({ type: 'info', text: '组合表现平稳，关注个别弱势标的' });
    } else {
        suggestions.push({ type: 'warning', text: '组合风险较高，建议优化配置' });
    }
    
    // 基于个股分析
    const losers = holdings.filter(h => h.profit_pct < -10);
    if (losers.length > 0) {
        suggestions.push({ 
            type: 'warning', 
            text: `${losers.map(h => h.name).join('、')}亏损超10%，建议评估是否继续持有` 
        });
    }
    
    const winners = holdings.filter(h => h.profit_pct > 20);
    if (winners.length > 0) {
        suggestions.push({ 
            type: 'good', 
            text: `${winners.map(h => h.name).join('、')}盈利超20%，可考虑部分止盈` 
        });
    }
    
    // 分散度建议
    if (holdings.length < 3) {
        suggestions.push({ type: 'info', text: '持仓较为集中，建议适当分散投资' });
    }
    
    return suggestions;
}

/**
 * 检测预警
 */
function detectAlerts(holdings) {
    const alerts = [];
    
    holdings.forEach(h => {
        // 暴跌预警
        if (h.profit_pct < -15) {
            alerts.push({
                level: 'danger',
                symbol: h.symbol,
                name: h.name,
                type: 'loss',
                message: `${h.name}亏损超15%，建议密切关注`,
                value: h.profit_pct
            });
        }
        // 暴涨预警
        else if (h.profit_pct > 25) {
            alerts.push({
                level: 'warning',
                symbol: h.symbol,
                name: h.name,
                type: 'gain',
                message: `${h.name}盈利超25%，可考虑止盈`,
                value: h.profit_pct
            });
        }
        // 低评分预警
        if (h.ai_score < 40) {
            alerts.push({
                level: 'warning',
                symbol: h.symbol,
                name: h.name,
                type: 'low_score',
                message: `${h.name}AI评分偏低(${h.ai_score})，技术面走弱`,
                value: h.ai_score
            });
        }
    });
    
    return alerts;
}

/**
 * 显示AI分析弹窗
 */
function showAIAnalysisModal() {
    const modal = document.createElement('div');
    modal.id = 'aiAnalysisModal';
    modal.className = 'ai-modal';
    modal.innerHTML = `
        <div class="ai-modal-content">
            <div class="ai-analysis-header">
                <div class="ai-avatar">🤖</div>
                <h3>AI 正在分析您的持仓...</h3>
            </div>
            <div class="ai-progress-container">
                <div class="ai-progress-bar">
                    <div class="ai-progress-fill" id="aiProgressFill" style="width: 0%"></div>
                </div>
                <div class="ai-progress-text" id="aiProgressText">准备开始...</div>
            </div>
            <div class="ai-analysis-steps">
                <div class="ai-step active" id="step1">📊 市场数据</div>
                <div class="ai-step" id="step2">📈 技术指标</div>
                <div class="ai-step" id="step3">🎯 AI评分</div>
                <div class="ai-step" id="step4">⚠️ 风险预警</div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // 触发显示动画
    setTimeout(() => modal.classList.add('show'), 10);
}

/**
 * 更新进度
 */
async function updateAIProgress(progress, text) {
    const fill = document.getElementById('aiProgressFill');
    const textEl = document.getElementById('aiProgressText');
    
    if (fill) fill.style.width = progress + '%';
    if (textEl) textEl.textContent = text;
    
    // 更新步骤高亮
    const stepIndex = Math.min(3, Math.floor(progress / 25));
    for (let i = 1; i <= 4; i++) {
        const step = document.getElementById(`step${i}`);
        if (step) {
            step.classList.toggle('active', i <= stepIndex + 1);
            step.classList.toggle('completed', i <= stepIndex);
        }
    }
}

/**
 * 显示AI分析结果
 */
function showAIAnalysisResult(result) {
    const modal = document.getElementById('aiAnalysisModal');
    if (!modal) return;
    
    // 计算风险等级
    const riskLevel = result.totalScore >= 70 ? 'low' : (result.totalScore >= 50 ? 'medium' : 'high');
    const riskText = { low: '低风险', medium: '中等风险', high: '高风险' }[riskLevel];
    const riskEmoji = { low: '🟢', medium: '🟡', high: '🔴' }[riskLevel];
    
    // 生成预警HTML
    const alertsHtml = result.alerts.length > 0 ? `
        <div class="ai-section ai-alerts">
            <h4>⚠️ 预警提醒 (${result.alerts.length}条)</h4>
            ${result.alerts.map(alert => `
                <div class="alert-item ${alert.level}">
                    <span class="alert-icon">${alert.level === 'danger' ? '🔴' : '🟡'}</span>
                    <span class="alert-text">${alert.message}</span>
                </div>
            `).join('')}
        </div>
    ` : '<div class="ai-section ai-alerts"><h4>✅ 暂无预警</h4><p>您的持仓暂无异常波动</p></div>';
    
    modal.innerHTML = `
        <div class="ai-modal-content ai-result">
            <div class="ai-result-header">
                <button class="ai-close-btn" onclick="closeAIAnalysis()">✕</button>
                <div class="ai-score-circle">
                    <svg viewBox="0 0 100 100">
                        <circle class="score-bg" cx="50" cy="50" r="45"/>
                        <circle class="score-fill ${riskLevel}" cx="50" cy="50" r="45" 
                                stroke-dasharray="${result.totalScore * 2.83} 283"/>
                    </svg>
                    <div class="score-value">${result.totalScore}</div>
                </div>
                <div class="ai-score-info">
                    <div class="risk-badge ${riskLevel}">${riskEmoji} ${riskText}</div>
                    <div class="analysis-time">${new Date().toLocaleString('zh-CN')}</div>
                </div>
            </div>
            
            <div class="ai-result-body">
                <div class="ai-score-breakdown">
                    <div class="score-item">
                        <div class="score-label">技术面</div>
                        <div class="score-bar">
                            <div class="score-fill-bar" style="width: ${result.technicalScore}%"></div>
                        </div>
                        <div class="score-number">${result.technicalScore}</div>
                    </div>
                    <div class="score-item">
                        <div class="score-label">风险度</div>
                        <div class="score-bar">
                            <div class="score-fill-bar" style="width: ${result.riskScore}%"></div>
                        </div>
                        <div class="score-number">${result.riskScore}</div>
                    </div>
                    <div class="score-item">
                        <div class="score-label">分散度</div>
                        <div class="score-bar">
                            <div class="score-fill-bar" style="width: ${result.diversityScore}%"></div>
                        </div>
                        <div class="score-number">${result.diversityScore}</div>
                    </div>
                </div>
                
                ${alertsHtml}
                
                <div class="ai-section ai-suggestions">
                    <h4>💡 AI建议</h4>
                    ${result.suggestions.map(s => `
                        <div class="suggestion-item ${s.type}">
                            <span class="suggestion-icon">${s.type === 'good' ? '✅' : s.type === 'warning' ? '⚠️' : 'ℹ️'}</span>
                            <span>${s.text}</span>
                        </div>
                    `).join('')}
                </div>
                
                <div class="ai-section ai-holdings-detail">
                    <h4>📊 持仓分析</h4>
                    ${result.holdings.map(h => {
                        const isProfit = h.profit_pct >= 0;
                        return `
                            <div class="holding-detail-item">
                                <div class="holding-info">
                                    <span class="holding-name">${h.name}</span>
                                    <span class="holding-symbol">${h.symbol}</span>
                                </div>
                                <div class="holding-metrics">
                                    <span class="holding-score">AI ${h.ai_score}</span>
                                    <span class="holding-profit ${isProfit ? 'up' : 'down'}">
                                        ${isProfit ? '+' : ''}${h.profit_pct.toFixed(2)}%
                                    </span>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
            
            <div class="ai-result-footer">
                <button class="btn btn-primary" onclick="closeAIAnalysis()">我知道了</button>
                <button class="btn btn-secondary" onclick="shareAIReport()">分享报告</button>
            </div>
        </div>
    `;
}

/**
 * 显示分析错误
 */
function showAIAnalysisError() {
    const modal = document.getElementById('aiAnalysisModal');
    if (modal) {
        modal.innerHTML = `
            <div class="ai-modal-content ai-error">
                <div class="error-icon">❌</div>
                <h3>分析失败</h3>
                <p>AI分析服务暂时不可用，请稍后重试</p>
                <button class="btn btn-primary" onclick="closeAIAnalysis()">关闭</button>
            </div>
        `;
    }
}

/**
 * 关闭AI分析弹窗
 */
function closeAIAnalysis() {
    const modal = document.getElementById('aiAnalysisModal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 300);
    }
}

/**
 * 分享AI报告
 */
function shareAIReport() {
    if (aiAnalysisState.result) {
        const text = `MiniRock AI评估报告\n综合评分: ${aiAnalysisState.result.totalScore}/100\n${aiAnalysisState.result.alerts.length > 0 ? '⚠️ 有' + aiAnalysisState.result.alerts.length + '条预警' : '✅ 暂无预警'}\n#MiniRock #AI投资`;
        
        if (navigator.share) {
            navigator.share({ title: 'MiniRock AI评估报告', text });
        } else {
            navigator.clipboard.writeText(text).then(() => {
                showToast('报告已复制到剪贴板', 'success');
            });
        }
    }
}

/**
 * 工具函数
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// 导出
try {
    window.AIService = {
        performAICheckWithAnimation,
        performRealAIAnalysis,
        closeAIAnalysis
    };
} catch (e) {
    console.log('AIService loaded');
}
