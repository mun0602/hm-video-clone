import os
from dotenv import load_dotenv

# Load các biến môi trường từ file .env
load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./tiktok.db")
    
    # Cloudflare R2 Credentials
    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "")
    R2_PUBLIC_URL: str = os.getenv("R2_PUBLIC_URL", "")
    
    # JWT Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey123456789")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # CORS
    CORS_ORIGINS: list = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]

settings = Settings()
