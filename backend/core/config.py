from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App Settings
    PROJECT_NAME: str
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # 30 minutes
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080 # 7 days in minutes
    INVITE_EXPIRE_HOURS: int = 168 # 7 days
    SIGNUP_VERIFICATION_EXPIRE_HOURS: int = 24
    
    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: str
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        
    # Celery
    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/2"

    # Rate Limiting
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # Logging
    LOG_LEVEL: str = "INFO"

    # LLM Settings
    DEFAULT_LLM_PROVIDER: str
    DEFAULT_LLM_MODEL: str
    
    # Vector Store
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    
    # External APIs
    TAVILY_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # LangSmith Tracing
    LANGCHAIN_TRACING_V2: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: Optional[str] = None

    # Email (invite delivery)
    RESEND_API_KEY: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None
    EMAIL_FROM_ADDRESS: str = "onboarding@resend.dev"
    EMAIL_FROM_NAME: str = "HR Bot"
    # Where accept-invite links point. No frontend exists yet, so this is a
    # placeholder - update it once the frontend has a real accept-invite route.
    FRONTEND_BASE_URL: str = "http://localhost:3000"

settings = Settings()
