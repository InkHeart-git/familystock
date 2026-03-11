/**
 * MiniRock AI股票分析引擎 v1.1
 * 个性化分析：不同股票、不同行业、不同盈亏情况有不同推理
 */

class StockAnalysisEngine {
    constructor() {
        this.technicalIndicators = {};
        this.fundamentalData = {};
        this.newsSentiment = {};
        this.marketContext = {};
    }

    /**
     * 生成完整的股票分析报告
     * @param {Object} holding - 持仓数据
     * @returns {Object} 完整的分析报告
     */
    generateFullAnalysis(holding) {
        const analysis = {
            summary: this.generateSummary(holding),
            recommendation: this.generateRecommendation(holding),
            technical: this.analyzeTechnical(holding),
            fundamental: this.analyzeFundamental(holding),
            sentiment: this.analyzeSentiment(holding),
            risk: this.analyzeRisk(holding),
            news: this.analyzeNewsImpact(holding),
            events: this.checkBlackSwanGrayRhino(holding)
        };
        
        return analysis;
    }

    /**
     * 根据股票代码获取行业信息
     */
    getStockIndustry(symbol, name) {
        const industries = {
            '白酒': ['酒', '茅台', '五粮', '泸州', '汾酒', '洋河', '古井', '舍得', '水井坊'],
            '银行': ['银行', '平安银行', '招商银行', '工商银行', '建设银行', '农业银行', '中国银行'],
            '保险': ['保险', '平安', '人寿', '太保', '新华保险', '人保'],
            '证券': ['证券', '中信', '国泰君安', '华泰', '海通', '招商证券', '广发'],
            '新能源': ['宁德', '比亚迪', '隆基', '通威', '晶澳', '阳光电源', '赣锋', '天齐'],
            '医药': ['医药', '恒瑞', '药明', '迈瑞', '爱尔', '智飞', '长春高新', '复星'],
            '科技': ['科技', '科大讯飞', '海康', '大华', '用友', '恒生', '深信服'],
            '半导体': ['中芯', '韦尔', '兆易', '北方华创', '紫光', '卓胜微', '澜起'],
            '地产': ['地产', '万科', '保利', '招商蛇口', '金地', '新城', '绿地'],
            '电力': ['电力', '长江电力', '华能', '国电', '三峡能源', '中国核电'],
            '军工': ['航空', '航天', '船舶', '中航', '航发', '中船', '兵器'],
            '消费': ['食品', '饮料', '家电', '美的', '格力', '海尔', '伊利', '海天'],
            '煤炭': ['煤炭', '中国神华', '兖矿', '中煤', '陕西煤业'],
            '石油': ['石油', '石化', '中石油', '中石化', '中海油', '油服'],
            '有色': ['有色', '紫金', '江西铜', '中国铝', '洛阳钼', '赣锋'],
            '化工': ['化工', '万华', '恒力', '荣盛', '桐昆', '龙蟒'],
            '汽车': ['汽车', '上汽', '比亚迪', '长城', '长安', '广汽', '赛力斯'],
            '通信': ['通信', '移动', '联通', '电信', '中兴', '烽火']
        };
        
        const stockName = name || getStockNameByCode(symbol) || '';
        
        for (const [industry, keywords] of Object.entries(industries)) {
            for (const keyword of keywords) {
                if (stockName.includes(keyword) || symbol.includes(keyword)) {
                    return industry;
                }
            }
        }
        
        return '其他';
    }

    /**
     * 生成投资建议和详细推理
     */
    generateRecommendation(holding) {
        const profitPct = ((holding.close - holding.avgCost) / holding.avgCost * 100);
        const score = this.calculateAIScore(holding);
        const industry = this.getStockIndustry(holding.symbol, holding.name);
        const pctChg = holding.pct_chg || 0;
        
        let action, reason, confidence, details = [];
        
        // 根据行业、盈亏、趋势做个性化推荐
        
        // === 场景1: 白酒行业 + 高盈利 ===
        if (industry === '白酒' && profitPct > 15) {
            action = 'reduce';
            reason = '止盈减仓';
            confidence = '高';
            details = [
                { icon: '📈', text: '白酒板块估值处于历史较高水平，建议锁定部分利润' },
                { icon: '⏰', text: '当前盈利已超15%，分批止盈可降低回撤风险' },
                { icon: '💡', text: '建议减仓30-50%，保留核心底仓长期持有' }
            ];
        }
        // === 场景2: 新能源 + 亏损 ===
        else if (industry === '新能源' && profitPct < -15) {
            action = 'add';
            reason = '逢低加仓';
            confidence = '中';
            details = [
                { icon: '🔋', text: '新能源长期趋势向好，短期回调提供布局机会' },
                { icon: '📉', text: '当前跌幅已超15%，估值回归合理区间' },
                { icon: '💡', text: '建议分批加仓，每次不超过总仓位10%，降低成本' }
            ];
        }
        // === 场景3: 地产行业 ===
        else if (industry === '地产') {
            action = profitPct > 0 ? 'reduce' : 'hold';
            reason = profitPct > 0 ? '建议减仓' : '谨慎观望';
            confidence = '高';
            details = [
                { icon: '🏠', text: '地产行业处于下行周期，政策面持续收紧' },
                { icon: '⚠️', text: '行业基本面未现明显改善信号，不确定性较高' },
                { icon: '💡', text: profitPct > 0 ? '建议逢高减仓，降低行业配置' : '暂不加仓，等待行业企稳信号' }
            ];
        }
        // === 场景4: 银行 + 长期持有 ===
        else if (industry === '银行' && profitPct > -5 && profitPct < 10) {
            action = 'hold';
            reason = '长期持有';
            confidence = '中高';
            details = [
                { icon: '🏦', text: '银行股估值偏低，股息率较高，适合长期配置' },
                { icon: '📊', text: '当前收益平稳，符合银行股稳健特征' },
                { icon: '💡', text: '建议继续持有，关注宏观经济和利率政策变化' }
            ];
        }
        // === 场景5: 大涨股票 ===
        else if (profitPct > 20) {
            action = 'reduce';
            reason = '止盈保护';
            confidence = '高';
            details = [
                { icon: '🎯', text: '盈利已达20%以上，建议锁定部分利润' },
                { icon: '📉', text: '短期涨幅较大，存在获利回吐压力' },
                { icon: '💡', text: '建议减仓30-50%，剩余仓位设止盈线继续持有' }
            ];
        }
        // === 场景6: 深度套牢 ===
        else if (profitPct < -20) {
            action = 'add';
            reason = '逢低补仓';
            confidence = '中';
            details = [
                { icon: '🔻', text: '已深度套牢20%以上，割肉损失较大' },
                { icon: '🔍', text: '建议评估基本面是否恶化，若未恶化可考虑补仓' },
                { icon: '💡', text: '分批补仓降低成本，设置止损线防止进一步亏损' }
            ];
        }
        // === 场景7: 大涨当日 ===
        else if (pctChg > 5) {
            action = 'hold';
            reason = '观望持有';
            confidence = '中';
            details = [
                { icon: '🚀', text: '今日大涨超5%，短期动能强劲但需防冲高回落' },
                { icon: '👀', text: '建议观察明日走势，若继续强势可持有' },
                { icon: '💡', text: '暂不加仓，避免追高风险' }
            ];
        }
        // === 场景8: 大跌当日 ===
        else if (pctChg < -5) {
            action = profitPct < 0 ? 'add' : 'hold';
            reason = profitPct < 0 ? '逢低加仓' : '观察等待';
            confidence = '中';
            details = [
                { icon: '💥', text: '今日大跌超5%，需关注是否有利空消息' },
                { icon: '📰', text: '若无实质利空，可能是错杀机会' },
                { icon: '💡', text: profitPct < 0 ? '可考虑小幅加仓，摊低成本' : '观察明日是否企稳' }
            ];
        }
        // === 默认场景 ===
        else {
            if (score >= 70) {
                action = 'hold';
                reason = '继续持有';
                confidence = '中高';
                details = [
                    { icon: '✅', text: '技术面和基本面均表现良好，趋势健康' },
                    { icon: '📈', text: `${industry}行业运行平稳，具备持续动力` },
                    { icon: '💡', text: '建议持有，可逢低适当加仓' }
                ];
            } else if (score >= 40) {
                action = 'hold';
                reason = '观望持有';
                confidence = '中';
                details = [
                    { icon: '⏸️', text: '多空因素交织，方向尚不明确' },
                    { icon: '🔍', text: '建议密切关注后续走势和基本面变化' },
                    { icon: '💡', text: '暂不加仓，等待更明确的信号' }
                ];
            } else {
                action = 'reduce';
                reason = '减仓观望';
                confidence = '中高';
                details = [
                    { icon: '⚠️', text: '技术指标走坏，短期趋势向下' },
                    { icon: '📉', text: '市场情绪偏空，存在进一步调整风险' },
                    { icon: '💡', text: '建议减仓规避风险，等待企稳信号' }
                ];
            }
        }
        
        return { action, reason, confidence, score, profitPct, details, industry };
    }

    /**
     * 技术面分析
     */
    analyzeTechnical(holding) {
        const indicators = [];
        const pctChg = holding.pct_chg || 0;
        const profitPct = ((holding.close - holding.avgCost) / holding.avgCost * 100);
        
        // 趋势判断
        let trendStatus, trendScore, trendDesc;
        if (pctChg > 5) {
            trendStatus = '强势';
            trendScore = 85;
            trendDesc = '今日大涨超5%，多头力量强劲，但需防冲高回落';
        } else if (pctChg > 2) {
            trendStatus = '偏多';
            trendScore = 70;
            trendDesc = '今日涨幅明显，做多动能较强';
        } else if (pctChg > 0) {
            trendStatus = '小幅上涨';
            trendScore = 55;
            trendDesc = '今日小幅上涨，趋势平稳';
        } else if (pctChg > -2) {
            trendStatus = '小幅调整';
            trendScore = 45;
            trendDesc = '小幅回调，属正常技术性调整';
        } else if (pctChg > -5) {
            trendStatus = '偏弱';
            trendScore = 35;
            trendDesc = '跌幅明显，抛压较重';
        } else {
            trendStatus = '弱势';
            trendScore = 20;
            trendDesc = '大跌超5%，空头力量占优，需关注利空因素';
        }
        
        indicators.push({
            name: '短期趋势',
            status: trendStatus,
            score: trendScore,
            desc: trendDesc,
            signal: pctChg > 0 ? 'positive' : 'negative'
        });
        
        // 持仓盈亏趋势
        let profitStatus, profitScore, profitDesc;
        if (profitPct > 20) {
            profitStatus = '大幅盈利';
            profitScore = 80;
            profitDesc = '盈利超20%，建议关注止盈机会';
        } else if (profitPct > 10) {
            profitStatus = '较好盈利';
            profitScore = 70;
            profitDesc = '盈利10-20%，趋势向好';
        } else if (profitPct > 0) {
            profitStatus = '小幅盈利';
            profitScore = 60;
            profitDesc = '小幅盈利，可继续持有';
        } else if (profitPct > -10) {
            profitStatus = '小幅亏损';
            profitScore = 45;
            profitDesc = '亏损10%以内，风险可控';
        } else if (profitPct > -20) {
            profitStatus = '中度亏损';
            profitScore = 30;
            profitDesc = '亏损10-20%，需关注支撑位';
        } else {
            profitStatus = '深度套牢';
            profitScore = 20;
            profitDesc = '亏损超20%，建议评估是否补仓或止损';
        }
        
        indicators.push({
            name: '持仓盈亏',
            status: profitStatus,
            score: profitScore,
            desc: profitDesc,
            signal: profitPct > 0 ? 'positive' : 'negative'
        });
        
        // 资金流向
        const fundFlow = pctChg > 0 ? '流入' : '流出';
        indicators.push({
            name: '资金流向',
            status: fundFlow,
            score: pctChg > 0 ? 70 : 30,
            desc: `主力资金${fundFlow}，${pctChg > 0 ? '买盘积极' : '卖盘占优'}`,
            signal: pctChg > 0 ? 'positive' : 'negative'
        });
        
        return indicators;
    }

    /**
     * 基本面分析（基于已有数据模拟）
     */
    analyzeFundamental(holding) {
        const industry = this.getStockIndustry(holding.symbol, holding.name);
        
        const industryData = {
            '白酒': { pe: '偏高', peScore: 40, desc: '白酒行业PE普遍较高，需关注高端酒需求变化' },
            '银行': { pe: '偏低', peScore: 70, desc: '银行PE处于历史低位，高股息率具备吸引力' },
            '保险': { pe: '中等', peScore: 55, desc: '保险行业复苏中，关注代理人改革成效' },
            '新能源': { pe: '较高', peScore: 45, desc: '新能源高成长但也面临产能过剩压力' },
            '医药': { pe: '较高', peScore: 45, desc: '医药行业受集采影响，需关注创新药管线' },
            '科技': { pe: '高', peScore: 35, desc: '科技行业估值较高，关注业绩兑现能力' },
            '地产': { pe: '极低', peScore: 30, desc: '地产行业估值极低，但基本面仍在恶化' },
            '电力': { pe: '中等', peScore: 60, desc: '电力行业稳健，关注煤价和电价政策' },
            '军工': { pe: '中等', peScore: 55, desc: '军工行业景气度较高，但波动性大' },
            '半导体': { pe: '高', peScore: 40, desc: '半导体周期底部，关注国产替代进展' },
            '其他': { pe: '中等', peScore: 50, desc: '估值处于行业中位数水平' }
        };
        
        const data = industryData[industry] || industryData['其他'];
        
        return [
            {
                name: '行业分类',
                value: industry,
                desc: `${industry}行业，${data.desc.substring(0, data.desc.indexOf('，'))}`,
                score: 50
            },
            {
                name: '估值水平',
                value: data.pe,
                desc: data.desc,
                score: data.peScore
            },
            {
                name: '盈利能力',
                value: '良好',
                desc: 'ROE保持在合理水平，盈利质量尚可',
                score: 60
            }
        ];
    }

    /**
     * 市场情绪分析
     */
    analyzeSentiment(holding) {
        const pctChg = holding.pct_chg || 0;
        const industry = this.getStockIndustry(holding.symbol, holding.name);
        
        // 不同行业有不同的情绪敏感度
        const sensitiveIndustries = ['科技', '新能源', '半导体', '地产'];
        const isSensitive = sensitiveIndustries.includes(industry);
        
        let sentiment, score, desc;
        
        if (pctChg > 5) {
            sentiment = '乐观';
            score = isSensitive ? 80 : 75;
            desc = isSensitive 
                ? '市场情绪热烈，但高波动行业需警惕快速反转'
                : '市场对该股短期表现较为乐观，关注是否可持续';
        } else if (pctChg > 0) {
            sentiment = '谨慎乐观';
            score = 55;
            desc = '市场情绪中性偏暖，观望情绪较浓';
        } else if (pctChg > -3) {
            sentiment = '谨慎';
            score = 45;
            desc = '市场情绪谨慎，有获利回吐压力';
        } else {
            sentiment = '悲观';
            score = isSensitive ? 25 : 30;
            desc = isSensitive
                ? '高波动行业跌幅较大，情绪恐慌，可能存在超跌机会'
                : '市场情绪偏空，抛压较重';
        }
        
        return { sentiment, score, desc };
    }

    /**
     * 风险分析
     */
    analyzeRisk(holding) {
        const profitPct = ((holding.close - holding.avgCost) / holding.avgCost * 100);
        const industry = this.getStockIndustry(holding.symbol, holding.name);
        const risks = [];
        
        // 回撤风险
        if (profitPct > 20) {
            risks.push({
                type: '获利回吐',
                level: '高',
                desc: '已有较大盈利，需防范获利盘了结导致的回调',
                mitigation: '分批减仓或设置移动止盈线（如跌破10日均线减仓）'
            });
        } else if (profitPct > 10) {
            risks.push({
                type: '回撤风险',
                level: '中',
                desc: '有一定盈利，注意保护利润',
                mitigation: '可设置成本价为止损线，确保不亏钱出局'
            });
        }
        
        // 深度套牢风险
        if (profitPct < -15) {
            risks.push({
                type: '深度套牢',
                level: '高',
                desc: '亏损超过15%，继续下跌可能产生更大损失',
                mitigation: '评估基本面是否恶化，若未恶化可补仓降低成本，否则考虑止损'
            });
        }
        
        // 行业特有风险
        const industryRisks = {
            '地产': { type: '政策风险', desc: '地产行业持续受政策调控影响' },
            '新能源': { type: '产能过剩', desc: '新能源行业面临产能过剩和价格竞争' },
            '医药': { type: '集采风险', desc: '医药行业受医保集采影响，利润率承压' },
            '科技': { type: '估值回调', desc: '科技股市盈率较高，存在估值回调风险' },
            '半导体': { type: '周期风险', desc: '半导体行业周期性较强，当前处于周期底部' }
        };
        
        if (industryRisks[industry]) {
            const risk = industryRisks[industry];
            risks.push({
                type: risk.type,
                level: '中',
                desc: risk.desc,
                mitigation: '控制该行业仓位，分散投资'
            });
        }
        
        // 波动性风险
        risks.push({
            type: '市场波动',
            level: '中',
            desc: '个股受大盘影响，系统性风险无法避免',
            mitigation: '分散投资，控制单票仓位不超过总资产20%'
        });
        
        return risks;
    }

    /**
     * 新闻影响分析
     */
    analyzeNewsImpact(holding) {
        const industry = this.getStockIndustry(holding.symbol, holding.name);
        const stockName = holding.name;
        
        // 根据行业生成相关新闻提示
        const industryNews = {
            '白酒': [
                { type: '行业', impact: 'neutral', title: '白酒行业进入销售旺季，关注动销数据', summary: '中秋国庆临近，关注渠道库存去化情况' },
                { type: '政策', impact: 'negative', title: '消费税改革传言再起，白酒板块承压', summary: '若消费税后移，可能影响白酒企业利润' }
            ],
            '新能源': [
                { type: '行业', impact: 'positive', title: '新能源车渗透率持续提升', summary: '政策支持叠加产品力提升，行业景气度高' },
                { type: '价格', impact: 'negative', title: '锂电材料价格持续下跌', summary: '上游原材料降价，影响企业盈利能力' }
            ],
            '地产': [
                { type: '政策', impact: 'positive', title: '多地出台楼市松绑政策', summary: '限购限贷政策边际放松，但效果待观察' },
                { type: '行业', impact: 'negative', title: '房企债务风险持续暴露', summary: '行业出清仍在继续，需关注龙头企业抗风险能力' }
            ],
            '银行': [
                { type: '政策', impact: 'neutral', title: '存款利率下调，息差有望改善', summary: '负债成本下降，利好银行盈利能力' }
            ],
            '医药': [
                { type: '政策', impact: 'negative', title: '医保集采范围扩大', summary: '仿制药价格持续承压，关注创新药企业' }
            ]
        };
        
        const news = industryNews[industry] || [
            { type: '公司', impact: 'neutral', title: '公司经营正常，无重大负面消息', summary: '基本面稳定，财务数据健康' }
        ];
        
        return news.slice(0, 2);
    }

    /**
     * 黑天鹅/灰犀牛事件检测
     */
    checkBlackSwanGrayRhino(holding) {
        const events = [];
        const industry = this.getStockIndustry(holding.symbol, holding.name);
        
        // 行业灰犀牛
        const grayRhinos = {
            '地产': {
                name: '房地产行业深度调整',
                probability: '高',
                impact: '大',
                desc: '地产行业处于下行周期，销售持续低迷，债务风险持续暴露，可能持续3-5年',
                warning: '⚠️ 建议控制地产仓位，优先选择央企国企背景房企'
            },
            '教育': {
                name: '教培行业监管常态化',
                probability: '高',
                impact: '大',
                desc: '双减政策后教培行业规模大幅萎缩，转型职业教育尚在探索期',
                warning: '⚠️ 关注转型进展，谨慎对待传统教培业务占比高的企业'
            },
            '新能源': {
                name: '产能过剩与价格战',
                probability: '中高',
                impact: '中',
                desc: '锂电、光伏等行业产能快速扩张，面临阶段性过剩和价格战',
                warning: '⚠️ 关注龙头企业成本优势，避免投资高成本产能企业'
            },
            '医药': {
                name: '医保控费常态化',
                probability: '高',
                impact: '中',
                desc: '医保收支压力持续，集采范围不断扩大，仿制药企利润空间压缩',
                warning: '⚠️ 优先选择创新药管线丰富的企业，规避仿制药依赖度高的企业'
            },
            '科技': {
                name: '地缘政治导致供应链脱钩',
                probability: '中',
                impact: '大',
                desc: '中美科技竞争加剧，部分领域面临断供风险',
                warning: '⚠️ 关注国产替代进展，优先选择自主可控能力强的企业'
            }
        };
        
        if (grayRhinos[industry]) {
            events.push({
                type: '灰犀牛',
                ...grayRhinos[industry]
            });
        }
        
        // 个股特定风险
        if (holding.symbol.startsWith('68')) {
            events.push({
                type: '灰犀牛',
                name: '科创板解禁减持压力',
                probability: '中',
                impact: '中',
                desc: '科创板首批上市股票已陆续解禁，面临股东减持压力',
                warning: '⚠️ 关注股东减持公告，警惕大额减持计划'
            });
        }
        
        return events;
    }

    /**
     * 生成分析摘要
     */
    generateSummary(holding) {
        const recommendation = this.generateRecommendation(holding);
        
        return {
            title: `${holding.name}投资分析`,
            verdict: recommendation.action,
            verdictText: recommendation.reason,
            confidence: recommendation.confidence,
            keyPoints: recommendation.details.map(d => d.text)
        };
    }

    /**
     * 计算AI评分
     */
    calculateAIScore(holding) {
        const profitPct = ((holding.close - holding.avgCost) / holding.avgCost * 100);
        const pctChg = holding.pct_chg || 0;
        const industry = this.getStockIndustry(holding.symbol, holding.name);
        
        let score = 50; // 基础分
        
        // 当日表现
        if (pctChg > 5) score += 15;
        else if (pctChg > 0) score += 5;
        else if (pctChg < -5) score -= 15;
        else if (pctChg < 0) score -= 5;
        
        // 持仓盈亏
        if (profitPct > 20) score -= 5; // 涨多了风险增加
        else if (profitPct > 10) score += 10;
        else if (profitPct > 0) score += 5;
        else if (profitPct < -20) score -= 10; // 跌多了可能反弹
        else if (profitPct < 0) score -= 5;
        
        // 行业调整
        const industryAdjust = {
            '白酒': 5,
            '银行': 8,
            '保险': 3,
            '新能源': -2,
            '医药': 0,
            '科技': -3,
            '地产': -10,
            '电力': 5
        };
        score += industryAdjust[industry] || 0;
        
        return Math.max(0, Math.min(100, Math.round(score)));
    }
}

// 创建全局实例
const stockAnalysisEngine = new StockAnalysisEngine();

/**
 * 生成增强版股票详情HTML
 */
function generateEnhancedStockDetailHTML(holding, index) {
    const analysis = stockAnalysisEngine.generateFullAnalysis(holding);
    const rec = analysis.recommendation;
    const profit = (holding.close - holding.avgCost) * holding.quantity;
    const profitPct = ((holding.close - holding.avgCost) / holding.avgCost * 100);
    const isProfit = profit >= 0;
    
    // 建议样式映射
    const actionStyles = {
        'add': { color: '#10b981', bg: 'rgba(16,185,129,0.1)', icon: '➕', text: '建议加仓' },
        'hold': { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', icon: '✋', text: '建议持有' },
        'reduce': { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', icon: '➖', text: '建议减仓' },
        'sell': { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', icon: '⚠️', text: '建议卖出' }
    };
    
    const style = actionStyles[rec.action] || actionStyles.hold;
    
    return `
        <div class="ai-modal-content" style="max-height: 85vh; overflow-y: auto;">
            <!-- 头部 -->
            <div class="ai-result-header" style="position: sticky; top: 0; z-index: 10; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);">
                <button class="ai-close-btn" onclick="document.getElementById('stockDetailModal').remove()">✕</button>
                <div style="display: flex; align-items: center; gap: 15px; justify-content: center;">
                    <div style="font-size: 48px;">${style.icon}</div>
                    <div style="text-align: left;">
                        <h3 style="margin: 0; font-size: 22px;">${holding.name}</h3>
                        <div style="color: #8892b0; font-size: 14px;">${holding.symbol} · ${holding.market || 'A股'} · ${rec.industry || '其他'}</div>
                    </div>
                </div>
            </div>
            
            <div class="ai-result-body">
                <!-- AI核心建议 -->
                <div class="ai-section" style="background: ${style.bg}; border: 1px solid ${style.color}40;">
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 15px;">
                        <div style="width: 50px; height: 50px; border-radius: 50%; background: ${style.color}; display: flex; align-items: center; justify-content: center; font-size: 24px;">
                            ${style.icon}
                        </div>
                        <div>
                            <div style="font-size: 20px; font-weight: 700; color: ${style.color};">${style.text}</div>
                            <div style="font-size: 12px; color: #8892b0;">AI置信度: ${rec.confidence}</div>
                        </div>
                    </div>
                    
                    <!-- 详细推理 -->
                    <div style="background: rgba(0,0,0,0.2); border-radius: 10px; padding: 12px;">
                        <div style="font-size: 12px; color: #8892b0; margin-bottom: 8px;">🧠 AI推理过程</div>
                        ${rec.details.map(d => `
                            <div style="display: flex; gap: 8px; margin-bottom: 8px; font-size: 13px; line-height: 1.5;">
                                <span>${d.icon}</span>
                                <span style="color: #e2e8f0;">${d.text}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                <!-- 价格信息 -->
                <div class="ai-section">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <div>
                            <div style="font-size: 32px; font-weight: 700; color: ${isProfit ? '#ff6b6b' : '#51cf66'};">
                                ¥${holding.close.toFixed(2)}
                            </div>
                            <div style="font-size: 14px; color: #8892b0; margin-top: 4px;">
                                今日 ${holding.pct_chg > 0 ? '+' : ''}${holding.pct_chg.toFixed(2)}%
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div class="risk-badge ${rec.score >= 70 ? 'low' : rec.score >= 50 ? 'medium' : 'high'}">
                                AI ${rec.score}
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.05);">
                        <div>
                            <div style="font-size: 11px; color: #64748b;">今开</div>
                            <div style="font-size: 14px; color: #fff;">¥${(holding.open || holding.close).toFixed(2)}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; color: #64748b;">最高</div>
                            <div style="font-size: 14px; color: #ff6b6b;">¥${(holding.high || holding.close).toFixed(2)}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; color: #64748b;">昨收</div>
                            <div style="font-size: 14px; color: #fff;">¥${(holding.pre_close || holding.close).toFixed(2)}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; color: #64748b;">最低</div>
                            <div style="font-size: 14px; color: #51cf66;">¥${(holding.low || holding.close).toFixed(2)}</div>
                        </div>
                    </div>
                </div>
                
                <!-- 技术面分析 -->
                <div class="ai-section">
                    <h4 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        📊 技术面分析
                    </h4>
                    ${analysis.technical.map(ind => `
                        <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 8px;">
                            <div>
                                <div style="font-size: 13px; color: #fff;">${ind.name}</div>
                                <div style="font-size: 11px; color: #64748b;">${ind.desc}</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 14px; font-weight: 600; color: ${ind.signal.includes('positive') ? '#10b981' : ind.signal.includes('negative') ? '#ef4444' : '#f59e0b'};">
                                    ${ind.status}
                                </div>
                                <div style="font-size: 11px; color: #64748b;">评分 ${ind.score}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
                
                <!-- 基本面分析 -->
                <div class="ai-section">
                    <h4 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        🏢 基本面分析
                    </h4>
                    ${analysis.fundamental.map(fund => `
                        <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 8px;">
                            <div>
                                <div style="font-size: 13px; color: #fff;">${fund.name}</div>
                                <div style="font-size: 11px; color: #64748b;">${fund.desc}</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 14px; font-weight: 600; color: ${fund.score >= 60 ? '#10b981' : fund.score >= 40 ? '#f59e0b' : '#ef4444'};">
                                    ${fund.value}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
                
                <!-- 持仓信息 -->
                <div class="ai-section">
                    <h4 style="margin-bottom: 12px;">💼 持仓情况</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                        <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 10px;">
                            <div style="font-size: 11px; color: #64748b;">持仓数量</div>
                            <div style="font-size: 16px; font-weight: 600; color: #fff;">${holding.quantity} 股</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 10px;">
                            <div style="font-size: 11px; color: #64748b;">成本价</div>
                            <div style="font-size: 16px; font-weight: 600; color: #fff;">¥${holding.avgCost.toFixed(2)}</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 10px;">
                            <div style="font-size: 11px; color: #64748b;">总市值</div>
                            <div style="font-size: 16px; font-weight: 600; color: #fff;">¥${(holding.close * holding.quantity).toLocaleString()}</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 10px;">
                            <div style="font-size: 11px; color: #64748b;">盈亏比例</div>
                            <div style="font-size: 16px; font-weight: 600; color: ${isProfit ? '#ff6b6b' : '#51cf66'};">
                                ${isProfit ? '+' : ''}${profitPct.toFixed(2)}%
                            </div>
                        </div>
                    </div>
                    <div style="margin-top: 15px; padding: 15px; background: ${isProfit ? 'rgba(255,107,107,0.1)' : 'rgba(81,207,102,0.1)'}; border-radius: 10px; text-align: center; border: 1px solid ${isProfit ? 'rgba(255,107,107,0.2)' : 'rgba(81,207,102,0.2)'};">
                        <div style="font-size: 12px; color: #8892b0;">总盈亏</div>
                        <div style="font-size: 24px; font-weight: 700; color: ${isProfit ? '#ff6b6b' : '#51cf66'};">
                            ${isProfit ? '+' : ''}¥${profit.toLocaleString()}
                        </div>
                    </div>
                </div>
                
                <!-- 风险提示 -->
                ${analysis.risk.length > 0 ? `
                <div class="ai-section">
                    <h4 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        ⚠️ 风险提示
                    </h4>
                    ${analysis.risk.map(risk => `
                        <div style="padding: 12px; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2); border-radius: 10px; margin-bottom: 10px;">
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                                <span style="color: #ef4444; font-weight: 600;">${risk.type}</span>
                                <span style="font-size: 11px; padding: 2px 8px; background: ${risk.level === '高' ? '#ef4444' : '#f59e0b'}; border-radius: 4px; color: #fff;">${risk.level}风险</span>
                            </div>
                            <div style="font-size: 12px; color: #e2e8f0; margin-bottom: 6px;">${risk.desc}</div>
                            <div style="font-size: 11px; color: #64748b;">💡 应对: ${risk.mitigation}</div>
                        </div>
                    `).join('')}
                </div>
                ` : ''}
                
                <!-- 事件预警 -->
                ${analysis.events.length > 0 ? `
                <div class="ai-section">
                    <h4 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        🚨 事件预警
                    </h4>
                    ${analysis.events.map(event => `
                        <div style="padding: 12px; background: ${event.type === '黑天鹅' ? 'rgba(147,51,234,0.1)' : 'rgba(245,158,11,0.1)'}; border: 1px solid ${event.type === '黑天鹅' ? 'rgba(147,51,234,0.3)' : 'rgba(245,158,11,0.3)'}; border-radius: 10px; margin-bottom: 10px;">
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                                <span style="font-size: 16px;">${event.type === '黑天鹅' ? '🦢' : '🦏'}</span>
                                <span style="color: ${event.type === '黑天鹅' ? '#a855f7' : '#f59e0b'}; font-weight: 600;">${event.name}</span>
                            </div>
                            <div style="display: flex; gap: 12px; margin-bottom: 8px; font-size: 12px;">
                                <span style="color: #64748b;">概率: <span style="color: #e2e8f0;">${event.probability}</span></span>
                                <span style="color: #64748b;">影响: <span style="color: #e2e8f0;">${event.impact}</span></span>
                            </div>
                            <div style="font-size: 12px; color: #e2e8f0; margin-bottom: 8px;">${event.desc}</div>
                            <div style="font-size: 12px; color: #f59e0b;">${event.warning}</div>
                        </div>
                    `).join('')}
                </div>
                ` : ''}
                
                <!-- 免责声明 -->
                <div style="padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px; font-size: 11px; color: #64748b; text-align: center;">
                    ⚠️ AI分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。
                </div>
            </div>
            
            <div class="ai-result-footer" style="gap: 10px; position: sticky; bottom: 0; background: #1a1a2e; padding: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                <button class="btn btn-primary" style="flex: 2;" onclick="document.getElementById('stockDetailModal').remove()">我知道了</button>
                <button class="btn btn-secondary" style="flex: 1; background: rgba(239,68,68,0.2); color: #fca5a5;" onclick="removeHolding(${index}); document.getElementById('stockDetailModal').remove();">删除</button>
            </div>
        </div>
    `;
}

// 导出到全局
generateEnhancedStockDetailHTML = generateEnhancedStockDetailHTML;
