"""分批拉 PE/PB，每批 logout 重连 + 强制 10s 超时

策略：
- 每次拿 50 只一批
- 批开始时 login，结束 logout
- 单只超时 10s（用 threading.Thread 强制 join timeout）
- 每 10 只写一次盘
- 输出进度到 stdout
- 30 分钟硬上限
"""
import os
import sys
import time
import threading
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import pandas as pd
import baostock as bs
from src.config.settings import get_settings

settings = get_settings()
CACHE = settings.universe_pe_csv
SINGLE_TIMEOUT_SEC = 10
HARD_DEADLINE = 1800  # 30 分钟

# 禁用代理
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ[k] = ""


def login():
    try:
        bs.logout()
    except Exception:
        pass
    time.sleep(0.5)
    lg = bs.login()
    return lg.error_code == "0"


def to_float(s):
    s = str(s).strip()
    if not s:
        return float("nan")
    try:
        return float(s)
    except Exception:
        return float("nan")


def fix_code(code: str) -> str:
    code = str(code).zfill(6)
    if code.startswith("6") or code.startswith("5"):
        return f"sh.{code}"
    return f"sz.{code}"


def fetch_one_with_timeout(bs_code: str, current_year: int, timeout: int):
    """单只股票 PE/PB，daemon thread + join timeout

    注意：baostock 是 C 层阻塞，daemon 超时后线程仍在跑，
    但下次 logout() 会让该 session 的后续调用快速失败。
    """
    result = {"ok": False}

    def target():
        try:
            fields = "date,code,close,pettm,pbMRQ"
            rs = bs.query_history_k_data_plus(
                bs_code, fields, start_date=f"{current_year}-01-01", end_date="",
                frequency="d", adjustflag="3",
            )
            data = []
            while rs.next():
                data.append(rs.get_row_data())
            if data:
                latest = data[-1]
                d = dict(zip(rs.fields, latest))
                result["pe"] = to_float(d.get("pettm", ""))
                result["pb"] = to_float(d.get("pbMRQ", ""))
                result["ok"] = True
        except Exception as e:
            result["err"] = str(e)[:80]

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    return result if t.is_alive() is False else None  # None = 超时


def main():
    from datetime import datetime
    current_year = datetime.now().year

    df = pd.read_csv(CACHE, dtype={"code": str})
    print(f"[init] universe {len(df)} 只", flush=True)
    na_mask = df["pe"].isna() | df["pb"].isna()
    todo = df[na_mask].copy()
    print(f"[init] 待补 PE/PB: {len(todo)} 只", flush=True)

    if len(todo) == 0:
        print("[done] 全部有数据", flush=True)
        return

    total = len(todo)
    filled = 0
    failed = 0
    timeout_cnt = 0
    start = time.time()

    if not login():
        print("[fatal] login 失败", flush=True)
        return

    for idx, (_, row) in enumerate(todo.iterrows()):
        if time.time() - start > HARD_DEADLINE:
            print(f"[timeout] 硬上限 {HARD_DEADLINE}s 到达，停止", flush=True)
            break

        code = str(row["code"]).zfill(6)
        bs_code = fix_code(code)

        result = fetch_one_with_timeout(bs_code, current_year, SINGLE_TIMEOUT_SEC)
        if result is None:
            timeout_cnt += 1
            failed += 1
            if timeout_cnt <= 3 or timeout_cnt % 20 == 0:
                print(f"[{idx+1}/{total}] {code} 超时", flush=True)
            # 每 5 次超时 logout 重连
            if timeout_cnt % 5 == 0:
                login()
            time.sleep(0.2)
            continue

        if not result.get("ok"):
            failed += 1
        else:
            pe = result.get("pe")
            pb = result.get("pb")
            mask = df["code"].astype(str).str.zfill(6) == code
            if mask.any():
                if not pd.isna(pe):
                    df.loc[mask, "pe"] = pe
                if not pd.isna(pb):
                    df.loc[mask, "pb"] = pb
            filled += 1

        if (idx + 1) % 10 == 0:
            df.to_csv(CACHE, index=False, encoding="utf-8")
            elapsed = time.time() - start
            speed = (idx + 1) / elapsed if elapsed > 0 else 0
            remain = (total - idx - 1) / speed if speed > 0 else 0
            print(
                f"[{idx+1}/{total}] filled={filled} fail={failed} "
                f"speed={speed:.2f}/s elapsed={elapsed:.0f}s remain={remain:.0f}s",
                flush=True,
            )

        time.sleep(0.05)

    df.to_csv(CACHE, index=False, encoding="utf-8")
    try:
        bs.logout()
    except Exception:
        pass

    elapsed = time.time() - start
    print(f"\n[done] filled={filled} fail={failed} elapsed={elapsed:.0f}s", flush=True)
    pe_ok = df["pe"].notna().sum()
    pb_ok = df["pb"].notna().sum()
    print(f"[final] pe 非空: {pe_ok}/{len(df)} ({pe_ok*100/len(df):.1f}%)", flush=True)
    print(f"[final] pb 非空: {pb_ok}/{len(df)} ({pb_ok*100/len(df):.1f}%)", flush=True)


if __name__ == "__main__":
    main()
