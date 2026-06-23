from pydantic_settings import BaseSettings
 
class Settings(BaseSettings):
    MONGO_URI: str
    MONGO_DB: str = "acommie"
    VERSION: str = "1.0.0"
    API_KEY: str = ""
 
    class Config:
        env_file = ".env"
 
settings = Settings()
 