#!/bin/bash
# sync_shared_memory.sh - 重大进展自动写入共享记忆
# 用法: ./sync_shared_memory.sh "Phase 3.2 完成" "评论功能后端+前端"
# 或直接运行: ./sync_shared_memory.sh auto  从git log最新commit读取

MEM_DIR="/var/www/ai-god-of-stocks/shared/memory/reports"
LOG_DIR="/var/www/ai-god-of-stocks/shared/memory/reports"

if [ "$1" == "auto" ]; then
    # 从git log读取最新提交
    cd /var/www/ai-god-of-stocks
    COMMIT=$(git log -1 --format='%H')
    SUBJECT=$(git log -1 --format='%s')
    DATE=$(date +%Y-%m-%d)
    AUTHOR=$(git log -1 --format='%an')
    
    echo "## git_${COMMIT:0:8}" > /tmp/sync_${DATE}.md
    echo "" >> /tmp/sync_${DATE}.md
    echo "**日期**: $DATE" >> /tmp/sync_${DATE}.md
    echo "**提交**: $SUBJECT" >> /tmp/sync_${DATE}.md
    echo "**作者**: $AUTHOR" >> /tmp/sync_${DATE}.md
    echo "" >> /tmp/sync_${DATE}.md
    git log -1 --format='%b' >> /tmp/sync_${DATE}.md
    
    cp /tmp/sync_${DATE}.md "$MEM_DIR/git_sync_${DATE}.md"
    echo "✅ 共享记忆已同步: git_sync_${DATE}.md"
    rm /tmp/sync_${DATE}.md
else
    TITLE="$1"
    DESC="$2"
    DATE=$(date +%Y%m%d_%H%M%S)
    
    cat > "$MEM_DIR/report_${DATE}.md" << EOF
# $TITLE

**日期**: $(date +%Y-%m-%d)
**Agent**: PM
**状态**: ✅ 完成

$DESC
EOF
    echo "✅ 共享记忆已写入: report_${DATE}.md"
fi
