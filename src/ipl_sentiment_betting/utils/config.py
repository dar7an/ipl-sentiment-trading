import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration management for the application."""
    
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    @classmethod
    def validate(cls):
        """Validates that all required environment variables are set."""
        if not cls.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable not found. Please create a .env file with your key.")
