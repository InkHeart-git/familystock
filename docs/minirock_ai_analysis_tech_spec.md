# MiniRock AI分析系统技术方案

## 文档信息
- **版本**: v1.0
- **日期**: 2026-03-21
- **作者**: 玲珑
- **状态**: 方案设计阶段

---

## 目录
1. [系统架构](#1-系统架构)
2. [API设计](#2-api设计)
3. [AI分析方案](#3-ai分析方案)
4. [流式输出优化](#4-流式输出优化)
5. [卡片UI设计](#5-卡片ui设计)
6. [部署方案](#6-部署方案)

---

## 1. 系统架构

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户层 (Frontend)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  个股详情页  │  │  组合分析页  │  │     AI智能诊断卡片       │  │
│  │ stock-detail│  │  portfolio  │  │   (流式动画输出)         │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          └────────────────┴─────────────────────┘
                           │
                    HTTP/WebSocket
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                    API层 (Backend)                               │
│  ┌───────────────────────┼──────────────────────────────────┐   │
│  │              FastAPI + Uvicorn (Port 8000)                │   │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐  │   │
│  │  │/ai/analyze│  │/portfolio│  │   /ai/analyze-stock    │  │   │
│  │  │  -stock  │  │/holdings │  │   /stream (SSE)        │  │   │
│  │  └────┬─────┘  └────┬─────┘  └───────────┬────────────┘  │   │
│  └───────┼─────────────┼────────────────────┼───────────────┘   │
└──────────┼─────────────┼────────────────────┼───────────────────┘
           │             │                    │
           │     ┌───────┴───────┐            │
           │     │  PostgreSQL   │            │
           │     │  (用户/持仓)   │            │
           │     └───────────────┘            │
           │                                  │
           └──────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                      AI服务层                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────────────┐  │
│  │ Kimi (首选) │  │ Volcano(备用)│  │  DeepSeek (保底)       │  │
│  │ k2p5模型   │  │ ark-code    │  │  deepseek-chat         │  │
│  └─────────────┘  └─────────────┘  └────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | HTML5 + Tailwind CSS + Vanilla JS | 单页面应用，无框架依赖 |
| 后端 | FastAPI + Python 3.12 | 高性能异步API框架 |
| 数据库 | PostgreSQL + SQLite | PostgreSQL存用户数据，SQLite存股票行情 |
| AI服务 | Kimi/Volcano/DeepSeek API | 三梯队降级策略 |
| 部署 | Nginx + Uvicorn | 反向代理 + ASGI服务器 |

---

## 2. API设计

### 2.1 核心API列表

#### 2.1.1 AI个股分析
```
POST /api/ai/analyze-stock
Content-Type: application/json

Request Body:
{
  "symbol": "300317.SZ",        // 股票代码
  "name": "珈伟新能",            // 股票名称
  "current_price": 6.97,         // 当前价格
  "avg_cost": 4.32,              // 持仓成本
  "quantity": 21400,             // 持仓数量
  "change_percent": 15.97,       // 涨跌幅%
  "profit_percent": 39.15        // 盈亏比例%
}

Response:
{
  "symbol": "300317.SZ",
  "name": "珈伟新能",
  "analysis": "## 专业分析\n\n### 一、技术面...",
  "summary": "短期强势，建议持有",
  "related_news": [...],
  "news_count": 5,
  "timestamp": "2026-03-21T20:00:00",
  "source": "Kimi"  // 使用的AI服务
}
```

#### 2.1.2 AI分析流式输出 (SSE)
```
GET /api/ai/analyze-stock/stream?symbol=300317.SZ&name=珈伟新能&...

SSE Events:
event: start
data: {"type": "start", "message": "AI分析开始"}

event: card
data: {"type": "card", "card_id": 1, "title": "重要预警", "data": {...}}

event: card
data: {"type": "card", "card_id": 2, "title": "技术分析", "data": {...}}

event: complete
data: {"type": "complete", "total_cards": 3}

event: error
data: {"type": "error", "message": "分析失败"}
```

#### 2.1.3 持仓管理
```
GET    /api/portfolio/holdings?user_id=xxx  // 获取持仓
POST   /api/portfolio/holdings              // 添加持仓
DELETE /api/portfolio/holdings/{symbol}     // 删除持仓
```

### 2.2 路由配置

```python
# app/main.py
from fastapi import FastAPI
from app.routers import ai_analysis, portfolio, stock, tushare

app = FastAPI(title="MiniRock API", version="1.0")

# API路由注册
app.include_router(ai_analysis.router, prefix="/api/ai", tags=["AI分析"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["持仓管理"])
app.include_router(stock.router, prefix="/api/stock", tags=["股票数据"])
app.include_router(tushare.router, prefix="/api/tushare", tags=["行情数据"])
```

---

## 3. AI分析方案

### 3.1 伪装提示词策略 (Coding Plan模式)

**核心思路**: 利用AI的代码规划能力，让模型生成结构化的分析数据。

```python
SYSTEM_PROMPT = """你是一位资深股票分析师，拥有15年A股市场经验。
请对以下股票进行全面分析，并以JSON格式返回分析结果。

分析维度：
1. 技术面分析（趋势、支撑/压力位）
2. 基本面评估（业绩、行业地位）
3. 持仓盈亏分析（针对用户持仓情况）
4. 风险提示（黑天鹅/灰犀牛识别）
5. 操作建议（买入/持有/卖出）

输出格式必须为标准JSON：
{
  "cards": [
    {
      "type": "warning|technical|suggestion",
      "title": "卡片标题",
      "risk_level": "高风险|中风险|低风险",
      "content": "分析内容（使用【】标记关键词）",
      "highlights": ["关键词1", "关键词2"]
    }
  ],
  "summary": "一句话总结",
  "confidence": 0.85
}

注意：
- 使用中文回答
- 内容简洁专业，避免过度乐观
- 风险提示必须具体
"""
```

### 3.2 江湖算命话术 + 答案之书 文本优化方案

**设计思路**: 结合传统算命文化的心理暗示技巧和现代心理学，让AI分析更具"仪式感"和"心理安抚"作用。

#### 3.2.1 话术模板库

```python
# 开场白模板 (营造仪式感)
OPENING_TEMPLATES = [
    "【天象】今日{stock_name}星象显示...",
    "【卦象】为您的持仓卜得一卦...",
    "【运势】{stock_name}今日气运走向...",
    "【天机】市场给出的信号是..."
]

# 涨跌解读模板 (巴纳姆效应)
BULLISH_TEMPLATES = [
    "您来得正是时候，此股正值【上升之气】",
    "古人云：顺势而为，此股 momentum 正盛",
    "卦象显示【飞龙在天】，正是大展宏图之际",
    "您的眼光独到，此股潜力不凡"
]

BEARISH_TEMPLATES = [
    "市场正在【蓄势待发】，短期调整属正常",
    "天道有常，涨久必跌，跌久必涨，无需焦虑",
    "此股正在【沉淀积蓄】，耐心等待方为上策",
    "您的持仓成本安全，风雨过后见彩虹"
]

# 答案之书式建议 (模糊但积极)
ANSWER_BOOK_TEMPLATES = [
    "此时不宜轻举妄动，静心观察为上",
    "机会正在路上，保持警觉",
    "相信您的直觉，但也需理性分析",
    "现在不是最佳时机，再等等",
    "大胆行动的时候到了",
    "与他人交流会带来新的 insights"
]

# 心理安抚话术
COMFORT_TEMPLATES = [
    "您不是一个人在战斗，市场先生也在犹豫",
    "历史数据显示，类似情况80%会【转危为安】",
    "专业的投资者都懂得：【控制风险比追求收益更重要】",
    "您的决策是正确的，只是需要时间验证"
]
```

#### 3.2.2 个性化提示词生成

```python
def generate_fortune_prompt(stock_data, user_holding):
    """生成带算命风格的AI提示词"""
    
    profit_pct = user_holding.get('profit_percent', 0)
    
    # 根据盈亏状态选择话术基调
    if profit_pct > 20:
        tone = "恭喜您，此股已现【盈利之象】"
        strategy = "可考虑分批止盈，落袋为安"
    elif profit_pct > 0:
        tone = "小有盈余，走势平稳"
        strategy = "建议继续持有，等待更大涨幅"
    elif profit_pct > -10:
        tone = "微幅调整，不必惊慌"
        strategy = "市场情绪波动，基本面未变"
    else:
        tone = "暂时的困境，蕴含着转机的种子"
        strategy = "审视持仓逻辑，决定是否补仓或止损"
    
    prompt = f"""【股市运势分析】

为股票 {stock_data['name']}({stock_data['symbol']}) 进行运势解读：

【当前形势】
- 现价：{stock_data['current_price']}元
- 涨跌：{stock_data['change_percent']}%
- 您的持仓盈亏：{profit_pct}%

【天机解读】
{tone}。
{strategy}。

请以【江湖智者】的身份，结合现代金融分析，给出：
1. 一句【运势箴言】（如：顺势而为，不急不躁）
2. 三个【关键提醒】（用【】标记重要信息）
3. 一个【行动建议】（具体可操作）

语气要求：
- 既有传统的神秘感和仪式感
- 又有现代金融的专业性和可信度
- 让用户感到被理解和被安抚
"""
    return prompt
```

### 3.3 三梯队AI服务降级策略

```python
# API配置
AI_CONFIG = {
    "primary": {
        "name": "Kimi",
        "url": "https://api.kimi.com/coding/v1/messages",
        "model": "k2p5",
        "key": "sk-kimi-xxx",
        "timeout": 60
    },
    "secondary": {
        "name": "Volcano Ark",
        "url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "model": "ark-code-latest",
        "key": "6ea54b0e-xxx",
        "timeout": 45
    },
    "fallback": {
        "name": "DeepSeek",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "key": "sk-ba29925a6dc84f6da02ac006a2fc93f2",
        "timeout": 60
    }
}

async def call_ai_api_with_fallback(prompt: str) -> str:
    """带降级策略的AI调用"""
    
    # 第一梯队：Kimi
    result = await call_kimi_api(prompt)
    if result:
        return {"content": result, "source": "Kimi"}
    
    print("⚠️ Kimi失败，降级到Volcano...")
    
    # 第二梯队：Volcano Ark
    result = await call_volcano_api(prompt)
    if result:
        return {"content": result, "source": "Volcano"}
    
    print("⚠️ Volcano失败，降级到DeepSeek...")
    
    # 第三梯队：DeepSeek
    result = await call_deepseek_api(prompt)
    if result:
        return {"content": result, "source": "DeepSeek"}
    
    raise Exception("所有AI服务均不可用")
```

---

## 4. 流式输出优化

### 4.1 问题背景

**问题**: AI分析API响应时间约60秒，前端timeout 10秒，导致用户一直看到转圈动画。

**解决方案**: 采用SSE (Server-Sent Events) 流式输出，逐张生成卡片，减少等待焦虑。

### 4.2 流式输出架构

```
用户点击AI分析
     │
     ▼
┌─────────────────┐
│  显示加载动画    │  ← 立即响应
│  "AI正在思考..." │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   SSE连接建立   │
│  /ai/analyze-   │
│   stock/stream  │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐  ┌───────┐
│卡片1   │  │卡片2   │  ← 逐张流式输出
│(2秒后) │  │(5秒后) │
└───┬───┘  └───┬───┘
    │          │
    ▼          ▼
┌─────────────────┐
│  前端实时渲染    │  ← 用户立即看到内容
│  createCard()   │
└─────────────────┘
```

### 4.3 后端实现 (SSE)

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio

router = APIRouter()

@router.get("/analyze-stock/stream")
async def analyze_stock_stream(
    symbol: str,
    name: str,
    current_price: float,
    avg_cost: float = 0,
    quantity: int = 0,
    change_percent: float = 0,
    profit_percent: float = 0
):
    """流式AI分析 - SSE"""
    
    async def generate_stream():
        # 发送开始事件
        yield f"event: start\ndata: {json.dumps({'type': 'start'})}\n\n"
        
        # 准备分析数据
        stock_data = {
            "symbol": symbol,
            "name": name,
            "current_price": current_price,
            "avg_cost": avg_cost,
            "quantity": quantity,
            "change_percent": change_percent,
            "profit_percent": profit_percent
        }
        
        try:
            # 生成第一张卡片：重要预警 (约1-2秒)
            warning_card = await generate_warning_card(stock_data)
            yield f"event: card\ndata: {json.dumps({'type': 'card', 'card_id': 1, 'card_type': 'warning', 'data': warning_card})}\n\n"
            await asyncio.sleep(0.1)  # 让前端有时间渲染
            
            # 生成第二张卡片：技术分析 (约3-5秒)
            technical_card = await generate_technical_card(stock_data)
            yield f"event: card\ndata: {json.dumps({'type': 'card', 'card_id': 2, 'card_type': 'technical', 'data': technical_card})}\n\n"
            await asyncio.sleep(0.1)
            
            # 生成第三张卡片：操作建议 (约5-8秒)
            suggestion_card = await generate_suggestion_card(stock_data)
            yield f"event: card\ndata: {json.dumps({'type': 'card', 'card_id': 3, 'card_type': 'suggestion', 'data': suggestion_card})}\n\n"
            
            # 发送完成事件
            yield f"event: complete\ndata: {json.dumps({'type': 'complete', 'total_cards': 3})}\n\n"
            
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用Nginx缓冲
        }
    )
```

### 4.4 前端实现 (EventSource)

```javascript
async function startStreamAnalysis(stockData) {
  // 显示加载状态
  showLoadingState();
  
  // 构建SSE URL
  const params = new URLSearchParams({
    symbol: stockData.code,
    name: stockData.name,
    current_price: stockData.price,
    avg_cost: stockData.holding?.avg_cost || stockData.price,
    quantity: stockData.holding?.quantity || 0,
    change_percent: stockData.changePercent,
    profit_percent: stockData.holding?.profit_percent || 0
  });
  
  const eventSource = new EventSource(
    `${API_CONFIG.baseURL}/ai/analyze-stock/stream?${params}`
  );
  
  const allCardsData = [];
  
  eventSource.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      
      switch (message.type) {
        case 'start':
          console.log('AI分析开始');
          break;
          
        case 'card':
          // 收到卡片数据，立即渲染
          createAnalysisCard(message.card_type, message.data);
          allCardsData.push(message.data);
          
          // 隐藏加载动画（收到第一张卡片后）
          if (allCardsData.length === 1) {
            hideLoadingState();
          }
          break;
          
        case 'complete':
          eventSource.close();
          showCompleteState();
          break;
          
        case 'error':
          eventSource.close();
          showErrorState(message.message);
          break;
      }
    } catch (e) {
      console.error('解析SSE消息失败:', e);
    }
  };
  
  eventSource.onerror = (error) => {
    console.error('SSE连接错误:', error);
    eventSource.close();
    showErrorState('连接中断，请重试');
  };
}

// 创建分析卡片
function createAnalysisCard(cardType, data) {
  const container = document.getElementById('aiAnalysisCards');
  
  const cardHTML = `
    <div class="analysis-card card-${cardType} animate-fade-in-up">
      <div class="card-header">
        <i class="fas ${data.icon}"></i>
        <span class="card-title">${data.title}</span>
        ${data.risk_level ? `<span class="risk-badge ${data.risk_level}">${data.risk_level}</span>` : ''}
      </div>
      <div class="card-content">
        ${highlightKeywords(data.content)}
      </div>
    </div>
  `;
  
  // 插入到容器末尾
  container.insertAdjacentHTML('beforeend', cardHTML);
  
  // 滚动到新卡片
  const newCard = container.lastElementChild;
  newCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// 高亮关键词（用【】包裹的文字）
function highlightKeywords(text) {
  return text.replace(/【(.+?)】/g, '<span class="highlight-keyword">$1</span>');
}
```

### 4.5 动画效果 CSS

```css
/* 卡片淡入上滑动画 */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in-up {
  animation: fadeInUp 0.5s ease-out forwards;
}

/* 加载动画 */
@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

.loading-dots span {
  animation: pulse 1.4s ease-in-out infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

/* 打印机效果 */
@keyframes typewriter {
  from { width: 0; }
  to { width: 100%; }
}

.typewriter-effect {
  overflow: hidden;
  white-space: nowrap;
  animation: typewriter 2s steps(40, end);
}
```

---

## 5. 卡片UI设计

### 5.1 卡片类型及样式

参考截图设计，三种核心卡片：

#### 5.1.1 重要预警卡片 (Warning)
```html
<div class="analysis-card card-warning">
  <div class="card-header">
    <i class="fas fa-exclamation-triangle"></i>
    <span class="card-title">重要预警</span>
    <span class="risk-badge risk-medium">中风险</span>
  </div>
  <div class="card-content">
    今日【股价下跌】【-3.33%】，短期波动加剧。
    最新财报业绩符合预期，但需关注市场整体情绪变化。
  </div>
</div>
```

**样式**：
- 背景：粉色渐变 (#fee2e2 → #fecaca)
- 边框：左侧红色条 (4px solid #ef4444)
- 图标：警告三角形
- 圆角：16px
- 阴影：0 4px 12px rgba(239, 68, 68, 0.15)

#### 5.1.2 技术分析卡片 (Technical)
```html
<div class="analysis-card card-technical">
  <div class="card-header">
    <i class="fas fa-chart-line"></i>
    <span class="card-title">技术分析</span>
  </div>
  <div class="card-content">
    短期趋势为【震荡调整】，今日跌破28.5元。
    下方【支撑位】在27.0元附近，上方【压力位】在29.5元。
  </div>
</div>
```

**样式**：
- 背景：蓝色渐变 (#dbeafe → #bfdbfe)
- 边框：左侧蓝色条 (4px solid #3b82f6)
- 图标：折线图
- 关键词高亮：红色背景标签

#### 5.1.3 操作建议卡片 (Suggestion)
```html
<div class="analysis-card card-suggestion">
  <div class="card-header">
    <i class="fas fa-hand-pointer"></i>
    <span class="card-title">操作建议</span>
  </div>
  <div class="card-content">
    建议【持有】现有仓位，当前浮盈26.19%。
    可设置【目标价位】30.0元，【止损位】26.5元【保护利润】。
  </div>
</div>
```

**样式**：
- 背景：绿色渐变 (#d1fae5 → #a7f3d0)
- 边框：左侧绿色条 (4px solid #10b981)
- 图标：手指点击

### 5.2 CSS样式代码

```css
/* 卡片基础样式 */
.analysis-card {
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.analysis-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

/* 预警卡片 */
.card-warning {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  border-left: 4px solid #ef4444;
}

/* 技术分析卡片 */
.card-technical {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  border-left: 4px solid #3b82f6;
}

/* 操作建议卡片 */
.card-suggestion {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  border-left: 4px solid #10b981;
}

/* 卡片头部 */
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.card-header i {
  font-size: 20px;
  color: currentColor;
}

.card-title {
  font-weight: 600;
  font-size: 16px;
  flex: 1;
}

/* 风险标签 */
.risk-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.risk-high {
  background: #fecaca;
  color: #dc2626;
}

.risk-medium {
  background: #fef3c7;
  color: #d97706;
}

.risk-low {
  background: #d1fae5;
  color: #059669;
}

/* 关键词高亮 */
.highlight-keyword {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

/* 内容区域 */
.card-content {
  line-height: 1.6;
  color: #374151;
  font-size: 14px;
}
```

---

## 6. 部署方案

### 6.1 服务器配置

```nginx
# /etc/nginx/sites-enabled/minirock
server {
    listen 80;
    server_name 43.160.193.165;
    root /var/www/familystock/frontend;
    index index.html;

    # 前端文件
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API代理 - 关键：支持SSE需要禁用缓冲
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # SSE支持配置
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

### 6.2 系统服务配置

```ini
# /etc/systemd/system/minirock-api.service
[Unit]
Description=MiniRock API Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/var/www/familystock/api
Environment=PATH=/var/www/familystock/api/venv/bin
ExecStart=/var/www/familystock/api/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 6.3 启动命令

```bash
# 启动API服务
sudo systemctl start minirock-api
sudo systemctl enable minirock-api

# 查看状态
sudo systemctl status minirock-api
sudo journalctl -u minirock-api -f

# 重载Nginx
sudo nginx -t && sudo systemctl reload nginx
```

---

## 7. 性能优化建议

### 7.1 响应时间优化

| 优化方案 | 预期效果 | 实现难度 |
|---------|---------|---------|
| 流式输出 | 2秒内显示第一张卡片 | ⭐ 低 |
| AI模型缓存 | 重复股票直接返回缓存 | ⭐⭐ 中 |
| 预生成分析 | 热门股票后台预分析 | ⭐⭐⭐ 高 |
| 精简提示词 | 减少token，加速生成 | ⭐ 低 |
| 模型降级 | 先用轻量模型快速响应 | ⭐⭐ 中 |

### 7.2 缓存策略

```python
from functools import lru_cache
import hashlib

# 简单的内存缓存
_analysis_cache = {}

async def get_cached_analysis(stock_symbol: str, max_age: int = 300):
    """获取缓存的分析结果"""
    cache_key = f"analysis:{stock_symbol}"
    
    if cache_key in _analysis_cache:
        timestamp, result = _analysis_cache[cache_key]
        if time.time() - timestamp < max_age:
            return result
    
    return None

def cache_analysis(stock_symbol: str, result: dict):
    """缓存分析结果"""
    cache_key = f"analysis:{stock_symbol}"
    _analysis_cache[cache_key] = (time.time(), result)
```

---

## 8. 总结

### 8.1 技术亮点

1. **流式输出设计**: 采用SSE实现逐卡片流式输出，将60秒等待转化为2秒可见反馈
2. **三梯队降级**: Kimi → Volcano → DeepSeek，确保服务高可用
3. **算命话术融合**: 结合心理学和传统文化，提升用户体验
4. **卡片化UI**: 参考截图设计，信息层次清晰，交互友好

### 8.2 后续优化方向

1. 接入Redis实现分布式缓存
2. 添加用户反馈循环，持续优化提示词
3. 实现真正的流式Token输出（逐字显示）
4. 增加更多卡片类型（资金流向、机构评级等）

---

**文档结束**