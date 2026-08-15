"""自然语言输入解析
识别用户说的股票代码/名称，识别用户意图
"""

import re
from typing import Optional, Tuple, Dict, Any


def extract_stock_code(text: str) -> Optional[str]:
    """从文本中提取股票代码（6位数字）."""
    # 匹配6位数字
    matches = re.findall(r'\b(\d{6})\b', text)
    if matches:
        return matches[0]  # 返回第一个找到的
    return None


def extract_stock_name(text: str, name_map: Dict[str, str] = None) -> Optional[str]:
    """尝试从文本提取股票名称（简单匹配，需要名称映射表）."""
    # TODO: 加入全市场名称映射表
    # 现在先不做，靠代码识别为主
    return None


def parse_user_query(text: str, stock_name_map: Dict[str, str] = None) -> Dict[str, Any]:
    """解析用户查询，返回结构化信息.

    返回：
    {
        'has_stock': bool,         # 是否识别到股票
        'stock_code': str|None,   # 股票代码
        'intent': str,            # 意图：analyze / screen / chat
        'question': str|None,     # 问题类型
    }
    """

    code = extract_stock_code(text)

    # 判断意图
    text_lower = text.lower()

    intent = 'analyze'  # 默认是分析单只股票

    if any(word in text_lower for word in ['选股', '筛选', '池', '候选']):
        intent = 'screen'
    elif any(word in text_lower for word in ['为什么', '怎么看', '分析', '如何', '能不能买']):
        intent = 'analyze'

    return {
        'has_stock': code is not None,
        'stock_code': code,
        'intent': intent,
        'original_text': text,
    }


def is_ask_analysis(result: Dict[str, Any]) -> bool:
    """判断用户是否要求分析股票."""
    return result['has_stock'] and result['intent'] == 'analyze'
