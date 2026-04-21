# 共享记忆更新 SOP

**版本**: 1.0
**日期**: 2026-04-22
**目的**: 确保每次开发更新都同步到共享记忆，运维团队可追溯

---

## 核心原则

**每次开发完成一个小更新（API/前端/BugFix/配置变更），必须更新共享记忆。**

---

## 更新时机

触发条件（满足任一）：
- 完成一个 API 端点
- 完成一个前端功能
- 修复一个 Bug
- 完成一个 Phase
- 部署上线
- 配置变更（环境变量/ systemd / Nginx 等）

---

## 更新内容（必须包含）

每个更新记录必须包含：

```
## [update_id] 标题

**时间**: YYYY-MM-DD HH:MM
**Agent**: pm / lingxi / hermes
**类型**: api | frontend | bugfix | config | deploy | phase
**状态**: done | failed | in-progress
**Git提交**: (可选)
**内容**:
  - 变更1
  - 变更2
**影响**:
  - 谁受影响
  - 需要注意什么
**待办**:
  - (可选) 后续跟进事项
```

---

## 存储位置（三处同时更新）

| 位置 | 用途 |
|------|------|
| `/var/www/ai-god-of-stocks/shared/memory/reports/` | Markdown 人类可读报告 |
| `/var/www/ai-god-of-stocks/shared/memory.db` | SQLite task_states + sync_log 机器可查 |
| `/var/www/familystock/data/` | 同步复制（供灵犀读取） |

---

## 执行脚本

每次完成后运行：

```bash
# 标准用法
/var/www/ai-god-of-stocks/shared/update_shared_memory.sh \
  --title "Phase 3.2 评论功能" \
  --type "phase" \
  --status "done" \
  --content "后端4个API+前端评论Tab" \
  --git "4765eeb" \
  --impact "用户可评论AI帖子和交易"

# 快速用法（从最新git commit自动读取）
/var/www/ai-god-of-stocks/shared/update_shared_memory.sh --auto
```

---

## 三步检查清单

每次更新后确认：
- [ ] Markdown 报告已写入 `/var/www/ai-god-of-stocks/shared/memory/reports/`
- [ ] SQLite task_states 已写入 `shared/memory.db`
- [ ] 同步复制到 `/var/www/familystock/data/`

---

## 禁止事项

- ❌ 不写共享记忆就下线
- ❌ 只写一处（Markdown 和 SQLite 必须同时更新）
- ❌ 模糊描述（如"修复bug"而不说明是什么bug）
