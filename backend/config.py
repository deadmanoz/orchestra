from pydantic_settings import BaseSettings
from typing import Literal, Union
from pydantic import field_validator

class Settings(BaseSettings):
    # Environment
    environment: Literal["development", "production"] = "development"
    debug: bool = True

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 3030
    cors_origins: Union[str, list[str]] = ["http://localhost:5173"]

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # Handle empty string
            if not v or not v.strip():
                return ["http://localhost:5173"]
            # Parse comma-separated values and filter empty strings
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        if isinstance(v, list):
            return v
        return ["http://localhost:5173"]

    # Database
    database_path: str = "data/orchestra.db"
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
