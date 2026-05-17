from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "investring"
    database_url: str = ""
    
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
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.database_url:
            self.database_url = f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
