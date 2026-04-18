#!/usr/bin/env python3
"""
双代理健康检查与故障转移系统
OpenClaw ↔ Hermes 互检机制
"""

import requests
import json
import time
import sqlite3
from datetime import datetime
from typing import Dict, Optional

# 配置
CONFIG = {
    "openclaw": {
        "endpoint": "http://43.160.193.165:8080/api/health",
        "timeout": 10,
        "retry": 3
    },
    "hermes": {
        "endpoint": "http://127.0.0.1:8000/api/health",
        "timeout": 10,
        "retry": 3
    },
    "check_interval": 300,  # 5分钟
    "fail_threshold": 3,    # 连续3次失败视为故障
    "notification": {
        "feishu_webhook": None,  # 待配置
        "enabled": True
    }
}

class DualAgentHealthChecker:
    """双代理健康检查器"""
    
    def __init__(self, db_path: str = "/var/www/ai-god-of-stocks/data/health_check.db"):
        self.db_path = db_path
        self.init_db()
        
    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                status TEXT NOT NULL,
                response_time REAL,
                error_msg TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS failover_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_agent TEXT NOT NULL,
                to_agent TEXT NOT NULL,
                reason TEXT NOT NULL,
                tasks TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def check_agent(self, name: str, config: Dict) -> Dict:
        """检查单个代理健康状态"""
        result = {
            "name": name,
            "status": "unknown",
            "response_time": 0,
            "error": None,
            "timestamp": datetime.now().isoformat()
        }
        
        for attempt in range(config.get("retry", 1)):
            try:
                start = time.time()
                response = requests.get(
                    config["endpoint"],
                    timeout=config["timeout"]
                )
                result["response_time"] = round(time.time() - start, 3)
                
                if response.status_code == 200:
                    result["status"] = "healthy"
                    return result
                else:
                    result["status"] = "unhealthy"
                    result["error"] = f"HTTP {response.status_code}"
                    
            except requests.exceptions.Timeout:
                result["status"] = "timeout"
                result["error"] = f"Timeout after {config['timeout']}s"
            except requests.exceptions.ConnectionError:
                result["status"] = "connection_error"
                result["error"] = "Connection refused"
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
            
            if attempt < config.get("retry", 1) - 1:
                time.sleep(1)
        
        return result
    
    def record_check(self, result: Dict):
        """记录健康检查结果"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO health_checks (agent_name, status, response_time, error_msg) VALUES (?, ?, ?, ?)",
            (result["name"], result["status"], result["response_time"], result["error"])
        )
        conn.commit()
        conn.close()
    
    def get_recent_failures(self, agent_name: str, minutes: int = 15) -> int:
        """获取最近失败次数"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """SELECT COUNT(*) FROM health_checks 
               WHERE agent_name = ? AND status != 'healthy' 
               AND timestamp > datetime('now', '-{} minutes')""".format(minutes),
            (agent_name,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def should_failover(self, agent_name: str) -> bool:
        """判断是否应触发故障转移"""
        failures = self.get_recent_failures(agent_name)
        return failures >= CONFIG["fail_threshold"]
    
    def execute_failover(self, from_agent: str, to_agent: str, reason: str):
        """执行故障转移"""
        print(f"🚨 故障转移: {from_agent} → {to_agent}")
        print(f"   原因: {reason}")
        
        # 记录故障转移
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO failover_log (from_agent, to_agent, reason, tasks) VALUES (?, ?, ?, ?)",
            (from_agent, to_agent, reason, json.dumps(self.get_tasks_to_takeover(from_agent)))
        )
        conn.commit()
        conn.close()
        
        # TODO: 实际执行故障转移逻辑
        # 这里需要实现任务接管的具体逻辑
        
    def get_tasks_to_takeover(self, agent_name: str) -> list:
        """获取需要接管的任务列表"""
        # 根据代理名称返回需要接管的任务
        if agent_name == "hermes":
            return [
                "market_monitor",
                "daily_report", 
                "subagent_management",
                "morning_posts",
                "afternoon_posts"
            ]
        elif agent_name == "openclaw":
            return [
                "stock_data_service",
                "ai_prediction",
                "data_sync"
            ]
        return []
    
    def run_check(self):
        """运行完整健康检查"""
        print(f"\n🔍 双代理健康检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # 检查OpenClaw
        openclaw_result = self.check_agent("openclaw", CONFIG["openclaw"])
        self.record_check(openclaw_result)
        self.print_result(openclaw_result)
        
        # 检查Hermes
        hermes_result = self.check_agent("hermes", CONFIG["hermes"])
        self.record_check(hermes_result)
        self.print_result(hermes_result)
        
        # 故障转移判断
        if openclaw_result["status"] != "healthy" and self.should_failover("openclaw"):
            self.execute_failover("openclaw", "hermes", openclaw_result["error"])
            
        if hermes_result["status"] != "healthy" and self.should_failover("hermes"):
            self.execute_failover("hermes", "openclaw", hermes_result["error"])
        
        print("=" * 60)
        
    def print_result(self, result: Dict):
        """打印检查结果"""
        status_icon = {
            "healthy": "✅",
            "unhealthy": "❌",
            "timeout": "⏱️",
            "connection_error": "🔌",
            "error": "⚠️",
            "unknown": "❓"
        }
        
        icon = status_icon.get(result["status"], "❓")
        print(f"{icon} {result['name'].upper():12} | {result['status']:15} | {result['response_time']:.3f}s")
        if result["error"]:
            print(f"   └─ 错误: {result['error']}")


def main():
    """主函数"""
    checker = DualAgentHealthChecker()
    
    # 单次检查模式
    checker.run_check()
    
    # 持续监控模式（可选）
    # import sys
    # if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
    #     print(f"\n🔄 持续监控模式（每{CONFIG['check_interval']}秒检查一次）")
    #     while True:
    #         checker.run_check()
    #         time.sleep(CONFIG["check_interval"])


if __name__ == "__main__":
    main()
