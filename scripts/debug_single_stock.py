#!/usr/bin/env python
"""调试：分析单只股票，输出完整报告"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from src.agent.analyzer import StockAgentAnalyzer


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/debug_single_stock.py 600519")
        sys.exit(1)

    code = sys.argv[1]
    analyzer = StockAgentAnalyzer(
        min_roe=10.0,
        min_gross_margin=20.0,
        max_debt_ratio=70.0,
        check_years=3
    )

    print(f"\n开始分析 {code}...\n")
    report = analyzer.analyze(code)
    print("\n" + "="*70)
    print(report)
    print("="*70 + "\n")

    # 保存到文件
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'outputs')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'{code}_analysis.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"报告已保存到: {out_path}")


if __name__ == '__main__':
    main()
