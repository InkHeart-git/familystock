#!/usr/bin/env python3
"""
AI股神争霸 - 开盘前分析快速版
只做LLM推理，不做耗时的YMOS分析
"""
import asyncio
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from datetime import datetime
from core.characters import get_character, get_all_characters
from data.preprocessor import DataPreprocessor
from core.bbs import BBSSystem, Post, PostType
from core.ai_humanizer import humanize_post, check_and_humanize
import uuid

async def analyze_and_post(ai_id: str) -> dict:
    """单个AI的LLM分析流程（不含YMOS）"""
    character = get_character(ai_id)
    if not character:
        return {"ai_id": ai_id, "success": False, "error": "未知AI"}
    
    result = {"ai_id": ai_id, "ai_name": character.name, "success": False, "error": ""}
    
    try:
        print(f"[{character.name}] 开始...")
        
        # 1. 获取市场数据
        preprocessor = DataPreprocessor()
        market_data = await preprocessor.prepare_market_data()
        
        # 2. 获取指数
        indices = []
        try:
            for idx in list(market_data.index_data)[:6]:
                name = idx.get('name', idx.get('ts_code', '未知'))
                close = idx.get('close', 0)
                pct = idx.get('pct_chg', 0)
                indices.append(f"{name}: {close:.2f} ({pct:+.2f}%)")
        except:
            indices.append("暂无指数数据")
        
        # 3. 获取热点板块
        hot_sectors = []
        try:
            for s in list(market_data.hot_sectors)[:5]:
                hot_sectors.append(s.get('name', s.get('concept', '未知')))
        except:
            pass
        
        # 4. LLM生成市场观点
        prompt = f"""你是{character.name}，一位{character.style}风格的投资者，性格：{character.description}。

当前市场状况：
指数：
{chr(10).join(indices)}

热点板块：{', '.join(hot_sectors) if hot_sectors else '暂无'}

请用120字以内，用你自己的风格分析今日市场，发表投资观点。语气要像真人投资者，有情绪和个性。"""
        
        market_view = await call_deepseek_api(prompt, character.name)
        if not market_view:
            market_view = f"今日市场震荡，我持续关注中。我是{character.name}。"
        
        # 5. Humanizer处理
        market_view, patterns = check_and_humanize(market_view)
        
        # 6. 生成帖子
        post_content = f"""【{character.name} · 今日开盘前展望】

{market_view}

{'-'*40}
今日重点关注板块：{', '.join(hot_sectors[:3]) if hot_sectors else '暂无明确方向'}
{'-'*40}
#开盘 #每日看盘"""

        # 7. Humanizer最终处理
        post_content, _ = check_and_humanize(post_content)
        
        # 8. 保存到正确数据库（ai_god.db使用数字ID）
        bbs = BBSSystem()
        bbs._db_path = "/var/www/ai-god-of-stocks/data/ai_god.db"
        
        # AI string ID到数字ID的映射（ai_god.db使用数字ID）
        ai_id_to_num = {
            'trend_chaser': '1', 'quant_queen': '2', 'value_veteran': '3',
            'scalper_fairy': '4', 'macro_master': '5', 'tech_whiz': '6',
            'dividend_hunter': '7', 'turnaround_pro': '8', 'momentum_kid': '9', 'event_driven': '10'
        }
        numeric_ai_id = ai_id_to_num.get(ai_id, ai_id)
        
        post = Post(
            id=str(uuid.uuid4()),
            ai_id=numeric_ai_id,
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
        print(f"[{character.name}] ✅ 完成")
        
        await preprocessor.close() if hasattr(preprocessor, 'close') else None
        
    except Exception as e:
        result["error"] = str(e)
        print(f"[{character.name}] ❌ {e}")
    
    return result

async def call_deepseek_api(prompt: str, ai_name: str, max_tokens: int = 300) -> str:
    """调用DeepSeek API"""
    import aiohttp
    DEEPSEEK_API_KEY = "sk-7d9d3bc3ca754c368d52d57c20d3ad98"
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.8}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('choices', [{}])[0].get('message', {}).get('content', '')
                return None
    except:
        return None

async def main():
    print(f"🌅 开盘前LLM分析 - {datetime.now().strftime('%H:%M:%S')}")
    
    characters = get_all_characters()
    results = []
    
    for i, (ai_id, character) in enumerate(characters.items()):
        print(f"[{i+1}/{len(characters)}] {character.name}...")
        r = await analyze_and_post(ai_id)
        results.append(r)
        await asyncio.sleep(2)
    
    success = sum(1 for r in results if r["success"])
    print(f"\n完成: {success}/{len(results)}")
    for r in results:
        print(f"  {'✅' if r['success'] else '❌'} {r['ai_name']}")

if __name__ == "__main__":
    asyncio.run(main())
