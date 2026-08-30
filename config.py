import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY     = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL       = "gemini-2.5-flash-lite"  # flash lite mais recente disponível
TEMPERATURE        = 0.7
MAX_REFINEMENT     = 2
EMBEDDING_MODEL    = "models/gemini-embedding-001"
CHROMA_PATH        = "./chroma_db"
DB_PATH            = "./historico.db"


# ── Configuração tipada — adição aditiva ──────────────────────────────────────
# As constantes de módulo acima permanecem — llm.py e rag.py as importam
# diretamente e não podem quebrar.

@dataclass(frozen=True)
class Settings:
    """Configuração tipada. As constantes de módulo acima permanecem como estão —
    llm.py e rag.py as importam diretamente e não podem quebrar."""
    google_api_key: str = GOOGLE_API_KEY
    text_model: str = GEMINI_MODEL
    text_model_reasoning: str = "gemini-2.5-flash"     # julgamento ambíguo
    vision_model: str = "gemini-2.5-flash"             # validação multimodal
    image_model: str = "gemini-2.5-flash-preview-05-20"  # geração de asset visual
    temperature: float = TEMPERATURE
    embedding_model: str = EMBEDDING_MODEL
    chroma_path: str = CHROMA_PATH
    db_path: str = DB_PATH
    # Carrossel
    carousel_max_revisions: int = 2
    carousel_output_dir: str = "./outputs/carrosseis"
    carousel_checkpoints: str = "./data/carousel_checkpoints.sqlite"
    fonts_dir: str = "./assets/fonts"


def get_settings() -> Settings:
    """Retorna a configuração singleton do projeto."""
    return Settings()
