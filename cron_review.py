#!/usr/bin/env python3
"""每日收盘复盘 cron 脚本"""
import sys
import os
sys.path.insert(0, "/var/www/ai-god-of-stocks")

from engine.review_reporter import main
if __name__ == "__main__":
    main()
