#!/usr/bin/env python3
"""
为指定AI执行交易流程（用于补充执行）
"""

import asyncio
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from datetime import datetime
from core.characters import get_character
from data.preprocessor import DataPreprocessor
from data.db_manager import DatabaseManager
from engine.selector import StockSelector
from engine.trading import TradingEngine, PortfolioManager
from core.bbs import BBSSystem, Post, PostType
import uuid

async def trade_single_ai(char_id):
    """为单个AI执行交易"""
    
    character = get_character(char_id)
    print(f"\n{'='*60}")
    print(f"🤖 {character.name} ({character.style})")
    print(f"{'='*60}")
    
    preprocessor = DataPreprocessor()
    db = DatabaseManager()
    portfolio_manager = PortfolioManager(db)
    bbs = BBSSystem()
    
    try:
        # 准备市场数据
        print(f"📊 准备市场数据...")
        market_data = await preprocessor.prepare_market_data()
        
        # 加载投资组合
        portfolio = await portfolio_manager.load_portfolio(char_id)
        print(f"💰 资产: 现金¥{portfolio.cash:,.0f} | 持仓{len(portfolio.holdings)}只")
        
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
        
        # 交易决策
        print(f"📈 交易决策...")
        engine = TradingEngine(char_id, portfolio)
        decision = await engine.make_decision(market_data, selected)
        
        if decision:
            print(f"✅ 决策: {decision.action.value.upper()} {decision.name} {decision.quantity}股")
            
            # 执行交易
            trade_success = engine.execute_trade(decision)
            print(f"💼 执行: {'成功' if trade_success else '失败'}")
            
            # 保存持仓
            await portfolio_manager.save_portfolio(portfolio)
            
            # 保存交易记录
            try:
                await db.save_trade(char_id, character.name, decision, trade_success)
                print(f"📝 交易记录已保存")
            except Exception as e:
                print(f"❌ 交易记录失败: {e}")
            
            # 生成帖子
            try:
                action_text = "买入" if decision.action.value == "buy" else "卖出"
                content = f"""【交易动态】

{character.avatar} **{character.name}** {action_text}操作

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
                print(f"📤 帖子已发布")
                
            except Exception as e:
                print(f"❌ 帖子失败: {e}")
        else:
            print(f"⚠️ 无交易决策")
            
            # 无交易帖子
            try:
                reason = "今日市场没有符合我选股标准的股票。" if not selected else "经过综合分析，当前不是最佳入场时机。"
                
                content = f"""【交易观察】

{character.avatar} **{character.name}** 今日无交易操作

**当前状态**:
- 现金: ¥{portfolio.cash:,.2f}
- 持仓数量: {len(portfolio.holdings)} 只
- 总资产: ¥{portfolio.total_value:,.2f}

**无交易原因**:
{reason}

**下一步计划**:
继续监控市场，等待符合{character.style}策略的机会出现。

---
*{character.description}*
"""
                
                post = Post(
                    id=str(uuid.uuid4()),
                    ai_id=char_id,
                    ai_name=character.name,
                    ai_avatar=character.avatar,
                    post_type=PostType.ANALYSIS,
                    content=content,
                    timestamp=datetime.now(),
                    likes=0,
                    replies=0
                )
                
                bbs.posts.append(post)
                bbs.save_post(post)
                print(f"📤 无交易说明已发布")
                
            except Exception as e:
                print(f"❌ 帖子失败: {e}")
        
        print(f"✅ {character.name} 完成")
        
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await preprocessor.close()
        await db.close()

if __name__ == "__main__":
    # 为其他4个AI执行
    ai_list = ["quant_queen", "value_veteran", "scalper_fairy", "macro_master"]
    
    for ai_id in ai_list:
        asyncio.run(trade_single_ai(ai_id))
        print("\n" + "-"*60 + "\n")
