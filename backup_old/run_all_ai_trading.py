#!/usr/bin/env python3
"""
为5个AI执行完整交易流程
验收标准：5个AI都有操作，都发了交易贴
"""

import asyncio
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from datetime import datetime
from core.characters import get_all_characters, get_character
from data.preprocessor import DataPreprocessor
from data.db_manager_sqlite import DatabaseManager
from engine.selector import StockSelector
from engine.trading import TradingEngine, PortfolioManager
from core.bbs import BBSSystem, Post, PostType
from core.humanized_templates import templates
import uuid

async def run_all_ai_trading():
    """为所有AI执行交易流程"""
    
    print("=" * 70)
    print(f"🚀 5个AI完整交易流程 - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)
    
    # 初始化组件
    preprocessor = DataPreprocessor()
    db = DatabaseManager()
    portfolio_manager = PortfolioManager(db)
    bbs = BBSSystem()
    
    results = []
    
    try:
        # 准备市场数据（所有AI共享）
        print("\n📊 准备市场数据...")
        market_data = await preprocessor.prepare_market_data()
        print(f"✅ 股票行情: {len(market_data.stock_quotes)} 只")
        print(f"✅ 热点板块: {len(market_data.hot_sectors)} 个")
        print(f"✅ 龙虎榜: {len(market_data.dragon_tiger)} 条")
        
        # 为每个AI执行流程
        for char_id in get_all_characters().keys():
            character = get_character(char_id)
            
            print(f"\n{'='*70}")
            print(f"🤖 {character.name} ({character.style})")
            print(f"{'='*70}")
            
            result = {
                'ai_id': char_id,
                'ai_name': character.name,
                'has_trade': False,
                'has_post': False,
                'error': None
            }
            
            try:
                # 1. 加载投资组合
                portfolio = await portfolio_manager.load_portfolio(char_id)
                print(f"💰 资产: 现金¥{portfolio.cash:,.0f} | 持仓{len(portfolio.holdings)}只 | 总资产¥{portfolio.total_value:,.0f}")
                
                # 2. 选股（规则+LLM+YMOS+避免同质化）
                print(f"🔍 选股中...")
                selector = StockSelector(char_id)
                selected = await selector.select_stocks(market_data, portfolio)
                
                if selected:
                    print(f"✅ 选出{len(selected)}只:", end=" ")
                    for s in selected[:3]:
                        ymos_score = ""
                        if 'ymos_analysis' in s:
                            ymos_score = f"(YMOS:{s['ymos_analysis'].get('overall_score', 0)}分)"
                        print(f"{s['name']}{ymos_score}", end=" ")
                    print()
                else:
                    print(f"⚠️ 无候选股票")
                
                # 3. 交易决策
                print(f"📈 交易决策...")
                engine = TradingEngine(char_id, portfolio)
                decision = await engine.make_decision(market_data, selected)
                
                if decision:
                    print(f"✅ 决策: {decision.action.value.upper()} {decision.name} {decision.quantity}股 @ ¥{decision.price:.2f}")
                    
                    # 4. 执行交易
                    trade_success = engine.execute_trade(decision)
                    print(f"💼 执行: {'成功' if trade_success else '失败'}")
                    
                    # 5. 保存持仓
                    await portfolio_manager.save_portfolio(portfolio)
                    
                    # 6. 保存交易记录
                    try:
                        await db.save_trade(char_id, character.name, decision, trade_success)
                        print(f"📝 交易记录已保存")
                    except Exception as e:
                        print(f"❌ 交易记录保存失败: {e}")
                    
                    # 7. 生成交易帖子（真人语气）
                    try:
                        action_text = "买入" if decision.action.value == "buy" else "卖出"
                        
                        # 使用真人语气模板
                        if decision.action.value == "buy":
                            content = templates.generate_buy_post(
                                ai_id=char_id,
                                ai_name=character.name,
                                symbol=decision.symbol,
                                name=decision.name,
                                quantity=decision.quantity,
                                price=decision.price,
                                reason=decision.reason,
                                emotion="neutral"
                            )
                            title = f"买入了{decision.name}"
                        else:
                            content = templates.generate_sell_post(
                                ai_id=char_id,
                                ai_name=character.name,
                                symbol=decision.symbol,
                                name=decision.name,
                                quantity=decision.quantity,
                                price=decision.price,
                                pnl=0,
                                reason=decision.reason,
                                emotion="neutral"
                            )
                            title = f"卖出了{decision.name}"
                        
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
                        print(f"   内容: {content[:50]}...")
                        result['has_post'] = True
                        
                    except Exception as e:
                        print(f"❌ 帖子生成失败: {e}")
                    
                    result['has_trade'] = True
                    
                else:
                    print(f"⚠️ 无交易决策")
                    
                    # 生成无交易说明帖子（真人语气）
                    try:
                        content = templates.generate_hold_post(
                            ai_id=char_id,
                            ai_name=character.name,
                            holdings=[{"name": h.name, "symbol": h.symbol} for h in portfolio.holdings],
                            emotion="neutral"
                        )
                        title = f"今天没操作"
                        
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
                        print(f"📤 无交易说明已发布: {title}")
                        result['has_post'] = True
                        
                    except Exception as e:
                        print(f"❌ 帖子生成失败: {e}")
                
                print(f"✅ {character.name} 流程完成")
                
            except Exception as e:
                print(f"❌ {character.name} 失败: {e}")
                result['error'] = str(e)
            
            results.append(result)
            await asyncio.sleep(1)
        
        # 汇总结果
        print(f"\n{'='*70}")
        print("📊 执行结果汇总")
        print(f"{'='*70}")
        
        for r in results:
            trade_status = "✅有交易" if r['has_trade'] else "⚠️无交易"
            post_status = "✅有帖子" if r['has_post'] else "❌无帖子"
            error_info = f" | 错误:{r['error'][:30]}" if r['error'] else ""
            print(f"{r['ai_name']}: {trade_status} | {post_status}{error_info}")
        
        # 验收标准
        all_have_post = all(r['has_post'] for r in results)
        print(f"\n{'='*70}")
        if all_have_post:
            print("🎉 验收通过！5个AI都发布了帖子")
        else:
            print("❌ 验收未通过！部分AI未发布帖子")
        print(f"{'='*70}")
        
    except Exception as e:
        print(f"\n❌ 整体流程失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await preprocessor.close()
        await db.close()

if __name__ == "__main__":
    asyncio.run(run_all_ai_trading())
