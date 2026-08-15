"""DEPRECATED：更新全市场股票列表

原行为：写 data/universe/a_stocks_{date}.csv（带日期戳，每日一个新文件）。
问题：写出的文件从未被代码读取，纯粹是数据冗余。实际使用走
  - /api/download/universe 接口（settings.universe_pe_csv）
  - 或 scripts/data_maint/rebuild_industry.py
请直接用上面两个入口，不要再用本脚本。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

print("DEPRECATED: 此脚本已废弃，请改用 /api/download/universe 接口")
print("          或 scripts/data_maint/rebuild_industry.py")
print("本脚本保留仅为历史兼容，请勿再调用。", file=sys.stderr)
sys.exit(1)
