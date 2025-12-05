"""
WBI 签名工具
参考: https://socialsisteryi.github.io/bilibili-API-collect/docs/misc/sign/wbi.html
"""
import hashlib
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

# WBI 签名重排映射表
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]


def get_mixin_key(img_key: str, sub_key: str) -> str:
    """
    生成 mixin_key
    Args:
        img_key: img_url 中的文件名
        sub_key: sub_url 中的文件名
    Returns:
        mixin_key
    """
    raw_wbi_key = img_key + sub_key
    mixin_key = ''.join([raw_wbi_key[i] for i in MIXIN_KEY_ENC_TAB])[:32]
    return mixin_key


def generate_wbi_sign(params: Dict, img_key: str, sub_key: str) -> Dict[str, str]:
    """
    生成 WBI 签名参数
    Args:
        params: 原始请求参数
        img_key: img_url 中的文件名
        sub_key: sub_url 中的文件名
    Returns:
        包含 w_rid 和 wts 的参数字典
    """
    mixin_key = get_mixin_key(img_key, sub_key)
    
    # 添加 wts 参数
    wts = int(time.time())
    params_with_wts = {**params, 'wts': wts}
    
    # 排序并编码
    sorted_params = sorted(params_with_wts.items())
    encoded_params = urlencode(sorted_params)
    
    # 计算 MD5
    sign_str = encoded_params + mixin_key
    w_rid = hashlib.md5(sign_str.encode()).hexdigest()
    
    return {
        'w_rid': w_rid,
        'wts': str(wts)
    }


def extract_wbi_keys(img_url: str, sub_url: str) -> Tuple[str, str]:
    """
    从 URL 中提取 img_key 和 sub_key
    Args:
        img_url: img_url 字段值
        sub_url: sub_url 字段值
    Returns:
        (img_key, sub_key)
    """
    # 从 URL 中提取文件名（去掉扩展名）
    img_key = img_url.split('/')[-1].split('.')[0]
    sub_key = sub_url.split('/')[-1].split('.')[0]
    return img_key, sub_key

