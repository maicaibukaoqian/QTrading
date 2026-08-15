# 第三方依赖 / 数据源 / 知识产权声明

> 用途：对外说明本项目用到的所有第三方代码、数据、AI 提示词的来源与授权边界。
> 位置：与 LICENSE 互补——LICENSE 描述本项目本身的授权；本文件描述"借来的部分"。

---

## 一、本项目授权

本项目主体采用 MIT License（详见 LICENSE）。
所有"本项目原创"内容——包括 5 个量化策略、7 维风险评分规则、问股对话架构、前端 UI、Markdown 文档——均按 MIT 授权。

下文列出的第三方内容不包含在本项目 MIT 授权范围内，使用时需遵守各自的协议。

---

## 二、Python 依赖（requirements.txt）

| 包 | 版本约束 | 协议 | 来源 |
|----|----------|------|------|
| baostock | >= 0.8.8 | BSD | http://www.baostock.com |
| akshare | >= 1.12 | MIT | https://github.com/akfamily/akshare |
| efinance | >= 1.1 | MIT | https://github.com/Micro-sheep/efinance |
| pandas | >= 2.0 | BSD-3-Clause | https://github.com/pandas-dev/pandas |
| numpy | >= 1.24 | BSD-3-Clause | https://github.com/numpy/numpy |
| fastapi | >= 0.110 | MIT | https://github.com/fastapi/fastapi |
| uvicorn[standard] | >= 0.27 | BSD-3-Clause | https://github.com/encode/uvicorn |
| pydantic | >= 2.6 | MIT | https://github.com/pydantic/pydantic |
| pydantic-settings | >= 2.2 | MIT | https://github.com/pydantic/pydantic-settings |
| requests | >= 2.31 | Apache-2.0 | https://github.com/psf/requests |
| httpx | >= 0.27 | BSD-3-Clause | https://github.com/encode/httpx |
| click | >= 8.0 | BSD-3-Clause | https://github.com/pallets/click |
| pytest | >= 8.0 | MIT | https://github.com/pytest-dev/pytest |
| pyarrow | >= 14.0 | Apache-2.0 | https://github.com/apache/arrow |
| matplotlib | >= 3.5 | MDT / PSF | https://github.com/matplotlib/matplotlib |

协议兼容性：上述协议（BSD / MIT / Apache-2.0）均与 MIT 兼容，可一起分发，不要求本项目整体切换协议。

---

## 三、数据源（最重要的部分）

| 数据源 | 提供方 | 数据范围 | 授权 / 用途条款 | 我们的使用方式 |
|--------|--------|----------|----------------|----------------|
| baostock | 上海宽睿信息科技 | A 股 K 线 / 财务 / 行业分类 | 仅供个人学习研究使用，禁止商业用途（官网条款） | 本地缓存 + 增量更新，不做服务端分发 |
| akshare | 开源社区（akfamily） | 沪深京股票 / 期货 / 基金 / 行业分类 / 股息率 | MIT 协议；二次分发受原始数据源约束 | 兜底 + 股息率补充 |
| efinance | 开源社区（Micro-sheep） | A 股 K 线 | MIT 协议；二次分发受东方财富条款约束 | 三层兜底最末位 |
| 东方财富 | 东方财富 | 行情 / 财务 | 仅供个人浏览查询（平台 ToS） | 通过 akshare / efinance 间接口接，不直连 |
| 同花顺 / 新浪财经 | 同花顺 / 新浪 | 行情 | 仅供个人浏览 | 不直接使用，akshare 内部可选 |

### 关键边界（务必保留）

1. 不在任何 SaaS / 托管服务中实时转发上述数据——本地缓存 + 一次性下载是允许的用法
2. 不把上述数据二次打包出售 / 重新分发
3. 不用本项目做"实时行情"商业服务（违反 baostock / 东财条款）
4. 不做"实盘交易接入"——项目只做"研究辅助"，不接券商 API、不发单

如要做"商业 SaaS 版"，必须切换到正规商业数据源（如 Wind / 同花顺 iFinD / Choice / 聚宽商用版），由合规团队评估。

---

## 四、前端字体 / CSS

| 资源 | 来源 | 协议 | 用途 |
|------|------|------|------|
| Noto Serif SC | Google Fonts | SIL Open Font License 1.1 | 中文标题 / 报刊风正文 |
| Noto Sans SC | Google Fonts | SIL Open Font License 1.1 | 中文 UI |
| IBM Plex Mono | Google Fonts | SIL Open Font License 1.1 | 数字 / 代码 |
| ZCOOL XiaoWei | Google Fonts | SIL Open Font License 1.1 | 印章 / 装饰 |

SIL OFL 1.1 允许免费用于商业产品，仅需保留版权声明——本项目 frontend/index.html 已通过 Google Fonts CDN 加载，CDN 自动附带协议。

---

## 五、LLM 提示词原创性声明

本项目所有 LLM 提示词（src/ai_prompts/）全部为项目原创，基于公开教科书体系：

| 框架维度 | 参考的公开内容 |
|----------|----------------|
| 基础面 | 公司财务分析公开教材（营收 / 净利润 / 毛利率 / ROE） |
| 估值面 | 经典估值方法（PE / PB / 股息率）—— 任何 CFA / 投资学教材都讲 |
| 技术面 | 经典技术指标（均线 / MACD / KDJ / 形态）—— 任何证券分析教材都讲 |
| 筹码面 | A 股公开数据（股东人数 / 机构持仓 / 北向资金）—— 交易所 / 证监会披露 |
| 风险面 | 财务风险 / 经营风险 / 治理风险 / 政策风险 / 市场风险 5 类 |

本项目提示词严格遵守：

- 不引用任何特定个人的讲义、课程、语录
- 不引用任何特定投资流派的术语（如缠论 / 波浪 / 江恩 / 特定战法名称）
- 不复制任何第三方 prompt 模板
- 仅基于公开教科书的通用分析框架
- 所有规则附带单位 + 数值阈值（如 PE < 30），避免"凭感觉"的表述

如有质疑，可对照 src/ai_prompts/investment_analyst.py 与公开教材章节独立验证。

---

## 六、本项目不包含的内容

为避免误解，特此声明本项目不包含以下任何内容：

- 任何券商交易接口 / 实盘下单能力
- 任何"内幕消息 / 庄家动向 / 主力监控"功能
- 任何"必涨 / 必跌 / 目标价"判断
- 任何用户持仓 / 交易记录的同步
- 任何账号体系 / 支付 / 会员系统
- 任何爬虫绕过反爬措施的工具

如项目后续添加上述任一功能，将同步更新本文件并另开新文件（如 SECURITY.md / PRIVACY.md）做专项说明。

---

## 七、合规检查清单（提 PR 时过一遍）

- [ ] 没新增硬编码路径
- [ ] 没新增 print 调试输出
- [ ] 没动 data/universe/* 写盘逻辑
- [ ] 没在 prompt / docstring / 数据规则里写"特定投资流派"或"特定个人讲义"
- [ ] 没新增依赖到 requirements.txt（如新增，必须在本文件登记协议 + 数据源条款）
- [ ] 没把任何第三方数据源实时转发到响应里

---

## 八、联系方式

如有协议 / 数据使用 / 知识产权相关疑问：

- GitHub Issue：在仓库开 issue，标签 [license] 或 [ip]
- 裁判争议：所有争议以中国法律为准（项目作者所在地）

---

最后更新：2026-08-15
本文件与 LICENSE 一起构成本项目的完整授权声明。
