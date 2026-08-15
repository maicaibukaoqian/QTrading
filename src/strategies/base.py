"""策略基类
所有选股/买卖策略继承这个基类，统一接口
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Any, Dict, List, Optional


class BaseScreener(ABC):
    """选股策略基类."""

    name: str = "base"
    description: str = "基类"

    @abstractmethod
    def screen(self, universe: pd.DataFrame) -> pd.DataFrame:
        """执行选股，返回筛选后结果."""
        pass


class BaseStrategy(ABC):
    """交易策略基类（给vnpy用）."""

    name: str = "base"
    description: str = "基类"

    @abstractmethod
    def on_bar(self, bar) -> None:
        """K线更新时调用."""
        pass
