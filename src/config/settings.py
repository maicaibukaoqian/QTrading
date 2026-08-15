"""全局配置
用户在这里填写自己的API Key等配置
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根：src/config/settings.py 的两级父目录
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """系统配置，支持环境变量（QUANT_ 前缀）和 .env 文件"""

    model_config = SettingsConfigDict(
        env_prefix="QUANT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ===== 大语言模型 API（用于AI点评，可选） =====
    ai_api_key: Optional[str] = Field(default=None, description="LLM API Key，None 时禁用 AI 点评")
    ai_api_base: str = Field(default="https://api.openai.com/v1", description="OpenAI 兼容端点")
    ai_model_name: str = Field(default="gpt-3.5-turbo", description="模型名")

    # ===== 日报生成 =====
    max_ai_comments: int = Field(default=50, ge=1, le=500, description="每天最多给多少只共振股生成AI点评")

    # ===== 路径（统一项目根绝对化，避免跨 CWD 启动数据分裂） =====
    data_root: str = Field(
        default=str(_PROJECT_ROOT / "data"),
        description="数据根目录（绝对路径）",
    )
    output_dir: str = Field(
        default=str(_PROJECT_ROOT / "data" / "outputs"),
        description="选股结果/分析报告输出目录（绝对路径）",
    )
    daily_dir: str = Field(
        default=str(_PROJECT_ROOT / "data" / "daily"),
        description="日报输出目录（绝对路径）",
    )
    cache_dir: str = Field(
        default=str(_PROJECT_ROOT / "data" / "cache"),
        description="K线/财务缓存目录（绝对路径）",
    )
    universe_dir: str = Field(
        default=str(_PROJECT_ROOT / "data" / "universe"),
        description="全市场行情缓存目录（绝对路径）",
    )

    # ===== 下载参数 =====
    kline_start_date: str = Field(default="2024-01-01", description="K线下载起始日期")
    download_sleep_min: float = Field(default=0.5, ge=0.0, description="下载最小 sleep 秒数")
    download_sleep_max: float = Field(default=1.3, ge=0.0, description="下载最大 sleep 秒数")
    fundamentals_sleep: float = Field(default=0.6, ge=0.0, description="财务数据下载 sleep 秒数")

    # ===== API 服务 =====
    api_host: str = Field(default="127.0.0.1", description="FastAPI 监听地址")
    api_port: int = Field(default=8000, ge=1, le=65535, description="FastAPI 端口")

    @model_validator(mode="after")
    def _absolutize_paths(self) -> "Settings":
        """env 传入相对路径时自动以项目根为基准绝对化。

        所有路径字段约定为绝对路径：默认已用 _PROJECT_ROOT 拼出绝对值，
        若用户通过 env 传相对路径（多用于开发场景），也兜底绝对化。
        """
        for fname in ("data_root", "output_dir", "daily_dir", "cache_dir", "universe_dir"):
            v = getattr(self, fname)
            if not Path(v).is_absolute():
                setattr(self, fname, str((_PROJECT_ROOT / v).resolve()))
        return self

    @property
    def ai_enabled(self) -> bool:
        """AI 点评是否可用（API Key 已配置）"""
        return bool(self.ai_api_key)

    @property
    def ai_endpoint(self) -> str:
        """LLM 调用端点 URL

        若 ai_api_base 已以 /chat/completions 结尾则原样使用（便于复制完整 URL）；
        否则自动拼接 /chat/completions。
        """
        base = (self.ai_api_base or "").rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    # ===== 派生路径（单一真源：所有数据文件都从这里出） =====
    @property
    def universe_pe_csv(self) -> str:
        return str(Path(self.universe_dir) / "all_stocks_pe.csv")

    @property
    def industry_csv(self) -> str:
        return str(Path(self.universe_dir) / "industry_only.csv")

    @property
    def chat_db_path(self) -> str:
        return str(Path(self.data_root) / "chat.db")

    @property
    def screen_all_csv(self) -> str:
        return str(Path(self.output_dir) / "screen_all.csv")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取单例配置"""
    return Settings()
