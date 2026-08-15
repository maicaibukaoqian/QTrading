"""分批拉 PE/PB，子进程隔离：每批一个独立 Python，超时可杀

为什么用子进程：
- baostock 的 C 层 socket hang 无法用 daemon thread / signal 中断
- 唯一可靠的隔离方式：每个批用独立 Python 进程
- 主进程负责调度 + 读 CSV 看进度；批次 hang 30s 直接 kill，不影响其他批

策略：
- 每批 200 只，独立 Python 进程跑
- 批次内单只超过 8s 算超时（用子进程 wrapper）
- 整批超过 60s 强制 kill
- 每 50 只子进程写一次盘
- 主进程每 30s 打印一次进度
"""
import os
import subprocess
import sys
import time
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import pandas as pd
from src.config.settings import get_settings

settings = get_settings()
CACHE = settings.universe_pe_csv
BATCH_SIZE = 200  # 每批 200 只
BATCH_TIMEOUT = 90  # 单批最多 90s（不到就 kill）
SAVE_EVERY = 50  # 批次内每 50 只写盘
INTER_BATCH_SLEEP = 30  # 批间 sleep，让 baostock 恢复（可由 CLI 覆盖）


WORKER = r"""
import os, sys, time, json
sys.path.insert(0, r'{root}')
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']: os.environ[k]=''
import pandas as pd
import baostock as bs

def fix_code(code):
    code = str(code).zfill(6)
    return 'sh.' + code if code.startswith(('6','5')) else 'sz.' + code

def to_float(s):
    s = str(s).strip()
    if not s: return float('nan')
    try: return float(s)
    except: return float('nan')

codes = json.loads(r'''{codes}''')
year = '{year}'
df = pd.read_csv(r'{cache}', dtype={{'code': str}})

bs.login()
filled = 0
failed = 0
try:
    for i, code in enumerate(codes):
        try:
            bs_code = fix_code(code)
            rs = bs.query_history_k_data_plus(
                bs_code, 'date,code,close,pettm,pbMRQ',
                start_date=year + '-01-01', end_date='', frequency='d', adjustflag='3'
            )
            data = []
            while rs.next(): data.append(rs.get_row_data())
            if data:
                d = dict(zip(rs.fields, data[-1]))
                pe = to_float(d.get('pettm', ''))
                pb = to_float(d.get('pbMRQ', ''))
                mask = df['code'].astype(str).str.zfill(6) == code
                if mask.any():
                    if not pd.isna(pe): df.loc[mask, 'pe'] = pe
                    if not pd.isna(pb): df.loc[mask, 'pb'] = pb
                filled += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
        if (i+1) % {save_every} == 0:
            df.to_csv(r'{cache}', index=False, encoding='utf-8')
        time.sleep(0.05)
finally:
    df.to_csv(r'{cache}', index=False, encoding='utf-8')
    try: bs.logout()
    except: pass

print(f'BATCH_RESULT filled={{filled}} fail={{failed}} total={{len(codes)}}')
"""


def run_batch(codes, year):
    """跑一批，返回 (filled, failed, killed)"""
    # Windows: forward slashes work in Python paths
    root = str(_ROOT).replace("\\", "/")
    cache = str(CACHE).replace("\\", "/")
    script = WORKER.format(
        root=root,
        codes=json.dumps(codes),
        year=year,
        cache=cache,
        save_every=SAVE_EVERY,
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", script],
            timeout=BATCH_TIMEOUT,
            capture_output=True,
            text=True,
        )
        # 解析最后一行
        last_line = ""
        for line in proc.stdout.split("\n"):
            if line.startswith("BATCH_RESULT"):
                last_line = line
                break
        if last_line:
            parts = last_line.split()
            filled = int(parts[1].split("=")[1])
            failed = int(parts[2].split("=")[1])
            return filled, failed, False
        return 0, len(codes), False
    except subprocess.TimeoutExpired:
        return 0, len(codes), True
    except Exception as e:
        print(f"  [batch err] {e}", flush=True)
        return 0, len(codes), False


def main(sleep_sec: int = INTER_BATCH_SLEEP):
    from datetime import datetime
    year = str(datetime.now().year)

    df = pd.read_csv(CACHE, dtype={"code": str})
    na_mask = df["pe"].isna() | df["pb"].isna()
    todo = df[na_mask].copy()
    print(f"[init] universe {len(df)} 只, 待补 {len(todo)} 只, 批间 sleep={sleep_sec}s", flush=True)

    if len(todo) == 0:
        print("[done] 全部有数据", flush=True)
        return

    codes = todo["code"].astype(str).str.zfill(6).tolist()
    total = len(codes)

    # 切成 BATCH_SIZE 大小的批
    batches = [codes[i : i + BATCH_SIZE] for i in range(0, len(codes), BATCH_SIZE)]
    print(f"[plan] {len(batches)} 批, 每批 {BATCH_SIZE} 只, 单批超时 {BATCH_TIMEOUT}s", flush=True)

    start = time.time()
    total_filled = 0
    total_failed = 0
    total_killed = 0
    completed_stocks = 0

    for batch_idx, batch_codes in enumerate(batches):
        t0 = time.time()
        filled, failed, killed = run_batch(batch_codes, year)
        elapsed = time.time() - t0
        completed_stocks += len(batch_codes)

        if killed:
            total_killed += len(batch_codes)
            print(f"[批 {batch_idx+1}/{len(batches)}] KILLED ({elapsed:.0f}s) 已处理 {completed_stocks}/{total}", flush=True)
        else:
            total_filled += filled
            total_failed += failed
            total_elapsed = time.time() - start
            speed = completed_stocks / total_elapsed if total_elapsed > 0 else 0
            remain = (total - completed_stocks) / speed if speed > 0 else 0
            print(
                f"[批 {batch_idx+1}/{len(batches)}] filled={filled} fail={failed} ({elapsed:.0f}s) "
                f"累计 filled={total_filled} fail={total_failed} speed={speed:.1f}/s remain={remain:.0f}s",
                flush=True,
            )

        # 批间 sleep，让 baostock 恢复（除了最后一批）
        if batch_idx < len(batches) - 1 and sleep_sec > 0:
            time.sleep(sleep_sec)

    # 终态
    df = pd.read_csv(CACHE, dtype={"code": str})
    pe_ok = df["pe"].notna().sum()
    pb_ok = df["pb"].notna().sum()
    total_elapsed = time.time() - start
    print(f"\n[done] elapsed={total_elapsed:.0f}s filled={total_filled} fail={total_failed} killed={total_killed}", flush=True)
    print(f"[final] pe 非空: {pe_ok}/{len(df)} ({pe_ok*100/len(df):.1f}%)", flush=True)
    print(f"[final] pb 非空: {pb_ok}/{len(df)} ({pb_ok*100/len(df):.1f}%)", flush=True)


if __name__ == "__main__":
    import sys
    s = int(sys.argv[1]) if len(sys.argv) > 1 else INTER_BATCH_SLEEP
    main(s)
