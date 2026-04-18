#!/usr/bin/env python3
"""
单个AI交易脚本 - 用于定时调度
"""

import asyncio
import sys
import argparse

sys.path.insert(0, '/var/www/ai-god-of-stocks')

from datetime import datetime
from core.characters import get_character
from data.preprocessor import DataPreprocessor
from data.db_manager_sqlite import DatabaseManager
from engine.selector import StockSelector
from engine.trading import TradingEngine, PortfolioManager
from core.bbs import BBSSystem, Post, PostType
from core.humanized_templates import templates
from core.subagent_state import state_manager, SubAgentState
import uuid

async def run_single_ai(ai_id: str):
    """运行单个AI的交易流程"""
    
    character = get_character(ai_id)
    if not character:
        print(f"❌ 未知AI: {ai_id}")
        return
    
    print(f"\n{'='*70}")
    print(f"🤖 {character.name} ({character.style}) - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*70}")
    
    # 初始化组件
    preprocessor = DataPreprocessor()
    db = DatabaseManager()
    portfolio_manager = PortfolioManager(db)
    bbs = BBSSystem()
    
    # 加载或创建状态
    state = state_manager.load(f"single_{ai_id}", [ai_id])
    
    try:
        # 准备市场数据
        print("📊 准备市场数据...")
        market_data = await preprocessor.prepare_market_data()
        
        # 加载投资组合
        portfolio = await portfolio_manager.load_portfolio(ai_id)
        print(f"💰 资产: 现金¥{portfolio.cash:,.0f} | 持仓{len(portfolio.holdings)}只")
        
        # 选股
        print("🔍 选股中...")
        selector = StockSelector(ai_id)
        selected = await selector.select_stocks(market_data, portfolio)
        
        if selected:
            print(f"✅ 选出{len(selected)}只")
        else:
            print("⚠️ 无候选股票")
            return
        
        # 交易决策
        print("📈 交易决策...")
        engine = TradingEngine(ai_id, portfolio)
        decision = await engine.make_decision(market_data, selected)
        
        if decision:
            print(f"✅ 决策: {decision.action.value.upper()} {decision.name} {decision.quantity}股")
            
            # 执行交易
            success = engine.execute_trade(decision)
            print(f"💼 执行: {'成功' if success else '失败'}")
            
            # 保存持仓
            await portfolio_manager.save_portfolio(portfolio)
            print("💾 持仓已保存")
            
            # 记录交易到状态
            pnl = 0  # 新买入，暂无盈亏
            state.record_trade(
                ai_id=ai_id,
                symbol=decision.symbol,
                name=decision.name,
                action=decision.action.value,
                quantity=decision.quantity,
                price=decision.price,
                pnl=pnl
            )
            
            # 生成真人语气帖子
            if decision.action.value == "buy":
                content = templates.generate_buy_post(
                    ai_id=ai_id,
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
                    ai_id=ai_id,
                    ai_name=character.name,
                    symbol=decision.symbol,
                    name=decision.name,
                    quantity=decision.quantity,
                    price=decision.price,
                    pnl=pnl,
                    reason=decision.reason,
                    emotion="neutral"
                )
                title = f"卖出了{decision.name}"
            
            # 保存帖子
            post = Post(
                id=str(uuid.uuid4()),
                ai_id=ai_id,
                ai_name=character.name,
                ai_avatar=character.avatar,
                post_type=PostType.TRADE,
                content=content,
                timestamp=datetime.now(),
                likes=0,
                replies=0
            )
            bbs.posts.append(post)
            bbs.save_post(post)
            
            # 记录帖子到状态
            state.record_post(ai_id, "trade", title, content)
            
            print(f"📤 帖子已发布: {title}")
            print(f"   内容: {content[:60]}...")
            
        else:
            print("⚠️ 无交易决策")
            
            # 生成无操作帖子
            content = templates.generate_hold_post(
                ai_id=ai_id,
                ai_name=character.name,
                holdings=[{"name": h.name, "symbol": h.symbol} for h in portfolio.holdings],
                emotion="neutral"
            )
            
            post = Post(
                id=str(uuid.uuid4()),
                ai_id=ai_id,
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
            
            state.record_post(ai_id, "analysis", "今天没操作", content)
            
            print(f"📤 帖子已发布: 今天没操作")
        
        # 更新状态
        state.update_mood_trend()
        state.reset_daily()
        state_manager.save(state)
        
        print(f"✅ {character.name} 完成")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="运行单个AI交易")
    parser.add_argument("ai_id", help="AI角色ID")
    args = parser.parse_args()
    
    asyncio.run(run_single_ai(args.ai_id))
