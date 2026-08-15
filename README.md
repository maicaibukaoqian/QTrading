<div align="center">

# 📈 量衡录 · A 股量化选股与风险研判系统

**多策略量化筛选 × 大模型研判** —— 从「多网站手动汇总」到「可复现的本地工作台」

<img src="https://img.shields.io/badge/License-MIT-3A6B35" alt="License: MIT"/>
<img src="https://img.shields.io/badge/Python-3.10%2B-3A6B35" alt="Python 3.10+"/>
<img src="https://img.shields.io/badge/A%20%E8%82%A1-5400%2B-3A6B35" alt="5400+ A股"/>
<img src="https://img.shields.io/badge/Strategy-5%20%E7%AD%96%E7%95%A5-3A6B35" alt="5 策略共振"/>
<img src="https://img.shields.io/badge/Risk-7%20%E7%BB%B4%E8%AF%84%E5%88%86-3A6B35" alt="7 维风险评分"/>

开源 · 免费 · 可商用 · 数据本地化

</div>

---

一个面向 **A 股个人投资者**的多策略选股与风险研判工具集：五个独立策略共振筛选、七维风险评分、自然语言问股、每日选股日报，支持 **FastAPI 后端 + CLI** 两种使用方式。数据全部本地化，代码以 **MIT** 协议开源。

---

## ✨ 核心特性

| 能力 | 说明 |
| :--- | :--- |
| 🎯 **五策略共振选股** | 价值 · 双低 · 高股息 · 趋势520 · 小阳建仓，按「命中策略数」排序，天然过滤信号噪声 |
| 🛡️ **七维风险评分** | 1–5 星独立评分，可下钻到每条触发规则，非黑箱分数 |
| 💬 **自然语言问股** | 以真实数据为事实基础，回答逐条可溯源，支持 GPT / DeepSeek / 智谱 / 通义千问 |
| 📰 **每日选股日报** | 每天推送命中 3+ 策略与需警惕标的，Markdown 存档可比对 |
| 🔁 **三层数据兜底** | baostock → AkShare → efinance，任一源限流/缺字段自动降级，命中率 &gt;99% |

---

## 📦 环境与快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 一键下载全市场数据（首次必须，约 1 小时）
python main.py download all

# 3. 全策略共振选股
python main.py screen all
```

---

## 🚀 使用方式

<details>
<summary><b>方式 A：FastAPI 后端（推荐，支持 Web / 远程调用）</b></summary>

```bash
python run_server.py
# 访问 http://127.0.0.1:8000/docs 查看 OpenAPI 文档
```

**主要接口**

| 方法 | 路径 | 说明 |
| :--- | :--- | :--- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/screen/strategies` | 查看 5 个策略默认参数 |
| POST | `/api/screen/all` | 全策略共振选股（异步） |
| GET | `/api/screen/results?file=screen_all` | 读最近选股结果 |
| POST | `/api/screen/{strategy}` | 单策略选股（异步） |
| POST | `/api/download/all` | 一键下载数据（异步） |
| POST | `/api/download/from-result` | 按选股结果下 K 线 |
| POST | `/api/daily/report` | 生成日报（可选 AI 点评） |
| GET | `/api/tasks/{id}` | 查任务进度 |
| POST | `/api/analyze` | 单股综合分析（同步、秒级） |

> ⚠️ **重要约束**：服务必须以 `workers=1` 启动（baostock 全局登录状态并发不安全），`run_server.py` 已硬编码。

可选：在项目根目录创建 `.env` 配置 AI 点评（不配则跳过 AI）：

```
QUANT_AI_API_KEY=sk-xxxx
QUANT_AI_API_BASE=https://api.openai.com/v1
QUANT_AI_MODEL_NAME=gpt-3.5-turbo
```

</details>

<details>
<summary><b>方式 B：CLI（本地调试 / cron）</b></summary>

```bash
# 一键下载全市场数据
python main.py download all

# 全策略共振选股
python main.py screen all

# 单策略选股
python main.py screen value
python main.py screen 520
python main.py screen dividend
python main.py screen doublelow
python main.py screen xiaoyang

# 单股综合分析
python main.py analyze 600519

# 生成今日日报（AI 点评需要 API Key）
python main.py daily report
python main.py daily report --no-ai
```

> CLI 内部走的是同一套 service 层（`src/api/services/`），不会和 API 走两套逻辑。

</details>

---

## 🎯 已实现的 5 个策略

详见 [`当前策略.md`](./当前策略.md)。

| 策略 | 核心条件 |
| :--- | :--- |
| 价值选股 | PE&lt;30 + 连续ROE&gt;10% + 毛利率&gt;20% + 负债率&lt;70% |
| 双低选股 | PE&lt;20 + PB&lt;2 + ROE&gt;8%（格雷厄姆烟蒂股） |
| 高股息红利 | PE&lt;30 + ROE&gt;8% + 股息率&gt;3% |
| 趋势 520 | 基本面合格 + 5 日线金叉 20 日线（均线趋势策略） |
| 小阳建仓 | 低位连续小阳线（主力吸筹信号） |

> **全策略共振**：被越多策略同时选中 → 优先级越高，输出按「命中策略数降序 + PE 升序」排。

---

## 🧱 项目结构

```
量化交易/
├── main.py                      # CLI 薄壳（业务逻辑已搬到 service 层）
├── run_server.py                # FastAPI 启动入口（workers=1）
├── requirements.txt
├── src/
│   ├── api/                     # FastAPI 后端
│   │   ├── app.py               # create_app() 工厂
│   │   ├── deps.py              # 依赖注入
│   │   ├── errors.py            # AppError 家族
│   │   ├── tasks/               # 任务系统（store/runner/progress）
│   │   ├── schemas/             # Pydantic 模型
│   │   ├── routers/             # FastAPI 路由
│   │   └── services/            # 业务服务层（main.py 业务逻辑全在这里）
│   ├── data/                    # 数据层（三层兜底 + 缓存 + session 管理）
│   ├── strategies/              # 5 个 screener
│   ├── agent/                   # 分析器 + AI 点评
│   ├── ai_prompts/              # LLM 系统 prompt（通用投研框架）
│   └── config/settings.py       # pydantic-settings
├── data/                        # 缓存 + 输出（git ignore）
├── frontend/                    # 静态前端（量衡录报刊风）
├── 当前策略.md                  # 5 个策略说明
├── AI_FINANCE_AGENT_PLAN.md     # 下一阶段（5 天冲刺）计划
└── PROJECT_STRUCTURE.md         # 架构说明
```

---

## 🗂️ 数据目录（自动生成，不入库）

`data/` 由程序在运行时自动创建和填充，**不随仓库提交**。首次使用前先跑一次 `python main.py download all` 生成全市场快照：

```
data/
├── universe/            # 全市场快照（自动下载）
│   ├── all_stocks_pe.csv   # 全部 A 股 PE/PB/市值/行业 快照
│   └── industry_only.csv   # 行业映射表
├── cache/               # 单股 K 线与财报缓存（按需，可清空重建）
│   ├── {code}_kline.csv
│   └── {code}_finance.csv
├── outputs/             # 选股结果（screen_all.csv 及各策略 *_screen_result.csv）
├── daily/               # 每日选股日报（Markdown）
└── chat.db              # 问股会话存储（SQLite）
```

- 所有路径均基于 `src/config/settings.py` 的 `project_root` 绝对化，**从任意工作目录启动**都能正确读写此目录。
- 缓存可随时清除重建：`python scripts/clear_cache.py`。
- 数据源采用 baostock → AkShare → efinance 三层兜底，任一源限流或字段缺失自动降级。

---

## ⚠️ 注意事项

1. **数据来源**：选股使用 baostock → AkShare → efinance 三层兜底。baostock 经常封 IP，所以用三层兜底 + 增量缓存降低被封概率。
2. **IP 限流**：财务数据下载是 5000+ 次请求，全市场约 1 小时，已加随机 sleep 0.5–1.3s。
3. **AI 点评**：可选。`ai_commenter.py` 调用第三方 LLM（OpenAI 兼容），配置 Key 才启用，不配则静默跳过。
4. **并发安全**：服务必须 `workers=1`。TaskRunner 内部 `ThreadPoolExecutor(max_workers=1)`，所有 download/screen/daily 任务严格串行。
5. **投资建议**：本项目仅用于学习交流，不构成投资建议，市场有风险，投资需谨慎。

---

<div align="center">

**MIT License** · 第三方依赖、数据源、AI 提示词原创性等知识产权边界见 [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md)

📄 [`LICENSE`](./LICENSE) &nbsp;·&nbsp; 🤝 [`CONTRIBUTING.md`](./CONTRIBUTING.md) &nbsp;·&nbsp; 🧭 [`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md) &nbsp;·&nbsp; 🗺️ [`AI_FINANCE_AGENT_PLAN.md`](./AI_FINANCE_AGENT_PLAN.md)

*本项目仅供学习研究，不构成任何投资建议 · 市场有风险，决策须自担*

</div>