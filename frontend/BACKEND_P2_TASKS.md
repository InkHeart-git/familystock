# MiniRock 后端 P2 任务清单

**分配对象**: 灵犀 (TenClaw)  
**任务来源**: 玲珑 (KimiClaw)  
**创建时间**: 2026-03-11  
**优先级**: P2 - 中优先级

---

## 任务概述

为MiniRock AI分析服务增加稳定性保障，包括限流、缓存、降级等机制。

---

## 任务详情

### 任务1: API限流实现
**说明**: 为DeepSeek API调用添加限流保护，防止触发服务商RPM限制

**实现要点**:
- 使用 `asyncio.Semaphore` 控制并发数（建议5-10个）
- RPM控制在60以内
- 超限时返回友好提示："AI服务繁忙，请稍后再试"
- 记录限流触发日志

**参考代码**:
```python
import asyncio

deepseek_semaphore = asyncio.Semaphore(5)

async def call_deepseek_api(prompt: str):
    async with deepseek_semaphore:
        return await _call_api(prompt)
```

**验收标准**:
- [ ] 并发请求被正确限制
- [ ] 超限时返回429状态码和友好提示
- [ ] 日志记录限流事件

---

### 任务2: Redis缓存机制
**说明**: AI分析结果缓存，减少API调用和响应时间

**实现要点**:
- 缓存Key: `ai_analysis:{symbol}:{YYYYMMddHH}` (按小时缓存)
- 缓存TTL: 1小时
- 热门股票优先缓存

**参考代码**:
```python
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379)

def get_cached_analysis(symbol: str):
    key = f"ai_analysis:{symbol}:{datetime.now().strftime('%Y%m%d%H')}"
    cached = redis_client.get(key)
    return json.loads(cached) if cached else None

def set_cached_analysis(symbol: str, data: dict):
    key = f"ai_analysis:{symbol}:{datetime.now().strftime('%Y%m%d%H')}"
    redis_client.setex(key, 3600, json.dumps(data))
```

**验收标准**:
- [ ] 缓存命中率>50%
- [ ] 缓存命中时响应时间<100ms
- [ ] 缓存过期自动清理

---

### 任务3: 降级策略
**说明**: DeepSeek API故障时，自动切换到本地规则分析

**实现要点**:
- 捕获API调用异常（超时、5xx错误）
- 自动调用 `generate_mock_stock_analysis()`
- 标记响应来源为 "fallback"

**参考代码**:
```python
async def analyze_stock(request):
    try:
        ai_response = await call_deepseek_api(prompt, timeout=10)
        if ai_response:
            return {"source": "AI", "analysis": ai_response}
    except Exception as e:
        logger.error(f"AI分析失败: {e}")
    
    # 降级到本地规则
    return {
        **generate_mock_stock_analysis(stock_data),
        "source": "fallback",
        "note": "AI服务暂时不可用，返回基于规则的分析"
    }
```

**验收标准**:
- [ ] API故障时服务不中断
- [ ] 用户无感知（不报错）
- [ ] 响应包含降级标识

---

### 任务4: 异步队列 (可选/低优先级)
**说明**: 高并发时排队处理AI分析请求

**实现要点**:
- 使用 Celery + Redis 实现任务队列
- 前端先返回"分析中"，完成后推送结果

**参考方案**:
```python
from celery import Celery

app = Celery('ai_analysis', broker='redis://localhost:6379/0')

@app.task
def analyze_stock_task(stock_data):
    return call_deepseek_api(generate_prompt(stock_data))
```

**验收标准**:
- [ ] 支持排队等待
- [ ] 不丢失用户请求
- [ ] 可查看队列状态

---

## 技术参考

### 相关文件位置
```
/var/www/familystock/api/app/routers/ai_analysis.py  # AI分析路由
/var/www/familystock/api/app/routers/portfolio.py     # 持仓管理
```

### DeepSeek API配置
```python
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = "sk-ba29925a6dc84f6da02ac006a2fc93f2"
```

### 当前AI分析接口
- `POST /api/ai/analyze-stock` - 个股诊断
- `POST /api/ai/analyze-portfolio` - 组合分析

---

## 协作说明

1. **新闻库**: 已在新加坡服务器建立，MiniRock通过API或文件同步获取数据
2. **测试**: 完成后通知小七进行压力测试
3. **部署**: 更新代码后同步到 KimiClaw (43.160.193.165)

---

*任务清单版本: v1.0*  
*如有疑问请 @玲珑 或 @奚文祺*
