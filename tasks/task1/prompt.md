# Task 1: 恢复 AI 自动交易调度

## 现状
- 持仓数据最后真正交易更新是 2026-04-09（8天前）
- cron_dispatcher.log 最后运行: 2026-04-09 16:31
- 收盘发帖 cron (`/etc/cron.d/ai_god_close`) 引用了不存在的 `agent_commands.sh`
- `price_update.sh` 只更新价格，不执行选股/交易/发帖
- `/var/www/ai-god-of-stocks/backup_old/run_subagents.py` 存在但引用了已移除的模块

## 目标
创建一个完整的每日 AI 交易调度脚本，每周一到五 15:40 执行：
1. 调用 MiniMax 为每个 AI 做选股
2. 执行交易决策
3. 更新持仓

## 验收标准
1. cron 表达式正确（周一到五 15:40）
2. 调度脚本存在且可执行
3. 手动执行后，10个AI中至少8个产生新的持仓变化（或确认保持不变）
4. ai_holdings.updated_at 变成今天

## 实现方案
使用 OpenClaw 的工具API直接触发，参考 cron_dispatcher.log 的流程：
1. 为每个AI调用 MiniMax 生成持仓分析
2. 根据分析结果更新 ai_holdings 表
3. 记录到日志

## 交付物
- `/var/www/ai-god-of-stocks/tasks/task1/schedule_ai_trading.sh`
- 更新 `/etc/cron.d/ai_god_trading`
