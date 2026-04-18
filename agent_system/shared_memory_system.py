#!/usr/bin/env python3
"""
Shared Memory System for Dual Agent Communication
Phase 1: 稳定性保障层 - 共享记忆系统
Phase 2: 成本优化层 - 响应缓存
"""

import json
import os
import time
import hashlib
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

# 共享数据目录
SHARED_DIR = Path("/var/www/ai-god-of-stocks/data/shared_memory")
CACHE_DIR = Path("/var/www/ai-god-of-stocks/data/cache")
STATE_FILE = Path("/var/www/ai-god-of-stocks/data/subagent_state.json")

# 确保目录存在
SHARED_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AgentState:
    """代理状态记录"""
    agent_id: str
    status: str  # "idle", "busy", "error", "offline"
    last_heartbeat: float
    current_task: Optional[str] = None
    task_progress: float = 0.0
    capabilities: List[str] = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    data: Any
    created_at: float
    ttl: int
    access_count: int = 0
    
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl
    
    def touch(self):
        self.access_count += 1


class SharedMemorySystem:
    """双代理共享记忆系统"""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_ttl = {
            "llm_response": 3600,
            "stock_data": 300,
            "market_index": 60,
            "analysis_result": 1800,
        }
        self._load_cache()
    
    def _load_cache(self):
        """从磁盘加载缓存"""
        cache_file = CACHE_DIR / "response_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    for key, entry_data in data.items():
                        entry = CacheEntry(**entry_data)
                        if not entry.is_expired():
                            self._cache[key] = entry
            except Exception as e:
                print(f"[SharedMemory] Failed to load cache: {e}")
    
    def _save_cache(self):
        """保存缓存到磁盘"""
        cache_file = CACHE_DIR / "response_cache.json"
        try:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
            
            with open(cache_file, 'w') as f:
                json.dump({k: asdict(v) for k, v in self._cache.items()}, f)
        except Exception as e:
            print(f"[SharedMemory] Failed to save cache: {e}")
    
    def update_agent_state(self, state: AgentState) -> bool:
        """更新代理状态"""
        with self._lock:
            try:
                states = {}
                if STATE_FILE.exists():
                    with open(STATE_FILE, 'r') as f:
                        states = json.load(f)
                
                states[state.agent_id] = asdict(state)
                
                with open(STATE_FILE, 'w') as f:
                    json.dump(states, f, indent=2)
                
                return True
            except Exception as e:
                print(f"[SharedMemory] Failed to update state: {e}")
                return False
    
    def get_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """获取代理状态"""
        with self._lock:
            try:
                if not STATE_FILE.exists():
                    return None
                
                with open(STATE_FILE, 'r') as f:
                    states = json.load(f)
                
                if agent_id in states:
                    return AgentState(**states[agent_id])
                return None
            except Exception as e:
                print(f"[SharedMemory] Failed to get state: {e}")
                return None
    
    def get_all_agent_states(self) -> Dict[str, AgentState]:
        """获取所有代理状态"""
        with self._lock:
            try:
                if not STATE_FILE.exists():
                    return {}
                
                with open(STATE_FILE, 'r') as f:
                    states = json.load(f)
                
                return {k: AgentState(**v) for k, v in states.items()}
            except Exception as e:
                print(f"[SharedMemory] Failed to get all states: {e}")
                return {}
    
    def is_agent_healthy(self, agent_id: str, timeout: int = 60) -> bool:
        """检查代理是否健康"""
        state = self.get_agent_state(agent_id)
        if not state:
            return False
        
        time_since_heartbeat = time.time() - state.last_heartbeat
        return time_since_heartbeat < timeout and state.status != "error"
    
    def _generate_cache_key(self, query_type: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        param_str = json.dumps(params, sort_keys=True)
        return f"{query_type}:{hashlib.md5(param_str.encode()).hexdigest()}"
    
    def get_cached_response(self, query_type: str, params: Dict[str, Any]) -> Optional[Any]:
        """获取缓存的响应"""
        with self._lock:
            key = self._generate_cache_key(query_type, params)
            
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    entry.touch()
                    print(f"[SharedMemory] Cache hit: {query_type}")
                    return entry.data
                else:
                    del self._cache[key]
            
            return None
    
    def cache_response(self, query_type: str, params: Dict[str, Any], 
                       data: Any, ttl: Optional[int] = None) -> bool:
        """缓存响应"""
        with self._lock:
            key = self._generate_cache_key(query_type, params)
            
            if ttl is None:
                ttl = self._cache_ttl.get(query_type, 300)
            
            entry = CacheEntry(
                key=key,
                data=data,
                created_at=time.time(),
                ttl=ttl
            )
            
            self._cache[key] = entry
            
            if len(self._cache) % 10 == 0:
                self._save_cache()
            
            return True
    
    def invalidate_cache(self, query_type: Optional[str] = None):
        """使缓存失效"""
        with self._lock:
            if query_type:
                keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{query_type}:")]
                for key in keys_to_remove:
                    del self._cache[key]
            else:
                self._cache.clear()
            
            self._save_cache()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total_entries = len(self._cache)
            expired_entries = sum(1 for v in self._cache.values() if v.is_expired())
            
            type_counts = {}
            for key in self._cache.keys():
                query_type = key.split(":")[0]
                type_counts[query_type] = type_counts.get(query_type, 0) + 1
            
            return {
                "total_entries": total_entries,
                "expired_entries": expired_entries,
                "active_entries": total_entries - expired_entries,
                "type_distribution": type_counts,
                "cache_dir": str(CACHE_DIR)
            }
    
    def acquire_task_lock(self, task_id: str, agent_id: str, ttl: int = 300) -> bool:
        """获取任务锁"""
        lock_file = SHARED_DIR / f"task_lock_{task_id}.json"
        
        with self._lock:
            if lock_file.exists():
                try:
                    with open(lock_file, 'r') as f:
                        lock_data = json.load(f)
                    
                    if time.time() - lock_data["acquired_at"] < lock_data["ttl"]:
                        return False
                except:
                    pass
            
            lock_data = {
                "agent_id": agent_id,
                "acquired_at": time.time(),
                "ttl": ttl
            }
            
            with open(lock_file, 'w') as f:
                json.dump(lock_data, f)
            
            return True
    
    def release_task_lock(self, task_id: str, agent_id: str) -> bool:
        """释放任务锁"""
        lock_file = SHARED_DIR / f"task_lock_{task_id}.json"
        
        with self._lock:
            if not lock_file.exists():
                return True
            
            try:
                with open(lock_file, 'r') as f:
                    lock_data = json.load(f)
                
                if lock_data["agent_id"] == agent_id:
                    lock_file.unlink()
                    return True
            except:
                pass
            
            return False
    
    def write_shared_data(self, key: str, data: Any):
        """写入共享数据"""
        file_path = SHARED_DIR / f"{key}.json"
        with open(file_path, 'w') as f:
            json.dump({
                "data": data,
                "updated_at": time.time()
            }, f)
    
    def read_shared_data(self, key: str) -> Optional[Any]:
        """读取共享数据"""
        file_path = SHARED_DIR / f"{key}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except:
            return None


_shared_memory = None

def get_shared_memory() -> SharedMemorySystem:
    """获取共享记忆系统实例"""
    global _shared_memory
    if _shared_memory is None:
        _shared_memory = SharedMemorySystem()
    return _shared_memory


if __name__ == "__main__":
    import sys
    
    sms = get_shared_memory()
    
    if len(sys.argv) < 2:
        print("Usage: python shared_memory_system.py <command> [args]")
        print("")
        print("Commands:")
        print("  status                    - 显示所有代理状态")
        print("  cache-stats               - 显示缓存统计")
        print("  update-state <agent> <status>  - 更新代理状态")
        print("  clear-cache [type]        - 清除缓存")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        states = sms.get_all_agent_states()
        print("Agent States:")
        for agent_id, state in states.items():
            print(f"  {agent_id}: {state.status} (heartbeat: {state.last_heartbeat})")
    
    elif cmd == "cache-stats":
        stats = sms.get_cache_stats()
        print(json.dumps(stats, indent=2))
    
    elif cmd == "update-state" and len(sys.argv) >= 4:
        agent_id = sys.argv[2]
        status = sys.argv[3]
        state = AgentState(
            agent_id=agent_id,
            status=status,
            last_heartbeat=time.time()
        )
        sms.update_agent_state(state)
        print(f"Updated {agent_id} status to {status}")
    
    elif cmd == "clear-cache":
        query_type = sys.argv[2] if len(sys.argv) > 2 else None
        sms.invalidate_cache(query_type)
        print(f"Cache cleared: {query_type or 'all'}")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
