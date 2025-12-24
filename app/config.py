from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    port: int = 5000
    mongodb_uri: str 
    jwt_secret: str 
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 720  # 30 days
    compiler_service_url: str 
    
    # Email Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""  # Set via environment variable
    smtp_password: str = ""  # Set via environment variable (App Password for Gmail)
    smtp_from_email: str = ""  # Set via environment variable
    smtp_from_name: str = "Online Code Compiler"
    frontend_url: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"
        extra = "allow"  # Allow extra fields from .env

settings = Settings()

