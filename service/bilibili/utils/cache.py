"""
响应缓存机制
"""
import hashlib
import json
import time
from typing import Optional, Any, Dict
from datetime import datetime, timedelta

from infra.logger import logger


class ResponseCache:
    """响应缓存管理器"""
    
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        初始化缓存管理器
        Args:
            default_ttl: 默认缓存时间（秒），默认5分钟
            max_size: 最大缓存条目数
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def _generate_key(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        生成缓存键
        Args:
            url: 请求URL
            params: 请求参数
        Returns:
            缓存键
        """
        key_data = {"url": url}
        if params:
            # 排序参数以确保一致性
            sorted_params = sorted(params.items())
            key_data["params"] = sorted_params
        
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        获取缓存
        Args:
            url: 请求URL
            params: 请求参数
        Returns:
            缓存的数据，如果不存在或已过期则返回None
        """
        key = self._generate_key(url, params)
        
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        expire_time = entry.get("expire_time")
        
        # 检查是否过期
        if expire_time and time.time() > expire_time:
            del self._cache[key]
            return None
        
        return entry.get("data")
    
    def set(
        self,
        url: str,
        data: Any,
        params: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ):
        """
        设置缓存
        Args:
            url: 请求URL
            data: 要缓存的数据
            params: 请求参数
            ttl: 缓存时间（秒），None则使用默认值
        """
        # 如果缓存已满，删除最旧的条目
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        key = self._generate_key(url, params)
        expire_time = time.time() + (ttl or self.default_ttl)
        
        self._cache[key] = {
            "data": data,
            "expire_time": expire_time,
            "created_at": time.time()
        }
    
    def _evict_oldest(self):
        """删除最旧的缓存条目"""
        if not self._cache:
            return
        
        # 找到最旧的条目
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].get("created_at", 0)
        )
        del self._cache[oldest_key]
    
    def clear(self, url_pattern: Optional[str] = None):
        """
        清除缓存
        Args:
            url_pattern: URL模式（可选），如果提供则只清除匹配的缓存
        """
        if url_pattern:
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if url_pattern in entry.get("url", "")
            ]
            for key in keys_to_delete:
                del self._cache[key]
        else:
            self._cache.clear()
    
    def cleanup_expired(self):
        """清理过期的缓存条目"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.get("expire_time", 0) < current_time
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug("ResponseCache", f"清理了 {len(expired_keys)} 个过期缓存条目")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        self.cleanup_expired()
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "default_ttl": self.default_ttl
        }

