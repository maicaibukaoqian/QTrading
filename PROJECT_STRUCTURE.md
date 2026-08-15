# 项目结构设计文档

## 项目定位：多策略量化选股 + 风险研判 Agent

基于经典投资原理（价值/趋势/动量/分红/小阳形态）+ 大模型研判的 A 股分析系统：
- **多策略量化层**：5 个独立选股策略（价值/双低/高股息/趋势 520/小阳建仓）
- **风险研判层**：7 维独立评分 + 组合风险聚合
- **FastAPI 后端**：单进程服务，REST API 暴露选股/下载/日报/AI 点评能力
- **CLI 薄壳**：本地调试 / cron 入口，业务逻辑复用 service 层

> 注：原计划中的 vnpy 实盘交易未纳入当前阶段。

---

## 整体架构

```
量化交易/
├── main.py                        # CLI 薄壳（仅做参数解析 + 调 service）
├── run_server.py                  # FastAPI 启动入口（强制 workers=1）
├── requirements.txt
│
├── src/
│   ├── api/                       # FastAPI 后端
│   │   ├── app.py                 # create_app() 工厂 + 异常处理 + CORS
│   │   ├── deps.py                # 依赖注入
│   │   ├── errors.py              # AppError 家族
│   │   ├── tasks/                 # 任务系统
│   │   │   ├── store.py           # Task 数据结构 + TaskStore
│   │   │   ├── runner.py          # 单 worker 线程池（保 baostock 串行）
│   │   │   └── progress.py        # ProgressReporter + StdoutTee
│   │   ├── schemas/               # Pydantic 请求/响应模型
│   │   ├── routers/               # FastAPI 路由
│   │   └── services/              # 业务服务层（main.py 业务逻辑全搬这里）
│   │
│   ├── data/                      # 数据层
│   │   ├── session.py             # baostock_session() 上下文管理器
│   │   ├── baostock_api.py        # 第一层数据源
│   │   ├── akshare_api.py         # 第二层
│   │   ├── efinance_api.py        # 第三层兜底
│   │   ├── cache.py               # 缓存 has/load/save
│   │   ├── indicators.py          # 技术指标
│   │   ├── stock_context.py       # 单股实时上下文
│   │   └── chat_store.py          # SQLite 问股会话
│   │
│   ├── strategies/                # 5 个 screener
│   │   ├── base.py
│   │   └── screeners/
│   │       ├── value.py
│   │       ├── double_low.py
│   │       ├── high_dividend.py
│   │       ├── trend_520.py
│   │       └── xiaoyang_build_position.py
│   │
│   ├── agent/                     # 智能体
│   │   ├── ai_commenter.py        # AI 点评（第三方 LLM，OpenAI 兼容）
│   │   ├── analyzer.py            # 单股综合分析调度
│   │   ├── generator.py           # 分析报告生成
│   │   ├── llm_caller.py          # LLM 客户端封装
│   │   └── parser.py
│   │
│   ├── ai_prompts/                # LLM 系统 prompt（通用投研框架）
│   │   └── investment_analyst.py  # 不绑定任何特定投资流派
│   │
│   ├── config/
│   │   └── settings.py            # pydantic-settings
│   │
│   ├── analysis/                  # 财务/技术/筹码/估值分析
│   └── backtest/                  # 回测框架（规划中）
│
├── data/                          # 缓存 + 输出（git ignore）
│   ├── universe/                  # 全市场列表
│   ├── cache/                     # 个股 K 线 + 财务
│   ├── outputs/                   # 选股 CSV
│   └── daily/                     # 日报 markdown
│
├── frontend/                      # 静态前端（量衡录报刊风）
│
├── 当前策略.md                    # 5 个策略说明
├── AI_FINANCE_AGENT_PLAN.md       # 下一阶段（5 天冲刺）计划
├── PROJECT_STRUCTURE.md           # 本文档
└── README.md                      # 项目说明
```

---

## 关键设计

### 后台任务系统（解决阻塞 + 串行）

- **不**用 FastAPI `BackgroundTasks`（无排队、无取消、无进度归属）
- `TaskRunner` 内部 `ThreadPoolExecutor(max_workers=1)`，所有 download/screen/daily 任务严格串行
- `TaskStore` 内存存储 + `RLock`，提供 `create/get/list/update/request_cancel`
- `ProgressReporter` 把进度/日志/步骤写回 `Task`；`StdoutTee` 捕获 screener 内部 print
- 启动必须 `uvicorn --workers 1`（`run_server.py` 硬编码）— baostock 全局登录状态并发不安全

### 服务层（main.py 业务逻辑全部抽出）

- `screen_service` — `STRATEGY_REGISTRY` 唯一参数来源；`run_single` / `run_all` 复用 main.py 逻辑
- `download_service` — 三层兜底 + 限流 sleep 搬过来
- `daily_service` — 日报生成 + AI 点评循环
- `chat_service` — 问股对话（流式 LLM）
- `analyze_service` — 单股综合分析
- `result_service` — 读 CSV + 分页 + 过滤

### 配置层

- `pydantic-settings` + `get_settings()` 单例（`lru_cache`）
- 环境变量前缀 `QUANT_`，也支持 `.env` 文件
- 所有路径字段派生自 `_PROJECT_ROOT = Path(__file__).resolve().parents[2]`
- `@property` 暴露派生路径（`universe_pe_csv` / `industry_csv` / `chat_db_path` / `screen_all_csv`）

### 5 个策略注册表

`src/api/services/screen_service.py:STRATEGY_REGISTRY` 是策略元信息唯一来源：

| key | 中文名 | 类 | 默认输出 | 核心条件 |
|-----|--------|-----|----------|----------|
| `value` | 价值 | `ValueStockScreener` | `value_screen_result.csv` | PE<30 + ROE>10% + 毛利率>20% + 负债<70% |
| `520` | 趋势 520 | `Trend520Screener` | `520_buy.csv` | 基本面合格 + 5日金叉20日 |
| `dividend` | 高股息 | `HighDividendScreener` | `high_dividend.csv` | PE<30 + ROE>8% + 股息率>3% |
| `doublelow` | 双低 | `DoubleLowScreener` | `double_low.csv` | PE<20 + PB<2 + ROE>8% |
| `xiaoyang` | 小阳 | `XiaoyangBuildPositionScreener` | `xiaoyang_build.csv` | 低位连续小阳 + 主力吸筹 |

URL 路径用 `key`（如 `POST /api/screen/520`），前端 option 也用 `value="520"`。

---

## 依赖清单 `requirements.txt`

```
fastapi
uvicorn
pydantic
pydantic-settings
pandas
numpy
baostock
akshare
efinance
requests
```

---

## 当前进度

- ✅ 多策略量化选股系统（5 个 screener + 共振选股 + 全市场数据下载）
- ✅ FastAPI 后端 + 异步任务系统（store/runner/progress）+ 流式 AI 点评
- ✅ 问股对话（多轮历史 + 流式输出 + SQLite 持久化）
- ✅ 路径配置统一（`Settings` 派生，跨 CWD 启动不分裂）
- ✅ 缓存 + 死数据清理（`clear_cache` 清 csv+parquet）
- ⬜ 风险评分模块（Day 1，5 天冲刺）
- ⬜ 财报 PDF 解析（Day 3，5 天冲刺）
- ⬜ 自然语言 Agent（Day 4，5 天冲刺）
- ⬜ 5 策略回测引擎（Day 5，5 天冲刺）

详见 `AI_FINANCE_AGENT_PLAN.md`。
