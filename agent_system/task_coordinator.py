#!/usr/bin/env python3
"""
Dual Agent Task Coordinator
Phase 3: 职能分工与任务调度

主代理 (Lingxi) 通过此模块协调子代理 (Hermes) 执行具体任务
"""

import json
import time
import uuid
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime

# 导入共享记忆系统
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks/agent_system')
from shared_memory_system import get_shared_memory, AgentState

# 任务队列目录
TASK_QUEUE_DIR = Path("/var/www/ai-god-of-stocks/data/task_queue")
TASK_QUEUE_DIR.mkdir(parents=True, exist_ok=True)


class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Task:
    """任务定义"""
    task_id: str
    task_type: str
    priority: TaskPriority
    payload: Dict[str, Any]
    status: TaskStatus
    assigned_agent: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class TaskCoordinator:
    """
    双代理任务协调器
    
    职能分工：
    - 主代理 (Lingxi): 任务创建、优先级排序、结果汇总
    - 子代理 (Hermes): 任务执行、数据获取、状态汇报
    """
    
    # 任务类型映射到最适合的代理
    TASK_TYPE_AGENTS = {
        "stock_analysis": "hermes",      # 股票分析 → Hermes
        "data_fetch": "hermes",          # 数据获取 → Hermes
        "market_scan": "hermes",         # 市场扫描 → Hermes
        "bbs_post": "hermes",            # BBS发帖 → Hermes
        "trading_decision": "lingxi",    # 交易决策 → Lingxi
        "portfolio_review": "lingxi",    # 持仓复盘 → Lingxi
        "conflict_resolution": "lingxi", # 冲突解决 → Lingxi
    }
    
    def __init__(self):
        self._lock = threading.RLock()
        self._shared_memory = get_shared_memory()
        self._task_handlers: Dict[str, Callable] = {}
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
    
    def register_task_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        with self._lock:
            self._task_handlers[task_type] = handler
    
    def create_task(self, task_type: str, payload: Dict[str, Any],
                    priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """创建新任务"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            payload=payload,
            status=TaskStatus.PENDING
        )
        
        # 保存到任务队列
        task_file = TASK_QUEUE_DIR / f"{task_id}.json"
        with open(task_file, 'w') as f:
            json.dump(asdict(task), f, indent=2, default=lambda x: x.value if isinstance(x, Enum) else x)
        
        print(f"[TaskCoordinator] Created task {task_id} ({task_type}, {priority.name})")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        task_file = TASK_QUEUE_DIR / f"{task_id}.json"
        if not task_file.exists():
            return None
        
        try:
            with open(task_file, 'r') as f:
                data = json.load(f)
            
            # 转换枚举
            data['status'] = TaskStatus(data['status'])
            data['priority'] = TaskPriority(data['priority'])
            
            return Task(**data)
        except Exception as e:
            print(f"[TaskCoordinator] Failed to load task {task_id}: {e}")
            return None
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """分配任务给指定代理"""
        task = self.get_task(task_id)
        if not task or task.status != TaskStatus.PENDING:
            return False
        
        task.assigned_agent = agent_id
        task.status = TaskStatus.ASSIGNED
        
        # 保存更新
        task_file = TASK_QUEUE_DIR / f"{task_id}.json"
        with open(task_file, 'w') as f:
            json.dump(asdict(task), f, indent=2, default=lambda x: x.value if isinstance(x, Enum) else x)
        
        print(f"[TaskCoordinator] Assigned task {task_id} to {agent_id}")
        return True
    
    def complete_task(self, task_id: str, result: Any = None, error: str = None) -> bool:
        """完成任务"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        task.completed_at = time.time()
        task.result = result
        task.error = error
        task.status = TaskStatus.FAILED if error else TaskStatus.COMPLETED
        
        # 保存更新
        task_file = TASK_QUEUE_DIR / f"{task_id}.json"
        with open(task_file, 'w') as f:
            json.dump(asdict(task), f, indent=2, default=lambda x: x.value if isinstance(x, Enum) else x)
        
        print(f"[TaskCoordinator] Completed task {task_id} ({'success' if not error else 'failed'})")
        return True
    
    def get_pending_tasks(self) -> List[Task]:
        """获取所有待处理任务"""
        tasks = []
        for task_file in TASK_QUEUE_DIR.glob("task_*.json"):
            try:
                with open(task_file, 'r') as f:
                    data = json.load(f)
                
                if data.get('status') in [TaskStatus.PENDING.value, TaskStatus.ASSIGNED.value]:
                    data['status'] = TaskStatus(data['status'])
                    data['priority'] = TaskPriority(data['priority'])
                    tasks.append(Task(**data))
            except:
                continue
        
        # 按优先级排序
        return sorted(tasks, key=lambda t: t.priority.value)
    
    def auto_assign_tasks(self) -> List[str]:
        """自动分配任务给合适的代理"""
        assigned = []
        pending = self.get_pending_tasks()
        
        for task in pending:
            if task.status != TaskStatus.PENDING:
                continue
            
            # 确定最适合的代理
            preferred_agent = self.TASK_TYPE_AGENTS.get(task.task_type, "hermes")
            
            # 检查代理健康状态
            if not self._shared_memory.is_agent_healthy(preferred_agent, timeout=120):
                # 如果首选代理不健康，尝试主代理
                if preferred_agent != "lingxi":
                    preferred_agent = "lingxi"
                else:
                    continue  # 无法分配
            
            if self.assign_task(task.task_id, preferred_agent):
                assigned.append(task.task_id)
        
        return assigned
    
    def start_scheduler(self, interval: int = 10):
        """启动任务调度器"""
        self._running = True
        
        def scheduler_loop():
            while self._running:
                try:
                    self.auto_assign_tasks()
                except Exception as e:
                    print(f"[TaskCoordinator] Scheduler error: {e}")
                
                time.sleep(interval)
        
        self._scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        print(f"[TaskCoordinator] Scheduler started (interval: {interval}s)")
    
    def stop_scheduler(self):
        """停止任务调度器"""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        print("[TaskCoordinator] Scheduler stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        all_tasks = list(TASK_QUEUE_DIR.glob("task_*.json"))
        
        status_counts = {}
        for task_file in all_tasks:
            try:
                with open(task_file, 'r') as f:
                    data = json.load(f)
                status = data.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            except:
                continue
        
        return {
            "total_tasks": len(all_tasks),
            "status_distribution": status_counts,
            "pending_tasks": len(self.get_pending_tasks()),
            "scheduler_running": self._running
        }


# 单例实例
_coordinator = None

def get_task_coordinator() -> TaskCoordinator:
    """获取任务协调器实例"""
    global _coordinator
    if _coordinator is None:
        _coordinator = TaskCoordinator()
    return _coordinator


# ========== CLI 接口 ==========

if __name__ == "__main__":
    import sys
    
    coordinator = get_task_coordinator()
    
    if len(sys.argv) < 2:
        print("Usage: python task_coordinator.py <command> [args]")
        print("")
        print("Commands:")
        print("  create <type> <payload_json> [priority]  - 创建任务")
        print("  status <task_id>                          - 查看任务状态")
        print("  pending                                   - 列出待处理任务")
        print("  assign <task_id> <agent>                - 分配任务")
        print("  complete <task_id> [result_json]          - 完成任务")
        print("  auto-assign                               - 自动分配任务")
        print("  start-scheduler [interval]                - 启动调度器")
        print("  stats                                     - 查看统计")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create" and len(sys.argv) >= 4:
        task_type = sys.argv[2]
        payload = json.loads(sys.argv[3])
        priority = TaskPriority[sys.argv[4].upper()] if len(sys.argv) > 4 else TaskPriority.NORMAL
        task_id = coordinator.create_task(task_type, payload, priority)
        print(f"Created: {task_id}")
    
    elif cmd == "status" and len(sys.argv) >= 3:
        task_id = sys.argv[2]
        task = coordinator.get_task(task_id)
        if task:
            print(json.dumps(asdict(task), indent=2, default=lambda x: x.value if isinstance(x, Enum) else x))
        else:
            print(f"Task not found: {task_id}")
    
    elif cmd == "pending":
        tasks = coordinator.get_pending_tasks()
        print(f"Pending tasks: {len(tasks)}")
        for task in tasks:
            print(f"  {task.task_id}: {task.task_type} ({task.priority.name})")
    
    elif cmd == "assign" and len(sys.argv) >= 4:
        task_id = sys.argv[2]
        agent = sys.argv[3]
        if coordinator.assign_task(task_id, agent):
            print(f"Assigned {task_id} to {agent}")
        else:
            print("Failed to assign")
    
    elif cmd == "complete" and len(sys.argv) >= 3:
        task_id = sys.argv[2]
        result = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
        if coordinator.complete_task(task_id, result):
            print(f"Completed {task_id}")
        else:
            print("Failed to complete")
    
    elif cmd == "auto-assign":
        assigned = coordinator.auto_assign_tasks()
        print(f"Auto-assigned {len(assigned)} tasks")
        for task_id in assigned:
            print(f"  - {task_id}")
    
    elif cmd == "start-scheduler":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        coordinator.start_scheduler(interval)
        print(f"Scheduler started (interval: {interval}s)")
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            coordinator.stop_scheduler()
    
    elif cmd == "stats":
        stats = coordinator.get_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        print(f"Unknown command or missing args: {cmd}")
        sys.exit(1)
