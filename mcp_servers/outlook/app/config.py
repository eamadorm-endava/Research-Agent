from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    tenant_id: str = "common"
    client_id: str = ""
    # Add relevant Graph API or OAuth settings here
    
    class Config:
        env_prefix = "OUTLOOK_"
        env_file = ".env"

settings = Settings()
