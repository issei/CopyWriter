import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY     = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL       = "gemini-2.5-flash"
TEMPERATURE        = 0.7
MAX_REFINEMENT     = 2
EMBEDDING_MODEL    = "models/gemini-embedding-001"
CHROMA_PATH        = "./chroma_db"
DB_PATH            = "./historico.db"
