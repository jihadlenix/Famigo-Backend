from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FAMIGO_", env_file=".env", extra="ignore")
    DATABASE_URL: str = "sqlite:///C:/Users/AUB/Desktop/Mobile/famigo/Famigo-Backend/famigo.db"

    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_MIN: int = 60 * 24
    REFRESH_TOKEN_DAYS: int = 30
settings = Settings()
