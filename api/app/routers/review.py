"""
Phase 4.4: 复盘数据API路由
提供每日复盘报告数据给前端可视化
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, date
import json
import os
import logging

logger = logging.getLogger("review_router")

router = APIRouter(prefix="/review", tags=["复盘报告"])

REPORTS_DIR = "/var/www/ai-god-of-stocks/reports"


# ==================== Pydantic Models ====================

class HoldingDetail(BaseModel):
    symbol: str
    name: str
    quantity: int
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight_pct: float


class AIRanking(BaseModel):
    rank: int
    ai_id: int
    ai_name: str
    return_pct: float
    signal: str


class SummaryData(BaseModel):
    date: str
    ai_count: int
    total_value_all: float
    avg_return_pct: float
    rankings: List[AIRanking]
    adjust_needed: List[Dict]


class AIResult(BaseModel):
    ai_id: int
    ai_name: str
    seed_capital: float
    current_total: float
    total_return_pct: float
    today_return_pct: float
    position_value: float
    cash: float
    position_ratio: float
    holdings: List[HoldingDetail]
    trade_count: int
    win_count: int
    win_rate: float
    avg_score: float
    score_hit_rate: float
    consecutive_loss_days: int
    strategy_signal: str


class ReviewResponse(BaseModel):
    date: str
    summary: SummaryData
    ai_results: Dict[str, AIResult]


# ==================== Helper ====================

def _load_latest_report() -> dict:
    """加载最新的复盘报告JSON"""
    try:
        if not os.path.exists(REPORTS_DIR):
            raise FileNotFoundError(f"Reports dir not found: {REPORTS_DIR}")

        # 找最新日期的报告
        files = [f for f in os.listdir(REPORTS_DIR) if f.startswith("review_") and f.endswith(".json")]
        if not files:
            raise FileNotFoundError("No review reports found")

        files.sort(reverse=True)
        latest = files[0]
        path = os.path.join(REPORTS_DIR, latest)

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load report: {e}")
        raise HTTPException(status_code=404, detail=f"复盘报告不存在: {str(e)}")


def _load_report_by_date(date_str: str) -> dict:
    """加载指定日期的复盘报告"""
    path = os.path.join(REPORTS_DIR, f"review_{date_str}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"复盘报告不存在: {date_str}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ==================== API Endpoints ====================

@router.get("/today", response_model=ReviewResponse)
async def get_today_report():
    """
    获取今日复盘报告
    GET /api/review/today
    """
    report = _load_latest_report()

    # 转换 rankings 中的 ai_id 为 int
    for r in report.get("summary", {}).get("rankings", []):
        r["ai_id"] = int(r["ai_id"])

    return report


@router.get("/date/{date_str}", response_model=ReviewResponse)
async def get_report_by_date(date_str: str):
    """
    获取指定日期复盘报告
    GET /api/review/date/2026-04-20
    """
    # 简单校验日期格式
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    report = _load_report_by_date(date_str)

    for r in report.get("summary", {}).get("rankings", []):
        r["ai_id"] = int(r["ai_id"])

    return report


@router.get("/history")
async def get_report_history(limit: int = 10):
    """
    获取复盘报告历史列表
    GET /api/review/history?limit=10
    """
    try:
        files = [f for f in os.listdir(REPORTS_DIR) if f.startswith("review_") and f.endswith(".json")]
        files.sort(reverse=True)
        files = files[:limit]

        history = []
        for f in files:
            date_str = f.replace("review_", "").replace(".json", "")
            # 读取摘要数据
            try:
                path = os.path.join(REPORTS_DIR, f)
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                summary = data.get("summary", {})
                history.append({
                    "date": date_str,
                    "ai_count": summary.get("ai_count", 0),
                    "total_value": summary.get("total_value_all", 0),
                    "avg_return_pct": summary.get("avg_return_pct", 0),
                })
            except Exception:
                history.append({"date": date_str, "error": "加载失败"})

        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rankings")
async def get_rankings():
    """
    获取最新收益排行（简化版，供榜单图表使用）
    GET /api/review/rankings
    """
    report = _load_latest_report()
    rankings = report.get("summary", {}).get("rankings", [])

    return {
        "date": report.get("date", datetime.now().strftime("%Y-%m-%d")),
        "rankings": [
            {
                "rank": r["rank"],
                "ai_id": int(r["ai_id"]),
                "ai_name": r["ai_name"],
                "return_pct": round(r["return_pct"] * 100, 2),
                "signal": r["signal"],
            }
            for r in rankings
        ]
    }


@router.get("/heatmap")
async def get_heatmap():
    """
    获取操作热力图数据（每日各AI的操作强度）
    GET /api/review/heatmap
    """
    # 读取最近7天报告，汇总操作情况
    try:
        files = [f for f in os.listdir(REPORTS_DIR) if f.startswith("review_") and f.endswith(".json")]
        files.sort(reverse=True)
        files = files[:7]

        heatmap_data = {}
        for f in files:
            date_str = f.replace("review_", "").replace(".json", "")
            path = os.path.join(REPORTS_DIR, f)
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)

            for ai_id, result in data.get("ai_results", {}).items():
                if ai_id not in heatmap_data:
                    heatmap_data[ai_id] = {
                        "ai_id": int(ai_id),
                        "ai_name": result.get("ai_name", ""),
                        "days": [],
                    }
                heatmap_data[ai_id]["days"].append({
                    "date": date_str,
                    "trade_count": result.get("trade_count", 0),
                    "position_ratio": result.get("position_ratio", 0),
                    "total_return_pct": result.get("total_return_pct", 0),
                })

        return {
            "dates": [f.replace("review_", "").replace(".json", "") for f in reversed(files)],
            "ais": list(heatmap_data.values()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
