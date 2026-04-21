"""
MiniRock API 服务入口
FastAPI应用主文件
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.routers import portfolio, ai_analysis, tushare, auth, stock, review, competition_progress

app = FastAPI(
    title="MiniRock API",
    description="智能投资终端API服务",
    version="2.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(portfolio.router, prefix="/api")
app.include_router(ai_analysis.router, prefix="/api")
app.include_router(tushare.router_tushare, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(stock.router_stock, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(competition_progress.router, prefix="/api")

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "service": "minirock-api", "version": "2.0.0"}

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "MiniRock API Service",
        "version": "2.0.0",
        "docs": "/docs"
    }


@app.get("/api/version")
async def get_version():
    """获取API版本信息"""
    return {
        "version": "v20250321",
        "environment": "production",
        "service": "minirock-api",
        "build_time": "2026-03-21 07:30:00"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
