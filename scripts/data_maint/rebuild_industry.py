"""一次性脚本：重建 universe 缓存（code/name/pe/pb/industry）

策略：
  1. baostock query_stock_industry 一次拉全市场行业（~2s）→ 写 industry_only.csv
  2. baostock 循环拉 K 线 PE/PB，每 200 只重新 login 一次（避免 session 僵死）
  3. 合并 industry

注意：baostock 大批量请求会静默卡死，2026-08 重试多次仍不稳定。
建议改用 /api/download/universe 接口（已实现 settings 路径统一）。
"""
import os
import sys
import time

# 让脚本能 import src
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
import baostock as bs

from src.config.settings import get_settings

settings = get_settings()
CACHE = settings.universe_pe_csv
INDUSTRY_CACHE = settings.industry_csv


def to_float(s):
    s = str(s).strip()
    if not s:
        return float("nan")
    try:
        return float(s)
    except:
        return float("nan")


def fetch_industry():
    rs = bs.query_stock_industry()
    rows = []
    while rs.next():
        rows.append(rs.get_row_data())
    df = pd.DataFrame(rows, columns=rs.fields)
    df["code"] = df["code"].str.split(".").str[1]
    return dict(zip(df["code"], df["industry"]))


def login_fresh():
    try:
        bs.logout()
    except:
        pass
    time.sleep(1)
    lg = bs.login()
    return lg.error_code == "0"


def main():
    from datetime import datetime
    current_year = datetime.now().year

    if not login_fresh():
        print("登录失败")
        return

    # 1. 行业
    print("拉全市场行业...", flush=True)
    ind_map = fetch_industry()
    print(f"行业 {len(ind_map)} 条", flush=True)
    os.makedirs(os.path.dirname(INDUSTRY_CACHE), exist_ok=True)
    pd.DataFrame([{"code": k, "industry": v} for k, v in ind_map.items()]).to_csv(
        INDUSTRY_CACHE, index=False, encoding="utf-8"
    )
    print(f"行业已写入 {INDUSTRY_CACHE}", flush=True)

    # 2. 拉全市场列表
    rs_basic = bs.query_stock_basic(code="")
    rows = []
    while rs_basic.next():
        rows.append(rs_basic.get_row_data())
    basic_df = pd.DataFrame(rows, columns=rs_basic.fields)
    basic_df = basic_df[(basic_df["status"] == "1") & (basic_df["type"] == "1")].reset_index(drop=True)
    print(f"全市场 A 股 {len(basic_df)} 只", flush=True)

    # 3. 单线程循环，每 200 只重新 login
    result = []
    total = len(basic_df)
    REFRESH_EVERY = 200
    stale_count = 0
    for idx, (_, row) in enumerate(basic_df.iterrows()):
        if idx > 0 and idx % REFRESH_EVERY == 0:
            print(f"  重新登录刷新 session @ {idx}", flush=True)
            if not login_fresh():
                print(f"  重新登录失败，继续尝试", flush=True)

        bs_code = row["code"]
        code = bs_code.split(".")[1]
        name = row["code_name"]
        try:
            rs = bs.query_history_k_data_plus(
                bs_code, "date,code,close,pettm,pbMRQ",
                start_date=f"{current_year}-01-01", end_date="",
                frequency="d", adjustflag="3",
            )
            data = []
            while rs.next():
                data.append(rs.get_row_data())
            if not data:
                stale_count += 1
                if stale_count > 50:
                    print(f"  连续 {stale_count} 只无数据，可能 session 卡死，刷新", flush=True)
                    login_fresh()
                    stale_count = 0
                continue
            stale_count = 0
            latest = data[-1]
            d = dict(zip(rs.fields, latest))
            pe = to_float(d.get("pettm", ""))
            pb = to_float(d.get("pbMRQ", ""))
            if pd.isna(pe) and pd.isna(pb):
                continue
            result.append({
                "code": code, "name": name,
                "pe": pe, "pb": pb,
                "industry": ind_map.get(code, ""),
            })
        except Exception as e:
            print(f"  {code} 异常: {e}", flush=True)
            login_fresh()

        if (idx + 1) % 200 == 0:
            print(f"  进度 {idx+1}/{total}，已收 {len(result)} 只", flush=True)
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            pd.DataFrame(result).to_csv(CACHE, index=False, encoding="utf-8")

        time.sleep(0.1)

    try:
        bs.logout()
    except:
        pass

    # 4. 最终写盘
    out_df = pd.DataFrame(result)
    print(f"共 {len(out_df)} 只", flush=True)
    if "industry" in out_df.columns:
        print(f"行业非空：{(out_df['industry'] != '').sum()} 只", flush=True)
    out_df.to_csv(CACHE, index=False, encoding="utf-8")
    print(f"已写入 {CACHE}", flush=True)
    print("600519:", out_df[out_df["code"] == "600519"].to_dict("records"), flush=True)


if __name__ == "__main__":
    main()
