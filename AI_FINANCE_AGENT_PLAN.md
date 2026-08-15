# 下一步完善计划

> **目标定位**：开源 AI 项目比赛 · 涉及创业方向
> **核心叙事**：「A 股全市场行情 + 财报 + 多策略量化框架」的开源 AI 投研 Agent
> **当前完成度**：64% → **目标 85%**（5 天可达）
> **文档日期**：2026-08-15

---

## 〇、为什么是「开源 + 创业」

比赛分两条线评估，**两条都要让评委看见**：

| 维度 | 怎么演 |
|------|--------|
| **开源价值** | 通用投研框架 + 5 个可复用的策略 + baostock 三层兜底的数据层；**不绑定任何特定投资流派或私人讲义** |
| **创业可行** | 三层付费模式：核心开源 → 托管 SaaS → 策略/技能市场 |

为了让"开源"立得住，**所有 prompt / 框架 / 规则都是基于公开教科书（基础/估值/技术/筹码/风险 5 维）原创**——与脱敏要求一致。

---

## 一、定位回顾

创业比赛/对外宣讲的核心定位是：

> **基于 A 股全市场行情 + 财报数据 + 多策略量化框架的 AI 投研 Agent**

需要在评委/用户面前明确演示 5 项能力：

| 序号 | 能力维度 | 关键问题 | 当前 | 目标 |
|------|----------|----------|------|------|
| 1 | **资料理解** | "能读懂财报/公告/研报吗？" | 40% | 80% |
| 2 | **规则匹配** | "能按我的战法选股吗？" | 85% | 90% |
| 3 | **风险提示** | "能告诉我这只股票安不安全吗？" | 35% | 85% |
| 4 | **投研整理** | "能给我整理一份投研简报吗？" | 75% | 85% |
| 5 | **流程辅助** | "能帮我做决策记录/回测验证吗？" | 50% | 75% |

**差距最大**的是**风险提示**（35% → 85%）和**资料理解**（40% → 80%），这是接下来 5 天的主攻方向。

---

## 二、5 天冲刺安排

> **完成状态**：Day 0 ✅ / Day 1 ✅ / Day 2-5 ⬜

### Day 0 — 开源基础（已完成 ✅）

**目标**：让项目具备「开源可评」的基础——评委/参赛者能 5 分钟内 clone → run → 看见 demo。

**已交付**：
- `LICENSE`（MIT + 免责声明，明示「不构成投资建议」）
- `CONTRIBUTING.md`（贡献流程 + 代码风格 + 策略/风险维度接入规范）
- `.claude/skills/a-share-research/SKILL.md` + 6 个 reference（strategies / risk-scoring / paths-and-cache / llm-and-prompt / pr-checklist / framework / task-and-api）—— Claude Code 加载本项目时自动激活
- `README.md` 已重写为开源向（quickstart + 5 策略表 + 5 维风险图位 + 架构说明）

**验收**：
- [x] GitHub 仓库根有 LICENSE + CONTRIBUTING.md
- [x] `pip install -r requirements.txt && python run_server.py` 5 分钟能跑起来
- [x] Claude Code 加载本项目时自动拿到 A 股投研上下文

---

### Day 1 — 风险评分模块（已完成 ✅）

**目标**：让用户问任何一只股票，都能拿到 1-5 星的量化风险评分 + 分维度解释。

**已交付**：
- `src/agent/risk_scorer.py`（单文件 7 维 + 加权汇总 + 完整 dataclass）
- `GET /api/stock/{code}/risk` 端点
- 前端 行情卡 加风险子卡（星级 + 7 维 mini-bar + 红色警告列表）

**7 个维度**（1=安全，5=高风险）：
1. 估值异常（PE 亏损 / >100）
2. 负债（资产负债率 > 70%）
3. 盈利下滑（近 2 期 ROE 下降 ≥ 3pct）
4. 特别处理（ST / *ST / 退市）
5. 规模（流通市值 < 10亿）
6. 政策（房地产 / 教育 / 互联网平台）
7. 流动性（日均成交额 < 500万）

**验收（已通过）**：
- [x] `curl http://127.0.0.1:8000/api/stock/600519/risk` 返回结构化 JSON
  - 茅台：5 星 低风险，0 warning
  - 万科 A：3 星 中风险，3 warning（PE 亏损 + 负债 83% + 房地产政策）
  - 平安：4 星 中低风险
- [x] 前端 行情卡 可见风险星级 + 7 维 mini-bar + 红色警告

**实现细节**：
- 7 维函数独立、可单测；每个函数 `try/except` 包住，失败按 score=3（未知）
- `_get_market_cap` 用 threading 3s 硬超时，避免 akshare 在线被封时拖死前端
- `_load_universe_row` 直接 `pd.read_csv(universe_pe_csv)`，不走 `bs_api.get_all_stocks`（后者在缓存非当日时会调 baostock 登录卡住）
- ST 维度：name 为空时默认 score=1（假设正常）—— universe CSV 重建后才会补 name，缺失不等于 ST

---

### Day 2 — 风险详情 + 持仓集中度（最关键下一问）

**目标**：把"单股风险"扩展到"组合风险"。

**要做的事**：
- **单股风险详情**：`/api/stock/{code}/risk/detail`，把每个维度的判定逻辑和数据来源展开成 markdown
- **持仓集中度**：`/api/portfolio/risk`
  - 接收 `codes: [600519, 000858, ...]` 参数
  - 算：行业分布 / 单股权重 / 风险评分均值 / 最大单股风险
  - 返回"组合风险评分"（按权重加权平均）

**为什么是 Day 2**：
- Day 1 给了"单只"，Day 2 给"组合"，是**最常见的下一问**
- 投研比赛里"我持有这些股票，整体风险如何"是必答题

**验收标准**：
- 组合 5 只股票调用 `/api/portfolio/risk`，返回行业饼图数据 + 加权风险分
- 前端能看到"组合风险等级"标签

---

### Day 3 — 财报 PDF 解析

**目标**：让用户上传一份财报 PDF，Agent 自动读出关键财务指标 + 给一段结构化摘要。

**要做的事**：
- 新建 `src/agent/pdf_analyzer.py`
- 用 `pypdf` 提取文本 → 按章节（资产负债表/利润表/现金流量表/管理层讨论）切片
- 关键指标抽取（正则 + LLM 兜底）：
  - 营业收入 / 净利润 / 同比
  - 毛利率 / 净利率 / ROE
  - 资产负债率
  - 经营性现金流
- 用 LLM 生成 200 字内的"这家公司本季度怎么样"摘要
- 新增 API：`POST /api/document/analyze`（multipart/form-data）
- 前端：问股页加一个"📎 上传财报"按钮

**为什么是 Day 3**：
- **资料理解**维度（40% → 80%）的核心证据点
- 评委问"你的 Agent 怎么读财报？"时，能直接演示
- 现有 LLM 客户端已经封装好（`src/agent/llm_caller.py`），工作量中等

**验收标准**：
- 上传一份 600519 2024 年报 PDF，返回结构化 JSON + 200 字摘要
- 前端能看到提取的财务指标卡片 + 摘要文本

---

### Day 4 — 自然语言 Agent

**目标**：用户说"帮我找低估值高股息的银行股"，Agent 自动解析 + 调用选股器 + 给出结果。

**要做的事**：
- 新建 `src/agent/nl_query.py`
- LLM 解析用户输入 → 结构化 intent：
  ```json
  {
    "strategy": "high_dividend",  // 或 "value" / "520" / "doublelow" / "xiaoyang"
    "industry": "银行",
    "params": {"pe_max": 10, "dividend_yield_min": 5},
    "explanation": "用户想找 PE<10、股息率>5% 的银行股"
  }
  ```
- 调用现有 5 个 screener 跑 + 过滤
- 返回 markdown 表格 + LLM 生成的"为什么这几只符合"短说明
- 新增 API：`POST /api/agent/query`，body: `{"text": "..."}`
- 前端：问股页支持纯文字提问（不需要先选股票）

**为什么是 Day 4**：
- 现有 chat 已经能做"指定股票 + 自由问答"，但**不能跨股票推理**
- 这一步让用户感觉"真的在和 Agent 对话"，**体感差异最大**
- 流程辅助维度（50% → 70%）

**验收标准**：
- 输入"低估值高分红的银行股"，返回 screener 命中的列表 + 文字说明
- 文字提问的"提问 → 回答"链路通畅

---

### Day 5 — 5 策略回测引擎

**目标**：每个选股策略都能在历史数据上回测，看到胜率/年化收益/最大回撤。

**要做的事**：
- 新建 `src/backtest/engine.py`
- 数据：2020-2024 年的 K 线 + 财报（如果缓存不全，按需补拉）
- 策略：复用 `src/strategies/screeners/` 5 个 screener
- 调仓逻辑：每月初按 screener 选股，等权持有下月第一个交易日卖出
- 指标计算：
  - 年化收益 / 最大回撤 / 夏普比率
  - 胜率（按月调仓计）
  - vs 沪深 300 超额收益
- 输出：每个策略一条曲线 + 一张结果表
- 新增 API：`POST /api/backtest/run`，body: `{"strategy": "value", "start": "2020-01-01", "end": "2024-12-31"}`
- 前端：单策略结果页加一个"📈 回测"标签

**为什么是 Day 5**：
- 验证策略有效性的**唯一可量化方式**（评委必问"你的策略到底能不能赚钱？"）
- 流程辅助维度（70% → 75%）+ 规则匹配维度（85% → 90%）
- 即使回测结果一般，**有数据**比"看起来不错"强 10 倍

**验收标准**：
- `POST /api/backtest/run` 跑 5 个策略，每个返回 `{annual_return, max_drawdown, sharpe, vs_csi300}`
- 前端能看到回测结果表格

---

## 三、评分预期变化

| 维度 | 8/15 当前 | Day0+1 后 | Day3 后 | Day5 后 | Day4+Skill 后 |
|------|----------|---------|---------|---------|--------------|
| 资料理解 | 40% | 40% | 80% | 80% | 85% |
| 规则匹配 | 85% | 85% | 85% | 90% | 92% |
| 风险提示 | 35% | **80%** ✅ | 80% | 85% | 85% |
| 投研整理 | 75% | 75% | 75% | 80% | 85% |
| 流程辅助 | 50% | 50% | 55% | 75% | 80% |
| **加权总评** | **64%** | **70%** | **77%** | **83%** | **85%** |

**当前进度**：Day 0 + Day 1 已交付，**加权总评 70%**。下一冲刺 Day 2（组合风险）。

---

## 四、5 天实施顺序

| 天 | 模块 | 状态 | 代码文件 | API | 前端改动 |
|----|------|------|----------|-----|----------|
| 0 | 开源基础 | ✅ | `LICENSE` / `CONTRIBUTING.md` / `.claude/skills/a-share-research/*` / `README.md` | — | — |
| 1 | 风险评分 | ✅ | `src/agent/risk_scorer.py` | `GET /api/stock/{code}/risk` | 行情卡加风险卡片 |
| 2 | 风险详情 + 持仓 | ⬜ | 同上扩展 + `src/agent/portfolio_risk.py` | `GET /api/portfolio/risk` | 组合页骨架 |
| 3 | 财报 PDF | ⬜ | `src/agent/pdf_analyzer.py` | `POST /api/document/analyze` | 问股页加上传按钮 |
| 4 | NL Agent | ⬜ | `src/agent/nl_query.py` | `POST /api/agent/query` | 问股页支持自由文字 |
| 5 | 回测引擎 | ⬜ | `src/backtest/engine.py` | `POST /api/backtest/run` | 单策略页加回测标签 |

**注意**：
- Day 0 完成基础开源可评性（5min quickstart）
- Day 1 必须先做（其他天的前置）
- Day 2 依赖 Day 1 的单股 risk API
- Day 3/4/5 互相独立，可调换顺序

---

## 五、关键文件清单

**Day 0（已交付 ✅）**：
- `LICENSE`（MIT + 免责声明）
- `CONTRIBUTING.md`
- `.claude/skills/a-share-research/SKILL.md`
- `.claude/skills/a-share-research/references/strategies.md`
- `.claude/skills/a-share-research/references/risk-scoring.md`
- `.claude/skills/a-share-research/references/paths-and-cache.md`
- `.claude/skills/a-share-research/references/llm-and-prompt.md`
- `.claude/skills/a-share-research/references/pr-checklist.md`
- `.claude/skills/a-share-research/references/framework.md`
- `.claude/skills/a-share-research/references/task-and-api.md`

**Day 1（已交付 ✅）**：
- `src/agent/risk_scorer.py`（单文件 7 维评分）
- `src/api/routers/stock.py`（加 `/risk` 端点）
- `frontend/css/chat.css`（加风险卡样式）
- `frontend/js/chat.js`（行情卡加风险渲染）

**Day 2-5 计划新增**：
- `src/agent/portfolio_risk.py`（Day 2）
- `src/agent/pdf_analyzer.py`（Day 3）
- `src/agent/nl_query.py`（Day 4）
- `src/agent/skills/`（Day 4 子任务：动态 Skill 加载）
- `src/backtest/engine.py`（Day 5）

**修改**：
- `src/api/app.py`：注册新 router
- `src/api/routers/chat.py`：加 `/agent/query` 端点
- `src/api/schemas/*.py`：补请求/响应模型
- `frontend/`：Day 2-5 每处 < 50 行

**不动**：
- 数据层（`src/data/*`）已有 PE/PB/ROE/debt_ratio/industry 全套
- 5 个 screener（`src/strategies/screeners/*`）已稳定
- LLM 客户端（`src/agent/llm_caller.py`）已封装好
- 配置（`src/config/settings.py`）已统一

---

## 六、动态 Skill 加载架构（Day 4 子任务 / 横向能力）

### 现状盘点

| 场景 | 是否有动态 skill 机制 | 备注 |
|------|---------------------|------|
| **Claude Code（你跟我对话）** | 有，但内容是空的 | `.claude/skills/` 目录机制存在；刚才把旧 skill 搬走后，**目录里目前没内容** |
| **API 内部 LLM（chat / AI 点评）** | **没有** | 所有 LLM 调用都用单一静态 system prompt，没有"按需加载"概念 |

**所以严格说，"动态 Skill 加载"这个能力今天是 0**。

### 架构设计

```
用户提问
    ↓
意图分类器（关键词 / 小模型 / LLM 自判）
    ↓
命中 → Skill Registry 查表
    ↓
加载 Skill（system prompt 增量 + 少量 few-shot examples）
    ↓
基础 system prompt + Skill 内容 拼接
    ↓
发给 LLM
```

### 候选 Skill 列表（6 个起步）

| Skill key | 触发关键词 | 内容方向 |
|-----------|-----------|----------|
| `stock_screening` | "低估值""高股息""金叉""小阳""选股" | 5 个策略的算法 + 选股参数含义 |
| `risk_assessment` | "风险""能不能买""安不安全" | 7 维评分规则 + 风险等级 |
| `fundamental` | "ROE""毛利率""负债率""现金流""财报" | 财务三件套解读 + 数据驱动框架 |
| `technical` | "K 线""均线""MACD""金叉死叉""形态" | 经典技术指标定义 + 形态识别 |
| `macro_industry` | "大盘""板块""政策""加息""行业" | 通用宏观框架（不绑特定观点） |
| `trading_discipline` | "仓位""止损""止盈""做 T" | 通用资金管理原则 |

每条 Skill 都是**项目原创的通用内容**，不引用任何外部资料。

### 加载策略三个层级

| 层级 | 复杂度 | 做法 | 价值 |
|------|--------|------|------|
| **L1 静态兜底** | 最简 | 单一 system prompt，不变 | **我们今天的位置** |
| **L2 关键词路由** | 中等 | 维护 `keyword → skill_id` 字典，命中就 append | 性价比最高，1-2 小时能搭完 |
| **L3 LLM 自判** | 最强 | 让 LLM 先"分类"用户问题（返回 1~N 个 skill name），再加载 | 最灵活但需要二次 LLM 调用 |

**Day 4 实施 L1 → L2**，L3 留作后续优化。

### Day 4 子任务拆分

| 时段 | 任务 | 产出 |
|------|------|------|
| Day 4 上午 | 写 `src/agent/skills/base.py` + `registry.py` + 3 个 skill（stock_screening / risk_assessment / fundamental） | Skill 框架跑通 |
| Day 4 下午 | 写 `src/agent/skills/loader.py`（L2 关键词路由）+ 集成到 `chat_service` | 现有 chat 切换为动态 prompt |
| Day 4 晚上 | 补 3 个 skill（technical / macro_industry / trading_discipline）+ 端到端测试 | 6 个 skill 全部可用 |

### 关键文件

```
src/agent/skills/
├── __init__.py
├── base.py                  # Skill 基类（name/triggers/system_prompt）
├── registry.py              # SkillRegistry：按 name 取 skill
├── loader.py                # 动态加载器：user query → 命中 skills
└── definitions/
    ├── stock_screening.py
    ├── risk_assessment.py
    ├── fundamental.py
    ├── technical.py
    ├── macro_industry.py
    └── trading_discipline.py
```

### 验收标准

- `curl -X POST /api/agent/query -d '{"text":"600519 现在能买吗"}'` → 命中 `risk_assessment` skill，prompt 含"7 维评分"提示
- `curl -X POST /api/agent/query -d '{"text":"低估值银行股有哪些"}'` → 命中 `stock_screening` skill，调出 value 选股器
- `curl -X POST /api/agent/query -d '{"text":"大盘怎么看"}'` → 命中 `macro_industry` skill，给出宏观分析

### 与 Claude Code 的关系

`.claude/skills/` 目录机制是 Claude Code 原生的（不是我们搭的）。**为了让我跟你对话时也有 A 股上下文**，需要把上面 6 个 Skill 的内容**也写到本地 skill 目录**（建议名 `a-share-research`），这样我加载你项目时自动激活。

这一份**用同一个 SkillRegistry 在启动时同步生成**——避免两处维护。

---

## 七、5 天之后的备选

如果 5 天做完还有余力，按价值/工作量比排序：

| 模块 | 价值 | 工作量 | 说明 |
|------|------|--------|------|
| 持仓导入（券商对账单 CSV） | 高 | 1 天 | 真实场景闭环 |
| 风险监控（每日扫描持仓） | 中 | 1 天 | 持续运营能力 |
| 板块轮动策略 | 中 | 2 天 | 增强差异化 |
| 微信小程序前端 | 中 | 3 天 | 触达更多用户 |
| 多 LLM 模型切换 | 低 | 0.5 天 | 锦上添花 |

---

## 八、风险与依赖

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| pypdf 解析财务报表格式不统一 | 中 | Day 3 延期 | 退化为 LLM 直接读 PDF 全文（精度降但能用） |
| 回测历史数据不全 | 高 | Day 5 延期 | 用现有 2024-2025 数据先跑通骨架，逐年补拉 |
| NL Agent LLM 解析不稳定 | 中 | Day 4 精度低 | 加 schema 校验 + 重试机制 |
| 比赛时间提前 | 低 | 全计划压缩 | 砍 Day 5（最重），保留 Day 1-3 |

---

**下一步行动**：从 Day 1 开始，先搭风险评分骨架，1-2 小时可出第一版可调用的 API。
