"""
向后兼容的子代理状态管理
"""
import json
import time
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any


STATE_FILE = "/var/www/ai-god-of-stocks/data/subagent_state.json"


@dataclass
class SubAgentState:
    """子代理状态"""
    agent_id: str = ""
    mood: float = 0.5
    mood_trend: List[float] = field(default_factory=list)
    last_action: str = ""
    last_update: float = field(default_factory=time.time)
    daily_actions: int = 0
    total_trades: int = 0
    win_count: int = 0
    consecutive_holds: int = 0
    
    def update_mood_trend(self):
        self.mood_trend.append(self.mood)
        if len(self.mood_trend) > 20:
            self.mood_trend = self.mood_trend[-20:]
    
    def reset_daily(self):
        self.daily_actions = 0
        self.last_update = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StateManager:
    """状态管理器（简化版）"""
    
    def __init__(self):
        self._states: Dict[str, SubAgentState] = {}
    
    def load(self, key: str, ai_ids: List[str]) -> SubAgentState:
        """加载或创建状态"""
        # 尝试从文件加载
        try:
            with open(STATE_FILE, 'r') as f:
                all_states = json.load(f)
                for aid in ai_ids:
                    if aid in all_states:
                        data = all_states[aid]
                        self._states[aid] = SubAgentState(**data)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        # 返回请求的AI状态（如果没有则创建）
        for aid in ai_ids:
            if aid not in self._states:
                self._states[aid] = SubAgentState(agent_id=aid)
        
        return self._states[ai_ids[0]]
    
    def save(self, state: SubAgentState):
        """保存状态"""
        self._states[state.agent_id] = state
        
        # 持久化到文件
        try:
            all_states = {}
            try:
                with open(STATE_FILE, 'r') as f:
                    all_states = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            
            all_states[state.agent_id] = state.to_dict()
            
            with open(STATE_FILE, 'w') as f:
                json.dump(all_states, f, indent=2)
        except Exception:
            pass


# 全局单例
state_manager = StateManager()
