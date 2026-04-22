#!/bin/bash
# MiniRock 信息市场数据层 RAF 长任务循环
# 用法: bash run.sh
# 前置: pip install requests feedparser jieba pymysql

set -e

PROJECT_DIR="/var/www/ai-god-of-stocks/api/raf_news_market"
VENV="/var/www/familystock/api/venv/bin/python3"
PROMPT="$PROJECT_DIR/prompt.json"

echo "[INFO] MiniRock 信息市场数据层 RAF 启动"
echo "[INFO] 项目目录: $PROJECT_DIR"
echo ""

# 循环读取任务
while true; do
    # 读取当前任务ID
    TASK_ID=$(python3 -c "import json; d=json.load(open('$PROMPT')); print(d.get('current_task',''))")
    
    if [ -z "$TASK_ID" ]; then
        echo "[DONE] 所有任务已完成，退出循环"
        break
    fi
    
    TASK_FILE="$PROJECT_DIR/../tasks/running/${TASK_ID}.json"
    
    if [ ! -f "$TASK_FILE" ]; then
        echo "[ERROR] 任务文件不存在: $TASK_FILE"
        break
    fi
    
    # 读取任务信息
    TASK_TITLE=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d.get('title',''))")
    TASK_ACTION=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d.get('action',''))")
    TASK_TARGET=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d.get('target',''))")
    TASK_ACCEPTANCE=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d.get('acceptance',''))")
    TASK_VERIFY=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d.get('verification',''))")
    TASK_ESTIMATED=$(python3 -c "import json; d=json.load(open('$TASK_FILE')); print(d.get('estimated_time',''))")
    
    echo "=========================================="
    echo "[开始] $TASK_TITLE"
    echo "[预期] $TASK_ESTIMATED"
    echo "[验收] $TASK_ACCEPTANCE"
    echo "=========================================="
    
    # 标记为running
    mv "$PROJECT_DIR/../tasks/inbox/${TASK_ID}.json" "$PROJECT_DIR/../tasks/running/${TASK_ID}.json" 2>/dev/null || true
    python3 -c "
import json
d=json.load(open('$PROMPT'))
d['current_task']='$TASK_ID'
d['status']='running'
json.dump(d,open('$PROMPT','w'),ensure_ascii=False,indent=2)
"
    
    # 执行任务
    SUCCESS=false
    
    case "$TASK_ACTION" in
        "read")
            echo "[执行] 读取文件/数据库: $TASK_TARGET"
            if [[ "$TASK_TARGET" == *.db ]]; then
                RESULT=$(sqlite3 "$TASK_TARGET" ".schema news" 2>&1)
            else
                RESULT=$(cat "$TASK_TARGET" 2>&1 | head -50)
            fi
            echo "$RESULT"
            if [ $? -eq 0 ]; then SUCCESS=true; fi
            ;;
        "write")
            echo "[执行] 编写脚本: $TASK_TARGET"
            echo "[说明] 脚本将由主会话委派子代理编写"
            # 脚本编写任务，标记为需要主会话处理
            SUCCESS="needs_main_session"
            ;;
        "cron")
            echo "[执行] 配置定时任务: $TASK_TARGET"
            echo "[说明] cron配置由主会话处理"
            SUCCESS="needs_main_session"
            ;;
        *)
            echo "[ERROR] 未知动作: $TASK_ACTION"
            ;;
    esac
    
    # 更新状态
    if [ "$SUCCESS" = "true" ]; then
        echo "[完成] $TASK_ID"
        python3 -c "
import json
d=json.load(open('$PROMPT'))
d['completed_tasks']+=1
# 找下一个任务
import os
inbox=sorted(os.listdir('$PROJECT_DIR/../tasks/inbox/'))
running=sorted(os.listdir('$PROJECT_DIR/../tasks/running/'))
if inbox:
    next_id=inbox[0].replace('.json','')
    d['current_task']=next_id
    d['status']='in_progress'
else:
    d['current_task']=''
    d['status']='all_done'
json.dump(d,open('$PROMPT','w'),ensure_ascii=False,indent=2)
"
        # 移动到done
        mv "$PROJECT_DIR/../tasks/running/${TASK_ID}.json" "$PROJECT_DIR/../tasks/done/${TASK_ID}.json" 2>/dev/null || true
    elif [ "$SUCCESS" = "needs_main_session" ]; then
        echo "[跳过] 需要主会话处理"
        break
    else
        echo "[失败] $TASK_ID，需要人工介入"
        break
    fi
    
    echo ""
done

echo "[INFO] RAF 循环结束"
