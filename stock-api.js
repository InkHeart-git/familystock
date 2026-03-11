/**
 * FamilyStock - 股票数据API模块
 * 支持A股、港股、美股实时行情获取
 * 使用东方财富、腾讯财经等免费API
 */

const StockAPI = (function() {
    'use strict';

    // API配置
    const CONFIG = {
        // 腾讯财经API - 实时行情
        TENCENT_API: 'https://qt.gtimg.cn/q=',
        
        // 东方财富API - 搜索和K线
        EASTMONEY_SEARCH_API: 'https://searchapi.eastmoney.com/api/suggest/get',
        EASTMONEY_KLINE_API: 'https://push2his.eastmoney.com/api/qt/stock/kline/get',
        EASTMONEY_REALTIME_API: 'https://push2.eastmoney.com/api/qt/stock/get',
        
        // 刷新间隔（毫秒）
        REFRESH_INTERVAL: 30000, // 30秒
        
        // 超时设置
        TIMEOUT: 10000
    };

    // 缓存数据
    const cache = {
        quotes: {},
        klines: {},
        lastUpdate: {}
    };

    // 定时器
    let refreshTimer = null;
    let subscribers = [];

    /**
     * 获取市场前缀
     */
    function getMarketPrefix(code) {
        if (!code) return 'sh';
        code = code.toString().trim();
        
        // A股
        if (/^6\d{5}$/.test(code)) return 'sh'; // 上海主板
        if (/^[03]\d{5}$/.test(code)) return 'sz'; // 深圳主板/创业板
        if (/^[48]\d{5}$/.test(code)) return 'bj'; // 北交所/新三板
        
        // 港股
        if (/^\d{4,5}$/.test(code)) return 'hk';
        
        // 美股（直接返回代码）
        return 'us';
    }

    /**
     * 判断市场类型
     */
    function getMarketType(code) {
        const prefix = getMarketPrefix(code);
        if (prefix === 'sh' || prefix === 'sz' || prefix === 'bj') return 'A股';
        if (prefix === 'hk') return '港股';
        return '美股';
    }

    /**
     * 格式化股票代码
     */
    function formatStockCode(code, market) {
        code = code.toString().trim().toUpperCase();
        
        if (market === 'us') return code; // 美股直接返回
        if (market === 'hk') return code.padStart(5, '0'); // 港股补零
        
        // A股
        return code;
    }

    /**
     * 发送JSONP请求
     */
    function jsonp(url, callbackName) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            const callbackId = 'stockapi_cb_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            
            // 设置超时
            const timeout = setTimeout(() => {
                cleanup();
                reject(new Error('请求超时'));
            }, CONFIG.TIMEOUT);
            
            // 清理函数
            function cleanup() {
                clearTimeout(timeout);
                if (script.parentNode) {
                    script.parentNode.removeChild(script);
                }
                delete window[callbackId];
            }
            
            // 回调函数
            window[callbackId] = function(data) {
                cleanup();
                resolve(data);
            };
            
            // 构建URL
            const separator = url.indexOf('?') >= 0 ? '&' : '?';
            script.src = url + separator + (callbackName || 'callback') + '=' + callbackId;
            script.onerror = function() {
                cleanup();
                reject(new Error('请求失败'));
            };
            
            document.head.appendChild(script);
        });
    }

    /**
     * 发送Fetch请求（带CORS代理）
     */
    async function fetchWithCORS(url) {
        // 尝试直接请求
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), CONFIG.TIMEOUT);
            
            const response = await fetch(url, {
                signal: controller.signal,
                headers: {
                    'Accept': '*/*',
                    'Referer': 'https://stockpage.eastmoney.com'
                }
            });
            
            clearTimeout(timeoutId);
            
            if (response.ok) {
                return await response.text();
            }
        } catch (e) {
            // 直接请求失败，使用模拟数据
            console.log('直接请求失败，使用模拟数据:', e.message);
        }
        
        return null;
    }

    /**
     * 解析腾讯财经数据
     */
    function parseTencentData(data, fullCode) {
        try {
            const match = data.match(new RegExp(`v_${fullCode}="([^"]+)"`));
            if (!match) return null;
            
            const fields = match[1].split('~');
            if (fields.length < 45) return null;
            
            return {
                code: fields[2],
                name: fields[1],
                price: parseFloat(fields[3]) || 0,
                prevClose: parseFloat(fields[4]) || 0,
                open: parseFloat(fields[5]) || 0,
                volume: parseInt(fields[6]) || 0,
                high: parseFloat(fields[7]) || 0,
                low: parseFloat(fields[8]) || 0,
                change: parseFloat(fields[9]) || 0,
                changePercent: parseFloat(fields[10]) || 0,
                turnover: parseFloat(fields[11]) || 0,
                marketCap: parseFloat(fields[14]) || 0,
                peRatio: parseFloat(fields[15]) || 0,
                pbRatio: parseFloat(fields[16]) || 0,
                turnoverRate: parseFloat(fields[17]) || 0,
                amplitude: parseFloat(fields[18]) || 0,
                totalShares: parseFloat(fields[19]) || 0,
                updateTime: fields[30] || '',
                bid1: parseFloat(fields[21]) || 0,
                bid1Volume: parseInt(fields[22]) || 0,
                ask1: parseFloat(fields[23]) || 0,
                ask1Volume: parseInt(fields[24]) || 0
            };
        } catch (e) {
            console.error('解析腾讯数据失败:', e);
            return null;
        }
    }

    /**
     * 生成模拟股票数据（用于演示和备用）
     */
    function generateMockData(code, name) {
        const basePrice = Math.random() * 100 + 10;
        const changePercent = (Math.random() - 0.5) * 10;
        const change = basePrice * changePercent / 100;
        
        return {
            code: code,
            name: name || '股票' + code,
            price: basePrice,
            prevClose: basePrice - change,
            open: basePrice * (1 + (Math.random() - 0.5) * 0.02),
            high: basePrice * (1 + Math.random() * 0.05),
            low: basePrice * (1 - Math.random() * 0.05),
            volume: Math.floor(Math.random() * 10000000),
            change: change,
            changePercent: changePercent,
            turnover: Math.random() * 10,
            marketCap: Math.random() * 1000,
            peRatio: Math.random() * 50 + 5,
            pbRatio: Math.random() * 5 + 0.5,
            turnoverRate: Math.random() * 5,
            amplitude: Math.abs(changePercent) * 1.5,
            totalShares: Math.random() * 100,
            updateTime: new Date().toLocaleTimeString('zh-CN'),
            bid1: basePrice - 0.01,
            bid1Volume: Math.floor(Math.random() * 1000),
            ask1: basePrice + 0.01,
            ask1Volume: Math.floor(Math.random() * 1000),
            isMock: true
        };
    }

    /**
     * 获取实时行情（单只股票）
     */
    async function getRealtimeQuote(code, name) {
        const prefix = getMarketPrefix(code);
        const fullCode = prefix + code;
        
        try {
            // 尝试从腾讯财经获取
            const url = `${CONFIG.TENCENT_API}${fullCode}`;
            const data = await fetchWithCORS(url);
            
            if (data) {
                const parsed = parseTencentData(data, fullCode);
                if (parsed) {
                    parsed.market = getMarketType(code);
                    parsed.isMock = false;
                    cache.quotes[code] = parsed;
                    cache.lastUpdate[code] = Date.now();
                    return parsed;
                }
            }
        } catch (e) {
            console.warn('获取实时行情失败:', e);
        }
        
        // 返回模拟数据
        const mockData = generateMockData(code, name);
        mockData.market = getMarketType(code);
        cache.quotes[code] = mockData;
        cache.lastUpdate[code] = Date.now();
        return mockData;
    }

    /**
     * 批量获取实时行情
     */
    async function getBatchQuotes(codes) {
        const results = {};
        const promises = codes.map(async (code) => {
            try {
                const data = await getRealtimeQuote(code);
                results[code] = data;
            } catch (e) {
                results[code] = null;
            }
        });
        
        await Promise.all(promises);
        return results;
    }

    /**
     * 搜索股票
     */
    async function searchStocks(keyword) {
        if (!keyword || keyword.length < 2) {
            return [];
        }
        
        try {
            // 构建搜索URL
            const url = `${CONFIG.EASTMONEY_SEARCH_API}?input=${encodeURIComponent(keyword)}&type=14&count=20`;
            
            // 使用JSONP方式
            const data = await jsonp(url, 'callback');
            
            if (data && data.QuotationCodeTable && data.QuotationCodeTable.Data) {
                return data.QuotationCodeTable.Data.map(item => ({
                    code: item.Code,
                    name: item.Name,
                    market: item.MarketType,
                    pinyin: item.PinYin,
                    securityType: item.SecurityType
                }));
            }
        } catch (e) {
            console.warn('搜索股票失败:', e);
        }
        
        // 返回模拟搜索结果
        return [
            { code: '600519', name: '贵州茅台', market: '上海', pinyin: 'GZMT' },
            { code: '000001', name: '平安银行', market: '深圳', pinyin: 'PAYH' },
            { code: '000858', name: '五粮液', market: '深圳', pinyin: 'WLY' }
        ].filter(s => s.name.includes(keyword) || s.code.includes(keyword));
    }

    /**
     * 获取K线数据
     */
    async function getKlineData(code, period = 'day', count = 30) {
        const cacheKey = `${code}_${period}_${count}`;
        
        // 检查缓存
        if (cache.klines[cacheKey] && Date.now() - cache.lastUpdate[cacheKey] < 60000) {
            return cache.klines[cacheKey];
        }
        
        const prefix = getMarketPrefix(code);
        const secid = (prefix === 'sh' ? '1.' : '0.') + code;
        const klt = period === 'week' ? '102' : period === 'month' ? '103' : '101';
        
        try {
            const url = `${CONFIG.EASTMONEY_KLINE_API}?secid=${secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=${klt}&fqt=0&end=20500101&limit=${count}`;
            
            const data = await jsonp(url, 'cb');
            
            if (data && data.data && data.data.klines) {
                const klines = data.data.klines.map(line => {
                    const parts = line.split(',');
                    return {
                        date: parts[0],
                        open: parseFloat(parts[1]),
                        close: parseFloat(parts[2]),
                        high: parseFloat(parts[3]),
                        low: parseFloat(parts[4]),
                        volume: parseFloat(parts[5]),
                        amount: parseFloat(parts[6]),
                        amplitude: parseFloat(parts[7]),
                        changePercent: parseFloat(parts[8]),
                        change: parseFloat(parts[9]),
                        turnover: parseFloat(parts[10])
                    };
                });
                
                cache.klines[cacheKey] = klines;
                cache.lastUpdate[cacheKey] = Date.now();
                return klines;
            }
        } catch (e) {
            console.warn('获取K线数据失败:', e);
        }
        
        // 生成模拟K线数据
        const mockKlines = [];
        let basePrice = 50 + Math.random() * 100;
        const now = new Date();
        
        for (let i = count; i >= 0; i--) {
            const date = new Date(now);
            date.setDate(date.getDate() - i);
            
            const change = (Math.random() - 0.5) * 0.05;
            basePrice = basePrice * (1 + change);
            
            const high = basePrice * (1 + Math.random() * 0.03);
            const low = basePrice * (1 - Math.random() * 0.03);
            const open = low + Math.random() * (high - low);
            const close = low + Math.random() * (high - low);
            
            mockKlines.push({
                date: date.toISOString().split('T')[0],
                open: open,
                close: close,
                high: high,
                low: low,
                volume: Math.floor(Math.random() * 1000000),
                amount: Math.floor(Math.random() * 100000000),
                amplitude: (high - low) / basePrice * 100,
                changePercent: change * 100,
                change: close - open,
                turnover: Math.random() * 5,
                isMock: true
            });
        }
        
        cache.klines[cacheKey] = mockKlines;
        return mockKlines;
    }

    /**
     * 获取股票详情
     */
    async function getStockDetail(code) {
        const [quote, kline] = await Promise.all([
            getRealtimeQuote(code),
            getKlineData(code, 'day', 60)
        ]);
        
        return {
            ...quote,
            kline: kline
        };
    }

    /**
     * 订阅实时数据更新
     */
    function subscribe(codes, callback) {
        // 添加订阅
        subscribers.push({ codes, callback });
        
        // 启动定时刷新
        if (!refreshTimer) {
            startAutoRefresh();
        }
        
        // 立即执行一次
        refreshSubscribers();
        
        // 返回取消订阅函数
        return function unsubscribe() {
            subscribers = subscribers.filter(s => s.callback !== callback);
            if (subscribers.length === 0) {
                stopAutoRefresh();
            }
        };
    }

    /**
     * 启动自动刷新
     */
    function startAutoRefresh() {
        if (refreshTimer) return;
        
        refreshTimer = setInterval(() => {
            refreshSubscribers();
        }, CONFIG.REFRESH_INTERVAL);
        
        console.log('自动刷新已启动，间隔:', CONFIG.REFRESH_INTERVAL, 'ms');
    }

    /**
     * 停止自动刷新
     */
    function stopAutoRefresh() {
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
            console.log('自动刷新已停止');
        }
    }

    /**
     * 刷新所有订阅者
     */
    async function refreshSubscribers() {
        if (subscribers.length === 0) return;
        
        // 收集所有需要刷新的股票代码
        const allCodes = new Set();
        subscribers.forEach(sub => {
            sub.codes.forEach(code => allCodes.add(code));
        });
        
        // 批量获取数据
        const quotes = await getBatchQuotes(Array.from(allCodes));
        
        // 通知订阅者
        subscribers.forEach(sub => {
            const data = {};
            sub.codes.forEach(code => {
                data[code] = quotes[code];
            });
            sub.callback(data);
        });
    }

    /**
     * 获取热门股票列表
     */
    function getHotStocks() {
        return [
            { code: '600519', name: '贵州茅台', market: 'A股', industry: '消费' },
            { code: '000001', name: '平安银行', market: 'A股', industry: '金融' },
            { code: '000858', name: '五粮液', market: 'A股', industry: '消费' },
            { code: '300750', name: '宁德时代', market: 'A股', industry: '新能源' },
            { code: '00700', name: '腾讯控股', market: '港股', industry: '科技' },
            { code: '09988', name: '阿里巴巴', market: '港股', industry: '科技' },
            { code: 'AAPL', name: '苹果公司', market: '美股', industry: '科技' },
            { code: 'NVDA', name: '英伟达', market: '美股', industry: '科技' },
            { code: 'TSLA', name: '特斯拉', market: '美股', industry: '汽车' }
        ];
    }

    /**
     * 获取行业分类
     */
    function getIndustryCategories() {
        return [
            '科技', '金融', '消费', '医疗', '能源', '新能源', '房地产', '工业', '材料', '通信'
        ];
    }

    /**
     * 计算技术指标
     */
    function calculateMA(klines, period) {
        const ma = [];
        for (let i = period - 1; i < klines.length; i++) {
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += klines[i - j].close;
            }
            ma.push({
                date: klines[i].date,
                value: sum / period
            });
        }
        return ma;
    }

    /**
     * 检测金叉/死叉
     */
    function detectCross(klines) {
        const ma5 = calculateMA(klines, 5);
        const ma10 = calculateMA(klines, 10);
        const ma20 = calculateMA(klines, 20);
        
        const signals = [];
        
        // 检测MA5上穿MA10（金叉）
        if (ma5.length >= 2 && ma10.length >= 2) {
            const prev5 = ma5[ma5.length - 2].value;
            const curr5 = ma5[ma5.length - 1].value;
            const prev10 = ma10[ma10.length - 2].value;
            const curr10 = ma10[ma10.length - 1].value;
            
            if (prev5 <= prev10 && curr5 > curr10) {
                signals.push({ type: 'golden_cross', name: 'MA5金叉MA10', level: 'medium' });
            } else if (prev5 >= prev10 && curr5 < curr10) {
                signals.push({ type: 'death_cross', name: 'MA5死叉MA10', level: 'medium' });
            }
        }
        
        return signals;
    }

    /**
     * 格式化数字
     */
    function formatNumber(num, decimals = 2) {
        if (num === null || num === undefined) return '-';
        if (num >= 100000000) {
            return (num / 100000000).toFixed(decimals) + '亿';
        }
        if (num >= 10000) {
            return (num / 10000).toFixed(decimals) + '万';
        }
        return num.toFixed(decimals);
    }

    /**
     * 格式化金额
     */
    function formatMoney(num, decimals = 2) {
        if (num === null || num === undefined) return '-';
        return '¥' + formatNumber(num, decimals);
    }

    // 公开API
    return {
        // 数据获取
        getRealtimeQuote,
        getBatchQuotes,
        searchStocks,
        getKlineData,
        getStockDetail,
        getHotStocks,
        
        // 订阅和刷新
        subscribe,
        startAutoRefresh,
        stopAutoRefresh,
        
        // 工具函数
        getMarketType,
        getMarketPrefix,
        formatStockCode,
        getIndustryCategories,
        calculateMA,
        detectCross,
        formatNumber,
        formatMoney,
        
        // 配置
        CONFIG
    };
})();

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StockAPI;
}