"""自然语言回答生成
把结构化分析结果，转换成 AI 风格的自然语言回答
"""


def generate_answer(report: str, question: str) -> str:
    """生成最终回答.

    参数：
        report: 自动分析生成的markdown报告
        question: 用户原始问题

    返回：
        最终回答文本
    """

    answer = f"""根据量化分析框架，对该股票的综合分析如下：

{report}

---

> 内容为量化投研科普，市场有风险，决策与盈亏由你自己承担。
"""

    return answer
