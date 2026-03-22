// 个性化话术系统前端SDK
const PersonalizationSDK = {
    // 上报用户行为
    reportBehavior: function(behaviorType, behaviorData = {}) {
        try {
            // 获取当前用户ID（实际从登录态获取）
            const userId = localStorage.getItem('user_id') || 'demo_user';
            
            // 收集设备信息
            const deviceType = /Mobile|Android|iPhone|iPad/.test(navigator.userAgent) ? 'mobile' : 'pc';
            const ipAddress = ''; // 服务端获取
            
            // 上报数据
            fetch('/api/personalization/behavior/report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: userId,
                    behavior_type: behaviorType,
                    behavior_data: behaviorData,
                    device_type: deviceType,
                    ip_address: ipAddress
                })
            }).catch(err => {
                console.warn('行为上报失败:', err);
            });
        } catch (e) {
            console.warn('行为上报异常:', e);
        }
    },
    
    // 获取用户偏好风格
    getUserStyle: function() {
        const userId = localStorage.getItem('user_id') || 'demo_user';
        return fetch('/api/personalization/style/' + userId)
            .then(res => res.json())
            .catch(err => {
                console.warn('获取用户风格失败:', err);
                return { data: { preferred_style: 'warm', confidence_score: 0.5 } };
            });
    },
    
    // 生成个性化分析
    generateAnalysis: function(stockData, newsList = []) {
        const userId = localStorage.getItem('user_id') || 'demo_user';
        return fetch('/api/personalization/analysis/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                stock_data: stockData,
                news_list: newsList
            })
        }).then(res => res.json())
        .catch(err => {
            console.warn('生成个性化分析失败:', err);
            return { data: { analysis: '分析生成失败，请重试', style_used: 'warm' } };
        });
    }
};

// 自动上报页面访问事件
document.addEventListener('DOMContentLoaded', function() {
    PersonalizationSDK.reportBehavior('page_view', {
        page: window.location.pathname,
        title: document.title
    });
});

// 自动上报点击事件
document.addEventListener('click', function(e) {
    const target = e.target;
    if (target.tagName === 'BUTTON' || target.tagName === 'A') {
        PersonalizationSDK.reportBehavior('element_click', {
            tag: target.tagName,
            text: target.textContent.trim().substring(0, 50),
            id: target.id,
            className: target.className
        });
    }
});

window.PersonalizationSDK = PersonalizationSDK;
