#!/bin/bash
#
# browser-lock.sh - Manages CDP mutex between OpenClaw browser and Playwright scripts
# Only one CDP client can connect at a time
#

LOCK_FILE="/tmp/openclaw-browser.lock"
CHROME_PID_FILE="/tmp/openclaw-chrome.pid"
DEFAULT_TIMEOUT=300

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if Chrome is running with CDP
discover_cdp_port() {
    local port=$(pgrep -a chrome | grep -o 'remote-debugging-port=[0-9]*' | cut -d= -f2 | head -1)
    echo "${port:-18800}"
}

# Acquire lock
acquire_lock() {
    local timeout=${1:-30}
    local start_time=$(date +%s)
    
    while true; do
        if mkdir "$LOCK_FILE" 2>/dev/null; then
            echo $$ > "$LOCK_FILE/pid"
            echo $(discover_cdp_port) > "$LOCK_FILE/cdp_port"
            log_info "Lock acquired (PID: $$)"
            return 0
        fi
        
        # Check if existing lock is stale
        if [ -f "$LOCK_FILE/pid" ]; then
            local old_pid=$(cat "$LOCK_FILE/pid" 2>/dev/null)
            if ! kill -0 "$old_pid" 2>/dev/null; then
                log_warn "Removing stale lock from PID $old_pid"
                rm -rf "$LOCK_FILE"
                continue
            fi
        fi
        
        # Check timeout
        local current_time=$(date +%s)
        if [ $((current_time - start_time)) -gt "$timeout" ]; then
            log_error "Timeout waiting for lock"
            return 1
        fi
        
        log_info "Waiting for lock..."
        sleep 2
    done
}

# Release lock
release_lock() {
    if [ -f "$LOCK_FILE/pid" ]; then
        local pid=$(cat "$LOCK_FILE/pid")
        if [ "$pid" = "$$" ]; then
            rm -rf "$LOCK_FILE"
            log_info "Lock released"
            return 0
        fi
    fi
    log_warn "Lock not owned by this process"
    return 1
}

# Run a script with lock
run_with_lock() {
    local script="$1"
    shift
    local timeout=${1:-$DEFAULT_TIMEOUT}
    
    if ! acquire_lock 30; then
        log_error "Failed to acquire lock"
        exit 1
    fi
    
    local cdp_port=$(discover_cdp_port)
    log_info "Using CDP port: $cdp_port"
    
    # Set timeout
    (
        sleep "$timeout"
        log_warn "Script timeout after ${timeout}s"
        kill $$ 2>/dev/null
    ) &
    local timeout_pid=$!
    
    # Run script
    local exit_code=0
    export CDP_PORT="$cdp_port"
    if [ -f "$script" ]; then
        node "$script" "$@" || exit_code=$?
    else
        log_error "Script not found: $script"
        exit_code=1
    fi
    
    # Kill timeout watcher
    kill "$timeout_pid" 2>/dev/null
    wait "$timeout_pid" 2>/dev/null
    
    release_lock
    return $exit_code
}

# Show status
show_status() {
    if [ -d "$LOCK_FILE" ]; then
        echo "Status: 🔒 LOCKED"
        if [ -f "$LOCK_FILE/pid" ]; then
            local pid=$(cat "$LOCK_FILE/pid")
            echo "  PID: $pid"
            if kill -0 "$pid" 2>/dev/null; then
                echo "  Process: Running"
            else
                echo "  Process: Dead (stale lock)"
            fi
        fi
        if [ -f "$LOCK_FILE/cdp_port" ]; then
            echo "  CDP Port: $(cat "$LOCK_FILE/cdp_port")"
        fi
        if [ -f "$LOCK_FILE/timestamp" ]; then
            echo "  Since: $(cat "$LOCK_FILE/timestamp")"
        fi
    else
        echo "Status: 🔓 UNLOCKED"
        local port=$(discover_cdp_port)
        echo "  CDP Port: $port"
    fi
}

# Force release (use with caution)
force_release() {
    if [ -d "$LOCK_FILE" ]; then
        log_warn "Force releasing lock"
        if [ -f "$LOCK_FILE/pid" ]; then
            local pid=$(cat "$LOCK_FILE/pid")
            kill "$pid" 2>/dev/null
            sleep 1
        fi
        rm -rf "$LOCK_FILE"
        log_info "Lock force released"
    else
        log_info "No lock to release"
    fi
}

# Main command dispatcher
case "${1:-}" in
    acquire)
        acquire_lock "${2:-30}"
        ;;
    release)
        release_lock
        ;;
    run)
        shift
        if [ $# -lt 1 ]; then
            echo "Usage: $0 run <script.js> [args...]"
            exit 1
        fi
        run_with_lock "$@"
        ;;
    status)
        show_status
        ;;
    force-release)
        force_release
        ;;
    *)
        echo "Browser Lock Manager"
        echo ""
        echo "Usage:"
        echo "  $0 acquire [timeout]     - Acquire lock (default 30s wait)"
        echo "  $0 release               - Release lock"
        echo "  $0 run <script> [args]   - Run script with lock"
        echo "  $0 status                - Show lock status"
        echo "  $0 force-release         - Force release lock (careful!)"
        echo ""
        echo "Examples:"
        echo "  $0 run scripts/test-minirock-full.js"
        echo "  $0 run --timeout 600 scripts/long-test.js"
        exit 1
        ;;
esac
