"""
订阅数据持久化存储
"""
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

from infra.logger import logger


class SubscriptionStorage:
    """订阅数据存储管理器"""
    
    def __init__(self, storage_dir: str = "cache/bilibili"):
        """
        初始化存储管理器
        Args:
            storage_dir: 存储目录
        """
        self.storage_dir = storage_dir
        self.subscriptions_file = os.path.join(storage_dir, "subscriptions.json")
        self.tasks_file = os.path.join(storage_dir, "tasks.json")
        self.filters_file = os.path.join(storage_dir, "filters.json")
        self.baselines_file = os.path.join(storage_dir, "baselines.json")
        
        os.makedirs(storage_dir, exist_ok=True)
    
    def load_subscriptions(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        加载订阅配置
        Returns:
            订阅配置字典 {group_id: [subscription_dict, ...]}
        """
        if not os.path.exists(self.subscriptions_file):
            return {}
        
        try:
            with open(self.subscriptions_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warn("SubscriptionStorage", f"加载订阅配置失败: {e}")
            return {}
    
    def save_subscriptions(self, subscriptions: Dict[str, List[Dict[str, Any]]]):
        """
        保存订阅配置
        Args:
            subscriptions: 订阅配置字典
        """
        try:
            with open(self.subscriptions_file, "w", encoding="utf-8") as f:
                json.dump(subscriptions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warn("SubscriptionStorage", f"保存订阅配置失败: {e}")
    
    def load_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        加载任务配置
        Returns:
            任务配置字典 {task_id: task_dict}
        """
        if not os.path.exists(self.tasks_file):
            return {}
        
        try:
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warn("SubscriptionStorage", f"加载任务配置失败: {e}")
            return {}
    
    def save_tasks(self, tasks: Dict[str, Dict[str, Any]]):
        """
        保存任务配置
        Args:
            tasks: 任务配置字典
        """
        try:
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warn("SubscriptionStorage", f"保存任务配置失败: {e}")
    
    def load_filters(self) -> Dict[str, Dict[str, Any]]:
        """
        加载过滤规则配置
        Returns:
            过滤规则配置字典 {group_id: filter_dict}
        """
        if not os.path.exists(self.filters_file):
            return {}
        
        try:
            with open(self.filters_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warn("SubscriptionStorage", f"加载过滤规则失败: {e}")
            return {}
    
    def save_filters(self, filters: Dict[str, Dict[str, Any]]):
        """
        保存过滤规则配置
        Args:
            filters: 过滤规则配置字典
        """
        try:
            with open(self.filters_file, "w", encoding="utf-8") as f:
                json.dump(filters, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warn("SubscriptionStorage", f"保存过滤规则失败: {e}")
    
    def load_baselines(self) -> Dict[str, Dict[str, str]]:
        """
        加载更新基线
        Returns:
            基线字典 {task_id: baseline_value}
        """
        if not os.path.exists(self.baselines_file):
            return {}
        
        try:
            with open(self.baselines_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warn("SubscriptionStorage", f"加载更新基线失败: {e}")
            return {}
    
    def save_baselines(self, baselines: Dict[str, Dict[str, str]]):
        """
        保存更新基线
        Args:
            baselines: 基线字典
        """
        try:
            with open(self.baselines_file, "w", encoding="utf-8") as f:
                json.dump(baselines, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warn("SubscriptionStorage", f"保存更新基线失败: {e}")

