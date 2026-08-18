"""应用配置（pydantic-settings，支持 .env 覆盖）。"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "P2 经营归因分析系统"
    host: str = "127.0.0.1"
    port: int = 8001
    db_path: Path = BASE_DIR / "data" / "db.sqlite3"
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    export_dir: Path = BASE_DIR / "data" / "exports"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    ws_token_ttl: int = 300
    max_result_rows: int = 100


settings = Settings()
