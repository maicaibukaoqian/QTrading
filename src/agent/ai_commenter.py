"""单股一句话 AI 短评

基于通用投研 prompt（src/ai_prompts/investment_analyst.py），
紧扣 PE/PB/ROE/命中策略，生成一句话点评。
"""

from typing import Optional

from src.agent.llm_caller import LLMCallError, LLMUnavailableError, get_llm_client
from src.ai_prompts.investment_analyst import build_daily_comment_prompt


def generate_stock_comment(code: str, name: str, pe: float, pb: float, roe: float, strategies: str) -> Optional[str]:
    settings_prompt = build_daily_comment_prompt()

    user_prompt = f"""
股票信息：
- 代码: {code}
- 名称: {name}
- PE: {pe:.2f}
- PB: {pb:.2f}
- ROE: {roe:.2f}%
- 被策略选中: {strategies}

要求：一句话，30-50字，紧扣数据，直白、实战、避免套话。
"""

    try:
        client = get_llm_client()
        text = client.chat(
            messages=[
                {"role": "system", "content": settings_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=100,
            temperature=0.7,
        )
        return text.replace("\n", " ").strip() or None
    except (LLMUnavailableError, LLMCallError) as e:
        print(f"[ai-commenter] API 调用失败 {code} {name}: {e}")
        return None
