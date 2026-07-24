"""应用配置管理，通过 pydantic-settings 读取 .env 环境变量."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"

    # LLM API
    llm_api_base: str = "https://aicopilot.goldwind.com.cn:3213/v1"
    llm_api_key: str = "sk-xxx"
    llm_model: str = "glm-5.2"
    llm_mode: str = ""

    # 服务
    host: str = "0.0.0.0"
    port: int = 8080

    # SSL（内网自签名证书环境）
    ssl_verify: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
