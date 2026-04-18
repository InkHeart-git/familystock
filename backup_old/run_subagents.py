#!/usr/bin/env python3
"""
AI股神争霸赛 - 子代理启动器
启动5个子代理，每个控制1个五虎+1个小五
"""

import asyncio
import sys
import os
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from config.subagents import SUBAGENT_CONFIG, get_ai_pair
from core.characters import get_character
from engine.trading import TradingEngine, PortfolioManager
from engine.selector import StockSelector
from data.db_manager import DatabaseManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SubAgent:
    """子代理 - 控制2个AI（1个五虎+1个小五）"""
    
    def __init__(self, subagent_id: str):
        self.config = SUBAGENT_CONFIG[subagent_id]
        self.ai_ids = self.config["ai_ids"]
        self.ai_names = self.config["ai_names"]
        self.db = DatabaseManager()
        self.portfolio_manager = PortfolioManager(self.db)
        
    async def run(self):
        """运行子代理任务"""
        logger.info(f"[{self.config['name']}] 启动 - 控制: {', '.join(self.ai_names)}")
        
        for ai_id in self.ai_ids:
            try:
                await self.process_ai(ai_id)
            except Exception as e:
                logger.error(f"[{ai_id}] 处理失败: {e}")
                
    async def process_ai(self, ai_id: str):
        """处理单个AI的选股、交易、发帖"""
        from data.preprocessor import DataPreprocessor
        
        character = get_character(ai_id)
        logger.info(f"[{character.name}] 开始选股...")
        
        # 准备市场数据
        preprocessor = DataPreprocessor()
        market_data = await preprocessor.prepare_data()
        
        # 1. 选股
        selector = StockSelector(ai_id)
        selected = await selector.select_stocks(market_data)
        
        if not selected:
            logger.warning(f"[{character.name}] 未选出股票")
            return
            
        logger.info(f"[{character.name}] 选出 {len(selected)} 只股票")
        
        # 2. 加载投资组合
        portfolio = await self.portfolio_manager.load_portfolio(ai_id)
        
        # 3. 交易决策
        engine = TradingEngine(ai_id, portfolio)
        decision = await engine.make_decision(market_data, selected)
        
        if decision:
            # 4. 执行交易
            success = engine.execute_trade(decision)
            logger.info(f"[{character.name}] 交易{'成功' if success else '失败'}: {decision.symbol}")
            
            # 5. 保存持仓
            await self.portfolio_manager.save_portfolio(portfolio)
            
            # 6. 发帖
            await self.create_post(ai_id, character, decision, success)
        else:
            logger.info(f"[{character.name}] 无交易信号")
        
    async def create_post(self, ai_id: str, character, decision, success: bool):
        """创建交易帖子"""
        from core.bbs import BBSSystem, Post, PostType
        
        bbs = BBSSystem()
        
        action_text = "买入" if decision.action.value == "buy" else "卖出"
        title = f"【交易动态】{action_text} {decision.name}"
        
        content = f"""{character.avatar} **{character.name}** {action_text}操作

**股票**: {decision.name} ({decision.symbol})
**数量**: {decision.quantity} 股
**价格**: ¥{decision.price:.2f}
**金额**: ¥{decision.quantity * decision.price:,.2f}

**交易理由**:
{decision.reason}

**信心指数**: {decision.confidence * 100:.0f}%

---
*{character.description}*"""

        post = Post(
            id=str(int(asyncio.get_event_loop().time())),
            ai_id=ai_id,
            ai_name=character.name,
            title=title,
            content=content,
            post_type=PostType.TRADE,
            likes=0,
            replies=0,
            views=0,
            created_at=datetime.now()
        )
        
        post.trade_info = {
            'action': decision.action.value,
            'symbol': decision.symbol,
            'name': decision.name,
            'price': decision.price,
            'quantity': decision.quantity
        }
        
        bbs.posts.append(post)
        bbs.save_post(post)
        logger.info(f"[{character.name}] 帖子已发布: {title}")


async def run_all_subagents():
    """运行所有子代理"""
    logger.info("=" * 70)
    logger.info("启动5个子代理 - AI股神争霸赛")
    logger.info("=" * 70)
    
    tasks = []
    for subagent_id in SUBAGENT_CONFIG.keys():
        agent = SubAgent(subagent_id)
        tasks.append(agent.run())
    
    await asyncio.gather(*tasks)
    
    logger.info("=" * 70)
    logger.info("所有子代理执行完成")
    logger.info("=" * 70)


if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(run_all_subagents())
