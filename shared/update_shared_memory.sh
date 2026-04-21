#!/bin/bash
# update_shared_memory.sh - 共享记忆自动同步脚本
# 每次开发完成后必须运行，确保三处同时更新
#
# 用法:
#   ./update_shared_memory.sh --title "Phase 3.2 评论功能" --type phase --status done --content "描述" --git "commit" --impact "影响"
#   ./update_shared_memory.sh --auto   # 从最新git commit自动读取

set -e

MEM_DIR="/var/www/ai-god-of-stocks/shared/memory"
DB_PATH="/var/www/ai-god-of-stocks/shared/memory.db"
SYNC_DIR="/var/www/familystock/data"
UPDATE_ID="update_$(date +%Y%m%d_%H%M%S_$$)"

# 默认值
TITLE=""
TYPE="bugfix"
STATUS="done"
CONTENT=""
GIT=""
IMPACT=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --title)   TITLE="$2"; shift 2 ;;
        --type)     TYPE="$2"; shift 2 ;;
        --status)   STATUS="$2"; shift 2 ;;
        --content)  CONTENT="$2"; shift 2 ;;
        --git)      GIT="$2"; shift 2 ;;
        --impact)   IMPACT="$2"; shift 2 ;;
        --auto)     AUTO=1; shift ;;
        *)          echo "未知参数: $1"; exit 1 ;;
    esac
done

# AUTO 模式：从git log读取
if [[ "$AUTO" == "1" ]]; then
    cd /var/www/ai-god-of-stocks
    if git rev-parse HEAD >/dev/null 2>&1; then
        GIT=$(git log -1 --format='%H')
        GIT_SHORT=$(git log -1 --format='%h')
        TITLE=$(git log -1 --format='%s')
        BODY=$(git log -1 --format='%b')
        STATUS="done"
        if echo "$TITLE" | grep -qi "phase"; then
            TYPE="phase"
        elif echo "$TITLE" | grep -qi "fix"; then
            TYPE="bugfix"
        elif echo "$TITLE" | grep -qi "frontend\|ui"; then
            TYPE="frontend"
        else
            TYPE="api"
        fi
        CONTENT="$BODY"
        echo "📋 AUTO模式: 检测到提交 ${GIT_SHORT} - $TITLE"
    else
        echo "❌ 不是git仓库或无提交"
        exit 1
    fi
fi

if [[ -z "$TITLE" ]]; then
    echo "❌ 缺少 --title 参数"
    echo "用法: $0 --title '描述' --type phase --status done --content '详细' --git 'commit' --impact '影响'"
    exit 1
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
UPDATE_MD="${UPDATE_ID}.md"

# ==================== 第一层：Markdown 报告 ====================
cat > "$MEM_DIR/reports/${UPDATE_MD}" << EOF
## ${UPDATE_ID} ${TITLE}

**时间**: ${TIMESTAMP}
**Agent**: pm
**类型**: ${TYPE}
**状态**: ${STATUS}
**Git提交**: ${GIT:-（无）}
**内容**:
${CONTENT:-（无）}
**影响**:
${IMPACT:-（无）}
EOF

echo "✅ 第一层: Markdown 报告 → $MEM_DIR/reports/${UPDATE_MD}"

# ==================== 第二层：SQLite ====================
DATA_JSON=$(python3 -c "
import json, sys
print(json.dumps({
    'type': '$TYPE',
    'git': '$GIT',
    'content': '''${CONTENT}'''[:500],
    'impact': '''${IMPACT}'''[:200]
}, ensure_ascii=False).replace(\"'\", \"''\"))
" 2>/dev/null || echo "{}")

sqlite3 "$DB_PATH" "
INSERT INTO task_states (task_id, task_name, assigned_to, status, priority, data, completed_at, updated_at)
VALUES (
    '${UPDATE_ID}',
    '$(echo "$TITLE" | sed "s/'/''/g")',
    'pm',
    '$(echo "$STATUS" | sed "s/'/''/g")',
    5,
    '${DATA_JSON}',
    '${TIMESTAMP}',
    '${TIMESTAMP}'
)
" 2>/dev/null || echo "⚠️  task_states写入失败，跳过"

# 记录sync_log（不强制要求schema匹配）
sqlite3 "$DB_PATH" "
INSERT INTO sync_log (sync_type, agent_name, entity_type, entity_id, action, sync_status, error_msg)
VALUES ('bidirectional', 'pm', 'report', '${UPDATE_ID}', 'write', 'success', '');
" 2>/dev/null || echo "⚠️  sync_log写入失败（忽略）"

echo "✅ 第二层: SQLite task_states"

# ==================== 第三层：同步到familystock目录 ====================
cp "$MEM_DIR/reports/${UPDATE_MD}" "$SYNC_DIR/${UPDATE_MD}" 2>/dev/null && echo "✅ 第三层: 同步到 familystock/data/" || echo "⚠️  familystock同步失败"

echo ""
echo "========================================"
echo "✅ 共享记忆更新完成: ${UPDATE_ID}"
echo "========================================"
echo "📝 报告: $MEM_DIR/reports/${UPDATE_MD}"
echo "🗄️  SQLite: shared/memory.db"
echo "🔄  同步: $SYNC_DIR/"
