from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./investring.db"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    token_expire_days: int = 7
    
    # Tushare API
    tushare_token: str = ""
    
    # Application
    app_name: str = "InvestRing"
    debug: bool = True
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
