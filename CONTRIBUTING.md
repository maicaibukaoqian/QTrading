# 贡献指南

感谢你愿意为「量衡录」贡献代码 / 文档 / 策略 / 数据。

---

## 一、提交流程

1. **Fork** 本仓库，从 `main` 切分支（命名规范：`feat/xxx` / `fix/xxx` / `docs/xxx`）
2. 提交前跑 `python -c "from src.api.app import create_app; create_app()"` 确认 import 没破
3. 写清楚 commit message（参考 `feat: 新增 520 策略的回测支持`）
4. 提 PR，**在描述里写清楚：**
   - 改了什么
   - 怎么测（手动命令 / 输入输出样例）
   - 是否影响现有数据缓存（PE/PB/K 线是否需要重新拉）
5. 等 CI + 至少 1 位 reviewer 通过

---

## 二、代码风格

- Python 3.10+，`pathlib.Path` 优先，禁 `os.path.join`
- 函数尽量无副作用，便于单测
- LLM 调用统一走 `src/agent/llm_caller.py`，不在业务里直接 `import openai`
- 任何路径拼字符串 → 走 `src/config/settings.py` 的派生字段
- 任何读 cache → 走 `src/data/cache.py`，**不**在业务里 `pd.read_csv(f"data/cache/{code}_kline.csv")`
- 日志用 `logger = logging.getLogger(__name__)`，**不**用 `print`
- 中文注释 / docstring OK，但**禁止**把任何"私人投资经验 / 私人讲义"写进项目

---

## 三、新增策略怎么接

1. 在 `src/strategies/screeners/` 下加一个文件，继承 `src/strategies/base.py:Screener`
2. 实现 `name / description / default_params / screen(df) -> DataFrame`
3. 在 `src/api/services/screen_service.py:STRATEGY_REGISTRY` 注册一条
4. 在 `src/api/schemas/screen.py` 加 `XxxParams`
5. 在 `src/api/schemas/__init__.py` 导出
6. 跑 `python main.py screen xxx` 验证

---

## 四、新增风险维度怎么接

`src/agent/risk_scorer.py` 是单文件 7 维评分。新增维度：

1. 在 `DIMENSIONS` 字典加一条
2. 函数签名 `def score_xxx(code: str, ctx: dict) -> DimensionResult`
3. 把函数加到 `evaluate_all` 的调用链
4. 权重在 `WEIGHTS` 同步调整（总和必须 = 1.0）

---

## 五、提交策略 / 风险规则前的自检

- [ ] 规则在 A 股 5 年历史里**没有严重未来函数**（不能用未来才知道的数据做当前判断）
- [ ] 规则**没有绑定特定投资流派**（不能写"按缠论第几买"或"按特定人物讲义"）
- [ ] 规则的依据能引用公开资料（年报、交易所规则、教科书）
- [ ] 规则的阈值有**单位 + 数值范围**（如"PE < 30"，不能写"PE 偏低"）

---

## 六、Issue 模板

提 issue 请用以下前缀：

- `[bug]` 程序错误 / 数据错误
- `[feat]` 新功能 / 新策略 / 新维度
- `[docs]` 文档 / 注释
- `[perf]` 性能 / 重构
- `[data]` 数据源 / 缓存相关
- `[ask]` 提问 / 讨论

---

## 七、行为准则

- 不接受任何形式的仇恨言论、性别歧视、地域歧视
- 投资类讨论保持中立，不推销个股、不晒收益
- 任何 PR 都不应把"个人持仓 / 私人对话 / 第三方讲义原文"写进项目

---

## 八、License

贡献即代表你同意按本仓库的 [MIT License](./LICENSE) 授权你的代码。
