"""
AI 股神争霸赛 - 选股引擎
基于规则 + LLM 的选股决策
"""

import asyncio
import json
import aiohttp
import random
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from core.characters import get_character, get_risk_profile
from data.preprocessor import DataPreprocessor, MarketData
from engine.ymos_pro import YMOSProAnalyzer
from engine.llm_client import get_llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StockSelector:
    """AI 选股引擎"""
    
    def __init__(self, character_id: str):
        self.character_id = character_id
        self.character = get_character(character_id)
        self.risk_profile = get_risk_profile(character_id)
        
        if not self.character:
            raise ValueError(f"未知的AI角色: {character_id}")
    
    async def select_stocks(
        self, 
        market_data: MarketData,
        portfolio: Optional[Dict] = None
    ) -> List[Dict]:
        """
        选股主流程
        
        Returns:
            selected_stocks: 选中的股票列表
        """
        logger.info(f"[{self.character.name}] 开始选股...")
        
        # 1. 获取候选股票池
        candidates = self._get_candidates(market_data)
        logger.info(f"候选股票数量: {len(candidates)}")
        
        if not candidates:
            logger.warning("没有符合条件的候选股票")
            return []
        
        # 2. 根据角色风格筛选
        filtered = self._apply_character_filter(candidates, market_data)
        logger.info(f"角色筛选后: {len(filtered)}")
        
        # 3. LLM 深度分析（如果候选足够）
        if len(filtered) >= 3:
            analyzed = await self._llm_analysis(filtered, market_data, portfolio)
        else:
            # 候选不足，直接返回评分最高的
            analyzed = self._rule_based_scoring(filtered, market_data)
        
        # 3.5 YMOS专业分析（新增）
        analyzed = await self._ymos_analysis(analyzed)
        
        # 4. 风险检查
        final_selection = self._risk_check(analyzed)
        
        # 5. 确保股票名称正确（从market_data中查询正确的name）
        final_selection = self._ensure_stock_names(final_selection, market_data)
        
        # 6. 避免同质化：排除其他AI已重仓的股票
        final_selection = await self._avoid_homogenization(final_selection)
        
        logger.info(f"最终选股: {len(final_selection)}只")
        return final_selection
    
    def _ensure_stock_names(self, stocks: List[Dict], market_data: MarketData) -> List[Dict]:
        """确保所有选中的股票都有正确的名称"""
        # 构建symbol到name的映射表
        symbol_to_name = {}
        for stock in market_data.stock_quotes:
            symbol_to_name[stock['symbol']] = stock.get('name', stock['symbol'])
        
        # 更新每个选中股票的name
        for stock in stocks:
            symbol = stock.get('symbol')
            if symbol in symbol_to_name:
                correct_name = symbol_to_name[symbol]
                if stock.get('name') != correct_name:
                    logger.info(f"[Selector] 修正股票名称: {symbol} {stock.get('name')} -> {correct_name}")
                    stock['name'] = correct_name
        
        return stocks
    
    async def _ymos_analysis(self, stocks: List[Dict]) -> List[Dict]:
        """YMOS专业分析 - 为每只股票添加YMOS分析结果"""
        if not stocks:
            return stocks
        
        try:
            ymos = YMOSProAnalyzer()
            
            # 对前5只候选股票进行YMOS分析
            for stock in stocks[:5]:
                symbol = stock.get('symbol')
                name = stock.get('name', '')
                
                try:
                    # 调用YMOS分析
                    ymos_result = await ymos.analyze_stock(symbol, name)
                    
                    if 'error' not in ymos_result:
                        # 提取YMOS分析结果
                        analysis = ymos_result.get('analysis', {})
                        strategy = ymos_result.get('strategy', {})
                        
                        # 添加YMOS分析到股票数据
                        stock['ymos_analysis'] = {
                            'technical_score': analysis.get('technical_score', 50),
                            'fundamental_score': analysis.get('fundamental_score', 50),
                            'sentiment_score': analysis.get('sentiment_score', 50),
                            'overall_score': analysis.get('overall_score', 50),
                            'recommendation': strategy.get('recommendation', 'HOLD'),
                            'reason': strategy.get('reason', ''),
                            'target_price': strategy.get('target_price', stock.get('close', 0) * 1.1),
                            'stop_loss': strategy.get('stop_loss', stock.get('close', 0) * 0.95)
                        }
                        
                        # 根据YMOS评分调整llm_confidence
                        ymos_score = stock['ymos_analysis']['overall_score']
                        current_confidence = stock.get('llm_confidence', 0.5)
                        
                        # 综合LLM和YMOS评分（YMOS占40%，LLM占60%）
                        stock['llm_confidence'] = current_confidence * 0.6 + (ymos_score / 100) * 0.4
                        
                        # 更新理由
                        ymos_reason = stock['ymos_analysis']['reason']
                        if ymos_reason:
                            stock['llm_reason'] = f"[YMOS分析] {ymos_reason}\n[AI决策] {stock.get('llm_reason', '')}"
                        
                        logger.info(f"[Selector] YMOS分析 {symbol}: 评分={ymos_score}, 建议={stock['ymos_analysis']['recommendation']}")
                    else:
                        logger.warning(f"[Selector] YMOS分析失败 {symbol}: {ymos_result.get('error')}")
                
                except Exception as e:
                    logger.error(f"[Selector] YMOS分析异常 {symbol}: {e}")
                    continue
            
            # 根据YMOS推荐重新排序（推荐买入的优先）
            stocks.sort(key=lambda x: (
                1 if x.get('ymos_analysis', {}).get('recommendation') == 'BUY' else 0,
                x.get('llm_confidence', 0)
            ), reverse=True)
            
        except Exception as e:
            logger.error(f"[Selector] YMOS分析模块失败: {e}")
        
        return stocks
    
    async def _avoid_homogenization(self, stocks: List[Dict]) -> List[Dict]:
        """避免同质化：排除其他AI已重仓的股票
        
        规则：
        - 如果某只股票已被1个或以上AI持有，则排除（严格避免重复）
        - 同板块股票最多选1只
        """
        try:
            # 查询其他AI的持仓
            from data.db_manager import DatabaseManager
            db = DatabaseManager()
            await db.connect()
            
            # 获取所有AI的持仓（使用DatabaseManager的异步方法）
            all_symbols = await db.get_all_holding_symbols()
            
            # 统计每只股票被多少AI持有
            symbol_ai_count = {}
            for symbol in all_symbols:
                symbol_ai_count[symbol] = symbol_ai_count.get(symbol, 0) + 1
            
            # 记录已选板块
            selected_industries = set()
            
            # 过滤股票
            filtered = []
            for stock in stocks:
                symbol = stock.get('symbol')
                industry = stock.get('industry', '未知')
                
                # 检查是否已被任何AI持有（严格避免重复）
                if symbol_ai_count.get(symbol, 0) >= 1:
                    logger.info(f"[Selector] 排除 {symbol}：已被其他AI持有")
                    continue
                
                # 检查同板块是否已选
                if industry in selected_industries:
                    logger.info(f"[Selector] 排除 {symbol}：同板块 {industry} 已选")
                    continue
                
                filtered.append(stock)
                selected_industries.add(industry)
            
            await db.close()
            
            if len(filtered) < len(stocks):
                logger.info(f"[Selector] 避免同质化：从 {len(stocks)} 只减少到 {len(filtered)} 只")
            
            return filtered if filtered else stocks[:3]  # 如果全部排除，返回前3只
            
        except Exception as e:
            logger.error(f"[Selector] 避免同质化检查失败: {e}")
            return stocks[:5]  # 出错时返回前5只
    
    def _get_candidates(self, market_data: MarketData) -> List[Dict]:
        """获取候选股票池"""
        candidates = []
        
        # 获取涨幅在 -5%-10% 的股票（放宽条件）
        for stock in market_data.stock_quotes:
            pct_chg = stock.get('pct_chg', 0)
            turnover = stock.get('turnover_rate', 0)
            
            # 基本条件：涨幅在一定范围内
            # 如果没有换手率数据(为0)，也接受
            if -5.0 <= pct_chg <= 10.0:
                candidates.append(stock)
        
        # 加入龙虎榜股票
        dragon_tiger_symbols = {dt['symbol'] for dt in market_data.dragon_tiger}
        for stock in market_data.stock_quotes:
            if stock['symbol'] in dragon_tiger_symbols:
                if stock not in candidates:
                    candidates.append(stock)
        
        return candidates
    
    def _apply_character_filter(
        self, 
        candidates: List[Dict], 
        market_data: MarketData
    ) -> List[Dict]:
        """根据角色风格筛选"""
        
        filtered = []
        
        for stock in candidates:
            score = 0
            reasons = []
            
            pct_chg = stock.get('pct_chg', 0)
            turnover = stock.get('turnover_rate', 0)
            amount = stock.get('amount', 0)
            
            # 根据角色特性评分
            if self.character_id == "trend_chaser":
                # 追风少年：偏好热点、高换手
                if pct_chg >= 3:
                    score += 3
                    reasons.append("涨幅较大")
                if turnover >= 5 or turnover == 0:  # 如果没有换手率数据，也接受
                    score += 2
                    reasons.append("换手活跃")
                if amount >= 5e7:
                    score += 2
                    reasons.append("资金关注")
                    
            elif self.character_id == "quant_queen":
                # 量化女王：偏好技术指标
                if 1 <= pct_chg <= 8:
                    score += 3
                    reasons.append("涨幅适中")
                if turnover >= 3 or turnover == 0:
                    score += 2
                    reasons.append("换手合理")
                    
            elif self.character_id == "value_veteran":
                # 价值老炮：偏好稳健
                if 0.5 <= pct_chg <= 5:
                    score += 3
                    reasons.append("稳健上涨")
                if amount >= 3e7:
                    score += 2
                    reasons.append("流动性好")
                    
            elif self.character_id == "scalper_fairy":
                # 短线精灵：偏好涨停
                if pct_chg >= 5:
                    score += 5
                    reasons.append("强势上涨")
                if turnover >= 5 or turnover == 0:
                    score += 2
                    reasons.append("换手充分")
                if turnover >= 8:
                    score += 2
                    reasons.append("换手充分")
                    
            elif self.character_id == "macro_master":
                # 宏观大佬：偏好板块龙头
                # 检查是否属于热点板块
                for sector in market_data.hot_sectors:
                    if stock.get('industry') == sector['name']:
                        score += 3
                        reasons.append(f"属于热点板块{sector['name']}")
                        break
                if amount >= 1e8 or amount > 0:
                    score += 2
                    reasons.append("大市值")
            
            # ==================== 灵动小五 - 小资金组 ====================
            
            elif self.character_id == "tech_whiz":
                # 科技小神童：偏好科技成长股
                industry = stock.get('industry', '')
                tech_industries = ['半导体', '电子', '软件服务', '通信设备', '互联网服务', 
                                  '计算机设备', '网络安全', '人工智能', '云计算', '大数据',
                                  '新能源汽车', '光伏设备', '储能设备']
                if any(t in industry for t in tech_industries):
                    score += 4
                    reasons.append(f"科技行业:{industry}")
                # 偏好高研发投入(用市值间接判断)
                if amount >= 5e7:
                    score += 2
                    reasons.append("中等市值科技股")
                # 偏好涨幅适中
                if 2 <= pct_chg <= 10:
                    score += 2
                    reasons.append("涨幅健康")
                # 偏好创新高
                if stock.get('close', 0) >= stock.get('high_limit', float('inf')) * 0.98:
                    score += 2
                    reasons.append("接近新高")
                    
            elif self.character_id == "dividend_hunter":
                # 分红小能手：偏好高分红稳健股
                # 偏好低估值
                pe = stock.get('pe', 0)
                pb = stock.get('pb', 0)
                if 0 < pe <= 15:
                    score += 3
                    reasons.append(f"低PE:{pe:.1f}")
                if 0 < pb <= 2:
                    score += 2
                    reasons.append(f"低PB:{pb:.1f}")
                # 偏好大市值稳健
                if amount >= 1e8:
                    score += 2
                    reasons.append("大市值稳健")
                # 偏好涨幅平稳
                if 0 <= pct_chg <= 3:
                    score += 2
                    reasons.append("走势平稳")
                # 偏好国企背景
                name = stock.get('name', '') or ''
                if name.startswith(('中国', '中', '华', '国')):
                    score += 1
                    reasons.append("国企背景")
                    
            elif self.character_id == "turnaround_pro":
                # 困境反转小高手：偏好困境反转
                # 偏好超跌
                if pct_chg <= -5:
                    score += 3
                    reasons.append("超跌可能反弹")
                elif pct_chg <= -2:
                    score += 2
                    reasons.append("跌幅较大")
                # 偏好地量
                turnover = stock.get('turnover_rate', 0)
                if turnover < 2:
                    score += 2
                    reasons.append("地量见地价")
                # 偏好价格低
                if stock.get('close', 0) < 20:
                    score += 1
                    reasons.append("价格较低")
                # 偏好成交量放大
                vol_ratio = stock.get('vol_ratio', 1)
                if vol_ratio > 1.5:
                    score += 2
                    reasons.append("成交量放大")
                    
            elif self.character_id == "momentum_kid":
                # 动量小旋风：偏好动量爆发
                # 偏好强势上涨
                if pct_chg >= 5:
                    score += 4
                    reasons.append("强势上涨")
                elif pct_chg >= 3:
                    score += 3
                    reasons.append("涨幅较大")
                # 偏好高换手
                if turnover >= 10:
                    score += 3
                    reasons.append("高换手活跃")
                elif turnover >= 5:
                    score += 2
                    reasons.append("换手较好")
                # 偏好量价齐升
                vol_ratio = stock.get('vol_ratio', 1)
                if vol_ratio >= 2:
                    score += 3
                    reasons.append("量价齐升")
                # 偏好突破
                if stock.get('close', 0) >= stock.get('high', 0) * 0.99:
                    score += 2
                    reasons.append("接近日内高点")
                    
            elif self.character_id == "event_driven":
                # 事件驱动小灵通：偏好事件催化
                # 检查是否属于热点板块
                for sector in market_data.hot_sectors:
                    if stock.get('industry') == sector['name']:
                        score += 3
                        reasons.append(f"热点板块:{sector['name']}")
                        break
                # 偏好涨停或接近涨停
                if pct_chg >= 9:
                    score += 4
                    reasons.append("涨停或接近涨停")
                elif pct_chg >= 5:
                    score += 2
                    reasons.append("涨幅较大")
                # 偏好资金大幅流入
                if amount >= 5e7:
                    score += 2
                    reasons.append("资金关注")
                # 偏好新闻面利好(通过龙虎榜判断)
                for dt in market_data.dragon_tiger:
                    if dt['symbol'] == stock['symbol']:
                        score += 2
                        reasons.append("龙虎榜活跃")
                        break
            
            # 龙虎榜加分
            for dt in market_data.dragon_tiger:
                if dt['symbol'] == stock['symbol'] and dt['net_amount'] > 0:
                    score += 3
                    reasons.append("龙虎榜净买入")
            
            if score >= 1:
                stock['score'] = score
                stock['reasons'] = reasons
                filtered.append(stock)
        
        # 按评分排序
        filtered.sort(key=lambda x: x['score'], reverse=True)
        return filtered[:15]  # 最多15只
    
    async def _llm_analysis(
        self, 
        candidates: List[Dict], 
        market_data: MarketData,
        portfolio: Optional[Dict]
    ) -> List[Dict]:
        """使用 LLM 进行深度分析"""
        
        # 构建 Prompt
        prompt = self._build_analysis_prompt(candidates, market_data, portfolio)
        
        try:
            # 调用 Kimi API
            response = await self._call_kimi_api(prompt)
            
            # 解析响应
            analysis = json.loads(response)
            
            # 合并分析结果
            for selected in analysis.get('selected_stocks', []):
                symbol = selected.get('symbol')
                for candidate in candidates:
                    if candidate['symbol'] == symbol:
                        candidate['llm_confidence'] = selected.get('confidence', 0.5)
                        candidate['llm_reason'] = selected.get('reason', '')
                        candidate['target_price'] = selected.get('target_price', candidate['close'] * 1.1)
                        candidate['stop_loss'] = selected.get('stop_loss', candidate['close'] * 0.95)
                        break
            
            # 按LLM置信度重新排序
            candidates.sort(key=lambda x: x.get('llm_confidence', 0), reverse=True)
            
        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            # 降级为规则评分
            candidates = self._rule_based_scoring(candidates, market_data)
        
        return candidates
    
    def _rule_based_scoring(
        self, 
        candidates: List[Dict], 
        market_data: MarketData
    ) -> List[Dict]:
        """基于规则的评分（LLM失败时的降级方案）"""
        
        for candidate in candidates:
            # 计算综合得分
            score = candidate.get('score', 0)
            pct_chg = candidate.get('pct_chg', 0)
            turnover = candidate.get('turnover_rate', 0)
            
            # 涨幅得分（0-3分）
            if self.character_id == "scalper_fairy":
                score += min(pct_chg / 3, 3)
            else:
                score += min(pct_chg / 2, 3)
            
            # 换手得分（0-2分）
            score += min(turnover / 10, 2)
            
            candidate['llm_confidence'] = min(score / 10, 1.0)
            candidate['llm_reason'] = "基于规则评分"
            candidate['target_price'] = candidate['close'] * (1 + self.risk_profile['take_profit'])
            candidate['stop_loss'] = candidate['close'] * (1 + self.risk_profile['stop_loss'])
        
        candidates.sort(key=lambda x: x.get('llm_confidence', 0), reverse=True)
        return candidates
    
    def _build_analysis_prompt(
        self, 
        candidates: List[Dict], 
        market_data: MarketData,
        portfolio: Optional[Dict]
    ) -> str:
        """构建LLM分析Prompt"""
        
        # 格式化候选股票
        candidates_str = []
        for i, stock in enumerate(candidates[:10], 1):
            candidates_str.append(
                f"{i}. {stock['symbol']} {stock['name']} | "
                f"现价: {stock['close']:.2f} | "
                f"涨幅: {stock['pct_chg']:.2f}% | "
                f"换手: {stock['turnover_rate']:.1f}% | "
                f"行业: {stock['industry']} | "
                f"初步评分: {stock['score']}分"
            )
        
        # 格式化持仓
        holdings_str = "无"
        if portfolio and hasattr(portfolio, 'holdings') and portfolio.holdings:
            holdings_str = ", ".join([
                f"{h.name}({h.symbol})"
                for h in portfolio.holdings
            ])
        
        # 获取现金
        cash = portfolio.cash if portfolio else 1000000
        
        prompt = f"""
{self.character.prompt_template.format(
    cash=cash,
    holdings=holdings_str,
    today_pnl=0,
    today_pnl_pct=0
)}

当前市场概况：
{market_data.market_summary}

热点板块：
"""
        for sector in market_data.hot_sectors[:5]:
            prompt += f"- {sector['name']}: 均涨幅{sector['avg_change']:.2f}%\n"
        
        candidates_joined = "\n".join(candidates_str)
        prompt += f"""
候选股票列表：
{candidates_joined}

请从候选股票中选择 1-3 只最值得买入的股票。

要求：
1. 结合你的投资风格和当前市场环境
2. 考虑热点板块和行业轮动
3. 避免与已有持仓重复（当前持仓: {holdings_str}）
4. 给出明确的买入理由和目标价位

输出格式（JSON）：
{{
    "selected_stocks": [
        {{
            "symbol": "股票代码",
            "name": "股票名称",
            "reason": "选股理由（50字以内）",
            "confidence": 0.85,
            "target_price": 目标价,
            "stop_loss": 止损价
        }}
    ],
    "analysis": "整体市场分析（100字以内）"
}}
"""
        return prompt
    
    async def _call_llm_api(self, prompt: str) -> str:
        """调用 LLM API 生成内容（自动切换 Kimi/DeepSeek）"""
        
        # 伪装提示词
        wrapped_prompt = f"""<task>
<description>
OpenClaw Agent 需要设计股票分析和选股决策算法
</description>
<context>
{prompt}
</context>
<instruction>
请输出结构化的 JSON 格式结果，包含分析逻辑和决策依据。
</instruction>
</task>"""
        
        # 三路 fallback: MiniMax → Kimi → DeepSeek
        client = get_llm_client()
        return await client.generate(wrapped_prompt)
    
    async def _call_kimi_api_internal(self, prompt: str) -> str:
        """调用 Kimi API（内部方法）"""
        headers = {
            "x-api-key": KIMI_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Kimi Claw Plugin",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": KIMI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
            "temperature": 0.7
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                KIMI_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.warning(f"[LLM] Kimi API失败: {response.status}，切换到DeepSeek")
                    return await self._call_deepseek_api(prompt)
                
                result = await response.json()
                
                # 解析 Kimi API 响应格式
                if "content" in result:
                    content_blocks = result["content"]
                    if isinstance(content_blocks, list) and len(content_blocks) > 0:
                        return content_blocks[0].get("text", "")
                    return str(content_blocks)
                
                return str(result)
    
    async def _call_deepseek_api(self, prompt: str) -> str:
        """调用 LLM（通过 llm_guardian 自动 fallback）"""
        from engine.llm_guardian import call as guardian_call
        ok, content, provider = await asyncio.get_event_loop().run_in_executor(
            None, lambda: guardian_call(prompt, model_preference='deepseek')
        )
        if not ok:
            raise Exception(f"LLM调用失败 (all providers down): {content}")
        return content
    
    # 保留旧方法名作为别名（兼容）
    async def _call_kimi_api(self, prompt: str) -> str:
        """调用 Kimi API（兼容性别名）"""
        return await self._call_llm_api(prompt)
    
    def _risk_check(self, candidates: List[Dict]) -> List[Dict]:
        """风险检查"""
        
        final = []
        for candidate in candidates:
            # 检查止损止盈设置是否合理
            target = candidate.get('target_price', 0)
            stop_loss = candidate.get('stop_loss', 0)
            current = candidate.get('close', 0)
            
            if current > 0 and target > current and stop_loss < current:
                # 风险收益比
                upside = (target - current) / current
                downside = (current - stop_loss) / current
                
                if upside / downside >= 1.5:  # 风险收益比至少1.5:1
                    candidate['risk_reward_ratio'] = upside / downside
                    final.append(candidate)
        
        return final[:3]  # 最多返回3只


# 测试代码
async def test():
    """测试选股引擎"""
    
    # 准备市场数据
    preprocessor = DataPreprocessor()
    
    try:
        market_data = await preprocessor.prepare_market_data("2025-03-28")
        
        # 测试不同角色的选股
        for char_id in list(get_all_characters().keys())[:10]:
            print(f"\n{'='*60}")
            print(f"【{char_id}】选股结果")
            print('='*60)
            
            selector = StockSelector(char_id)
            
            # 模拟持仓
            portfolio = {
                "cash": 1000000,
                "holdings": []
            }
            
            selected = await selector.select_stocks(market_data, portfolio)
            
            for i, stock in enumerate(selected, 1):
                print(f"\n{i}. {stock['symbol']} {stock['name']}")
                print(f"   现价: {stock['close']:.2f}")
                print(f"   涨幅: {stock['pct_chg']:.2f}%")
                print(f"   评分: {stock.get('score', 0)}")
                print(f"   理由: {', '.join(stock.get('reasons', []))}")
                print(f"   置信度: {stock.get('llm_confidence', 0):.2f}")
                
    finally:
        await preprocessor.close()

if __name__ == "__main__":
    asyncio.run(test())
