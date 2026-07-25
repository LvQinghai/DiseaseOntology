"""应用配置管理，通过 pydantic-settings 读取 .env 环境变量."""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"

    # LLM API
    llm_api_base: str = "https://aicopilot.goldwind.com.cn:3213/v1"
    llm_api_key: str = "sk-xxx"
    llm_model: str = "qwen3.7-max"
    llm_mode: str = ""

    # v3.0 迁移（Neo4j 标签/关系前缀迁移）
    run_migration: bool = True

    # v3.0 SQLite 元数据库（记录系统列表 + 各系统 prefix）
    sqlite_path: str = ""

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

    def get_sqlite_path(self) -> str:
        """获取 SQLite 数据库文件的绝对路径。

        优先级:
        1. 环境变量 SQLITE_PATH
        2. 默认: backend/data/systems.db (相对于 backend/ 目录)
        """
        if self.sqlite_path:
            return self.sqlite_path
        # 默认路径：backend/data/systems.db
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(backend_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "systems.db")


    # ──────────────────────────────────
    # v3.0 默认系统配置（疾病诊疗知识图谱）
    # ──────────────────────────────────
    DEFAULT_SYSTEM_ID: str = "disease_ontology"
    DEFAULT_SYSTEM_NAME: str = "疾病诊疗知识图谱"
    DEFAULT_SYSTEM_DESC: str = (
        "包含疾病、药物、症状、副作用、身体部位及其关系的疾病诊疗知识图谱"
    )
    DEFAULT_SYSTEM_PREFIX: str = "MED_"


settings = Settings()
