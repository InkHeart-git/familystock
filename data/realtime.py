"""
AI 股神争霸赛 - 实时行情模块
使用腾讯证券接口获取实时行情，延迟约3-5秒
"""

import urllib.request
import re
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TencentRealTime:
    """腾讯证券实时行情"""
    
    BASE_URL = "https://qt.gtimg.cn/q="
    
    # 字段映射
    FIELDS = {
        'name': 1,
        'code': 2,
        'price': 3,
        'prev_close': 4,
        'open': 5,
        'volume': 6,
        'time': 30,
        'change': 31,
        'pct_chg': 32,
        'high': 33,
        'low': 34,
        'turnover': 36,
        'amount': 37,
    }
    
    @classmethod
    def get_quote(cls, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取单个股票实时行情
        
        Args:
            symbol: 股票代码，如 sh000001, sz000001, hkHSI
        
        Returns:
            行情数据字典
        """
        try:
            url = f"{cls.BASE_URL}{symbol}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=5)
            data = resp.read().decode('gbk')
            
            return cls._parse_response(data, symbol)
            
        except Exception as e:
            logger.error(f"获取{symbol}实时行情失败: {e}")
            return None
    
    @classmethod
    def get_quotes(cls, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量获取股票实时行情
        
        Args:
            symbols: 股票代码列表
        
        Returns:
            {symbol: data} 字典
        """
        if not symbols:
            return {}
        
        try:
            # 腾讯接口支持批量查询，用,分隔
            symbol_str = ','.join(symbols)
            url = f"{cls.BASE_URL}{symbol_str}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode('gbk')
            
            result = {}
            lines = data.split(';')
            for line in lines:
                if '=' in line:
                    symbol_from_data = re.search(r'v_(\w+)="', line)
                    if symbol_from_data:
                        s = symbol_from_data.group(1)
                        result[s] = cls._parse_response(line, s)
            
            return result
            
        except Exception as e:
            logger.error(f"批量获取实时行情失败: {e}")
            return {}
    
    @classmethod
    def _safe_float(cls, value: str) -> float:
        """安全转换为浮点数"""
        try:
            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    @classmethod
    def _safe_int(cls, value: str) -> int:
        """安全转换为整数"""
        try:
            return int(float(value)) if value else 0
        except (ValueError, TypeError):
            return 0
    
    @classmethod
    def _parse_response(cls, data: str, symbol: str) -> Optional[Dict[str, Any]]:
        """解析腾讯证券响应数据"""
        match = re.search(r'v_\w+="(.+)"', data)
        if not match:
            return None
        
        fields = match.group(1).split('~')
        
        result = {
            'symbol': symbol,
            'name': cls._get_field(fields, 'name'),
            'price': cls._safe_float(cls._get_field(fields, 'price')),
            'prev_close': cls._safe_float(cls._get_field(fields, 'prev_close')),
            'open': cls._safe_float(cls._get_field(fields, 'open')),
            'change': cls._safe_float(cls._get_field(fields, 'change')),
            'pct_chg': cls._safe_float(cls._get_field(fields, 'pct_chg')),
            'high': cls._safe_float(cls._get_field(fields, 'high')),
            'low': cls._safe_float(cls._get_field(fields, 'low')),
            'volume': cls._safe_int(cls._get_field(fields, 'volume')),
            'amount': cls._safe_float(cls._get_field(fields, 'amount')),
            'time': cls._get_field(fields, 'time'),
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        return result
    
    @classmethod
    def _get_field(cls, fields: List[str], name: str) -> Optional[str]:
        """安全获取字段"""
        idx = cls.FIELDS.get(name)
        if idx is not None and idx < len(fields):
            return fields[idx]
        return None


class RealTimeDataManager:
    """实时数据管理器"""
    
    def __init__(self):
        self.tencent = TencentRealTime()
        self.cache: Dict[str, Dict] = {}
        self.cache_time: Dict[str, datetime] = {}
        self.cache_ttl = 5  # 缓存5秒
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取实时行情（带缓存）"""
        now = datetime.now()
        
        # 检查缓存
        if symbol in self.cache:
            cache_age = (now - self.cache_time.get(symbol, now)).total_seconds()
            if cache_age < self.cache_ttl:
                return self.cache[symbol]
        
        # 获取新数据
        data = await asyncio.to_thread(self.tencent.get_quote, symbol)
        
        if data:
            self.cache[symbol] = data
            self.cache_time[symbol] = now
        
        return data
    
    async def get_multiple(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取实时行情"""
        return await asyncio.to_thread(self.tencent.get_quotes, symbols)
    
    async def get_index_data(self) -> Dict[str, Dict]:
        """获取主要指数实时数据"""
        indices = [
            'sh000001',  # 上证指数
            'sz399001',  # 深证成指
            'sz399006',  # 创业板
            'hkHSI',     # 恒生指数
            'usIXIC',    # 纳斯达克
            'usDJI',     # 道琼斯
        ]
        
        data = await self.get_multiple(indices)
        return data
    
    async def get_ai_portfolio_quotes(self, holdings: List[Dict]) -> Dict[str, Dict]:
        """获取AI持仓股票的实时行情"""
        symbols = []
        for h in holdings:
            code = h.get('symbol', '')
            if code:
                # 转换代码格式
                if code.startswith('0') or code.startswith('3'):
                    symbols.append(f'sz{code}')
                elif code.startswith('6'):
                    symbols.append(f'sh{code}')
                elif code.startswith('8') or code.startswith('4'):
                    symbols.append(f'bj{code}')
        
        return await self.get_multiple(symbols)


# 全局实例
real_time_manager = RealTimeDataManager()


# 便捷函数
async def get_quote(symbol: str) -> Optional[Dict]:
    """获取单个股票实时行情"""
    return await real_time_manager.get_quote(symbol)

async def get_quotes(symbols: List[str]) -> Dict[str, Dict]:
    """批量获取实时行情"""
    return await real_time_manager.get_multiple(symbols)

async def get_realtime_index() -> Dict[str, Dict]:
    """获取主要指数实时数据"""
    return await real_time_manager.get_index_data()
