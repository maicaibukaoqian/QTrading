# data_maint — 数据维护脚本

## 一次性脚本（事故恢复用，跑完可删）

- **backfill_pe_pb.py** — 从历史选股 CSV 反向回填 universe cache 的 PE/PB。
  用途：2026-08 universe cache 被覆盖成只有 industry 的兜底版时，用此脚本
  从 `data/outputs/*.csv` 找回 390+ 只股票的 PE/PB。
- **rebuild_industry.py** — 全量重建 universe cache（code/name/pe/pb/industry）。
  警告：baostock 循环请求常静默卡死（2026-08 重试多次仍不稳），
  建议改用 `/api/download/universe` API。

## 已废弃

- **update_universe.py** — 写 `a_stocks_{date}.csv` 但无人读。请改用 API。
