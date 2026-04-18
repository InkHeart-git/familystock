#!/usr/bin/env python3
"""
AI股神争霸 - 开盘前分析子代理
每个AI独立运行，经过真正的LLM推理和YMOS分析
"""
import asyncio
import sys
import os
import json
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from datetime import datetime
from core.characters import get_character, get_all_characters
from data.preprocessor import DataPreprocessor
from engine.ymos_pro import YMOSProAnalyzer
from core.bbs import BBSSystem, Post, PostType
from core.ai_humanizer import humanize_post, check_and_humanize
import uuid

async def analyze_and_post(ai_id: str) -> dict:
    """单个AI的完整分析流程"""
    character = get_character(ai_id)
    if not character:
        return {"ai_id": ai_id, "success": False, "error": "未知AI"}
    
    result = {
        "ai_id": ai_id,
        "ai_name": character.name,
        "style": character.style,
        "success": False,
        "market_view": "",
        "ymos_results": [],
        "post_content": "",
        "error": ""
    }
    
    preprocessor = None
    bbs = None
    
    try:
        print(f"\n{'='*60}")
        print(f"🤖 {character.name} ({character.style}) 开盘前分析")
        print(f"{'='*60}")
        
        # 1. 获取真实市场数据
        print(f"[{character.name}] 📊 获取市场数据...")
        preprocessor = DataPreprocessor()
        market_data = await preprocessor.prepare_market_data()
        
        # 2. 获取指数数据
        indices = []
        try:
            for idx in list(market_data.index_data)[:6]:
                name = idx.get('name', idx.get('ts_code', '未知'))
                close = idx.get('close', 0)
                pct = idx.get('pct_chg', 0)
                indices.append(f"{name}: {close:.2f} ({pct:+.2f}%)")
        except Exception as e:
            print(f"[{character.name}] 获取指数失败: {e}")
            indices.append("暂无指数数据")
        
        result["indices"] = indices
        print(f"[{character.name}] ✅ 获取到{len(indices)}个指数")
        
        # 3. 获取热点板块
        hot_sectors = []
        try:
            for s in list(market_data.hot_sectors)[:5]:
                hot_sectors.append(s.get('name', s.get('concept', '未知')))
        except:
            pass
        print(f"[{character.name}] ✅ 热点板块: {hot_sectors}")
        
        # 4. 获取候选股票
        candidates = list(market_data.stock_quotes)[:50]
        print(f"[{character.name}] ✅ 候选股票: {len(candidates)}只")
        
        # 5. YMOS专业分析（前5只候选股）
        print(f"[{character.name}] 🔬 YMOS分析中...")
        ymos = YMOSProAnalyzer()
        ymos_results = []
        
        for stock in candidates[:5]:
            symbol = stock.get('symbol')
            name = stock.get('name', symbol)
            try:
                ymos_result = await ymos.analyze_stock(symbol, name)
                if 'error' not in ymos_result:
                    analysis = ymos_result.get('analysis', {})
                    strategy = ymos_result.get('strategy', {})
                    ymos_results.append({
                        "symbol": symbol,
                        "name": name,
                        "score": analysis.get('score', 0),
                        "rating": strategy.get('rating', 'N/A'),
                        "target": strategy.get('target_price', 0),
                        "reason": str(analysis.get('summary', ''))[:100]
                    })
                    print(f"[{character.name}]   {symbol} {name}: 评分{analysis.get('score', 0)}")
            except Exception as e:
                print(f"[{character.name}]   YMOS分析{stock.get('symbol')}失败: {e}")
        
        result["ymos_results"] = ymos_results
        
        # 6. 根据角色风格生成市场观点
        print(f"[{character.name}] 🧠 调用大模型生成市场观点...")
        
        view_prompt = f"""你是{character.name}，一位{character.style}风格的投资者，性格：{character.description}。

当前市场状况：
指数：
{chr(10).join(indices)}

热点板块：{', '.join(hot_sectors) if hot_sectors else '暂无'}

请用150字以内，分析今日市场，发表你的投资观点。语气要像真人投资者，有个人风格和情绪，不要像AI写的东西。避免使用"作为一个AI"、"我的分析是"这类开头。"""

        # 调用LLM API (使用DeepSeek，Kimi有问题)
        market_view = await call_deepseek_api(view_prompt, character.name)
        if not market_view:
            market_view = f"今日市场震荡，我持续关注中。{character.catchphrase}"
        result["market_view"] = market_view
        print(f"[{character.name}] ✅ 市场观点生成完成")
        
        # 7. Humanizer处理
        market_view_humanized, patterns = check_and_humanize(market_view)
        if patterns:
            print(f"[{character.name}] Humanizer检测到: {list(patterns.keys())}")
        
        # 8. 生成开盘前帖子
        post_content = f"""【{character.name} · 今日开盘前展望】

{market_view_humanized}

{'-'*40}

📊 重点关注：
"""
        
        # 添加YMOS分析结果
        if ymos_results:
            for i, r in enumerate(ymos_results[:3], 1):
                post_content += f"{i}. {r['name']}({r['symbol']}) - {r['rating']}评级\n"
                post_content += f"   {r['reason'][:60]}...\n"
        else:
            post_content += "暂无明确标的，持续观察中。\n"
        
        post_content += f"""
{'-'*40}
我是{character.name}，{character.description[:20]}...
#开盘 #每日看盘"""

        # 9. Humanizer最终处理
        post_content, patterns = check_and_humanize(post_content)
        result["post_content"] = post_content
        
        # 10. 保存到BBS
        print(f"[{character.name}] 💾 保存帖子...")
        bbs = BBSSystem()
        post = Post(
            id=str(uuid.uuid4()),
            ai_id=ai_id,
            ai_name=character.name,
            ai_avatar=character.avatar,
            post_type=PostType.ANALYSIS,
            content=post_content,
            timestamp=datetime.now(),
            likes=0,
            replies=0
        )
        bbs.save_post(post)
        result["success"] = True
        print(f"[{character.name}] ✅ 帖子已发布！")
        
    except Exception as e:
        result["error"] = str(e)
        print(f"[{character.name}] ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if preprocessor:
            try:
                await preprocessor.close()
            except:
                pass
    
    return result

async def call_deepseek_api(prompt: str, ai_name: str, max_tokens: int = 400) -> str:
    """调用DeepSeek API"""
    import aiohttp
    
    DEEPSEEK_API_KEY = "sk-7d9d3bc3ca754c368d52d57c20d3ad98"
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-chat"
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.8
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL, headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('choices', [{}])[0].get('message', {}).get('content', '')
                else:
                    error_text = await response.text()
                    print(f"[{ai_name}] DeepSeek API错误 {response.status}: {error_text[:200]}")
                    return None
    except Exception as e:
        print(f"[{ai_name}] DeepSeek API异常: {e}")
        return None

async def main():
    """主函数 - 为所有AI执行开盘前分析"""
    print("="*70)
    print(f"🌅 AI股神争霸 - 开盘前分析 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("="*70)
    
    characters = get_all_characters()
    print(f"\n🤖 共{len(characters)}个AI角色\n")
    
    results = []
    for i, (ai_id, character) in enumerate(characters.items()):
        print(f"\n[{i+1}/{len(characters)}] 处理 {character.name}...")
        result = await analyze_and_post(ai_id)
        results.append(result)
        await asyncio.sleep(3)  # 避免API调用过快
    
    # 汇总
    print("\n" + "="*70)
    print("📊 开盘前分析完成汇总")
    print("="*70)
    
    success_count = sum(1 for r in results if r["success"])
    print(f"成功: {success_count}/{len(results)}")
    
    for r in results:
        status = "✅" if r["success"] else f"❌ ({r.get('error', '未知错误')})"
        ymos_count = len(r.get('ymos_results', []))
        print(f"  {r['ai_name']}: {status} | YMOS分析:{ymos_count}只")
    
    print("="*70)
    
    return results

if __name__ == "__main__":
    asyncio.run(main())
