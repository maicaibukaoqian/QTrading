# A股量化交易系统 (基于 vnpy + 经典投资原理认知框架)

整体结构:

```
量化交易/
├── .claude/
│   └── skills/
│       └── a-share-trading-mentor/    ← 你的 经典投资原理认知框架 Skill (自动触发)
├── vnpy/                               ← VeighNa(vnpy) 框架源码 (你 clone 来的)
├── project/                            ← 我们的项目 (自己的代码在这里)
│   ├── __init__.py
│   ├── config.py                       ← 全局配置:路径/风控
│   ├── data/                           ← 数据缓存
│   ├── strategies/                     ← 策略实现
│   │   ├── __init__.py
│   │   └── roe_ma_strategy.py          ← 示例:ROE选股+5/20均线策略
│   ├── backtests/                      ← 回测结果输出
│   └── research/                       ← Jupyter 投研笔记
├── stock_screener/                     ← Phase 1:选股漏斗 (排雷+财务门槛)
│   ├── __init__.py
│   ├── config.py                       ← 选股阈值:ROE≥15% 连续3年 等等
│   ├── data_source.py                  ← AkShare 数据源封装
│   ├── screener.py                     ← 两层筛选逻辑
│   ├── output/                         ← 选股结果CSV输出
│   └── run.py                          ← 运行入口
├── webapp/                             ← Web前端:选股结果展示 ✨ 新增
│   ├── app.py                          ← Flask 后端
│   ├── templates/index.html            ← Bootstrap 网页
│   └── static/css/style.css            ← 样式
├── install_deps.bat                    ← 一键安装依赖
├── start_web.bat                       ← 一键启动Web前端 ✨ 新增
├── requirements.txt                    ← Python 依赖清单
└── PROJECT_README.md                   ← 你在这里
```

## 快速开始 (一键运行)

### 第一步:安装 vnpy

已经为你创建好 conda 环境 `quant`，你只需要:

双击运行 (或在 cmd 里执行):
```
cd vnpy
install.bat D:\anaconda3\envs\quant\python.exe https://pypi.tuna.tsinghua.edu.cn/simple
```

> 脚本会自动升级 pip、安装预编译 TA-Lib、把 vnpy 装到 quant 环境。

### 第二步:一键安装其余依赖

安装完 vnpy 后，**双击运行**:
```
install_deps.bat
```

它会自动激活 `quant` 环境、安装 `akshare`/`pandas`/`flask` 所有依赖。

### 第三步:生成选股候选池

打开 cmd:
```cmd
conda activate quant
python -m stock_screener.run
```

等几分钟，跑完会输出 `stock_screener/output/candidates_YYYYMMDD.csv`。

### 第四步:一键打开Web前端查看结果

**直接双击运行**:
```
start_web.bat
```

会自动启动 Flask，打开浏览器访问 `http://127.0.0.1:5000` 就能看到:
- 全部筛选后的股票表格
- 支持搜索代码/名称
- 支持按 PE / 市值 / 毛利率排序

## 功能模块

| 模块 | 作用 |
|---|---|
| `a-share-trading-mentor` | **认知层** — Claude 自动技能，聊A股时自动用 经典投资原理第一章逻辑帮你框架分析，绝不荐股，只给思考框架 |
| `stock_screener` | **选股层** — 两层漏斗:第一层排雷(ST/低市值/亏损)，第二层财务门槛(连续3年ROE≥15% / 毛利率≥20% / 负债率≤70%) |
| `project` | **策略层** — 对接 vnpy，示例策略 `RoeMaStrategy`:基本面选股出来后，用 5/20 均线纪律进出，严格风控 |
| `webapp` | **展示层** — Flask+Bootstrap 网页，搜索排序筛选结果 |

## 核心设计思路 (100% 遵循 经典投资原理认知)

1. **认知先行，规则跟上**:书里说的「不追高、顺势而为、分批建仓、严格止损」全落实成代码规则，情绪没法干涉。
2. **两层漏斗**:先基本面海选，再趋势择时 —— 长线价投+趋势进出，适合普通人。
3. **风控硬限制**:单票不超20%，总仓不超80%，固定8%止损 —— **生存第一，赚大钱第二**，完全符合「成为高手前提是活得足够久」。
4. **只做能验证的**:所有规则都能回测，用历史数据说话，不是拍脑袋说"这个战法必涨"。

## 手动命令版 (不想用一键脚本)

```cmd
:: 激活环境
conda activate quant

:: 装依赖
cd C:\Users\LJY\Desktop\量化交易
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 跑选股
python -m stock_screener.run

:: 启动前端
python -m webapp.app
:: 打开 http://127.0.0.1:5000
```

## 调整选股阈值

所有门槛都在 `stock_screener/config.py`，直接改参数就行:
- `ROE_MIN = 15.0` → ROE最低要求(%)
- `ROE_YEARS = 3` → 要求连续多少年达标
- `GROSS_MARGIN_MIN = 20.0` → 毛利率最低要求
- `MIN_MARKET_CAP = 30亿` → 最小市值
- 改完再跑一遍 `python -m stock_screener.run` 就得到新结果。
