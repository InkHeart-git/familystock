"""
冲突热点API路由
提供全球冲突热点数据
"""
from fastapi import APIRouter
from typing import List
from datetime import datetime
import random

router = APIRouter()

# 冲突热点数据源
CONFLICT_ZONES = [
    {
        "name": "美以-伊朗",
        "location": "Middle East",
        "lat": 32.0,
        "lon": 53.0,
        "intensity": 95,
        "status": "active",
        "description": "美以与伊朗紧张关系升级，核设施威胁",
        "impact": "全球能源安全",
        "casualties": None,
        "category": "军事冲突"
    },
    {
        "name": "巴以冲突",
        "location": "Gaza Strip",
        "lat": 31.5,
        "lon": 34.4,
        "intensity": 90,
        "status": "active",
        "description": "加沙地带持续战事，人道主义危机",
        "impact": "地区稳定",
        "casualties": "3万+",
        "category": "军事冲突"
    },
    {
        "name": "红海危机",
        "location": "Yemen / Red Sea",
        "lat": 15.0,
        "lon": 45.0,
        "intensity": 80,
        "status": "active",
        "description": "胡塞武装袭击商船，国际航运受阻",
        "impact": "全球供应链",
        "casualties": None,
        "category": "海上冲突"
    },
    {
        "name": "俄乌冲突",
        "location": "Ukraine",
        "lat": 49.0,
        "lon": 31.0,
        "intensity": 85,
        "status": "active",
        "description": "持续军事冲突，北约与俄罗斯对峙",
        "impact": "欧洲安全",
        "casualties": "50万+",
        "category": "军事冲突"
    },
    {
        "name": "台海局势",
        "location": "Taiwan Strait",
        "lat": 24.0,
        "lon": 121.0,
        "intensity": 70,
        "status": "tension",
        "description": "军事演习频繁，地缘政治风险上升",
        "impact": "芯片供应链",
        "casualties": None,
        "category": "地缘政治"
    },
    {
        "name": "朝鲜半岛",
        "location": "Korean Peninsula",
        "lat": 38.0,
        "lon": 127.0,
        "intensity": 65,
        "status": "tension",
        "description": "导弹试射频繁，美韩联军演习",
        "impact": "东北亚安全",
        "casualties": None,
        "category": "军事对峙"
    },
    {
        "name": "南海争端",
        "location": "South China Sea",
        "lat": 15.0,
        "lon": 115.0,
        "intensity": 60,
        "status": "tension",
        "description": "岛礁主权争议，军事化趋势",
        "impact": "航运通道",
        "casualties": None,
        "category": "领土争端"
    },
    {
        "name": "印巴边境",
        "location": "Kashmir",
        "lat": 34.5,
        "lon": 76.0,
        "intensity": 55,
        "status": "tension",
        "description": "克什米尔地区零星交火",
        "impact": "地区稳定",
        "casualties": None,
        "category": "边境冲突"
    }
]

# 实时新闻源 (模拟从新闻API获取)
NEWS_SOURCES = [
    {"source": "Reuters", "reliability": 0.95},
    {"source": "BBC", "reliability": 0.90},
    {"source": "Al Jazeera", "reliability": 0.85},
    {"source": "新华社", "reliability": 0.90},
    {"source": "CNN", "reliability": 0.80},
]


@router.get("/zones")
async def get_conflict_zones():
    """获取全球冲突热点列表"""
    # 模拟实时更新强度值 (轻微波动)
    zones = []
    for zone in CONFLICT_ZONES:
        # 随机波动 -5 到 +5
        intensity_variation = random.randint(-5, 5)
        updated_zone = zone.copy()
        updated_zone["intensity"] = max(0, min(100, zone["intensity"] + intensity_variation))
        updated_zone["lastUpdate"] = datetime.now().isoformat()
        zones.append(updated_zone)
    
    # 按强度排序
    zones.sort(key=lambda x: x["intensity"], reverse=True)
    
    return {
        "code": 0,
        "message": "success",
        "data": zones,
        "total": len(zones),
        "updateTime": datetime.now().isoformat()
    }


@router.get("/zones/{name}")
async def get_conflict_detail(name: str):
    """获取特定冲突详情"""
    zone = next((z for z in CONFLICT_ZONES if z["name"] == name), None)
    
    if not zone:
        return {
            "code": 404,
            "message": "冲突热点不存在",
            "data": None
        }
    
    # 生成详细报告
    detail = zone.copy()
    detail["lastUpdate"] = datetime.now().isoformat()
    detail["relatedNews"] = generate_related_news(zone["name"])
    detail["marketImpact"] = generate_market_impact(zone["category"])
    
    return {
        "code": 0,
        "message": "success",
        "data": detail
    }


@router.get("/summary")
async def get_conflict_summary():
    """获取冲突概览统计"""
    active_conflicts = [z for z in CONFLICT_ZONES if z["status"] == "active"]
    tension_zones = [z for z in CONFLICT_ZONES if z["status"] == "tension"]
    
    # 计算全球风险指数 (0-100)
    risk_index = sum(z["intensity"] for z in CONFLICT_ZONES) / len(CONFLICT_ZONES)
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "globalRiskIndex": round(risk_index, 1),
            "activeConflicts": len(active_conflicts),
            "tensionZones": len(tension_zones),
            "totalZones": len(CONFLICT_ZONES),
            "highestRisk": max(CONFLICT_ZONES, key=lambda x: x["intensity"])["name"],
            "categories": {
                "军事冲突": len([z for z in CONFLICT_ZONES if z["category"] == "军事冲突"]),
                "地缘政治": len([z for z in CONFLICT_ZONES if z["category"] == "地缘政治"]),
                "边境冲突": len([z for z in CONFLICT_ZONES if z["category"] == "边境冲突"]),
                "海上冲突": len([z for z in CONFLICT_ZONES if z["category"] == "海上冲突"]),
                "军事对峙": len([z for z in CONFLICT_ZONES if z["category"] == "军事对峙"]),
                "领土争端": len([z for z in CONFLICT_ZONES if z["category"] == "领土争端"]),
            }
        },
        "updateTime": datetime.now().isoformat()
    }


@router.get("/news")
async def get_conflict_news(limit: int = 10):
    """获取冲突相关新闻"""
    # 模拟新闻数据
    news_items = [
        {"time": "10:30", "category": "冲突", "text": "美军空袭也门胡塞武装目标，红海局势升级"},
        {"time": "10:25", "category": "市场", "text": "布伦特原油突破85美元，地缘风险溢价上升"},
        {"time": "10:15", "category": "政治", "text": "欧盟通过对俄第14轮制裁方案"},
        {"time": "10:10", "category": "冲突", "text": "以军空袭加沙南部，哈马斯称将扩大反击"},
        {"time": "10:05", "category": "市场", "text": "现货黄金创历史新高，避险需求激增"},
        {"time": "09:55", "category": "政治", "text": "北约秘书长：将增加对乌克兰军事援助"},
        {"time": "09:45", "category": "冲突", "text": "俄军对基辅发动大规模无人机袭击"},
        {"time": "09:30", "category": "市场", "text": "美元指数下跌，美联储降息预期升温"},
        {"time": "09:20", "category": "政治", "text": "中国外交部呼吁各方保持克制，政治解决争端"},
        {"time": "09:10", "category": "冲突", "text": "朝鲜发射巡航导弹，韩军提升警戒等级"},
        {"time": "09:00", "category": "市场", "text": "铜价上涨，智利矿山供应担忧加剧"},
        {"time": "08:50", "category": "政治", "text": "伊朗警告：若以色列攻击核设施将报复"},
    ]
    
    return {
        "code": 0,
        "message": "success",
        "data": news_items[:limit],
        "total": len(news_items),
        "updateTime": datetime.now().isoformat()
    }


def generate_related_news(zone_name: str) -> List[dict]:
    """生成相关新闻"""
    news_templates = {
        "美以-伊朗": [
            {"title": "伊朗宣布提高铀浓缩丰度至60%", "source": "Reuters", "time": "2小时前"},
            {"title": "以色列称已准备好对伊朗核设施采取行动", "source": "BBC", "time": "4小时前"},
        ],
        "巴以冲突": [
            {"title": "加沙人道主义危机持续恶化", "source": "Al Jazeera", "time": "1小时前"},
            {"title": "联合国呼吁立即停火", "source": "UN", "time": "3小时前"},
        ],
        "俄乌冲突": [
            {"title": "北约宣布新一轮对乌军援计划", "source": "Reuters", "time": "30分钟前"},
            {"title": "俄军称在顿涅茨克取得进展", "source": "TASS", "time": "2小时前"},
        ],
    }
    
    return news_templates.get(zone_name, [
        {"title": "地区局势持续紧张", "source": "Reuters", "time": "1小时前"},
        {"title": "国际社会呼吁对话解决", "source": "BBC", "time": "3小时前"},
    ])


def generate_market_impact(category: str) -> dict:
    """生成市场影响分析"""
    impact_map = {
        "军事冲突": {
            "affected_sectors": ["军工", "能源", "黄金", "石油"],
            "sentiment": "risk_off",
            "typical_reaction": "避险资产上涨，风险资产下跌"
        },
        "地缘政治": {
            "affected_sectors": ["外贸", "跨境电商", "能源进口"],
            "sentiment": "cautious",
            "typical_reaction": "相关板块波动加剧"
        },
        "边境冲突": {
            "affected_sectors": ["军工", "安防"],
            "sentiment": "neutral",
            "typical_reaction": "局部影响有限"
        },
    }
    
    return impact_map.get(category, {
        "affected_sectors": ["市场波动"],
        "sentiment": "neutral",
        "typical_reaction": "影响待观察"
    })
