from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_port: int = 8000
    searxng_base_url: str = "http://localhost:8080"
    searxng_port: int = 8080
    sqlite_db_path: str = "./data/omnisearch.db"
    research_planner: str = "rule"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    research_planner_model: str = "gpt-5"
    request_timeout: int = 15
    user_agent: str = "OmniSearch/0.1"
    tushare_token: str | None = None
    tushare_base_url: str | None = None
    cninfo_announcements_url: str = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    stock_data_ttl_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
