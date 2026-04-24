# PM 会话记录 2026-04-23

## 会话时间
2026-04-23 18:40 - 19:30 (北京时间)

## 本次工作内容

### 1. 进程守护脚本体系整理

**背景：** 服务器上存在4个版本的进程守护脚本，功能重叠，需要清理整合。

| 版本 | 文件 | 触发方式 | 监控范围 |
|------|------|----------|----------|
| V1 | `watchdog_hermes.sh` | bash while循环 | 仅 Hermes |
| V2 | `hermes_gateway_watchdog.sh` | bash while循环 | 仅 Hermes + 日志熔断 |
| V3 | `monitor_and_recover.sh` | systemd timer每2分钟 | 全栈5服务+资源监控 |
| 专用 | `watchdog_sentiment.sh` | cron每3分钟 | 情感评分进程 |

**清理操作：**
- 删除 `watchdog_hermes.sh` (V1)
- 删除 `hermes_gateway_watchdog.sh` (V2) - 已被V3完全覆盖
- 清理僵尸cron: `*/5 * * * * /var/www/ai-god-of-stocks/watchdog.sh` (文件不存在但每5分钟执行)
- 停用并禁用 `hermes-gateway-watchdog.timer` + `hermes-gateway-watchdog.service`

**最终运行状态：**
- `monitor_and_recover.sh` via systemd timer (每2分钟) - 主力全栈守护
- `watchdog_sentiment.sh` via cron (每3分钟) - 情感评分专用
- V3熔断机制: 冷却5分钟 + 1小时最多3次重启

---

### 2. ai-god-of-stocks.html 回归测试 & 修复

**问题：** 页面加载时4个API调用全部报错 `SyntaxError: Unexpected token '<'`

**根因：** Nginx 缺少 `/ai-api/` 代理规则，API请求被 `try_files` 匹配到 `index.html`，返回HTML而非JSON

**修复：**
1. `/etc/nginx/conf.d/ai-god-of-stocks.conf` (8085端口): 添加 `location /ai-api/` → `http://127.0.0.1:18085/`
2. `/etc/nginx/sites-enabled/minirock` (443 HTTPS): 添加 `location /ai-api/` → `http://127.0.0.1:18085/`

**验证：** 全部4个接口 200 OK - characters/rankings/posts/latest/stats

---

### 3. MiniRock 首页市场情报回归测试 & 修复

**问题：** 首页"市场情报"显示"加载失败，请刷新重试"

**根因：** `loadNewsData()` 数据提取路径错误
- API返回: `{"data": {"list": [...]}}`
- 前端代码: `data.news || data.data` (两个键均不存在)
- 导致 `news` 变量为空数组 → `.map()` 报错

**修复：**
- `MiniRock-auth.html` 第1382-1384行:
  - URL: `?limit=50` → `?page=1&page_size=50`
  - 提取: `data.news || data.data` → `data.data?.list || data.data || data.news || []`
- `news-list.html` 第406-408行: 同步修复

**验证：** 首页显示8条新闻，news-list.html显示20条，含标签(灰犀牛/利好/普通)

---

## 关键发现

1. **Nginx路由优先级陷阱**: `location /` 的 `try_files $uri $uri/ /index.html` 会吞掉所有未匹配的路径，包括API代理。需要在 `location /` 之前明确定义所有API路径的代理规则。

2. **API返回结构变更**: 新闻API从 `{"news": [...]}` 改为 `{"data": {"list": [...]}}`，前端数据提取代码需要同步更新。

3. **V3监控覆盖最全**: `monitor_and_recover.sh` 是唯一同时监控 OpenClaw + Hermes + AI-God API + MiniRock API + PostgreSQL + 内存/磁盘的守护脚本，V1/V2是冗余的。

## 修改文件清单

- `/etc/nginx/conf.d/ai-god-of-stocks.conf` - 添加 /ai-api/ 代理
- `/etc/nginx/sites-enabled/minirock` - 添加 /ai-api/ 代理
- `/var/www/familystock/frontend/MiniRock-auth.html` - 新闻数据提取路径修复
- `/var/www/familystock/frontend/news-list.html` - 新闻数据提取路径修复

## 待处理

- Phase 2+4 RAF任务队列剩余30+任务 (P2-API/P4-API/P2-FE/P4-FE等)
- Git提交待补充 (familystock仓库)
