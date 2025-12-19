import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    HF_TOKEN = os.getenv("HF_TOKEN")  # Optional Hugging Face token


settings = Settings()
