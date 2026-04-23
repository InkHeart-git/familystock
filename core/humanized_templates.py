"""
AI股神争霸赛 - 真人语气模板库（向后兼容）
"""
import random
from datetime import datetime
from typing import Dict, Any


class HumanizedPostTemplates:
    """人类化帖子模板生成器"""
    
    BUY_PHRASES = [
        "经过仔细考虑，我决定买入一些{quantity}股{name}，价格{price}。希望能有个好表现~",
        "看到{reason}，我决定在{price}买入{quantity}股{name}。拭目以待吧",
        "{name}最近的走势让我有些心动，刚才在{price}买入了{quantity}股",
    ]
    
    SELL_PHRASES = [
        "涨了不少，决定在{price}卖出{quantity}股{name}，落袋为安",
        "{name}涨得我有点心慌了，先在{price}卖出{quantity}股看看",
        "根据{reason}，我在{price}卖出了{quantity}股{name}",
    ]
    
    HOLD_PHRASES = [
        "{name}暂时不动，{reason}",
        "看了看行情，{name}还是先拿着吧",
        "继续持有{name}，{reason}",
    ]
    
    def generate_buy_post(self, **kwargs) -> str:
        template = random.choice(self.BUY_PHRASES)
        return template.format(
            quantity=kwargs.get('quantity', ''),
            name=kwargs.get('name', ''),
            price=kwargs.get('price', ''),
            reason=kwargs.get('reason', ''),
            ai_name=kwargs.get('ai_name', ''),
            symbol=kwargs.get('symbol', ''),
            emotion=kwargs.get('emotion', 'neutral')
        )
    
    def generate_sell_post(self, **kwargs) -> str:
        template = random.choice(self.SELL_PHRASES)
        return template.format(
            quantity=kwargs.get('quantity', ''),
            name=kwargs.get('name', ''),
            price=kwargs.get('price', ''),
            reason=kwargs.get('reason', ''),
            ai_name=kwargs.get('ai_name', ''),
            symbol=kwargs.get('symbol', ''),
            emotion=kwargs.get('emotion', 'neutral'),
            pnl=kwargs.get('pnl', 0)
        )
    
    def generate_hold_post(self, **kwargs) -> str:
        template = random.choice(self.HOLD_PHRASES)
        return template.format(
            name=kwargs.get('name', ''),
            reason=kwargs.get('reason', ''),
            symbol=kwargs.get('symbol', ''),
            ai_name=kwargs.get('ai_name', '')
        )


# 全局单例
templates = HumanizedPostTemplates()
