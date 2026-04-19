"""
发帖协调器 - 防刷屏 + 频率控制
"""

import time
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Deque

logger = logging.getLogger("PostCoord")


class PostCoordinator:
    """
    控制每个AI的发帖频率
    防止一个AI在短时间内发大量帖子刷屏
    
    规则：
    1. 每小时最多 N 条（根据话痨度）
    2. 连续同类型帖子需间隔 X 分钟
    3. 每日总量上限
    """
    
    def __init__(self, ai_id: str, hourly_cap: int = 6):
        self.ai_id = ai_id
        self.hourly_cap = hourly_cap
        
        # 滑动窗口：最近1小时的发帖记录
        self._recent_posts: Deque[float] = deque(maxlen=hourly_cap + 5)
        self._last_same_type: Deque[tuple] = deque(maxlen=20)  # (type, timestamp)
        
        # 每日统计
        self._today_posts = 0
        self._last_reset = datetime.now().date()
    
    def can_post(self) -> bool:
        """判断现在是否可以发帖"""
        self._check_day_reset()
        
        # 每日上限检查
        daily_cap = self.hourly_cap * 8  # 约8小时交易时段
        if self._today_posts >= daily_cap:
            return False
        
        # 每小时上限检查
        now = time.time()
        one_hour_ago = now - 3600
        
        # 清理超过1小时的记录
        while self._recent_posts and self._recent_posts[0] < one_hour_ago:
            self._recent_posts.popleft()
        
        if len(self._recent_posts) >= self.hourly_cap:
            # 需要等待
            wait_seconds = 3600 - (now - self._recent_posts[0])
            if wait_seconds > 0:
                logger.debug(f"[{self.ai_id}] 发帖冷却中，还需 {wait_seconds:.0f}秒")
                return False
        
        return True
    
    def record_post(self, post_type: str = "general"):
        """记录一次发帖"""
        now = time.time()
        self._recent_posts.append(now)
        self._last_same_type.append((post_type, now))
        self._today_posts += 1
    
    def get_wait_seconds(self) -> float:
        """获取还需等待多少秒才能发帖"""
        if not self._recent_posts:
            return 0
        
        one_hour_ago = time.time() - 3600
        while self._recent_posts and self._recent_posts[0] < one_hour_ago:
            self._recent_posts.popleft()
        
        if len(self._recent_posts) < self.hourly_cap:
            return 0
        
        return max(0, 3600 - (time.time() - self._recent_posts[0]))
    
    def can_post_type(self, post_type: str, min_interval: int = 15) -> bool:
        """检查同类型帖子间隔是否足够"""
        now = time.time()
        for ptype, ts in list(self._last_same_type):
            if ptype == post_type and (now - ts) < min_interval * 60:
                return False
        return True
    
    def _check_day_reset(self):
        """每日零点重置计数器"""
        today = datetime.now().date()
        if today > self._last_reset:
            self._today_posts = 0
            self._last_reset = today
            logger.info(f"[{self.ai_id}] 新的一天，发帖计数器已重置")
