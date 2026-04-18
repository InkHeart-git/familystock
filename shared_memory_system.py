#!/usr/bin/env python3
"""
双代理共享记忆系统
统一存储格式：SQLite + Markdown混合架构
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

class SharedMemorySystem:
    """共享记忆系统 - 双代理记忆同步"""
    
    def __init__(self, base_path: str = "/var/www/ai-god-of-stocks/shared"):
        self.base_path = Path(base_path)
        self.db_path = self.base_path / "memory.db"
        
        # 创建目录结构
        self._init_directories()
        self._init_database()
    
    def _init_directories(self):
        """初始化共享目录结构"""
        dirs = [
            "memory",           # 结构化记忆
            "memory/incidents", # 故障报告
            "memory/tasks",     # 任务队列
            "skills/openclaw",  # OpenClaw专属技能
            "skills/hermes",    # Hermes专属技能
            "skills/shared",    # 共享技能
            "templates/code",   # 代码模板
            "templates/config", # 配置模板
            "logs",             # 同步日志
        ]
        
        for d in dirs:
            (self.base_path / d).mkdir(parents=True, exist_ok=True)
        
        print(f"✅ 共享记忆目录已初始化: {self.base_path}")
    
    def _init_database(self):
        """初始化共享数据库"""
        conn = sqlite3.connect(self.db_path)
        
        # 任务状态表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                task_name TEXT NOT NULL,
                assigned_to TEXT NOT NULL,  -- 'openclaw' or 'hermes'
                status TEXT DEFAULT 'pending',  -- pending, running, completed, failed
                priority INTEGER DEFAULT 5,  -- 1-10
                data TEXT,  -- JSON格式任务数据
                result TEXT,  -- JSON格式结果
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        
        # 决策记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decision_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id TEXT UNIQUE NOT NULL,
                agent_name TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                context TEXT,  -- 决策上下文
                decision TEXT NOT NULL,  -- 决策内容
                reasoning TEXT,  -- 决策理由
                outcome TEXT,  -- 结果
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 故障知识库
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_kb (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                root_cause TEXT,
                solution TEXT,
                prevention TEXT,
                affected_agents TEXT,  -- JSON数组
                severity TEXT,  -- critical, high, medium, low
                status TEXT DEFAULT 'open',  -- open, resolved, closed
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        
        # 同步日志表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                entity_type TEXT NOT NULL,  -- task, decision, incident
                entity_id TEXT NOT NULL,
                action TEXT NOT NULL,  -- create, update, delete
                sync_status TEXT,  -- success, failed, conflict
                error_msg TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 触发器：自动更新updated_at
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS update_task_timestamp 
            AFTER UPDATE ON task_states
            BEGIN
                UPDATE task_states SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """)
        
        conn.commit()
        conn.close()
        
        print(f"✅ 共享记忆数据库已初始化: {self.db_path}")
    
    # ==================== 任务管理 ====================
    
    def create_task(self, task_id: str, task_name: str, assigned_to: str,
                   priority: int = 5, data: Dict = None) -> bool:
        """创建新任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT INTO task_states (task_id, task_name, assigned_to, priority, data)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, task_name, assigned_to, priority, json.dumps(data or {}))
            )
            conn.commit()
            conn.close()
            
            self._log_sync('task', assigned_to, task_id, 'create', 'success')
            return True
        except sqlite3.IntegrityError:
            print(f"⚠️ 任务已存在: {task_id}")
            return False
        except Exception as e:
            print(f"❌ 创建任务失败: {e}")
            return False
    
    def update_task_status(self, task_id: str, status: str, result: Dict = None) -> bool:
        """更新任务状态"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            if status in ['completed', 'failed']:
                conn.execute(
                    """UPDATE task_states 
                       SET status = ?, result = ?, completed_at = CURRENT_TIMESTAMP
                       WHERE task_id = ?""",
                    (status, json.dumps(result or {}), task_id)
                )
            else:
                conn.execute(
                    "UPDATE task_states SET status = ? WHERE task_id = ?",
                    (status, task_id)
                )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ 更新任务失败: {e}")
            return False
    
    def get_pending_tasks(self, agent_name: str = None) -> List[Dict]:
        """获取待处理任务"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        if agent_name:
            cursor = conn.execute(
                """SELECT * FROM task_states 
                   WHERE status = 'pending' AND assigned_to = ?
                   ORDER BY priority DESC, created_at ASC""",
                (agent_name,)
            )
        else:
            cursor = conn.execute(
                """SELECT * FROM task_states 
                   WHERE status = 'pending'
                   ORDER BY priority DESC, created_at ASC"""
            )
        
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tasks
    
    # ==================== 决策记录 ====================
    
    def log_decision(self, agent_name: str, decision_type: str, 
                    decision: str, context: str = None, reasoning: str = None) -> str:
        """记录决策"""
        decision_id = f"dec_{datetime.now().strftime('%Y%m%d%H%M%S')}_{agent_name}"
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO decision_log 
               (decision_id, agent_name, decision_type, context, decision, reasoning)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (decision_id, agent_name, decision_type, context, decision, reasoning)
        )
        conn.commit()
        conn.close()
        
        # 同时写入Markdown文档
        self._append_to_markdown(
            f"memory/DECISION_LOG.md",
            f"\n## {decision_id}\n\n"
            f"**Agent**: {agent_name}\n\n"
            f"**Type**: {decision_type}\n\n"
            f"**Decision**: {decision}\n\n"
            f"**Context**: {context or 'N/A'}\n\n"
            f"**Reasoning**: {reasoning or 'N/A'}\n\n"
            f"**Time**: {datetime.now().isoformat()}\n\n"
            f"---\n"
        )
        
        return decision_id
    
    # ==================== 故障知识库 ====================
    
    def create_incident(self, title: str, description: str, 
                       affected_agents: List[str], severity: str = 'medium') -> str:
        """创建故障记录"""
        incident_id = f"inc_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO incident_kb 
               (incident_id, title, description, affected_agents, severity)
               VALUES (?, ?, ?, ?, ?)""",
            (incident_id, title, description, json.dumps(affected_agents), severity)
        )
        conn.commit()
        conn.close()
        
        # 创建Markdown故障报告
        incident_file = self.base_path / f"memory/incidents/{incident_id}.md"
        incident_file.write_text(
            f"# {title}\n\n"
            f"**ID**: {incident_id}\n\n"
            f"**Severity**: {severity}\n\n"
            f"**Affected Agents**: {', '.join(affected_agents)}\n\n"
            f"**Status**: open\n\n"
            f"**Created**: {datetime.now().isoformat()}\n\n"
            f"## Description\n\n{description}\n\n"
            f"## Root Cause\n\n_TBD_\n\n"
            f"## Solution\n\n_TBD_\n\n"
            f"## Prevention\n\n_TBD_\n\n"
        )
        
        return incident_id
    
    def resolve_incident(self, incident_id: str, root_cause: str, 
                        solution: str, prevention: str = None) -> bool:
        """解决故障"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """UPDATE incident_kb 
               SET status = 'resolved', root_cause = ?, solution = ?, 
                   prevention = ?, resolved_at = CURRENT_TIMESTAMP
               WHERE incident_id = ?""",
            (root_cause, solution, prevention, incident_id)
        )
        conn.commit()
        conn.close()
        
        # 更新Markdown文件
        incident_file = self.base_path / f"memory/incidents/{incident_id}.md"
        if incident_file.exists():
            content = incident_file.read_text()
            content = content.replace("**Status**: open", "**Status**: resolved")
            content = content.replace("## Root Cause\n\n_TBD_", f"## Root Cause\n\n{root_cause}")
            content = content.replace("## Solution\n\n_TBD_", f"## Solution\n\n{solution}")
            if prevention:
                content = content.replace("## Prevention\n\n_TBD_", f"## Prevention\n\n{prevention}")
            incident_file.write_text(content)
        
        return True
    
    # ==================== 同步机制 ====================
    
    def sync_from_openclaw(self, memory_data: Dict):
        """从OpenClaw同步记忆"""
        # 将OpenClaw的Markdown记忆同步到共享数据库
        pass  # 具体实现根据OpenClaw记忆格式
    
    def sync_from_hermes(self, state_db_path: str):
        """从Hermes同步记忆"""
        # 将Hermes的SQLite状态同步到共享数据库
        pass  # 具体实现根据Hermes状态格式
    
    def _log_sync(self, entity_type: str, agent_name: str, entity_id: str,
                 action: str, status: str, error_msg: str = None):
        """记录同步日志"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO sync_log (sync_type, agent_name, entity_type, entity_id, action, sync_status, error_msg)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ('bidirectional', agent_name, entity_type, entity_id, action, status, error_msg)
        )
        conn.commit()
        conn.close()
    
    def _append_to_markdown(self, filepath: str, content: str):
        """追加内容到Markdown文件"""
        full_path = self.base_path / filepath
        if not full_path.exists():
            # 从filepath中提取文件名作为标题
            title = Path(filepath).stem
            full_path.write_text(f"# {title}\n\n")
        
        with open(full_path, 'a', encoding='utf-8') as f:
            f.write(content)
    
    # ==================== 统计与报告 ====================
    
    def generate_sync_report(self) -> Dict:
        """生成同步状态报告"""
        conn = sqlite3.connect(self.db_path)
        
        # 任务统计
        cursor = conn.execute(
            "SELECT status, COUNT(*) FROM task_states GROUP BY status"
        )
        task_stats = dict(cursor.fetchall())
        
        # 最近故障
        cursor = conn.execute(
            """SELECT incident_id, title, severity, status, created_at FROM incident_kb 
               WHERE status != 'closed'
               ORDER BY created_at DESC LIMIT 5"""
        )
        columns = [description[0] for description in cursor.description]
        recent_incidents = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # 同步成功率
        cursor = conn.execute(
            """SELECT sync_status, COUNT(*) FROM sync_log 
               WHERE timestamp > datetime('now', '-1 hour')
               GROUP BY sync_status"""
        )
        sync_stats = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            "tasks": task_stats,
            "recent_incidents": recent_incidents,
            "sync_stats": sync_stats,
            "generated_at": datetime.now().isoformat()
        }


def main():
    """测试共享记忆系统"""
    print("🧠 初始化双代理共享记忆系统...\n")
    
    memory = SharedMemorySystem()
    
    # 测试创建任务
    print("\n📝 测试任务管理:")
    memory.create_task(
        task_id="test_task_001",
        task_name="重建Hermes子代理层",
        assigned_to="hermes",
        priority=10,
        data={"phase": 1, "estimated_time": "2h"}
    )
    
    pending = memory.get_pending_tasks("hermes")
    print(f"   Hermes待处理任务: {len(pending)} 个")
    
    # 测试决策记录
    print("\n🎯 测试决策记录:")
    decision_id = memory.log_decision(
        agent_name="openclaw",
        decision_type="architecture",
        decision="采用主管-执行双代理模式",
        context="MiniRock子代理层13天宕机",
        reasoning="提高系统可靠性和任务执行效率"
    )
    print(f"   决策已记录: {decision_id}")
    
    # 测试故障记录
    print("\n🚨 测试故障知识库:")
    incident_id = memory.create_incident(
        title="Hermes子代理层宕机",
        description="config/和engine/目录被删除，子代理13天未运行",
        affected_agents=["hermes"],
        severity="critical"
    )
    print(f"   故障已记录: {incident_id}")
    
    # 生成报告
    print("\n📊 生成同步报告:")
    report = memory.generate_sync_report()
    print(f"   任务统计: {report['tasks']}")
    
    print("\n✅ 共享记忆系统测试完成!")


if __name__ == "__main__":
    main()
