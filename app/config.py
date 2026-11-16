from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/leads.db"
    jwt_secret: str = "development-secret-change-me"
    jwt_algorithm: str = "HS256"
    public_base_url: str = "http://localhost:8000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
