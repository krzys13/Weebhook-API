from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

    # DB parts
    db_user: str
    db_password: str
    db_host: str
    db_port: int = 3306
    db_name: str

    # worker
    worker_enabled: bool = True
    worker_concurrency: int = 10
    worker_retry_max: int = 3
    worker_retry_delay: float = 2.0

    # dedup
    deduplication_window_seconds: int = 10

    # api
    host: str = "0.0.0.0"
    port: int = 8000

    # logging
    log_level: str = "INFO"
    log_format: str = "text"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+asyncmy://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()