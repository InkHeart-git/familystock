#!/bin/bash
cd /var/www/ai-god-of-stocks
set -a
source .env
set +a
exec python3 engine/unified_scheduler.py --check-interval 30 >> watchdog.log 2>&1
