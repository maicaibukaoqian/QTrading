"""从历史选股 CSV 找回 PE/PB 数据，回填到 universe cache。

背景：之前我把 universe cache 覆盖成只有 industry 的兜底版，
把原 universe cache 的 PE/PB 数据丢了。这些 PE/PB 还在
data/outputs/ 里的历史选股 CSV 中（value/double_low/screen_all 等），
因为那些 CSV 是从完整 universe cache 生成的。

一次性脚本：跑完后即可删除。
"""
import os
import sys

# 让脚本能 import src（从项目根或 scripts/data_maint/ 跑都行）
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
from src.config.settings import get_settings

settings = get_settings()
universe_csv = settings.universe_pe_csv
outputs_dir = settings.output_dir

u = pd.read_csv(universe_csv, dtype={'code': str})
print(f'回填前 空 PE: {u["pe"].isna().sum()}, 空 PB: {u["pb"].isna().sum()}')

for f in os.listdir(outputs_dir):
    if not f.endswith('.csv'):
        continue
    path = os.path.join(outputs_dir, f)
    try:
        df = pd.read_csv(path, dtype={'code': str})
    except Exception as e:
        print(f'  skip {f}: {e}')
        continue
    if 'pe' not in df.columns or 'pb' not in df.columns:
        continue
    filled = 0
    for _, row in df.iterrows():
        code = str(row['code']).zfill(6)
        pe, pb = row.get('pe'), row.get('pb')
        mask = u['code'] == code
        if not mask.any():
            continue
        if pd.notna(pe) and pd.isna(u.loc[mask, 'pe'].iloc[0]):
            u.loc[mask, 'pe'] = pe
            filled += 1
        if pd.notna(pb) and pd.isna(u.loc[mask, 'pb'].iloc[0]):
            u.loc[mask, 'pb'] = pb
    print(f'  {f}: filled {filled}')

u.to_csv(universe_csv, index=False, encoding='utf-8')
print()
print(f'回填后 pe 非空: {u["pe"].notna().sum()}, pb 非空: {u["pb"].notna().sum()}')
print('601717:', u[u['code'] == '601717'].to_dict('records'))
print('600519:', u[u['code'] == '600519'].to_dict('records'))
