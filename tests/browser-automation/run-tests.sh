#!/bin/bash
#
# run-tests.sh - MiniRock automated test runner
# One-click testing for all modules
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORTS_DIR="/var/www/familystock/tests/reports"
BASE_URL="http://43.160.193.165"

# Ensure directories exist
mkdir -p "$REPORTS_DIR"

log_info() { echo -e "${GREEN}[TEST]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "\n${BLUE}========== $1 ==========${NC}"; }

# Check prerequisites
check_prerequisites() {
    log_section "环境检查"
    
    # Check Node.js
    if ! command -v node >/dev/null 2>&1; then
        log_error "Node.js 未安装"
        exit 1
    fi
    log_info "Node.js: $(node --version)"
    
    # Check Playwright
    if ! [ -d "$SCRIPT_DIR/node_modules/playwright" ]; then
        log_warn "Playwright 未安装，正在安装..."
        cd "$SCRIPT_DIR"
        npm install playwright
    fi
    log_info "Playwright: 已安装"
    
    # Check browser-lock.sh
    if ! [ -x "$SCRIPT_DIR/browser-lock.sh" ]; then
        chmod +x "$SCRIPT_DIR/browser-lock.sh"
    fi
    log_info "browser-lock.sh: 可执行"
    
    # Check if Chrome is running
    if ! pgrep -x chrome >/dev/null; then
        log_warn "Chrome 未运行，测试可能需要手动启动浏览器"
    else
        log_info "Chrome: 运行中"
    fi
}

# Run full test suite
run_full_test() {
    log_section "完整流程测试"
    log_info "开始测试: $(date '+%Y-%m-%d %H:%M:%S')"
    log_info "目标服务器: $BASE_URL"
    
    local report_file="$REPORTS_DIR/test-full-$(date +%Y%m%d-%H%M%S).json"
    
    cd "$SCRIPT_DIR"
    if ./browser-lock.sh run scripts/test-minirock-full.js; then
        log_info "测试完成 ✅"
    else
        log_error "测试发现失败 ❌"
    fi
    
    # Find and display latest report
    local latest_report=$(ls -t "$REPORTS_DIR"/test-report-*.json 2>/dev/null | head -1)
    if [ -n "$latest_report" ]; then
        log_info "测试报告: $latest_report"
        echo ""
        echo "结果摘要:"
        node -e "
            const fs = require('fs');
            const data = JSON.parse(fs.readFileSync('$latest_report', 'utf8'));
            console.log('  通过:', data.summary.passed);
            console.log('  失败:', data.summary.failed);
            console.log('  警告:', data.summary.warnings);
            console.log('');
            console.log('失败项:');
            data.tests.filter(t => t.status === 'FAIL').forEach(t => {
                console.log('  ❌', t.name, '-', t.detail);
            });
        "
    fi
}

# Run auth tests only
run_auth_test() {
    log_section "认证模块测试"
    log_info "测试注册、登录功能"
    
    cd "$SCRIPT_DIR"
    ./browser-lock.sh run scripts/test-minirock-auth.js 2>&1 | tee "$REPORTS_DIR/test-auth-$(date +%Y%m%d-%H%M%S).log"
}

# Run portfolio tests only
run_portfolio_test() {
    log_section "持仓功能测试"
    log_info "测试搜索、添加持仓、组合分析"
    
    cd "$SCRIPT_DIR"
    ./browser-lock.sh run scripts/test-minirock-portfolio.js 2>&1 | tee "$REPORTS_DIR/test-portfolio-$(date +%Y%m%d-%H%M%S).log"
}

# Generate HTML report
generate_report() {
    log_section "生成测试报告"
    
    local report_html="$REPORTS_DIR/index.html"
    
    cat > "$report_html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MiniRock 测试报告</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }
        .stat-card { padding: 20px; border-radius: 8px; text-align: center; }
        .stat-pass { background: #d4edda; color: #155724; }
        .stat-fail { background: #f8d7da; color: #721c24; }
        .stat-warn { background: #fff3cd; color: #856404; }
        .test-list { list-style: none; padding: 0; }
        .test-item { padding: 12px; margin: 8px 0; border-radius: 4px; display: flex; justify-content: space-between; }
        .test-pass { background: #d4edda; }
        .test-fail { background: #f8d7da; }
        .test-warn { background: #fff3cd; }
        .timestamp { color: #888; font-size: 0.9em; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 MiniRock 自动化测试报告</h1>
        <p class="timestamp">生成时间: EOF
    
    echo "$(date '+%Y-%m-%d %H:%M:%S')" >> "$report_html"
    
    cat >> "$report_html" << 'EOF'
</p>
        
        <h2>📊 最新测试结果</h2>
        <div class="summary">
EOF

    # Find latest report
    local latest=$(ls -t "$REPORTS_DIR"/test-report-*.json 2>/dev/null | head -1)
    if [ -n "$latest" ]; then
        node -e "
            const fs = require('fs');
            const data = JSON.parse(fs.readFileSync('$latest', 'utf8'));
            console.log('            <div class=\"stat-card stat-pass\"><div>✅ 通过</div><div style=\"font-size: 2em;\">' + data.summary.passed + '</div></div>');
            console.log('            <div class=\"stat-card stat-fail\"><div>❌ 失败</div><div style=\"font-size: 2em;\">' + data.summary.failed + '</div></div>');
            console.log('            <div class=\"stat-card stat-warn\"><div>⚠️ 警告</div><div style=\"font-size: 2em;\">' + data.summary.warnings + '</div></div>');
        " >> "$report_html"
        
        cat >> "$report_html" << 'EOF'
        </div>
        
        <h2>📝 详细测试项</h2>
        <ul class="test-list">
EOF

        node -e "
            const fs = require('fs');
            const data = JSON.parse(fs.readFileSync('$latest', 'utf8'));
            data.tests.forEach(t => {
                const statusClass = t.status === 'PASS' ? 'test-pass' : t.status === 'FAIL' ? 'test-fail' : 'test-warn';
                const statusIcon = t.status === 'PASS' ? '✅' : t.status === 'FAIL' ? '❌' : '⚠️';
                console.log('            <li class=\"test-item ' + statusClass + '\">');
                console.log('                <span>' + statusIcon + ' ' + t.name + '</span>');
                console.log('                <span class=\"badge\" style=\"background: ' + (t.status === 'PASS' ? '#28a745' : t.status === 'FAIL' ? '#dc3545' : '#ffc107') + '; color: white;\">' + t.status + '</span>');
                console.log('            </li>');
                if (t.detail) {
                    console.log('            <li style=\"margin-left: 20px; color: #666; font-size: 0.9em;\">' + t.detail + '</li>');
                }
            });
        " >> "$report_html"
        
        cat >> "$report_html" << 'EOF'
        </ul>
EOF
    fi
    
    cat >> "$report_html" << 'EOF'
        
        <h2>📁 历史报告</h2>
        <ul>
EOF

    # List all reports
    for report in $(ls -t "$REPORTS_DIR"/test-*.json 2>/dev/null | head -20); do
        local name=$(basename "$report")
        local date=$(echo "$name" | grep -o '[0-9]\{8\}-[0-9]\{6\}' || echo 'unknown')
        echo "            <li><a href=\"#\" onclick=\"alert('查看控制台报告: $name')\">$name</a></li>" >> "$report_html"
    done
    
    cat >> "$report_html" << 'EOF'
        </ul>
        
        <hr>
        <p style="color: #888; font-size: 0.85em;">
            MiniRock 自动化测试系统 | 
            <a href="http://43.160.193.165">返回应用</a>
        </p>
    </div>
</body>
</html>
EOF

    log_info "HTML 报告已生成: $report_html"
    log_info "访问: http://43.160.193.165/tests/reports/"
}

# Show usage
show_usage() {
    echo "MiniRock 自动化测试运行器"
    echo ""
    echo "Usage:"
    echo "  $0 full          - 运行完整测试流程"
    echo "  $0 auth          - 仅测试认证模块"
    echo "  $0 portfolio     - 仅测试持仓功能"
    echo "  $0 report        - 生成 HTML 报告"
    echo "  $0 check         - 检查环境"
    echo ""
    echo "Examples:"
    echo "  $0 full                      # 一键完整测试"
    echo "  $0 full > test.log 2>&1    # 输出到日志文件"
    echo "  $0 report                   # 生成可视化报告"
}

# Main dispatcher
case "${1:-}" in
    full)
        check_prerequisites
        run_full_test
        ;;
    auth)
        check_prerequisites
        run_auth_test
        ;;
    portfolio)
        check_prerequisites
        run_portfolio_test
        ;;
    report)
        generate_report
        ;;
    check)
        check_prerequisites
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
