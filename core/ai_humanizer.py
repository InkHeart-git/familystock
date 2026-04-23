"""向后兼容的 AI humanizer 接口"""
from engine.posting.humanizer import Humanizer

_humanizer = Humanizer()

def humanize_post(content: str, style_hint: str = "") -> str:
    """对帖子内容进行人类化处理（向后兼容接口）"""
    return _humanizer.humanize(content, style_hint)

def check_and_humanize(content: str, style_hint: str = "") -> str:
    """检查并人类化内容"""
    return humanize_post(content, style_hint)
