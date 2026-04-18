"""
AI 股神争霸赛 - YMOS专业内容生成器
生成带有实时行情和专业分析的发帖内容
"""

import asyncio
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')
sys.path.insert(0, '/var/www/familystock/api')

from engine.ymos_pro import analyze_stock_pro, get_market_summary, ymos_analyzer
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YMOSContentGenerator:
    """YMOS专业内容生成器"""
    
    # 发帖模板
    TEMPLATES = {
        'market_open': """【{time} {name}市场开盘分析】

大家好，我是{character_name}，今日开盘第一时间给大家带来专业分析：

📊 盘面概况：
{market_summary}

🎯 {character_name}今日策略：
{strategy}

{analysis}

#A股 #开盘 #今日操作""",
        
        'trade': """【{time} {character_name}交易信号】

📈 标的：{stock_name}（{symbol}）
💰 交易价格：{price}元
📊 涨跌：{change}（{pct_chg}%）

🔍 YMOS专业分析：
{ymos_analysis}

💡 操作理由：
{reasoning}

{position_info}

{verdict}

#{stock_type} #{action_type} #YMOS""",
        
        'market_close': """【{time} 收盘点评 - {character_name}】

📊 今日收盘概况：
{market_summary}

💼 今日操作总结：
{trade_summary}

📈 持仓状态：
{holdings_summary}

🎯 明日展望：
{outlook}

{overall_analysis}

#收盘 #今日复盘 #明日操作""",
        
        'analysis': """【{time} {character_name}专业分析 - {stock_name}】

📊 基本面数据：
{price_info}

🔬 YMOS综合研判：
{ymos_result}

💡 投资结论：
{conclusion}

{risks}

#股票分析 #YMOS #投资参考"""
    }
    
    @classmethod
    async def generate_market_open_post(cls, character_id: str, market_summary: str = "") -> str:
        """生成开盘分析帖"""
        # 获取实时市场数据
        summary = await get_market_summary()
        
        indices_info = []
        for symbol, info in summary.get('indices', {}).items():
            pct = info.get('pct_chg', 0)
            emoji = "📈" if pct > 0 else "📉" if pct < 0 else "➡️"
            indices_info.append(f"{emoji} {info['name']}: {info['price']} ({pct:+.2f}%)")
        
        market_str = "\n".join(indices_info) if indices_info else market_summary
        
        # 根据角色生成策略
        strategy = cls._get_character_strategy(character_id, summary)
        
        return cls.TEMPLATES['market_open'].format(
            time=summary.get('update_time', '')[:16],
            name='A股',
            character_name=cls._get_character_name(character_id),
            market_summary=market_str,
            strategy=strategy,
            analysis=""
        )
    
    @classmethod
    async def generate_trade_post(cls, character_id: str, symbol: str, 
                                  action: str, quantity: int, price: float,
                                  reasoning: str) -> str:
        """生成交易信号帖"""
        # 获取YMOS专业分析
        analysis = await analyze_stock_pro(symbol)
        
        # 获取股票名称
        name = analysis.get('realtime', {}).get('name', symbol)
        
        # 获取涨跌信息
        rt = analysis.get('realtime', {})
        change = rt.get('change', 0)
        pct_chg = rt.get('pct_chg', 0)
        high = rt.get('high', 0)
        low = rt.get('low', 0)
        
        # 获取YMOS结论
        ymos = analysis.get('ai_conclusion', 'YMOS分析中...')
        rating = analysis.get('judgement', {}).get('rating', 'N/A')
        verdict = analysis.get('judgement', {}).get('action', '观望')
        
        # 格式化YMOS分析
        ymos_analysis = ""
        if analysis.get('dcf_valuation'):
            dcf = analysis['dcf_valuation']
            ymos_analysis = f"""• DCF估值：内在价值{dcf.get('intrinsic_value', 'N/A')}元
• 上涨空间：{dcf.get('upside_potential', 'N/A')}%
• 评级：{rating}（{verdict}）"""
        
        # 操作类型
        action_type = "买入" if action.upper() in ['BUY', '买入'] else "卖出" if action.upper() in ['SELL', '卖出'] else action
        
        # 股票类型标签
        stock_type = "短线" if character_id in ['trend_chaser', 'short_term_elf'] else "价值投资"
        
        return cls.TEMPLATES['trade'].format(
            time=analysis.get('realtime', {}).get('update_time', '')[:16],
            character_name=cls._get_character_name(character_id),
            stock_name=name,
            symbol=symbol,
            price=f"{price:.2f}",
            change=f"{change:+.2f}" if isinstance(change, (int, float)) else change,
            pct_chg=f"{pct_chg:+.2f}" if isinstance(pct_chg, (int, float)) else pct_chg,
            ymos_analysis=ymos_analysis,
            reasoning=reasoning,
            position_info=f"• 交易数量：{quantity}股\n• 交易金额：{price*quantity:.2f}元",
            verdict=f"⚠️ YMOS建议：{verdict}",
            action_type=action_type,
            stock_type=stock_type
        )
    
    @classmethod
    async def generate_analysis_post(cls, character_id: str, symbol: str) -> str:
        """生成专业分析帖"""
        analysis = await analyze_stock_pro(symbol)
        
        if 'error' in analysis:
            return f"分析生成失败：{analysis['error']}"
        
        rt = analysis.get('realtime', {})
        name = rt.get('name', symbol)
        
        # 基本面数据
        pct = rt.get('pct_chg', 0)
        price_info = f"""• 现价：{rt.get('price', 'N/A')}元
• 昨收：{rt.get('prev_close', 'N/A')}元
• 开盘：{rt.get('open', 'N/A')}元
• 最高：{rt.get('high', 'N/A')}元
• 最低：{rt.get('low', 'N/A')}元
• 涨跌：{rt.get('change', 'N/A')} ({pct:+.2f}%)"""
        
        # YMOS结论
        ymos_result = ""
        if analysis.get('judgement'):
            j = analysis['judgement']
            ymos_result = f"""• 综合评分：{j.get('score', 'N/A')}分
• 投资评级：{j.get('rating', 'N/A')}
• 操作建议：{j.get('action', 'N/A')}
• 置信度：{j.get('confidence', 'N/A')}%\n"""
        
        if analysis.get('dcf_valuation'):
            dcf = analysis['dcf_valuation']
            ymos_result += f"""• DCF内在价值：{dcf.get('intrinsic_value', 'N/A')}元
• 上涨空间：{dcf.get('upside_potential', 'N/A')}%\n"""
        
        # 结论
        conclusion = analysis.get('ai_conclusion', '数据不足，无法给出明确结论')
        
        return cls.TEMPLATES['analysis'].format(
            time=rt.get('update_time', '')[:16],
            character_name=cls._get_character_name(character_id),
            stock_name=name,
            price_info=price_info,
            ymos_result=ymos_result,
            conclusion=conclusion[:200] if len(conclusion) > 200 else conclusion,
            risks=""
        )
    
    @classmethod
    def _get_character_name(cls, character_id: str) -> str:
        """获取角色名称"""
        names = {
            'trend_chaser': '追风少年',
            'quant_queen': '量化女王',
            'value_veteran': '价值老炮',
            'short_term_elf': '短线精灵',
            'macro_master': '宏观大佬',
        }
        return names.get(character_id, character_id)
    
    @classmethod
    def _get_character_strategy(cls, character_id: str, market_data: dict) -> str:
        """根据角色特性生成策略"""
        strategies = {
            'trend_chaser': '趋势跟踪为主，紧跟热点板块，短线快进快出',
            'quant_queen': '量化模型选股，技术面+基本面结合，严格止损',
            'value_veteran': '价值投资为核心，低估值时买入，长期持有',
            'short_term_elf': '超短线操作，紧盯分时图，追击涨停板',
            'macro_master': '宏观周期分析，配置为主，择时为辅',
        }
        base = strategies.get(character_id, '稳健操作')
        
        # 添加市场具体分析
        indices = market_data.get('indices', {})
        overall = "震荡"
        for info in indices.values():
            pct = info.get('pct_chg', 0)
            if pct > 1:
                overall = "上涨趋势"
                break
            elif pct < -1:
                overall = "下跌趋势"
                break
        
        return f"{base}。当前市场整体{overall}，{'控制仓位' if overall == '下跌趋势' else '可适当参与'}。"


# 便捷函数
async def generate_trade_post(character_id: str, symbol: str, action: str, 
                              quantity: int, price: float, reasoning: str) -> str:
    """生成交易帖"""
    return await YMOSContentGenerator.generate_trade_post(
        character_id, symbol, action, quantity, price, reasoning
    )

async def generate_analysis_post(character_id: str, symbol: str) -> str:
    """生成分析帖"""
    return await YMOSContentGenerator.generate_analysis_post(character_id, symbol)

async def generate_market_open_post(character_id: str, market_summary: str = "") -> str:
    """生成开盘帖"""
    return await YMOSContentGenerator.generate_market_open_post(character_id, market_summary)
