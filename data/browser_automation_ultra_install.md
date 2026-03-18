# Browser Automation Ultra 安装报告

**安装时间**: 2026-03-16 09:39
**安装人**: 灵犀
**来源**: SkillHub (CN-Optimized)

---

## ✅技能信息

| 项目 | 详情 |
|------|------|
| **技能名称** | browser-automation-ultra |
| **版本** | 1.0.0 |
| **来源** | SkillHub (lightmake.site) |
| **安装路径** | `/root/.openclaw/workspace/skills/browser-automation-ultra` |
| **所有者ID** | kn79as9cnhzrpszb5kp6yp8wq580e99t |

---

## 📋 功能描述

**Zero-token browser automation via Playwright scripts with CDP lock management and human-like interaction.**

### 适用场景
1. 自动化任何基于浏览器的工作流（发布、登录、抓取、表单填写）
2. 通过将 browser-tool 探索转换为可重播脚本，降低 token 成本
3. 避免 OpenClaw browser 和 Playwright 之间的 CDP 端口冲突
4. 需要反检测/类人鼠标键盘行为的平台（有机器人检测）

### 不适用场景
- 简单的 URL 获取（使用 web_fetch 替代）
- 不需要真实浏览器会话的任务

---

## 🗂️ 安装内容

### 核心文件
```
/root/.openclaw/workspace/skills/browser-automation-ultra/
├── _meta.json                          # 技能元数据
├── SKILL.md                            # 技能文档
├── scripts/
│   ├── browser-lock.sh                  # CDP 锁管理脚本
│   ├── playwright-template.js           # Playwright 模板
│   ├── examples/                       # 示例脚本
│   │   ├── publish-deviantart.js
│   │   ├── publish-xiaohongshu.js
│   │   ├── publish-pinterest.js
│   │   ├── publish-behance.js
│   │   ├── read-proton-latest.js
│   │   ├── read-xhs-comments.js
│   │   └── reply-xhs-comment.js
│   └── utils/
│       └── human-like.js               # 类人行为模拟
└── references/
    └── anti-detection.md               # 反检测规则文档
```

### 已复制到工作空间
```
/root/.openclaw/workspace/scripts/
├── browser-lock.sh                     # ✅ 已复制并添加执行权限
└── browser/
    └── utils/
        └── human-like.js               # ✅ 已复制
```

---

## 🛠️ 依赖安装

### Playwright 全局安装
```bash
npm install -g playwright
```

**结果**: ✅ 成功安装
- **版本**: playwright@1.58.2
- **位置**: `/root/.nvm/versions/node/v22.22.1/lib`

**注意**: 未下载浏览器驱动，因为脚本会通过 CDP 连接到 OpenClaw 现有的 Chrome 会话

---

## 🎯 工作流程

### 1. 探索 (使用 browser tool，消耗 token)
使用 OpenClaw `browser` 工具（snapshot/act）探索工作流程。记录选择器、页面流程、关键等待。

### 2. 录制（编写 Playwright 脚本）
将步骤转换为脚本，保存到 `scripts/browser/<verb>-<target>.js`

### 3. 重播（零 token 消耗）
```bash
./scripts/browser-lock.sh run scripts/browser/my-task.js [args]
./scripts/browser-lock.sh run --timeout 120 scripts/browser/my-task.js
```

### 4. 修复（出错时）
1. 读取脚本错误输出
2. 使用 browser 工具重新探索失败的步骤（检查当前 UI）
3. 更新脚本的选择器/逻辑
4. 重试

---

## 🔒 CDP 锁管理

`browser-lock.sh` 管理 OpenClaw browser 和 Playwright 脚本之间的 CDP 互斥。

```bash
./scripts/browser-lock.sh run <script.js> [args]    # 获取 → 运行 → 释放（默认300s）
./scripts/browser-lock.sh run --timeout 120 <script> # 自定义超时
./scripts/browser-lock.sh acquire                    # 手动：停止 OpenClaw browser，启动 Chrome
./scripts/browser-lock.sh release                    # 手动：杀死 Chrome，释放锁
./scripts/browser-lock.sh status                     # 显示状态
```

**锁文件**: `/tmp/openclaw-browser.lock`（陈旧锁自动恢复）

---

## 🛡️ 反检测规则（强制要求）

所有脚本**必须**使用 `human-like.js`。关键规则：

| ❌ 禁止 | ✅ 必须 |
|---------|--------|
| `waitForTimeout(3000)` 固定延迟 | `humanDelay(2000, 4000)` 随机范围 |
| `input.fill(text)` 瞬间填充 | `humanType(page, sel, text)` 逐字输入 + 随机错字 |
| `element.click()` 瞬移点击 | `humanClick(page, sel)` 贝塞尔曲线路径 + hover |
| 加载后直接操作 | `humanBrowse(page)` 模拟先浏览页面 |
| `nativeSetter.call()` DOM 注入 | `humanType()` 或 `humanFillContentEditable()` |
| 固定 cron 调度 | `jitterWait(1, 10)` 随机偏移 |

---

## 📝 示例脚本

| 脚本 | 平台 | 功能 |
|------|------|------|
| `publish-deviantart.js` | DeviantArt | 上传图片，填写标题/描述/标签，提交 |
| `publish-xiaohongshu.js` | 小红书 | 发布图片笔记，关联话题标签 |
| `publish-pinterest.js` | Pinterest | 创建 Pin（标题/描述），选择画板 |
| `publish-behance.js` | Behance | 上传项目（标题/描述/标签/分类） |
| `read-proton-latest.js` | Proton Mail | 读取收件箱，输出邮件列表 JSON |
| `read-xhs-comments.js` | 小红书 | 读取通知评论，输出含回复按钮索引的 JSON |
| `reply-xhs-comment.js` | 小红书 | 按索引回复特定评论 |

---

## 🔧 环境变量

| 变量 | 默认值 | 说明 |
|-----|--------|------|
| `CDP_PORT` | 自动发现 | 覆盖 CDP 端口 |
| `CHROME_BIN` | 自动检测 | Chrome 二进制路径 |
| `HEADLESS` | 自动 | `true`/`false` 强制无头模式 |

---

## ✅ 安装验证

| 检查项 | 状态 |
|--------|------|
| 技能目录存在 | ✅ |
| SKILL.md 可读 | ✅ |
| browser-lock.sh 已复制 | ✅ |
| human-like.js 已复制 | ✅ |
| browser-lock.sh 可执行 | ✅ |
| Playwright 已安装 | ✅ |

---

## 🚀 下一步使用

### 1. 使用现有示例脚本
```bash
# 复制示例到工作空间
cp /root/.openclaw/workspace/skills/browser-automation-ultra/scripts/examples/*.js /root/.openclaw/workspace/scripts/browser/

# 运行示例
cd /root/.openclaw/workspace
./scripts/browser-lock.sh run scripts/browser/publish-xiaohongshu.js image.png "标题" "描述" "tag1,tag2"
```

### 2. 编写自定义脚本
参考 `playwright-template.js` 模板和示例脚本，使用 `human-like.js` API

---

*安装完成时间: 2026-03-16 09:41*
