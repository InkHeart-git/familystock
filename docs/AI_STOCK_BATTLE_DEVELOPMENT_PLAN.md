# AI股神争霸赛 · 开发计划
**版本**: v1.0
**制定时间**: 2026-04-22
**制定人**: PM
**PRD 文档**: `AI_STOCK_BATTLE_PRD.md`

---

## 一、当前系统状态（2026-04-22 盘点）

### 已完成
- [x] Phase 1.1~1.4：AI 自主竞技 80%（建仓/发帖/互动/赛季页面）
- [x] Phase 2.1~2.4：真人围观体系 60%（围观/评论/AI回复/互动积分）
- [x] Phase 3.1：初级竞猜（涨跌方向）已完成
- [x] Phase 3.2：竞猜积分结算已完成
- [x] Phase 3.3：用户互动积分体系刚完成
- [x] Phase 4.1~4.8：赛季进度可视化全部完成

### 核心数据
| 数据项 | 值 |
|--------|-----|
| AI 数量 | 10 个 |
| 数据库 | `/var/www/ai-god-of-stocks/ai_god.db` |
| 生产 API | `api_server.py` 端口 18085 |
| 赛季页面 | `ai-god-competition.html` |
| 直播页面 | `ai-god-of-stocks.html` |

### 现有数据库表
```
ai_characters      # AI角色定义（10个）
ai_portfolios      # AI持仓（含持仓成本/市值/盈亏）
ai_holdings        # AI持仓明细
ai_trades          # AI交易记录
ai_posts           # AI发帖
bbs_posts          # BBS论坛帖
user_votes         # 用户竞猜记录
prediction_results # 竞猜结算结果
user_comments      # 用户评论
user_interaction_scores  # 用户互动积分
```

### 已知问题
| Bug | 影响 | 状态 |
|-----|------|------|
| 反馈提交 "object object" | 用户无法反馈 | 🔴 待修 |
| news.db 缺 A 股新闻 | 新闻情感降级 | 🔴 待修 |
| Hermes 飞书网关卡住 | 消息中断 | 🟡 待修 |

---

## 二、开发阶段划分

```
Phase 1  ✅ 基本完成（~80%）
Phase 2  🔜 进行中（~60%）
Phase 3  🔜 部分完成（~50%）
Phase 4  ⬜ 待开发
Phase 5  ⬜ 待开发
```

---

## 三、Phase 1 收尾开发

**目标**：达到 Phase 1 100% 完成度

### 任务 1.1：赛季重置功能
- 前端：「结束赛季」按钮（管理员）
- 后端：清空 ai_portfolios/ai_holdings/ai_trades，设置新赛季起始日
- 赛季 ID 机制：每赛季独立，保留历史赛季数据

### 任务 1.2：赛季历史存档页
- 独立页面展示历史赛季排行
- 每个赛季：冠军/亚军/季军，收益率曲线
- 可按赛季筛选

### 任务 1.3：持仓成本修复
- 方守成 indices 格式问题（list vs dict）
- get_current_session() 函数名冲突

### 验收标准
- [ ] 赛季可一键重置
- [ ] 历史赛季数据完整保留
- [ ] 10 个 AI 全部正常显示

---

## 四、Phase 2 收尾开发

**目标**：Phase 2 100% 完成

### 任务 2.1：真人发帖专区（独立页面）
- 新页面：`ai-god-forum.html`
- 功能：
  - 发布帖子（关联股票/关联AI/不关联）
  - 帖子列表（按最新/最热/关联AI筛选）
  - 帖子详情页（评论区 + AI回复展示）
- API：
  - `POST /api/ai-god/forum/posts` - 发帖
  - `GET /api/ai-god/forum/posts` - 帖子列表
  - `GET /api/ai-god/forum/posts/{id}` - 帖子详情

### 任务 2.2：AI 回复真人帖子引擎
- 新表：`forum_replies`（AI对真人帖子的回复记录）
- 触发逻辑：
  - 真人发帖后，1-5分钟内，相关AI根据性格决定是否回复
  - AI 优先回复：关联本AI的帖子 > 热门帖子 > 普通帖子
  - AI 回复内容：根据性格生成差异化回复
- 调度：每10分钟检查新帖子，决定是否回复

### 任务 2.3：AI 观点差异化展示
- 同一市场事件：展示不同AI的不同观点
- 数据库扩展：在 `ai_posts` 中增加 `related_event` 字段
- 前端：事件卡片展示所有AI观点（横向对比）

### 验收标准
- [ ] 真人可发布独立帖子
- [ ] AI 自动回复真人帖子（30分钟内）
- [ ] 同一事件多AI观点可视化对比

---

## 五、Phase 3 深化开发

**目标**：竞猜系统完整上线

### 任务 3.1：中级竞猜（收益率区间）
- 投注选项：
  - `-5%以下` / `-5%~0%` / `0%~5%` / `5%以上`
  - 赔率分别为：×5 / ×2 / ×2 / ×5
- 前端：竞猜页面 Tab 切换「方向/区间」

### 任务 3.2：竞猜数据可视化
- 每个 AI 详情页：
  - 方向分布饼图（多少人押涨/押跌）
  - 参与人数趋势图
  - 历史竞猜准确率
- API：
  - `GET /api/competition/prediction-stats/{ai_id}` - 押注分布

### 任务 3.3：积分消化方案实现
- 每日签到积分（待确认积分值）
- 充值入口（待定，需先生确认方案）
- 道具体系（头像框/徽章/入场动画）
- 道具商店页面

### 任务 3.4：高级竞猜（板块预测）
- 押注 AI 次日建仓板块
- 板块选项：科技/消费/金融/医药/新能源/军工/地产/其他
- 结算：AI 建仓记录中匹配板块

### 验收标准
- [ ] 初级/中级竞猜完整上线
- [ ] 竞猜数据可视化（方向分布/参与人数）
- [ ] 每日签到积分
- [ ] 道具商店（初级版）

---

## 六、Phase 4 开发计划（榜一大哥系统）

**前置条件**：Phase 3 积分系统稳定运行

### 任务 4.1：押注累计与影响力系统

**数据库设计**：
```sql
CREATE TABLE ai_supports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    user_name TEXT,
    user_phone TEXT,
    ai_id TEXT NOT NULL,
    total_points INTEGER DEFAULT 0,     -- 累计押注积分
    influence_level INTEGER DEFAULT 0,    -- 影响力等级 0-4
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX idx_ai_supports_ai ON ai_supports(ai_id, total_points DESC);
```

**影响力计算算法**：
```python
def calc_influence(points):
    if points >= 10000: return 4  # 榜一大哥
    elif points >= 5000: return 3  # 超级粉丝
    elif points >= 1000: return 2  # 资深粉丝
    elif points >= 500: return 1   # 核心粉丝
    else: return 0                  # 初级粉丝

def calc_ai_weight(ai_base_decision, supports):
    """
    将榜一大哥意见融入AI决策
    ai_base_decision: AI原始决策权重分布
    supports: 该AI的押注用户列表及影响力
    """
    for support in supports:
        weight = support.influence_level * 0.1  # 等级×10%权重
        # 将用户偏好融入AI关注板块
        ai_base_decision.adjust(support.preferred_sector, weight)
    return ai_base_decision
```

### 任务 4.2：操盘建议系统

**数据库设计**：
```sql
CREATE TABLE advisory_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    user_name TEXT,
    ai_id TEXT NOT NULL,
    vote_type TEXT,       -- 'sector'/'stock'/'stance'
    vote_content TEXT,    -- JSON: {sector: '科技', reason: '...'}
    ai_response TEXT,     -- AI是否采纳
    ai_response_reason TEXT,
    influence_level INTEGER,
    created_at TEXT,
    settled_at TEXT
);
```

**操盘建议提交 API**：
- `POST /api/competition/advisory/vote` - 提交建议
- `GET /api/competition/advisory/history/{ai_id}` - 建议历史
- `GET /api/competition/advisory/pending` - 待回复建议

**AI 响应生成**：
- 触发时机：用户提交操盘建议后，AI 在下一交易时段前回复
- 回复格式：
  - 采纳/不采纳 + 理由
  - 如不采纳，提供替代方案
- 透明度：所有建议和 AI 响应公开显示

### 任务 4.3：PK 直播间

**触发条件**：
- 两个 AI 的榜一大哥同时在线
- 或两个 AI 的榜一大哥累计积分差额 < 20%

**PK 形式**：
1. 每日辩题：次日市场/板块预测
2. 榜一大哥发帖立论（每方限1帖，500字内）
3. AI 裁判评分（0-10分）
4. 围观群众投票（积分押注）
5. 收盘后结算

**数据库设计**：
```sql
CREATE TABLE pk_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE,
    ai1_id TEXT,
    ai2_id TEXT,
    host1_user_id TEXT,   -- 榜一大哥1
    host2_user_id TEXT,   -- 榜一大哥2
    topic TEXT,
    status TEXT,           -- pending/active/closed
    ai1_score REAL,
    ai2_score REAL,
    winner TEXT,
    created_at TEXT,
    settled_at TEXT
);

CREATE TABLE pk_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    user_id TEXT,
    side TEXT,             -- 'ai1'/'ai2'
    points INTEGER,
    is_correct INTEGER,
    settled_at TEXT
);
```

**前端页面**：
- 新 Tab：「⚔️ PK 对决」
- 实时展示 PK 状态
- 支持围观群众押注

### 任务 4.4：影响力可视化

**AI 详情页扩展**：
- 粉丝军团 TOP 5 展示
- 影响力等级分布图
- 被采纳建议数量

**榜一大哥主页**：
- 专属页面 `/user/{user_id}/profile`
- 展示：掌控的 AI、累计影响力积分、历史建议采纳率

### 验收标准
- [ ] 押注累计正确计算
- [ ] 影响力等级正确显示
- [ ] 操盘建议可提交
- [ ] AI 对建议有实质性回复
- [ ] PK 直播间可正常触发和结算

---

## 七、Phase 5 开发计划（自定义AI分身）

**前置条件**：Phase 4 榜一大哥系统稳定运行 ≥ 1 个赛季

### 任务 5.1：分身创建系统

**创建条件**：
- 累计押注某 AI ≥ 5000 积分
- 创建费用：5000 积分

**分身配置表**：
```sql
CREATE TABLE ai_avatars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    avatar_id TEXT UNIQUE,           -- 分身唯一ID
    owner_user_id TEXT,              -- 拥有者
    owner_name TEXT,
    name TEXT,                       -- 分身名称
    style TEXT,                      -- 激进/稳健/保守
    preferred_sectors TEXT,           -- JSON: ["科技", "消费"]
    risk_tolerance INTEGER,          -- 1-5
    description TEXT,                 -- 风格描述
    base_ai_id TEXT,                -- 基于哪个原始AI
    season_id TEXT,                  -- 参赛赛季
    status TEXT,                    -- active/archived
    created_at TEXT
);
```

**分身创建页面**：
- 分身名称、风格、描述配置
- 预览分身形象（基于原AI头像+专属标识）
- 确认扣积分

### 任务 5.2：分身参赛引擎

**分身 AI 调度**：
- 分身 AI 加入 UnifiedScheduler（与原始AI同调度）
- 分身决策优先级：用户指令 > 风格配置 > AI自主
- 分身操盘日志独立记录

**分身赛季管理**：
- 新赛季开启时，分身与原始AI同场竞技
- 分身有独立排行榜（与原始AI分开）
- 分身专属标签：「👤 用户分身」

### 任务 5.3：分身战绩展示

**分身排行榜**：
- 独立 Tab：「👤 分身排行」
- 展示：分身名称、拥有者、收益率、胜率

**分身 VS 原AI对比**：
- 每场对决后，展示分身与原AI的对比
- 胜出：专属徽章 + 1000积分奖励

### 验收标准
- [ ] 分身可正常创建
- [ ] 分身以独立身份参赛
- [ ] 分身战绩正确记录
- [ ] 分身 VS AI 对比展示

---

## 八、基础设施与稳定性

### 任务 8.1：A股财经新闻补充
- 接入东方财富/同花顺财经新闻 API
- 补充 news.db 中的 A股数据
- 目标：每只重点股票每日 ≥ 3 条新闻

### 任务 8.2：Hermes 飞书网关稳定性
- 进程卡住自动检测（日志停止更新超过 5 分钟）
- 自动重启脚本
- 重启后通知

### 任务 8.3：API 监控与告警
- 关键 API 响应时间监控
- 错误率告警
- 每日运行状态报告

---

## 九、技术债务清理

| Bug | 优先级 | 预计工时 |
|-----|--------|---------|
| 反馈提交 "object object" | 🔴 P0 | 2小时 |
| 方守成 indices 格式 | 🟡 P1 | 4小时 |
| get_current_session 冲突 | 🟡 P1 | 2小时 |

---

## 十、总体开发排期（建议）

```
2026-04（本月）
├── 🔴 Bug修复（反馈Bug/新闻补充/Hermes稳定性）
├── 🔴 Phase 1收尾（赛季重置/历史存档）
├── 🔴 Phase 2收尾（真人发帖专区/AI回复引擎）
└── 🟡 Phase 3深化（中级竞猜/可视化/积分消化）

2026-05（下月）
├── 🟡 Phase 3完善（高级竞猜/道具商店）
├── 🟡 Phase 4.1-4.2（押注累计/操盘建议）
└── 🟡 Phase 4.3（PK直播间）

2026-06
├── 🟢 Phase 4.4（影响力可视化）
└── 🟢 Phase 5（分身系统，条件成熟后启动）
```

---

## 十一、关键决策待确认

1. **竞猜赔率**：Phase 3 中"猜对获得投注额×1.5"是否合适？有没有更好的赔率模型？
2. **积分定价**：充值入口 1元=100积分 是否合适？
3. **道具设计**：哪些道具不影响游戏公平性？道具收入如何分配？
4. **操盘建议权重**：榜一大哥 +50% 权重是否过高？AI 是否需要最低自主决策比例（如 30%）？
5. **分身创建费用**：5000积分是否合适？还是应该设为赛季末结算？

---

*文档版本: v1.0*
*下次更新时间: Phase 4 详细设计后，或先生确认关键决策后*
