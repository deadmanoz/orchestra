from pydantic_settings import BaseSettings
from typing import Literal
from pydantic import field_validator

class Settings(BaseSettings):
    # Environment
    environment: Literal["development", "production"] = "development"
    debug: bool = True

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 3030
    cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/orchestra.db"

    # Agents
    use_mock_agents: bool = True
    agent_port_range_start: int = 3701
    agent_port_range_end: int = 3799
    agent_timeout: int = 300  # 5 minutes

    # LangGraph
    langgraph_checkpoint_db: str = "./data/orchestra.db"

    # External APIs
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Paths
    working_directory: str = "./workspace"

    class Config:
        env_file = ".env"

settings = Settings()
