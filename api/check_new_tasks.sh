#!/bin/bash
# 15分钟检查新任务脚本

LOG_FILE="/var/log/familystock/task_check.log"
TASK_FILE="/var/www/familystock/tasks/$(date +%Y-%m-%d).md"

echo "[$(date)] 开始检查新任务..." >> $LOG_FILE

# 检查是否有待领取且分配给灵犀的任务
NEW_TASKS=$(grep -n "待领取.*@灵犀\|分配给.*灵犀.*待领取" $TASK_FILE 2>/dev/null)

if [ -n "$NEW_TASKS" ]; then
    echo "[$(date)] 发现新任务:" >> $LOG_FILE
    echo "$NEW_TASKS" >> $LOG_FILE
    
    # 自动领取任务（更新状态为进行中）
    sed -i 's/\[📋 待领取.*@灵犀\]/[🔄 进行中]/g' $TASK_FILE
    sed -i 's/状态.*待领取/状态 | 🔄 进行中\n领取时间 | '"$(date +'%Y-%m-%d %H:%M')"'/g' $TASK_FILE
    
    echo "[$(date)] 已自动领取新任务" >> $LOG_FILE
    
    # 记录到工作日志
    echo "## 🕐 $(date +'%Y-%m-%d %H:%M') 灵犀自动领取任务" >> /var/www/familystock/tasks/work-log.md
    echo "| 字段 | 内容 |" >> /var/www/familystock/tasks/work-log.md
    echo "|------|------|" >> /var/www/familystock/tasks/work-log.md
    echo "| 事件 | 自动检测到新任务并领取 |" >> /var/www/familystock/tasks/work-log.md
    echo "| 任务详情 | $NEW_TASKS" >> /var/www/familystock/tasks/work-log.md
else
    echo "[$(date)] 暂无新任务" >> $LOG_FILE
fi

# 检查任务进度，每30分钟更新一次
if [ $(( $(date +%M) % 30 )) -eq 0 ]; then
    echo "[$(date)] 定期更新任务进度..." >> $LOG_FILE
fi

echo "[$(date)] 检查完成" >> $LOG_FILE
