#!/usr/bin/env python3
"""
Cross-Agent Memory Bridge
Phase 3: 记忆增强体系

实现主代理与子代理之间的记忆共享和上下文同步
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

# 记忆存储目录
MEMORY_DIR = Path("/var/www/ai-god-of-stocks/data/cross_agent_memory")
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# 上下文文件
CONTEXT_FILE = MEMORY_DIR / "shared_context.json"
MEMORIES_FILE = MEMORY_DIR / "memories.jsonl"


@dataclass
class MemoryEntry:
    """跨代理记忆条目"""
    memory_id: str
    timestamp: float
    source_agent: str  # 产生记忆的代理
    target_agents: List[str]  # 需要接收此记忆的代理
    memory_type: str  # "fact", "decision", "observation", "insight"
    content: str
    context: Dict[str, Any]  # 相关上下文
    importance: int  # 1-10
    expiration: Optional[float] = None  # 过期时间


class CrossAgentMemoryBridge:
    """
    跨代理记忆桥梁
    
    功能：
    1. 记忆共享 - 一个代理的发现可以被其他代理访问
    2. 上下文保持 - 跨会话保持关键上下文
    3. 记忆优先级 - 重要记忆优先传递
    4. 记忆过期 - 自动清理过期记忆
    """
    
    def __init__(self):
        self._context: Dict[str, Any] = {}
        self._load_context()
    
    def _load_context(self):
        """加载共享上下文"""
        if CONTEXT_FILE.exists():
            try:
                with open(CONTEXT_FILE, 'r') as f:
                    self._context = json.load(f)
            except:
                self._context = {}
    
    def _save_context(self):
        """保存共享上下文"""
        with open(CONTEXT_FILE, 'w') as f:
            json.dump(self._context, f, indent=2)
    
    def set_context(self, key: str, value: Any, agent_id: str):
        """设置共享上下文"""
        self._context[key] = {
            "value": value,
            "updated_by": agent_id,
            "updated_at": time.time()
        }
        self._save_context()
    
    def get_context(self, key: str) -> Optional[Any]:
        """获取共享上下文"""
        entry = self._context.get(key)
        if entry:
            return entry["value"]
        return None
    
    def get_full_context(self) -> Dict[str, Any]:
        """获取完整上下文"""
        return {
            k: v["value"] for k, v in self._context.items()
        }
    
    def add_memory(self, source_agent: str, target_agents: List[str],
                   memory_type: str, content: str,
                   context: Dict[str, Any] = None,
                   importance: int = 5,
                   ttl_hours: Optional[int] = None) -> str:
        """
        添加跨代理记忆
        
        Args:
            source_agent: 产生记忆的代理ID
            target_agents: 需要接收此记忆的代理列表 (空列表表示广播给所有代理)
            memory_type: 记忆类型 (fact/decision/observation/insight)
            content: 记忆内容
            context: 相关上下文
            importance: 重要性 (1-10)
            ttl_hours: 过期时间 (小时)
        """
        memory_id = f"mem_{int(time.time() * 1000)}_{source_agent}"
        
        entry = MemoryEntry(
            memory_id=memory_id,
            timestamp=time.time(),
            source_agent=source_agent,
            target_agents=target_agents,
            memory_type=memory_type,
            content=content,
            context=context or {},
            importance=importance,
            expiration=time.time() + (ttl_hours * 3600) if ttl_hours else None
        )
        
        # 追加到记忆文件
        with open(MEMORIES_FILE, 'a') as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + '\n')
        
        return memory_id
    
    def get_memories_for_agent(self, agent_id: str, 
                               memory_type: Optional[str] = None,
                               min_importance: int = 1,
                               since: Optional[float] = None) -> List[MemoryEntry]:
        """
        获取指定代理的记忆
        
        Args:
            agent_id: 代理ID
            memory_type: 过滤特定类型的记忆
            min_importance: 最小重要性
            since: 只获取此时间之后的记忆
        """
        memories = []
        
        if not MEMORIES_FILE.exists():
            return memories
        
        try:
            with open(MEMORIES_FILE, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        data = json.loads(line)
                        entry = MemoryEntry(**data)
                        
                        # 检查是否过期
                        if entry.expiration and time.time() > entry.expiration:
                            continue
                        
                        # 检查是否目标代理
                        if entry.target_agents and agent_id not in entry.target_agents:
                            continue
                        
                        # 检查类型过滤
                        if memory_type and entry.memory_type != memory_type:
                            continue
                        
                        # 检查重要性
                        if entry.importance < min_importance:
                            continue
                        
                        # 检查时间
                        if since and entry.timestamp < since:
                            continue
                        
                        memories.append(entry)
                    except:
                        continue
        except:
            pass
        
        # 按重要性降序、时间降序排序
        return sorted(memories, key=lambda m: (-m.importance, -m.timestamp))
    
    def get_recent_insights(self, agent_id: str, hours: int = 24) -> List[str]:
        """获取最近的洞察"""
        since = time.time() - (hours * 3600)
        memories = self.get_memories_for_agent(
            agent_id, 
            memory_type="insight",
            min_importance=7,
            since=since
        )
        return [m.content for m in memories[:10]]
    
    def share_observation(self, source_agent: str, observation: str,
                        context: Dict[str, Any] = None,
                        importance: int = 5):
        """快捷方式：分享观察"""
        return self.add_memory(
            source_agent=source_agent,
            target_agents=[],  # 广播给所有代理
            memory_type="observation",
            content=observation,
            context=context,
            importance=importance,
            ttl_hours=24
        )
    
    def share_decision(self, source_agent: str, decision: str,
                       reasoning: str,
                       importance: int = 8):
        """快捷方式：分享决策"""
        return self.add_memory(
            source_agent=source_agent,
            target_agents=[],  # 广播给所有代理
            memory_type="decision",
            content=decision,
            context={"reasoning": reasoning},
            importance=importance,
            ttl_hours=168  # 7天
        )
    
    def cleanup_expired_memories(self):
        """清理过期记忆"""
        if not MEMORIES_FILE.exists():
            return 0
        
        temp_file = MEMORIES_FILE.with_suffix('.tmp')
        cleaned = 0
        
        try:
            with open(MEMORIES_FILE, 'r') as f_in, open(temp_file, 'w') as f_out:
                for line in f_in:
                    if not line.strip():
                        continue
                    
                    try:
                        data = json.loads(line)
                        entry = MemoryEntry(**data)
                        
                        # 检查是否过期
                        if entry.expiration and time.time() > entry.expiration:
                            cleaned += 1
                            continue
                        
                        f_out.write(line)
                    except:
                        f_out.write(line)
            
            # 替换原文件
            temp_file.replace(MEMORIES_FILE)
            
        except Exception as e:
            print(f"[MemoryBridge] Cleanup error: {e}")
        
        return cleaned
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        total = 0
        by_type = {}
        by_agent = {}
        expired = 0
        
        if MEMORIES_FILE.exists():
            try:
                with open(MEMORIES_FILE, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        try:
                            data = json.loads(line)
                            entry = MemoryEntry(**data)
                            total += 1
                            
                            by_type[entry.memory_type] = by_type.get(entry.memory_type, 0) + 1
                            by_agent[entry.source_agent] = by_agent.get(entry.source_agent, 0) + 1
                            
                            if entry.expiration and time.time() > entry.expiration:
                                expired += 1
                        except:
                            continue
            except:
                pass
        
        return {
            "total_memories": total,
            "expired_memories": expired,
            "active_memories": total - expired,
            "by_type": by_type,
            "by_agent": by_agent,
            "context_keys": list(self._context.keys())
        }


# 单例实例
_memory_bridge = None

def get_memory_bridge() -> CrossAgentMemoryBridge:
    """获取记忆桥梁实例"""
    global _memory_bridge
    if _memory_bridge is None:
        _memory_bridge = CrossAgentMemoryBridge()
    return _memory_bridge


# ========== CLI 接口 ==========

if __name__ == "__main__":
    import sys
    
    bridge = get_memory_bridge()
    
    if len(sys.argv) < 2:
        print("Usage: python memory_bridge.py <command> [args]")
        print("")
        print("Commands:")
        print("  observe <agent> <content> [importance]     - 添加观察")
        print("  decide <agent> <decision> <reasoning>      - 添加决策")
        print("  get <agent> [type] [min_importance]         - 获取记忆")
        print("  insights <agent> [hours]                    - 获取洞察")
        print("  context-set <key> <value> <agent>          - 设置上下文")
        print("  context-get <key>                           - 获取上下文")
        print("  cleanup                                     - 清理过期记忆")
        print("  stats                                       - 统计信息")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "observe" and len(sys.argv) >= 4:
        agent = sys.argv[2]
        content = sys.argv[3]
        importance = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        mem_id = bridge.share_observation(agent, content, importance=importance)
        print(f"Added observation: {mem_id}")
    
    elif cmd == "decide" and len(sys.argv) >= 5:
        agent = sys.argv[2]
        decision = sys.argv[3]
        reasoning = sys.argv[4]
        mem_id = bridge.share_decision(agent, decision, reasoning)
        print(f"Added decision: {mem_id}")
    
    elif cmd == "get" and len(sys.argv) >= 3:
        agent = sys.argv[2]
        mem_type = sys.argv[3] if len(sys.argv) > 3 else None
        min_imp = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        memories = bridge.get_memories_for_agent(agent, mem_type, min_imp)
        print(f"Found {len(memories)} memories:")
        for m in memories[:10]:
            print(f"  [{m.memory_type}] {m.content[:60]}...")
    
    elif cmd == "insights" and len(sys.argv) >= 3:
        agent = sys.argv[2]
        hours = int(sys.argv[3]) if len(sys.argv) > 3 else 24
        insights = bridge.get_recent_insights(agent, hours)
        print(f"Recent insights ({hours}h):")
        for i in insights:
            print(f"  - {i}")
    
    elif cmd == "context-set" and len(sys.argv) >= 5:
        key = sys.argv[2]
        value = sys.argv[3]
        agent = sys.argv[4]
        bridge.set_context(key, value, agent)
        print(f"Set context: {key} = {value}")
    
    elif cmd == "context-get" and len(sys.argv) >= 3:
        key = sys.argv[2]
        value = bridge.get_context(key)
        print(f"{key} = {value}")
    
    elif cmd == "cleanup":
        cleaned = bridge.cleanup_expired_memories()
        print(f"Cleaned {cleaned} expired memories")
    
    elif cmd == "stats":
        stats = bridge.get_memory_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        print(f"Unknown command or missing args: {cmd}")
        sys.exit(1)
