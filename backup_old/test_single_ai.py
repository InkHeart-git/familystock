#!/usr/bin/env python3
"""
手动触发单个AI交易流程 - 用于验证
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

async def test_single_ai(char_id="trend_chaser"):
    """为单个AI执行完整流程"""
    
    print("=" * 60)
    print(f"🚀 手动触发交易流程 - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    character = get_character(char_id)
    print(f"\n🤖 AI角色: {character.name} ({character.style})")
    print(f"📝 描述: {character.description}")
    
    # 初始化组件
    preprocessor = DataPreprocessor()
    db = DatabaseManager()
    portfolio_manager = PortfolioManager(db)
    
    try:
        # 1. 准备市场数据
        print("\n📊 准备市场数据...")
        market_data = await preprocessor.prepare_market_data()
        print(f"✅ 股票行情: {len(market_data.stock_quotes)} 只")
        print(f"✅ 热点板块: {len(market_data.hot_sectors)} 个")
        
        # 2. 加载投资组合
        print(f"\n💰 加载投资组合...")
        portfolio = await portfolio_manager.load_portfolio(char_id)
        print(f"   - 现金: ¥{portfolio.cash:,.2f}")
        print(f"   - 持仓: {len(portfolio.holdings)} 只")
        print(f"   - 总资产: ¥{portfolio.total_value:,.2f}")
        
        # 3. 选股
        print(f"\n🔍 开始选股 (规则+LLM+YMOS+避免同质化)...")
        selector = StockSelector(char_id)
        selected = await selector.select_stocks(market_data, portfolio)
        
        if selected:
            print(f"✅ 选出 {len(selected)} 只股票:")
            for i, stock in enumerate(selected[:5], 1):
                ymos_info = ""
                if 'ymos_analysis' in stock:
                    ymos = stock['ymos_analysis']
                    ymos_info = f" | YMOS:{ymos.get('overall_score', 0)}分 {ymos.get('recommendation', '')}"
                print(f"   {i}. {stock['name']} ({stock['symbol']}) - 置信度:{stock.get('llm_confidence', 0):.2f}{ymos_info}")
        else:
            print(f"⚠️ 没有选出符合条件的股票")
        
        # 4. 交易决策
        print(f"\n📈 交易决策...")
        engine = TradingEngine(char_id, portfolio)
        decision = await engine.make_decision(market_data, selected)
        
        if decision:
            print(f"✅ 交易决策: {decision.action.value.upper()} {decision.name}")
            print(f"   - 股票: {decision.name} ({decision.symbol})")
            print(f"   - 数量: {decision.quantity} 股")
            print(f"   - 价格: ¥{decision.price:.2f}")
            print(f"   - 金额: ¥{decision.quantity * decision.price:,.2f}")
            print(f"   - 信心: {decision.confidence * 100:.0f}%")
            print(f"   - 理由: {decision.reason[:100]}...")
            
            # 5. 执行交易
            print(f"\n💼 执行交易...")
            trade_success = engine.execute_trade(decision)
            print(f"✅ 交易执行: {'成功' if trade_success else '失败'}")
            
            # 6. 保存持仓
            await portfolio_manager.save_portfolio(portfolio)
            print(f"✅ 持仓已保存")
            
            # 7. 保存交易记录
            try:
                trade_id = await db.save_trade(
                    char_id,
                    character.name,
                    decision,
                    trade_success
                )
                print(f"✅ 交易记录已保存 (ID: {trade_id})")
            except Exception as e:
                print(f"❌ 保存交易记录失败: {e}")
            
            # 8. 生成交易帖子
            try:
                from core.bbs import BBSSystem, Post, PostType
                import uuid
                
                bbs = BBSSystem()
                action_text = "买入" if decision.action.value == "buy" else "卖出"
                
                title = f"{action_text}成功 {decision.name}"
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
*{character.catchphrase}*
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
                print(f"✅ 交易帖子已生成: {title}")
                
            except Exception as e:
                print(f"❌ 生成交易帖子失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ 无交易决策")
            print(f"   原因: 没有符合条件的交易机会")
            
            # 生成无交易说明
            try:
                from core.bbs import BBSSystem, Post, PostType
                import uuid
                
                bbs = BBSSystem()
                
                # 分析原因
                if not selected:
                    reason = "今日市场没有符合我选股标准的股票。"
                elif portfolio.cash < 10000:
                    reason = "当前现金不足，等待更好的入场时机。"
                elif len(portfolio.holdings) >= 3:
                    reason = "已达到最大持仓数量限制，先观察现有持仓表现。"
                else:
                    reason = "虽然发现了一些候选股票，但经过综合分析后，认为当前不是最佳入场时机。"
                
                title = f"今日无交易 - {character.name}的观察"
                content = f"""【交易观察】

{character.avatar} **{character.name}** 今日无交易操作

**当前状态**:
- 现金: ¥{portfolio.cash:,.2f}
- 持仓数量: {len(portfolio.holdings)} 只
- 总资产: ¥{portfolio.total_value:,.2f}

**无交易原因**:
{reason}

**选股情况**:
{"发现 " + str(len(selected)) + " 只候选股票" if selected else "未发现符合标准的候选股票"}

**下一步计划**:
继续监控市场，等待符合{character.style}策略的机会出现。

---
*{character.catchphrase}*
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
                print(f"✅ 无交易说明帖子已生成: {title}")
                
            except Exception as e:
                print(f"❌ 生成无交易说明失败: {e}")
        
        print(f"\n{'='*60}")
        print("✅ 流程完成!")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n❌ 流程失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await preprocessor.close()
        await db.close()

if __name__ == "__main__":
    # 测试追风少年
    asyncio.run(test_single_ai("trend_chaser"))
