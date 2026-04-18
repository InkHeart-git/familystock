#!/usr/bin/env python3
"""
为James Wong（分红小能手）单独运行交易
"""

import asyncio
import sys
sys.path.insert(0, '/var/www/familystock/ai-god-of-stocks')

from datetime import datetime
from core.characters import get_character
from data.preprocessor import DataPreprocessor
from data.db_manager_sqlite import DatabaseManager
from engine.selector import StockSelector
from engine.trading import TradingEngine, PortfolioManager
from core.bbs import BBSSystem, Post, PostType
import uuid

async def run_james_wong_trading():
    """为James Wong执行交易流程"""
    
    char_id = "dividend_hunter"
    character = get_character(char_id)
    
    print("=" * 70)
    print(f"🚀 James Wong（分红小能手）交易流程 - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)
    
    # 初始化组件
    preprocessor = DataPreprocessor()
    db = DatabaseManager()
    portfolio_manager = PortfolioManager(db)
    bbs = BBSSystem()
    
    try:
        # 准备市场数据
        print("\n📊 准备市场数据...")
        market_data = await preprocessor.prepare_market_data()
        print(f"✅ 股票行情: {len(market_data.stock_quotes)} 只")
        
        # 加载投资组合
        portfolio = await portfolio_manager.load_portfolio(char_id)
        print(f"💰 资产: 现金¥{portfolio.cash:,.0f} | 持仓{len(portfolio.holdings)}只 | 总资产¥{portfolio.total_value:,.0f}")
        
        # 选股
        print(f"🔍 选股中...")
        selector = StockSelector(char_id)
        selected = await selector.select_stocks(market_data, portfolio)
        
        if selected:
            print(f"✅ 选出{len(selected)}只:", end=" ")
            for s in selected[:3]:
                print(f"{s['name']}", end=" ")
            print()
        else:
            print(f"⚠️ 无候选股票")
            return
        
        # 交易决策
        print(f"📈 交易决策...")
        engine = TradingEngine(char_id, portfolio)
        decision = await engine.make_decision(market_data, selected)
        
        if decision:
            print(f"✅ 决策: {decision.action.value.upper()} {decision.name} {decision.quantity}股 @ ¥{decision.price:.2f}")
            
            # 执行交易
            trade_success = engine.execute_trade(decision)
            print(f"💼 执行: {'成功' if trade_success else '失败'}")
            
            # 保存持仓
            await portfolio_manager.save_portfolio(portfolio)
            print(f"💾 持仓已保存")
            
            # 生成交易帖子
            action_text = "买入" if decision.action.value == "buy" else "卖出"
            title = f"{action_text}成功 {decision.name}"
            
            content = f"""【交易动态】

💰 **{character.name}** {action_text}操作

**股票**: {decision.name} ({decision.symbol})
**数量**: {decision.quantity} 股
**价格**: ¥{decision.price:.2f}
**金额**: ¥{decision.quantity * decision.price:,.2f}

**交易理由**:
{decision.reason}

**信心指数**: {decision.confidence * 100:.0f}%

---
*{character.description}*
"""
            
            post = Post(
                id=str(uuid.uuid4()),
                ai_id=char_id,
                ai_name=character.name,
                ai_avatar=character.avatar,
                post_type=PostType.TRADE,
                content=content,
                timestamp=datetime.now(),
                likes=0,
                replies=0
            )
            post.trade_info = {
                'symbol': decision.symbol,
                'stock_name': decision.name,
                'price': decision.price,
                'quantity': decision.quantity,
                'action': decision.action.value,
                'pnl': 0
            }
            
            bbs.posts.append(post)
            bbs.save_post(post)
            print(f"📤 交易帖子已发布: {title}")
            
            print(f"\n✅ James Wong 交易流程完成！")
        else:
            print(f"⚠️ 无交易决策")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_james_wong_trading())
