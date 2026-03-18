#!/bin/bash
# 看板数据更新脚本 - 每15分钟执行

TODAY=$(date +%Y-%m-%d)
TASK_FILE="/var/www/familystock/tasks/$TODAY.md"
OUTPUT_FILE="/var/www/familystock/tasks/dashboard-data.json"

# 检查任务文件是否存在
if [ ! -f "$TASK_FILE" ]; then
    echo '{"tasks":[],"updated":"'$(date -Iseconds)'","error":"任务文件不存在"}' > "$OUTPUT_FILE"
    exit 1
fi

# 生成JSON头部
echo '{"tasks":[' > "$OUTPUT_FILE"

# 解析任务数据
first=true
grep -E '^\|\s*TASK-' "$TASK_FILE" | while read line; do
    # 提取任务信息
    task_id=$(echo "$line" | awk -F'|' '{print $2}' | tr -d ' ')
    title=$(echo "$line" | awk -F'|' '{print $3}' | sed 's/^ *//;s/ *$//')
    status_text=$(echo "$line" | awk -F'|' '{print $5}' | sed 's/^ *//;s/ *$//')
    agent=$(echo "$line" | awk -F'|' '{print $6}' | sed 's/^ *//;s/ *$//' | tr -d '@')
    
    # 跳过空行
    [ -z "$task_id" ] && continue
    
    # 转换状态
    if [[ "$status_text" == *"已完成"* ]] || [[ "$status_text" == *"✅"* ]]; then
        status="done"
    elif [[ "$status_text" == *"进行中"* ]] || [[ "$status_text" == *"🔄"* ]] || [[ "$status_text" == *"测试中"* ]] || [[ "$status_text" == *"🧪"* ]]; then
        status="progress"
    else
        status="todo"
    fi
    
    # 添加逗号（如果不是第一个）
    if [ "$first" = true ]; then
        first=false
    else
        echo ',' >> "$OUTPUT_FILE"
    fi
    
    # 输出任务JSON
    echo -n "{\"id\":\"$task_id\",\"title\":\"$title\",\"agent\":\"$agent\",\"status\":\"$status\"}" >> "$OUTPUT_FILE"
done

# 生成JSON尾部
echo '],"updated":"'$(date -Iseconds)'"}' >> "$OUTPUT_FILE"

echo "看板数据已更新: $OUTPUT_FILE"
