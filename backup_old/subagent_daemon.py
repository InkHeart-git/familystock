#!/usr/bin/env python3
"""
AI股神争霸赛 - 子代理守护进程
持续运行，每30分钟执行一次交易循环
"""

import asyncio
import sys
import time
import signal
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from config.subagents import SUBAGENT_CONFIG, get_ai_pair
from core.characters import get_character
from engine.trading import TradingEngine, PortfolioManager
from engine.selector import StockSelector
from data.db_manager import DatabaseManager
from data.preprocessor import DataPreprocessor
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/subagent_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SubAgentDaemon:
    """子代理守护进程"""
    
    def __init__(self, subagent_id: str):
        self.subagent_id = subagent_id
        self.config = SUBAGENT_CONFIG[subagent_id]
        self.ai_ids = self.config["ai_ids"]
        self.ai_names = self.config["ai_names"]
        self.db = DatabaseManager()
        self.portfolio_manager = PortfolioManager(self.db)
        self.running = True
        
        # 信号处理
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        
    def stop(self, signum, frame):
        """停止守护进程"""
        logger.info(f"[{self.config['name']}] 收到停止信号")
        self.running = False
        
    async def run(self):
        """主循环"""
        logger.info(f"=" * 70)
        logger.info(f"[{self.config['name']}] 守护进程启动")
        logger.info(f"控制AI: {', '.join(self.ai_names)}")
        logger.info(f"=" * 70)
        
        while self.running:
            try:
                # 执行交易循环
                await self.trading_cycle()
                
                # 等待30分钟
                logger.info(f"[{self.config['name']}] 等待30分钟后下次执行...")
                for _ in range(1800):  # 30分钟 = 1800秒
                    if not self.running:
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"[{self.config['name']}] 交易循环异常: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟重试
        
        logger.info(f"[{self.config['name']}] 守护进程已停止")
        
    async def trading_cycle(self):
        """执行一次交易循环"""
        logger.info(f"[{self.config['name']}] 开始交易循环 - {datetime.now()}")
        
        for ai_id in self.ai_ids:
            if not self.running:
                break
            try:
                await self.process_ai(ai_id)
            except Exception as e:
                logger.error(f"[{ai_id}] 处理失败: {e}")
                
        logger.info(f"[{self.config['name']}] 交易循环完成")
        
    async def process_ai(self, ai_id: str):
        """处理单个AI"""
        character = get_character(ai_id)
        logger.info(f"[{character.name}] 开始处理...")
        
        # 准备市场数据
        preprocessor = DataPreprocessor()
        market_data = await preprocessor.prepare_data()
        
        # 选股
        selector = StockSelector(ai_id)
        selected = await selector.select_stocks(market_data)
        
        if not selected:
            logger.info(f"[{character.name}] 未选出股票")
            return
            
        logger.info(f"[{character.name}] 选出 {len(selected)} 只股票")
        
        # 加载投资组合
        portfolio = await self.portfolio_manager.load_portfolio(ai_id)
        
        # 交易决策
        engine = TradingEngine(ai_id, portfolio)
        decision = await engine.make_decision(market_data, selected)
        
        if decision:
            # 执行交易
            success = engine.execute_trade(decision)
            logger.info(f"[{character.name}] 交易{'成功' if success else '失败'}: {decision.symbol}")
            
            # 保存持仓
            await self.portfolio_manager.save_portfolio(portfolio)
            
            # 发帖
            await self.create_post(ai_id, character, decision, success)
        else:
            logger.info(f"[{character.name}] 无交易信号")
            
    async def create_post(self, ai_id: str, character, decision, success: bool):
        """创建交易帖子"""
        from core.bbs import BBSSystem, Post, PostType
        from datetime import datetime
        
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
            id=str(int(time.time())),
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
        logger.info(f"[{character.name}] 帖子已发布")


async def main():
    """启动所有子代理守护进程"""
    logger.info("=" * 70)
    logger.info("启动5个子代理守护进程")
    logger.info("=" * 70)
    
    # 创建5个子代理
    agents = []
    for subagent_id in SUBAGENT_CONFIG.keys():
        agent = SubAgentDaemon(subagent_id)
        agents.append(agent.run())
    
    # 并发运行
    await asyncio.gather(*agents)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("主程序被中断")
