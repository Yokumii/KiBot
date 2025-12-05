"""
Bilibili 模板系统
"""
from .engine import TemplateEngine
from .templates import TemplateType, get_template, set_template

__all__ = [
    "TemplateEngine",
    "TemplateType",
    "get_template",
    "set_template",
]

