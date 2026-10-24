import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_name: str = "Enterprise Agentic Ops Workspace"
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    secret_key: str = "insecure-dev-secret-key-change-in-production-must-be-32-bytes"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # LLM Provider Configuration
    # Supported: "local" (deterministic simulation), "openai", "azure_openai", "anthropic"
    llm_provider: str = Field(default="local", env="LLM_PROVIDER")
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model_name: str = Field(default="gpt-4o", env="OPENAI_MODEL_NAME")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    azure_openai_api_key: str = Field(default="", env="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = Field(default="", env="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: str = Field(default="", env="AZURE_OPENAI_DEPLOYMENT")

    # Enterprise Integrations Mode
    m365_integration_mode: str = Field(default="simulator", env="M365_INTEGRATION_MODE")
    m365_tenant_id: str = Field(default="", env="M365_TENANT_ID")
    m365_client_id: str = Field(default="", env="M365_CLIENT_ID")
    m365_client_secret: str = Field(default="", env="M365_CLIENT_SECRET")

    sap_integration_mode: str = Field(default="simulator", env="SAP_INTEGRATION_MODE")
    sap_odata_base_url: str = Field(
        default="https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV",
        env="SAP_ODATA_BASE_URL"
    )
    sap_api_key: str = Field(default="", env="SAP_API_KEY")

    # Data Loss Prevention (PII Firewall) Hook
    dlp_firewall_enabled: bool = Field(default=True, env="DLP_FIREWALL_ENABLED")
    dlp_redaction_mode: str = Field(default="PARTIAL_MASK", env="DLP_REDACTION_MODE")

    # Database Paths
    database_path: str = Field(default="data/workspace.db", env="DATABASE_PATH")
    checkpoint_db_path: str = Field(default="data/checkpoints.db", env="CHECKPOINT_DB_PATH")

    @property
    def runtime_mode(self) -> str:
        if self.llm_provider == "local":
            return "LOCAL_DETERMINISTIC_ENGINE"
        return "LIVE_ENTERPRISE"

    @property
    def sap_mode(self) -> str:
        return "SAP_SANDBOX" if self.sap_integration_mode.lower() == "sandbox" else "LOCAL_SIMULATOR"

    @property
    def m365_mode(self) -> str:
        return "GRAPH_LIVE" if self.m365_integration_mode.lower() == "live" else "LOCAL_SIMULATOR"

    @property
    def mcp_mode(self) -> str:
        return "LOCAL_IN_PROCESS"

    @property
    def sap_sandbox_base_url(self) -> str:
        return self.sap_odata_base_url

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
