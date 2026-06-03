from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://casecell:casecell_pw@localhost:5432/casecell"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://test:test@localhost:5433/casecell_test"
    USE_MOCK_ERP: bool = True
    MOCK_ERP_DELAY_SECONDS: float = 0.1
    MOCK_ERP_FAIL_RATE: float = 0.0
    ERP_SYNC_INTERVAL_SECONDS: int = 300
    ERP_CALL_TIMEOUT_SECONDS: float = 10.0
    ERP_CIRCUIT_FAILURE_THRESHOLD: int = 5
    ERP_CIRCUIT_RECOVERY_SECONDS: int = 30
    RESERVATION_TTL_MINUTES: int = 15
    CLEANUP_INTERVAL_SECONDS: int = 60
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"  # "console" (human-readable) or "json" (machine-readable)
    CORS_ORIGINS: str = "http://localhost:5173"
    ADMIN_SECRET: str = "changeme"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
