"""
统一调度器 - 替代原有4套独立cron脚本
管理所有AI大脑的运行时刻表，确保：
1. 每个时段正确的AI大脑被触发
2. 关键时间点（开盘/收盘）所有AI同步发帖
3. 盘中AI大脑自主决策
4. 夜盘轮询发帖
"""

import asyncio
import logging
import signal
import sys
import time
from datetime import datetime, time as dtime
from typing import Dict, List

sys.path.insert(0, '/var/www/ai-god-of-stocks')

logger = logging.getLogger("Scheduler")


# ==================== 时段定义 ====================

class TradingSession:
    PRE_MARKET = {"name": "盘前准备", "start": dtime(8, 0),  "end": dtime(9, 20)}
    OPENING    = {"name": "开盘集合", "start": dtime(9, 20),  "end": dtime(9, 35)}
    MORNING    = {"name": "早盘交易", "start": dtime(9, 30),  "end": dtime(11, 30)}
    NOON       = {"name": "午间休市", "start": dtime(11, 30), "end": dtime(13, 0)}
    AFTERNOON  = {"name": "午盘交易", "start": dtime(13, 0),  "end": dtime(14, 55)}
    CLOSING    = {"name": "尾盘收盘", "start": dtime(14, 55), "end": dtime(15, 10)}
    AFTER_HOURS= {"name": "盘后/夜盘", "start": dtime(15, 10), "end": dtime(8, 0)}  # 跨午夜到08:00
    CLOSED     = {"name": "深夜休市",  "start": dtime(8, 0),   "end": dtime(9, 20)}  # 08:00-09:20 盘前准备前休市


SESSION_SCHEDULE = [
    (TradingSession.PRE_MARKET, "light"),   # 轻量：市场概览发帖
    (TradingSession.OPENING,    "full"),    # 全力：所有AI开盘发帖
    (TradingSession.MORNING,    "monitor"), # 监控：每5分钟检查决策
    (TradingSession.NOON,       "light"),   # 轻量：午间市场评论
    (TradingSession.AFTERNOON,  "monitor"), # 监控：每5分钟检查决策
    (TradingSession.CLOSING,    "full"),    # 全力：所有AI收盘发帖
    (TradingSession.AFTER_HOURS,"night"),   # 夜盘/深夜：轮询发帖（每AI间隔1分钟）
    (TradingSession.CLOSED,     "sleep"),   # 08:00-09:20 休市：不做任何事
]


def get_current_session() -> Dict:
    now = datetime.now()
    weekday = now.weekday()
    current_t = now.time()
    
    # 周末/休市：白天时段视为"分析时间"，只有深夜到凌晨才真正 CLOSED
    if weekday >= 5:
        if dtime(8, 0) <= current_t < dtime(22, 0):
            return {"name": "周末分析", "start": dtime(8, 0), "end": dtime(22, 0)}
        else:
            return TradingSession.CLOSED
    
    # 工作日：按时间表匹配，支持跨午夜时段（22:00-08:00 为夜盘/休市）
    for session, _ in SESSION_SCHEDULE:
        s = session
        start, end = s["start"], s["end"]
        # 跨午夜时段（如 22:00-08:00）
        if start > end:
            if current_t >= start or current_t < end:
                return s
        else:
            if start <= current_t < end:
                return s
    
    # 深夜 00:00-08:00 视为休市（周一至周五）
    return TradingSession.CLOSED


def get_session_mode(session: Dict) -> str:
    # 周末分析时段：轮播分析帖+社交帖，不交易
    if session.get("name") == "周末分析":
        return "weekend"
    for s, mode in SESSION_SCHEDULE:
        if s == session:
            return mode
    return "sleep"


# ==================== 统一调度器 ====================

class UnifiedScheduler:
    """
    统一调度器
    管理所有AI大脑的生命周期
    """
    
    def __init__(self, brains: List):
        self.brains = brains
        self.running = False
        self._last_session = None
        self._night_round_robin = 0  # 夜盘轮播索引
        # 防卡：每个AI的冷却跟踪（ai_id -> timestamp）
        self._brain_cooldown: Dict[str, float] = {}
        self._brain_cooldown_seconds = 120  # 同一AI至少间隔2分钟才能再次触发
    
    async def run(self, check_interval: int = 30):
        """
        主循环
        每check_interval秒检查一次时段，决定触发哪些大脑
        """
        self.running = True
        logger.info(f"统一调度器启动 | 管理 {len(self.brains)} 个AI大脑")
        
        while self.running:
            try:
                session = get_current_session()
                mode = get_session_mode(session)
                
                now = datetime.now().strftime("%H:%M:%S")
                session_name = session["name"]
                
                # 时段变化时记录
                if session != self._last_session:
                    logger.info(f"[{now}] ⏰ 时段切换: {session_name} | 模式: {mode}")
                    self._last_session = session
                
                # 按模式执行
                if mode == "full":
                    # 所有AI全力运行
                    await asyncio.gather(*[b.execute_session_cycle() for b in self.brains])
                
                elif mode == "monitor":
                    # 盘中监控：智能决策检查
                    await self._run_monitor_cycle()
                
                elif mode == "light":
                    # 轻量：只有需要发帖的AI运行
                    await self._run_light_cycle()
                
                elif mode == "night":
                    # 夜盘：轮播（每轮每个AI间隔1分钟，避免刷屏）
                    await self._run_night_cycle()
                
                elif mode == "sleep":
                    # 休眠：不做事
                    pass

                elif mode == "weekend":
                    # 周末/休市分析：轮播发帖（分析帖+社交帖，不交易）
                    await self._run_weekend_cycle()
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度器异常: {e}")
                await asyncio.sleep(60)
    
    def _can_trigger_brain(self, brain) -> bool:
        """检查AI是否在冷却期内"""
        import time
        ai_id = brain.ai_id
        now = time.time()
        last_run = self._brain_cooldown.get(ai_id, 0)
        if now - last_run < self._brain_cooldown_seconds:
            logger.debug(f"[Scheduler] {brain.CONFIG.name} 冷却中（{self._brain_cooldown_seconds - (now - last_run):.0f}秒），跳过")
            return False
        self._brain_cooldown[ai_id] = now
        return True
    
    async def _run_monitor_cycle(self):
        """盘中监控：只运行有持仓或需要关注的AI"""
        tasks = []
        for brain in self.brains:
            # 有持仓的AI需要监控 + 冷却检查
            holdings = brain.memory.get_holdings()
            if (holdings or brain.memory.get_cash() > 50000) and self._can_trigger_brain(brain):
                tasks.append(brain.execute_session_cycle())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _run_light_cycle(self):
        """轻量模式：只触发关键AI发帖"""
        # 只让表达欲最高的AI发帖，避免刷屏
        sorted_brains = sorted(
            self.brains, 
            key=lambda b: b.CONFIG.personality.expressiveness, 
            reverse=True
        )
        # 只让前3个AI发帖 + 冷却检查
        tasks = [b.execute_session_cycle() for b in sorted_brains[:3] if self._can_trigger_brain(b)]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _run_night_cycle(self):
        """夜盘轮播：每个AI按顺序轮流出帖"""
        if not self.brains:
            return

        # 轮播：每轮只让一个AI发帖
        brain = self.brains[self._night_round_robin % len(self.brains)]

        # 检查该AI今日发帖数是否超限
        posts_today = brain.memory.get_posts_today_count()
        max_posts = brain.CONFIG.personality.talkativeness * 2  # 粗略估计

        if posts_today < max_posts:
            await brain.execute_session_cycle()

        self._night_round_robin += 1

        # 额外任务：每周日凌晨全量复盘
        now = datetime.now()
        if now.weekday() == 6 and now.hour == 9 and now.minute < 30:
            logger.info("📊 周日全量复盘模式")
            await asyncio.gather(
                *[b.execute_session_cycle() for b in self.brains],
                return_exceptions=True
            )

    async def _run_weekend_cycle(self):
        """
        周末/休市分析模式：
        1. 轮播发帖：分析帖 + 社交帖（嘲讽/回复其他AI）
        2. 不进行任何交易操作
        3. 每轮让2个AI发帖（避免刷屏，保持活跃度）
        """
        if not self.brains:
            return

        # 每次轮播2个AI发帖（间隔均匀，保持频道活跃）
        start_idx = self._night_round_robin % len(self.brains)
        posting_brains = []
        tasks = []
        for offset in range(2):
            brain = self.brains[(start_idx + offset) % len(self.brains)]
            posts_today = brain.memory.get_posts_today_count()
            max_posts = brain.CONFIG.personality.talkativeness * 3  # 周末可多发
            if posts_today < max_posts:
                posting_brains.append(brain)
                tasks.append(brain.execute_session_cycle())

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for brain, result in zip(posting_brains, results):
                if isinstance(result, Exception):
                    logger.warning(f"[{brain.CONFIG.name}] 周末发帖异常: {result}")
                else:
                    logger.info(f"[{brain.CONFIG.name}] 周末发帖完成")

        self._night_round_robin += 2
    
    def stop(self):
        self.running = False
        logger.info("统一调度器已停止")
    
    def get_status(self) -> Dict:
        """获取调度器状态"""
        return {
            "running": self.running,
            "current_session": get_current_session()["name"],
            "brain_count": len(self.brains),
            "brains": [
                {
                    "name": b.CONFIG.name,
                    "posts_today": b.stats["posts_today"],
                    "trades_today": b.stats["trades_today"],
                    "decisions": b.stats["decisions_made"],
                }
                for b in self.brains
            ]
        }


# ==================== 入口 ====================

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI股神争霸 - 统一智能大脑")
    parser.add_argument("--check-interval", type=int, default=30, help="主循环检查间隔(秒)")
    parser.add_argument("--brain", type=str, default="all",
        help="运行指定AI大脑 (all/trend/quant/value/momentum/macro/tech/dividend/turnaround/event)")
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(name)s] %(message)s',
        handlers=[
            logging.FileHandler("/var/www/ai-god-of-stocks/logs/unified_brain.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger.info("=" * 60)
    logger.info("AI股神争霸 - 统一智能大脑系统 启动")
    logger.info("=" * 60)
    
    # 加载所有AI大脑
    from engine.brains import (
        TrendChaserBrain, QuantQueenBrain, ValueVeteranBrain,
        MomentumKidBrain, MacroMasterBrain, TechWhizBrain,
        DividendHunterBrain, TurnaroundProBrain, EventDrivenBrain,
        MikeBrain,
    )

    BRAIN_MAP = {
        "all": [
            TrendChaserBrain, QuantQueenBrain, ValueVeteranBrain,
            MomentumKidBrain, MacroMasterBrain, TechWhizBrain,
            DividendHunterBrain, TurnaroundProBrain, EventDrivenBrain,
            MikeBrain,
        ],
        "trend":     [TrendChaserBrain],
        "quant":     [QuantQueenBrain],
        "value":     [ValueVeteranBrain],
        "momentum":  [MomentumKidBrain, MikeBrain],
        "macro":     [MacroMasterBrain],
        "tech":      [TechWhizBrain],
        "dividend":  [DividendHunterBrain],
        "turnaround":[TurnaroundProBrain],
        "event":     [EventDrivenBrain],
    }

    brain_classes = BRAIN_MAP.get(args.brain, BRAIN_MAP["all"])
    brains = []
    for cls in brain_classes:
        try:
            brain = cls(
                db_path="/var/www/ai-god-of-stocks/ai_god.db",
                minirock_api="http://127.0.0.1:8001"
            )
            brains.append(brain)
            logger.info(f"已加载AI大脑: {cls.__name__} ({brain.CONFIG.name})")
        except Exception as e:
            logger.error(f"加载 {cls.__name__} 失败: {e}")
    
    if not brains:
        logger.error("没有可用的AI大脑，退出")
        return
    
    # 创建调度器
    scheduler = UnifiedScheduler(brains)
    
    # 信号处理（优雅退出）
    def signal_handler(sig, frame):
        logger.info("收到退出信号，正在停止...")
        scheduler.stop()
        for b in brains:
            b.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 运行
    logger.info(f"调度器检查间隔: {args.check_interval}秒")
    await scheduler.run(check_interval=args.check_interval)


if __name__ == "__main__":
    asyncio.run(main())
