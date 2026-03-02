const express = require('express');
const cors = require('cors');
const axios = require('axios');
const cheerio = require('cheerio');
const { fetchAllInfluencers, startAutoRefresh } = require('./influencer-crawler');
const { fetchShortVideoInfluencers, getShortVideoFallback } = require('./shortvideo-crawler');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = 3001;

// ==================== 股票数据 ====================

// A股列表（简化版）
const stockList = [
    { code: 'sh600519', name: '贵州茅台', sector: '消费' },
    { code: 'sh600036', name: '招商银行', sector: '金融' },
    { code: 'sh601012', name: '隆基绿能', sector: '能源' },
    { code: 'sh600276', name: '恒瑞医药', sector: '医疗' },
    { code: 'sh688981', name: '中芯国际', sector: '科技' },
    { code: 'sz000858', name: '五粮液', sector: '消费' },
    { code: 'sz002594', name: '比亚迪', sector: '科技' },
    { code: 'sz300750', name: '宁德时代', sector: '能源' },
    { code: 'sz300760', name: '迈瑞医疗', sector: '医疗' },
    { code: 'sz000001', name: '平安银行', sector: '金融' },
    { code: 'sh601318', name: '中国平安', sector: '金融' },
    { code: 'sh600887', name: '伊利股份', sector: '消费' },
    { code: 'sz002415', name: '海康威视', sector: '科技' },
    { code: 'sh603259', name: '药明康德', sector: '医疗' },
    { code: 'sz300014', name: '亿纬锂能', sector: '能源' }
];

// 获取股票实时数据
app.get('/api/stocks', async (req, res) => {
    try {
        const codes = stockList.map(s => s.code).join(',');
        const url = `https://hq.sinajs.cn/list=${codes}`;
        
        const response = await axios.get(url, {
            headers: {
                'Referer': 'https://finance.sina.com.cn',
                'User-Agent': 'Mozilla/5.0'
            },
            responseType: 'arraybuffer'
        });
        
        const data = new TextDecoder('gbk').decode(response.data);
        const stocks = parseSinaData(data);
        
        res.json({ success: true, data: stocks });
    } catch (error) {
        console.error('Stock fetch error:', error.message);
        res.json({ success: false, error: error.message, data: generateMockStocks() });
    }
});

// 解析新浪数据
function parseSinaData(data) {
    const lines = data.split('\n');
    const stocks = [];
    
    lines.forEach((line, index) => {
        if (!line.includes('="')) return;
        
        const match = line.match(/var hq_str_(\w+)="([^"]+)"/);
        if (!match) return;
        
        const code = match[1];
        const fields = match[2].split(',');
        if (fields.length < 5) return;
        
        const stockInfo = stockList.find(s => s.code === code) || { name: code, sector: '其他' };
        const price = parseFloat(fields[3]);
        const prevClose = parseFloat(fields[2]);
        const change = price - prevClose;
        const changePercent = prevClose > 0 ? (change / prevClose * 100) : 0;
        
        // 模拟AI评分（实际应该用算法计算）
        const aiScore = Math.floor(60 + Math.random() * 35);
        
        stocks.push({
            id: index,
            symbol: code.replace(/^(sh|sz)/, ''),
            name: stockInfo.name,
            sector: stockInfo.sector,
            price: price,
            change: change,
            changePercent: parseFloat(changePercent.toFixed(2)),
            volume: parseInt(fields[8]) || Math.floor(Math.random() * 1000000),
            marketCap: Math.floor(Math.random() * 1000) + 50,
            pe: (Math.random() * 50 + 5).toFixed(2),
            pb: (Math.random() * 5 + 0.5).toFixed(2),
            aiScore: aiScore,
            momentum: Math.floor(Math.random() * 100),
            value: Math.floor(Math.random() * 100),
            risk: Math.floor(Math.random() * 100),
            factors: {
                trend: Math.floor(Math.random() * 100),
                volume: Math.floor(Math.random() * 100),
                fundamental: Math.floor(Math.random() * 100),
                sentiment: Math.floor(Math.random() * 100)
            }
        });
    });
    
    return stocks;
}

function generateMockStocks() {
    return stockList.map((s, i) => ({
        id: i,
        symbol: s.code.replace(/^(sh|sz)/, ''),
        name: s.name,
        sector: s.sector,
        price: (Math.random() * 200 + 10).toFixed(2),
        change: (Math.random() * 10 - 3).toFixed(2),
        changePercent: (Math.random() * 5 - 1).toFixed(2),
        volume: Math.floor(Math.random() * 1000000),
        marketCap: Math.floor(Math.random() * 1000) + 50,
        pe: (Math.random() * 50 + 5).toFixed(2),
        pb: (Math.random() * 5 + 0.5).toFixed(2),
        aiScore: Math.floor(Math.random() * 40) + 60,
        momentum: Math.floor(Math.random() * 100),
        value: Math.floor(Math.random() * 100),
        risk: Math.floor(Math.random() * 100),
        factors: {
            trend: Math.floor(Math.random() * 100),
            volume: Math.floor(Math.random() * 100),
            fundamental: Math.floor(Math.random() * 100),
            sentiment: Math.floor(Math.random() * 100)
        }
    }));
}

// ==================== 期货数据 ====================

app.get('/api/futures', async (req, res) => {
    try {
        // 新浪财经期货数据
        const futuresCodes = ['CL', 'GC', 'NG', 'HG', 'ZW'];
        const futuresNames = ['WTI原油', '黄金', '天然气', '铜', '小麦'];
        
        // 由于期货接口需要特定权限，先用模拟数据但加上真实波动
        const futures = futuresNames.map((name, i) => {
            const basePrices = [81.25, 2845.30, 2.85, 4.25, 585.25];
            const volatility = [0.02, 0.005, 0.05, 0.015, 0.01];
            
            const basePrice = basePrices[i];
            const vol = volatility[i];
            const changePercent = (Math.random() - 0.5) * vol * 100;
            const change = basePrice * changePercent / 100;
            const price = basePrice + change;
            
            // 生成走势图数据
            const chart = [];
            let currentPrice = basePrice * 0.95;
            for (let j = 0; j < 7; j++) {
                currentPrice = currentPrice * (1 + (Math.random() - 0.5) * vol);
                chart.push(currentPrice);
            }
            chart.push(price);
            
            return {
                name: name,
                symbol: futuresCodes[i],
                price: price,
                change: change,
                changePercent: changePercent,
                trend: changePercent >= 0 ? 'up' : 'down',
                chart: chart
            };
        });
        
        res.json({ success: true, data: futures });
    } catch (error) {
        res.json({ success: false, error: error.message });
    }
});

// ==================== 新闻数据 ====================

app.get('/api/news', async (req, res) => {
    try {
        // 尝试抓取新浪财经新闻
        const url = 'https://finance.sina.com.cn/stock/';
        const response = await axios.get(url, {
            headers: { 'User-Agent': 'Mozilla/5.0' },
            timeout: 5000
        });
        
        const $ = cheerio.load(response.data);
        const news = [];
        
        // 提取新闻标题（简化版）
        $('.news-list li, .feed-card').each((i, elem) => {
            if (i >= 10) return false;
            const title = $(elem).find('a').text().trim();
            if (title && title.length > 10) {
                news.push({
                    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
                    category: i % 2 === 0 ? '市场' : '政策',
                    text: title.substring(0, 50) + '...'
                });
            }
        });
        
        if (news.length === 0) throw new Error('No news parsed');
        
        res.json({ success: true, data: news });
    } catch (error) {
        // 使用备用新闻
        const backupNews = [
            { time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), category: '市场', text: '上证指数突破3200点，券商板块集体大涨' },
            { time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), category: '政策', text: '央行宣布降准0.25个百分点，释放流动性约5000亿' },
            { time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), category: '国际', text: '美联储暗示可能暂停加息，全球股市普遍上涨' },
            { time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), category: '行业', text: '新能源汽车销量创新高，产业链公司受益明显' },
            { time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), category: '市场', text: '北向资金净流入超百亿，外资持续看好A股' }
        ];
        res.json({ success: true, data: backupNews, source: 'backup' });
    }
});

// ==================== 指数数据 ====================

app.get('/api/indices', async (req, res) => {
    try {
        const indices = [
            { name: '上证指数', code: 'sh000001' },
            { name: '深证成指', code: 'sz399001' },
            { name: '创业板指', code: 'sz399006' }
        ];
        
        const codes = indices.map(i => i.code).join(',');
        const url = `https://hq.sinajs.cn/list=${codes}`;
        
        const response = await axios.get(url, {
            headers: {
                'Referer': 'https://finance.sina.com.cn',
                'User-Agent': 'Mozilla/5.0'
            },
            responseType: 'arraybuffer'
        });
        
        const data = new TextDecoder('gbk').decode(response.data);
        const result = [];
        
        indices.forEach((index, i) => {
            const regex = new RegExp(`var hq_str_${index.code}="([^"]+)"`);
            const match = data.match(regex);
            
            if (match) {
                const fields = match[1].split(',');
                const price = parseFloat(fields[3]);
                const prevClose = parseFloat(fields[2]);
                const change = price - prevClose;
                const changePercent = prevClose > 0 ? (change / prevClose * 100) : 0;
                
                result.push({
                    name: index.name,
                    price: price.toFixed(2),
                    change: change.toFixed(2),
                    changePercent: changePercent.toFixed(2),
                    up: change >= 0
                });
            }
        });
        
        res.json({ success: true, data: result });
    } catch (error) {
        // 备用数据
        res.json({
            success: true,
            data: [
                { name: '上证指数', price: '3247.89', change: '+39.82', changePercent: '+1.24', up: true },
                { name: '深证成指', price: '10892.45', change: '-61.23', changePercent: '-0.56', up: false },
                { name: '创业板指', price: '2156.78', change: '+19.05', changePercent: '+0.89', up: true }
            ],
            source: 'backup'
        });
    }
});

// ==================== 大V观点（短视频平台）====================

app.get('/api/influencers/shortvideo', async (req, res) => {
    try {
        // 尝试抓取抖音/视频号
        const result = await fetchShortVideoInfluencers();
        
        if (result.influencers.length > 0) {
            res.json({ 
                success: true, 
                data: result.influencers,
                hotTopics: result.hotTopics,
                source: 'crawled'
            });
        } else {
            throw new Error('No short video data');
        }
    } catch (error) {
        console.log('Short video fetch failed, using fallback:', error.message);
        // 返回模拟的短视频数据
        res.json({ 
            success: true, 
            data: getShortVideoFallback(),
            source: 'fallback'
        });
    }
});

// ==================== 合并所有大V观点 ====================

app.get('/api/influencers/all', async (req, res) => {
    try {
        // 获取各平台数据
        const [weiboData, shortVideoData] = await Promise.all([
            fetchAllInfluencers().catch(() => []),
            fetchShortVideoInfluencers().catch(() => ({ influencers: [] }))
        ]);
        
        // 合并数据
        const allInfluencers = [
            ...weiboData,
            ...shortVideoData.influencers
        ];
        
        // 去重（按名字）
        const unique = allInfluencers.filter((v, i, a) => 
            a.findIndex(t => t.name === v.name) === i
        );
        
        // 如果数据不足，补充备用数据
        if (unique.length < 4) {
            const fallback = getShortVideoFallback();
            const combined = [...unique];
            
            fallback.forEach(item => {
                if (!combined.find(i => i.name === item.name)) {
                    combined.push(item);
                }
            });
            
            res.json({ success: true, data: combined, source: 'mixed' });
        } else {
            res.json({ success: true, data: unique, source: 'crawled' });
        }
    } catch (error) {
        console.error('All influencers error:', error);
        res.json({ success: true, data: getShortVideoFallback(), source: 'fallback' });
    }
});

app.get('/api/influencers', async (req, res) => {
    try {
        // 优先获取短视频平台数据（抖音/视频号）
        const result = await fetchShortVideoInfluencers();
        
        if (result.influencers.length >= 3) {
            res.json({ success: true, data: result.influencers, source: 'shortvideo' });
            return;
        }
        
        // 补充微博/B站数据
        const weiboData = await fetchAllInfluencers();
        const combined = [...result.influencers];
        
        weiboData.forEach(item => {
            if (!combined.find(i => i.name === item.name)) {
                combined.push(item);
            }
        });
        
        if (combined.length >= 4) {
            res.json({ success: true, data: combined, source: 'mixed' });
        } else {
            throw new Error('Insufficient data');
        }
    } catch (error) {
        console.log('Using short video fallback data:', error.message);
        // 返回短视频风格的备用数据
        res.json({ success: true, data: getShortVideoFallback(), source: 'fallback' });
    }
});

function getTrumpOpinion() {
    const opinions = [
        "如果我还在白宫，这场战争永远不会发生。拜登的软弱让全世界陷入混乱！",
        "MAGA！美国经济正在崩溃边缘，只有特朗普能让美国再次伟大！",
        "假新闻又在撒谎！民调显示我领先所有对手，这是史上最大的政治迫害！",
        "拜登政府把美国能源独立性拱手让人，现在又在到处求人买石油！",
        "中国正在吃掉我们的午餐，我们需要更强的领导人在谈判桌上！"
    ];
    return opinions[Math.floor(Math.random() * opinions.length)];
}

function getCanchanOpinion() {
    const opinions = [
        "从军事角度分析，红海局势的升级实际上反映了各方在地区的战略博弈。",
        "俄乌战场最新态势：北约援助的F-16战机即将形成战斗力，但飞行员培训仍是瓶颈。",
        "南海问题最新动态：各方军舰活动频繁，但实质性冲突概率较低。",
        "从装备性能来看，国产新型驱逐舰的综合作战能力已经达到世界一流水平。",
        "无人机战术在现代战争中的应用越来越广泛，值得深入研究其战术价值。"
    ];
    return opinions[Math.floor(Math.random() * opinions.length)];
}

function getJiegeOpinion() {
    const opinions = [
        "当前全球供应链面临巨大挑战，能源价格波动将直接影响通胀预期。",
        "黄金突破历史新高不是偶然，全球避险情绪的升温说明投资者对地缘政治风险有着清醒认识。",
        "大宗商品期货市场波动加剧，建议关注铜和锂的战略价值。",
        "美联储的货币政策选择愈发困难，需要在通胀和增长之间寻找平衡点。",
        "人民币国际化进程正在加速，这是多极化世界的必然趋势。"
    ];
    return opinions[Math.floor(Math.random() * opinions.length)];
}

function getDufuOpinion() {
    const opinions = [
        "从历史维度看，当前的国际秩序正在经历深刻变革，多极化趋势不可逆转。",
        "台海局势的演变需要冷静观察，军事准备与外交斡旋并行不悖。",
        "萨赫勒地区的反恐形势分析：法国撤军后留下的权力真空正在被多方势力填补。",
        "百年未有之大变局下，我们需要保持战略定力，同时做好底线思维。",
        "全球南方的崛起正在改变国际力量对比，这是历史的必然进程。"
    ];
    return opinions[Math.floor(Math.random() * opinions.length)];
}

// ==================== 启动服务 ====================

app.listen(PORT, async () => {
    console.log(`🚀 Data API Server running on http://localhost:${PORT}`);
    console.log('📊 Available endpoints:');
    console.log('  - GET /api/stocks     # A股实时数据');
    console.log('  - GET /api/futures    # 期货数据');
    console.log('  - GET /api/news       # 财经新闻');
    console.log('  - GET /api/indices    # 大盘指数');
    console.log('  - GET /api/influencers # 大V观点（自动抓取）');
    
    // 启动大V数据自动刷新
    console.log('\n🔄 Starting influencer crawler auto-refresh...');
    await startAutoRefresh(5); // 每5分钟刷新
});

module.exports = app;
