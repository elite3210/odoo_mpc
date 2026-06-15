from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    odoo_url: str = "https://www.heinzsport.com"
    odoo_db: str = "elite"

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001

    # Clave secreta para firmar JWT (genera una larga y aleatoria)
    jwt_secret: str
    jwt_expire_hours: int = 8

    audit_log_path: str = "audit.jsonl"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
