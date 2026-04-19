"""
Humanizer - 去除 AI 写作痕迹，让文本更像真人写的
基于 Wikipedia "Signs of AI writing" 规则
"""

import re
import random
from typing import Dict


# ---- AI 词汇替换表 ----
AI_VOCAB: Dict[str, str] = {
    "additional": "",
    "additionally": "",
    "furthermore": "",
    "moreover": "",
    "however": "",
    "therefore": "",
    "thus": "",
    "hence": "",
    "align with": "for",
    "aligned with": "for",
    "crucial": "key",
    "crucially": "importantly",
    "delve": "explore",
    "delving": "exploring",
    "emphasizing": "stating",
    "emphasise": "state",
    "enhance": "improve",
    "enhancing": "improving",
    "fostering": "building",
    "foster": "build",
    "garner": "get",
    "garnering": "getting",
    "highlight": "show",
    "highlights": "shows",
    "highlighted": "showed",
    "highlighting": "showing",
    "interplay": "relationship",
    "intricate": "complex",
    "intricacies": "details",
    "landscape": "field",
    "landscapes": "areas",
    "pivotal": "key",
    "pivotally": "importantly",
    "showcase": "show",
    "showcasing": "showing",
    "tapestry": "",
    "tapestries": "",
    "testament": "",
    "testaments": "",
    "underscore": "show",
    "underscoring": "showing",
    "valuable": "useful",
    "invaluable": "useful",
    "vibrant": "active",
    "enduring": "lasting",
    "comprehensive": "thorough",
    "robust": "strong",
    "dynamic": "active",
    "innovative": "new",
    "scalable": "usable",
    "streamline": "simplify",
    "streamlining": "simplifying",
    "leverage": "use",
    "leveraging": "using",
    "holistic": "full",
    "empower": "help",
    "empowering": "helping",
    "seamless": "smooth",
    "cutting-edge": "latest",
    "game-changing": "significant",
    "next-generation": "modern",
    "transformative": "major",
}

# ---- 空洞 -ing 短语替换 ----
VAGUE_ING: Dict[str, str] = {
    "highlighting the importance": "important",
    "underscoring the": "",
    "reflecting the": "",
    "symbolizing": "",
    "showcasing": "showing",
    "demonstrating": "showing",
    "illustrating": "showing",
    "fostering a": "building a",
    "ensuring": "making sure",
    "it is important to note that": "",
    "it should be noted that": "",
    "it is worth noting that": "",
    "it is clear that": "clearly",
    "it is evident that": "clearly",
    "as evidenced by": "as shown by",
}

# ---- Filler 短语 ----
FILLER_PAIRS = [
    ("in order to", "to"),
    ("due to the fact that", "because"),
    ("at this point in time", "now"),
    ("in the event that", "if"),
    ("with regard to", "about"),
    ("in light of the fact that", "because"),
    ("taking into consideration", "considering"),
    ("it is imperative that", "must"),
    ("it is essential that", "should"),
    ("it goes without saying", ""),
    ("needless to say", ""),
    ("last but not least", "finally"),
    ("each and every", "every"),
    ("nowhere else in the world", ""),
    ("one of the most", ""),
]

# ---- 宣传语词汇 ----
PROMO_WORDS = {
    "breathtaking", "stunning", "renowned", "groundbreaking",
    "nestled", "must-visit", "exquisite", "magnificent",
}

# ---- 系动词替代 ----
COPULA_MAP = {
    "serves as": "is",
    "stands as": "is",
    "boasts": "has",
    "boast": "have",
    "features": "has",
    "offers": "has",
    "delivers": "provides",
    "embodies": "is",
    "serving as a testament": "",
    "a testament to": "",
    "as a testament to": "",
}

# ---- Sycophancy 模式 ----
SYCOPHANCY_PATTERNS = [
    r"great question!?\s*",
    r"absolutely right!?\s*",
    r"of course!?\s*",
    r"certainly!?\s*",
    r"absolutely!?\s*",
    r"no problem!?\s*",
    r"here is\s+the\s+analysis\.?\s*",
    r"let me know if you would like",
    r"i hope this helps",
    r"would you like me to expand",
    r"please let me know",
    r"here's what you need to know",
]

# ---- 预编译正则 ----
_AI_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in AI_VOCAB.keys()) + r")\b",
    re.IGNORECASE,
)

_EM_DASH_RE = re.compile(r"(\S)—(\S)")

_RULE_OF_THREE_RE = re.compile(
    r"(\w+), (\w+), and (\w+)\s*(?:in|for|to|with|that|which|are|was)",
    re.IGNORECASE,
)

_SYCOPHANCY_RE = re.compile("|".join(SYCOPHANCY_PATTERNS), re.IGNORECASE | re.DOTALL)


class Humanizer:
    """
    AI 写作痕迹去除器
    输入 AI 风格文本，输出更像真人写的文本
    """

    def humanize(self, text: str, style_hint: str = "") -> str:
        if not text:
            return text

        result = text
        result = self._fix_ai_vocabulary(result)
        result = self._fix_em_dashes(result)
        result = self._fix_vague_ing(result)
        result = self._fix_promotional(result)
        result = self._fix_copula(result)
        result = self._fix_filler(result)
        result = self._fix_rule_of_three(result)
        result = self._remove_sycophancy(result)
        result = self._fix_quotes(result)
        result = self._inject_soul(result, style_hint)
        # 最终清理
        result = re.sub(r"^\s*[,，.。]+\s*", "", result)
        result = re.sub(r"\s{2,}", " ", result)
        result = result.strip(" ,.。，")
        return result

    def _fix_ai_vocabulary(self, text: str) -> str:
        def replace(m):
            word = m.group(0).lower()
            replacement = AI_VOCAB.get(word, word)
            if m.group(0)[0].isupper():
                return (replacement.capitalize() if replacement else "")
            return replacement

        return _AI_WORD_RE.sub(replace, text)

    def _fix_em_dashes(self, text: str) -> str:
        result = _EM_DASH_RE.sub(r"\1, \2", text)
        result = re.sub(r"\s{2,}", " ", result)
        return result

    def _fix_vague_ing(self, text: str) -> str:
        result = text
        for pattern, replacement in VAGUE_ING.items():
            result = re.sub(re.escape(pattern), replacement, result, flags=re.IGNORECASE)
        return result

    def _fix_promotional(self, text: str) -> str:
        result = text
        for word in PROMO_WORDS:
            result = re.sub(r"\b" + re.escape(word) + r"\b", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result)
        return result

    def _fix_copula(self, text: str) -> str:
        result = text
        for pattern, replacement in COPULA_MAP.items():
            result = re.sub(r"\b" + pattern + r"\b", replacement, result, flags=re.IGNORECASE)
        return result

    def _fix_filler(self, text: str) -> str:
        result = text
        for pattern, replacement in FILLER_PAIRS:
            result = re.sub(r"\b" + re.escape(pattern) + r"\b", replacement, result, flags=re.IGNORECASE)
        # 清理因删除连接词产生的多余空格和标点
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r", ,", ",", result)
        result = re.sub(r"\.\s*\.", ".", result)
        result = re.sub(r"\. ,", ".", result)
        result = re.sub(r", \.", ".", result)
        # 清理句首被删除词留下的多余逗号/空格
        result = re.sub(r"^,\s*", "", result)
        result = re.sub(r"^\s*,", "", result)
        return result

    def _fix_rule_of_three(self, text: str) -> str:
        # 三人组只保留第一个
        def simplify(m):
            return m.group(1)
        return _RULE_OF_THREE_RE.sub(simplify, text)

    def _remove_sycophancy(self, text: str) -> str:
        result = _SYCOPHANCY_RE.sub("", text)
        result = re.sub(r"\s{2,}", " ", result)
        return result

    def _fix_quotes(self, text: str) -> str:
        result = text
        result = result.replace("\u201c", '"').replace("\u201d", '"')
        result = result.replace("\u2018", "'").replace("\u2019", "'")
        return result

    def _inject_soul(self, text: str, style: str) -> str:
        """根据人设风格注入人味"""
        if not style:
            return text

        if style == "热血":
            punchy = ["冲！", "别怂！", "干就完了！", "梭哈！", "拿住！"]
            if random.random() < 0.3 and len(text) > 30:
                text = text + " " + random.choice(punchy)

        elif style == "理性":
            text = re.sub(r"!{2,}", "!", text)
            text = re.sub(r"\?{2,}", "?", text)

        elif style == "老练":
            wise = ["急什么，时间是朋友。", "稳住，别慌。", "慢慢来。"]
            if random.random() < 0.25 and len(text) > 30:
                text = text + " " + random.choice(wise)

        elif style == "幽默":
            jokes = ["今天又被市场教育了。", "韭菜日记。", "躺平。", "佛系持币。"]
            if random.random() < 0.3 and len(text) > 30:
                text = text + " " + random.choice(jokes)

        return text
