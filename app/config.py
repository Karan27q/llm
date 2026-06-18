import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")
    DATABASE_URL = os.getenv("DATABASE_URL")
    GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
    
    if not GOOGLE_GEMINI_API_KEY:
        # We don't raise it immediately during import to allow commands/migrations to run without it,
        # but we can validate it in the factory/service.
        pass
