"""
API服务入口 - 桥接到app.main
"""
from app.main import app

# 导出app供uvicorn使用
__all__ = ['app']
