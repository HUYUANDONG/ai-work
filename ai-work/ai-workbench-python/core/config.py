"""
应用配置（从环境变量读取，不写死密钥）。

对应 Nest：ConfigModule / ConfigService。
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用运行配置（供 AppRuntime 等使用）。

    Attributes:
        profile: 运行环境（local / dev / prod）。
        checkpoint_database_url: Checkpoint Postgres。
        java_base_url: Workbench Service 内网地址。
        java_mock_features: 是否用本地 fixture 充当特征。
        typesafe_api_key: Jev / TypeSafe Key。
        jev_*: 意图路由相关开关与门槛。
        worker_*: Worker 轮询与租约。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    profile: str = Field(default="local", validation_alias="WB_PROFILE")
    checkpoint_database_url: str = Field(
        default="",
        validation_alias="WB_CHECKPOINT_DATABASE_URL",
    )
    java_base_url: str = Field(
        default="http://127.0.0.1:8080",
        validation_alias="WB_JAVA_BASE_URL",
    )
    java_mock_features: bool = Field(
        default=True,
        validation_alias="WB_JAVA_MOCK_FEATURES",
    )
    typesafe_api_key: str = Field(default="", validation_alias="TYPESAFE_API_KEY")
    jev_intent_enabled: bool = Field(default=True, validation_alias="WB_JEV_INTENT_ENABLED")
    jev_model: str = Field(default="jev-latest", validation_alias="WB_JEV_MODEL")
    jev_min_confidence: float = Field(default=0.75, validation_alias="WB_JEV_MIN_CONFIDENCE")
    jev_allow_rules_fallback: bool = Field(
        default=True,
        validation_alias="WB_JEV_ALLOW_RULES_FALLBACK",
    )
    hmac_secret_in: str = Field(default="", validation_alias="WB_HMAC_SECRET_IN")
    hmac_secret_out: str = Field(default="", validation_alias="WB_HMAC_SECRET_OUT")
    worker_poll_interval_seconds: int = Field(
        default=20,
        validation_alias="WB_WORKER_POLL_INTERVAL_SECONDS",
    )
    worker_lease_seconds: int = Field(default=60, validation_alias="WB_WORKER_LEASE_SECONDS")
    worker_concurrency: int = Field(default=2, validation_alias="WB_WORKER_CONCURRENCY")

    # OpenAI 兼容 Chat Completions（报表分析文案；不算正式分）
    llm_api_key: str = Field(default="", validation_alias="WB_LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="WB_LLM_BASE_URL",
    )
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="WB_LLM_MODEL")
    report_output_dir: str = Field(
        default="tmp/reports",
        validation_alias="WB_REPORT_OUTPUT_DIR",
    )
    # 上下文预算（业界启发式；可用真实 prompt_tokens 校准）
    llm_context_window: int = Field(
        default=128_000,
        validation_alias="WB_LLM_CONTEXT_WINDOW",
    )
    llm_reserve_output: int = Field(
        default=4096,
        validation_alias="WB_LLM_RESERVE_OUTPUT",
    )
    chat_working_keep_last: int = Field(
        default=8,
        validation_alias="WB_CHAT_WORKING_KEEP_LAST",
    )


@lru_cache
def get_settings() -> Settings:
    """
    进程内单例配置。

    Returns:
        Settings: 已解析环境配置。
    """
    return Settings()
