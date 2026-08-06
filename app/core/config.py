from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JARVIS Medical Platform"
    environment: str = "development"
    debug: bool = True
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"
    trusted_hosts: str = "localhost,127.0.0.1,0.0.0.0,testserver"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        return _split_env_list(self.allowed_origins)

    @property
    def allowed_hosts(self) -> list[str]:
        return _split_env_list(self.trusted_hosts)


def _split_env_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
