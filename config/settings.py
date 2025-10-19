"""Configuration centralisée de l'application."""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration de l'application."""
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }
    
    # API Keys - IA Providers (Anthropic principal, OpenAI fallback)
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    
    # API Keys - Services
    github_token: str = Field(..., env="GITHUB_TOKEN") 
    
    # Monday.com OAuth Configuration
    monday_client_id: str = Field(..., env="MONDAY_CLIENT_ID")
    monday_client_key: str = Field(..., env="MONDAY_CLIENT_KEY") 
    monday_app_id: str = Field(..., env="MONDAY_APP_ID")
    
    # Monday.com API Token (Global API Token)
    monday_api_token: str = Field(..., env="MONDAY_API_TOKEN")

    # Webhook Configuration
    webhook_secret: str = Field(..., env="WEBHOOK_SECRET")
    allowed_origins: str = Field(default="*", env="ALLOWED_ORIGINS")
    
    # Git Configuration
    # default_repo_url supprimé - URL spécifiée dans description Monday.com
    default_base_branch: str = Field(default="main", env="DEFAULT_BASE_BRANCH")
    git_user_name: str = Field(default="AI-Agent", env="GIT_USER_NAME")
    git_user_email: str = Field(default="ai-agent@example.com", env="GIT_USER_EMAIL")
    
    # Monday.com Configuration
    monday_board_id: str = Field(..., env="MONDAY_BOARD_ID")
    monday_task_column_id: str = Field(..., env="MONDAY_TASK_COLUMN_ID") 
    monday_status_column_id: str = Field(..., env="MONDAY_STATUS_COLUMN_ID")
    monday_repository_url_column_id: Optional[str] = Field(default=None, env="MONDAY_REPOSITORY_URL_COLUMN_ID")
    
    # Database Configuration (Admin Backend)
    database_url: str = Field(default="postgresql://admin:password@localhost:5432/ai_agent_admin", env="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # Security Configuration
    secret_key: str = Field(..., env="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # AI Engine Configuration
    default_ai_provider: str = Field(default="anthropic", env="DEFAULT_AI_PROVIDER")
    ai_model_temperature: float = Field(default=0.1, env="AI_MODEL_TEMPERATURE")
    ai_max_tokens: int = Field(default=4000, env="AI_MAX_TOKENS")
    
    # Testing Configuration
    enable_smoke_tests: bool = Field(default=True, env="ENABLE_SMOKE_TESTS")
    test_coverage_threshold: int = Field(default=80, env="TEST_COVERAGE_THRESHOLD")
    max_test_retries: int = Field(default=3, env="MAX_TEST_RETRIES")
    
    # Background Processing - RabbitMQ Configuration
    rabbitmq_host: str = Field(default="localhost", env="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, env="RABBITMQ_PORT")
    rabbitmq_vhost: str = Field(default="ai_agent", env="RABBITMQ_VHOST")
    rabbitmq_user: str = Field(default="ai_agent_user", env="RABBITMQ_USER")
    rabbitmq_password: str = Field(default="secure_password_123", env="RABBITMQ_PASSWORD")
    rabbitmq_management_port: int = Field(default=15672, env="RABBITMQ_MANAGEMENT_PORT")
    rabbitmq_enable_management: bool = Field(default=True, env="RABBITMQ_ENABLE_MANAGEMENT")
    
    # Celery Configuration (construites à partir des variables RabbitMQ)
    @property
    def celery_broker_url(self) -> str:
        """URL du broker Celery construite dynamiquement."""
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"
    
    @property 
    def celery_result_backend(self) -> str:
        """Backend des résultats Celery utilisant PostgreSQL."""
        return f"db+{self.database_url}"
    
    # Database component properties (extracted from database_url)
    @property
    def db_host(self) -> str:
        """Extrait le host de database_url."""
        import re
        match = re.search(r'@([^@:]+):\d+/', self.database_url)
        return match.group(1) if match else "localhost"
    
    @property
    def db_port(self) -> int:
        """Extrait le port de database_url."""
        import re
        match = re.search(r':(\d+)/', self.database_url)
        return int(match.group(1)) if match else 5432
    
    @property
    def db_name(self) -> str:
        """Extrait le nom de DB de database_url."""
        import re
        match = re.search(r':\d+/([^?]+)', self.database_url)
        return match.group(1) if match else "ai_agent_admin"
    
    @property
    def db_user(self) -> str:
        """Extrait le user de database_url."""
        import re
        match = re.search(r'://([^:]+):', self.database_url)
        return match.group(1) if match else "admin"
    
    @property
    def db_password(self) -> str:
        """Extrait le password de database_url."""
        import re
        match = re.search(r'://[^:]+:(.+)@[^@]+:\d+/', self.database_url)
        return match.group(1) if match else "password"
    
    # Application Configuration
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Timeout Configuration
    task_timeout: int = Field(default=3600, env="TASK_TIMEOUT")  # 30 minutes
    test_timeout: int = Field(default=600, env="TEST_TIMEOUT")   # 5 minutes
    
    # Admin Frontend Configuration
    admin_frontend_url: str = Field(default="http://localhost:3000", env="ADMIN_FRONTEND_URL")
    
    # Monitoring Configuration
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=8080, env="METRICS_PORT")


@lru_cache()
def get_settings() -> Settings:
    """Retourne les paramètres de configuration avec cache."""
    return Settings() 