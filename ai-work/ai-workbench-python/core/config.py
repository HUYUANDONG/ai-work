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
        dashscope_api_key: 阿里云百炼 API Key。
        decision_*: 决策模型意图路由相关开关与门槛。
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
    dashscope_api_key: str = Field(default="", validation_alias="DASHSCOPE_API_KEY")
    decision_intent_enabled: bool = Field(
        default=True,
        validation_alias="WB_DECISION_INTENT_ENABLED",
    )
    decision_model: str = Field(
        default="decision-model-preview",
        validation_alias="WB_DECISION_MODEL",
    )
    decision_min_confidence: float = Field(
        default=0.75,
        validation_alias="WB_DECISION_MIN_CONFIDENCE",
    )
    decision_allow_rules_fallback: bool = Field(
        default=True,
        validation_alias="WB_DECISION_ALLOW_RULES_FALLBACK",
    )
    decision_workspace_id: str = Field(
        default="",
        validation_alias="WB_DECISION_WORKSPACE_ID",
    )
    decision_region: str = Field(
        default="cn-beijing",
        validation_alias="WB_DECISION_REGION",
    )
    decision_base_url: str = Field(
        default="",
        validation_alias="WB_DECISION_BASE_URL",
    )
    hmac_secret_in: str = Field(default="", validation_alias="WB_HMAC_SECRET_IN")
    hmac_secret_out: str = Field(default="", validation_alias="WB_HMAC_SECRET_OUT")
    # 百炼 OpenAI 兼容 Chat Completions（报表分析文案；不算正式分）
    llm_api_key: str = Field(default="", validation_alias="WB_LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias="WB_LLM_BASE_URL",
    )
    llm_model: str = Field(default="qwen-plus", validation_alias="WB_LLM_MODEL")
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
    # 记忆占输入预算达到该比例才触发一次 LLM 深度摘要（不频繁、不截断）
    chat_summary_pressure: float = Field(
        default=0.80,
        ge=0.50,
        le=0.95,
        validation_alias="WB_CHAT_SUMMARY_PRESSURE",
    )
    @property
    def resolved_llm_api_key(self) -> str:
        """报表 LLM Key：优先 WB_LLM_API_KEY，否则复用 DASHSCOPE_API_KEY。"""
        return (self.llm_api_key or "").strip() or (self.dashscope_api_key or "").strip()


@lru_cache
def get_settings() -> Settings:
    """
    进程内单例配置。

    Returns:
        Settings: 已解析环境配置。
    """
    return Settings()
