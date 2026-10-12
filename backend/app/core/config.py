from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NexusMatch API"
    app_env: str = "development"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "nexusmatch"
    postgres_user: str = "nexusmatch"
    postgres_password: str = "change_me_locally"

    mongodb_host: str = "localhost"
    mongodb_port: int = 27017
    mongodb_database: str = "nexusmatch_telemetry"
    mongo_initdb_root_username: str = "nexusmatch_admin"
    mongo_initdb_root_password: str = "change_me_locally"


settings = Settings()
