#!/usr/bin/env python3
"""
手动触发AI股神全流程测试
为5个AI各执行一次完整的分析、决策、持仓、发帖流程
"""

import asyncio
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from datetime import datetime
from core.characters import get_all_characters, get_character
from data.preprocessor import DataPreprocessor
from data.db_manager import DatabaseManager
from engine.selector import StockSelector
from engine.trading import TradingEngine, PortfolioManager
from scheduler.main import Scheduler

async def run_full_cycle():
    """为每个AI执行完整流程"""
    
    print("=" * 60)
    print(f"🚀 AI股神全流程测试 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 初始化组件
    preprocessor = DataPreprocessor()
    db = DatabaseManager()
    portfolio_manager = PortfolioManager(db)
    
    try:
        # 准备市场数据
        print("\n📊 准备市场数据...")
        market_data = await preprocessor.prepare_market_data()
        print(f"✅ 市场数据准备完成")
        print(f"   - 股票行情: {len(market_data.stock_quotes)} 只")
        print(f"   - 热点板块: {len(market_data.hot_sectors)} 个")
        print(f"   - 龙虎榜: {len(market_data.dragon_tiger)} 条")
        
        # 为每个AI执行流程
        for char_id in get_all_characters().keys():
            print(f"\n{'='*60}")
            character = get_character(char_id)
            print(f"🤖 {character.name} ({character.style})")
            print(f"{'='*60}")
            
            try:
                # 1. 加载投资组合
                portfolio = await portfolio_manager.load_portfolio(char_id)
                print(f"\n💰 当前资产:")
                print(f"   - 现金: ¥{portfolio.cash:,.2f}")
                print(f"   - 持仓: {len(portfolio.holdings)} 只")
                print(f"   - 总资产: ¥{portfolio.total_value:,.2f}")
                
                # 2. 选股 (包含规则筛选 + LLM分析 + YMOS分析 + 避免同质化)
                print(f"\n🔍 开始选股...")
                selector = StockSelector(char_id)
                selected = await selector.select_stocks(market_data, portfolio)
                
                if selected:
                    print(f"✅ 选股完成: {len(selected)} 只")
                    for i, stock in enumerate(selected[:3], 1):
                        ymos_info = ""
                        if 'ymos_analysis' in stock:
                            ymos = stock['ymos_analysis']
                            ymos_info = f" [YMOS:{ymos.get('overall_score', 0)}分 {ymos.get('recommendation', '')}]"
                        print(f"   {i}. {stock['name']} ({stock['symbol']}) - 置信度:{stock.get('llm_confidence', 0):.2f}{ymos_info}")
                else:
                    print(f"⚠️ 没有选出符合条件的股票")
                
                # 3. 交易决策
                print(f"\n📈 交易决策...")
                engine = TradingEngine(char_id, portfolio)
                decision = await engine.make_decision(market_data, selected)
                
                if decision:
                    print(f"✅ 交易决策: {decision.action.value.upper()} {decision.name}")
                    print(f"   - 数量: {decision.quantity} 股")
                    print(f"   - 价格: ¥{decision.price:.2f}")
                    print(f"   - 金额: ¥{decision.quantity * decision.price:,.2f}")
                    print(f"   - 理由: {decision.reason[:80]}...")
                    print(f"   - 信心: {decision.confidence * 100:.0f}%")
                    
                    # 4. 执行交易
                    print(f"\n💼 执行交易...")
                    trade_success = engine.execute_trade(decision)
                    print(f"✅ 交易执行: {'成功' if trade_success else '失败'}")
                    
                    # 5. 保存持仓
                    await portfolio_manager.save_portfolio(portfolio)
                    print(f"✅ 持仓已保存")
                    
                    # 6. 保存交易记录
                    try:
                        await db.save_trade(
                            char_id,
                            character.name,
                            decision,
                            trade_success
                        )
                        print(f"✅ 交易记录已保存")
                    except Exception as e:
                        print(f"❌ 保存交易记录失败: {e}")
                    
                    # 7. 生成交易帖子
                    try:
                        from scheduler.main import Scheduler
                        scheduler = Scheduler()
                        await scheduler._create_trade_post(char_id, decision, trade_success)
                        print(f"✅ 交易帖子已生成")
                    except Exception as e:
                        print(f"❌ 生成交易帖子失败: {e}")
                else:
                    print(f"⚠️ 无交易决策")
                    
                    # 生成无交易说明
                    try:
                        from scheduler.main import Scheduler
                        scheduler = Scheduler()
                        await scheduler._create_no_trade_post(char_id, portfolio, market_data, selected)
                        print(f"✅ 无交易说明帖子已生成")
                    except Exception as e:
                        print(f"❌ 生成无交易说明失败: {e}")
                
                print(f"\n✅ {character.name} 流程完成")
                
            except Exception as e:
                print(f"\n❌ {char_id} 流程失败: {e}")
                import traceback
                traceback.print_exc()
            
            await asyncio.sleep(1)  # 避免请求过快
        
        print(f"\n{'='*60}")
        print("🎉 全流程测试完成!")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n❌ 全流程测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await preprocessor.close()

if __name__ == "__main__":
    asyncio.run(run_full_cycle())
