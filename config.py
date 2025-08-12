"""
Configuración para la aplicación Nannyfy
"""
import os
from typing import Optional

class Settings:
    """Configuración de la aplicación"""
    
    # API Configuration
    BUTTER_API_TOKEN: str = os.getenv("BUTTER_API_TOKEN", "")
    BUTTER_BASE_URL: str = "https://api.buttercms.com"
    BUTTER_V2: str = "/v2"
    
    # App Configuration
    APP_TITLE: str = "Nannyfy ButterCMS Bridge"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "Plataforma moderna de cuidado infantil con blog integrado"
    
    # CORS Configuration
    ALLOWED_ORIGINS: list = ["*"]
    ALLOWED_METHODS: list = ["*"]
    ALLOWED_HEADERS: list = ["*"]
    ALLOW_CREDENTIALS: bool = True
    
    # Timeouts
    REQUEST_TIMEOUT: float = 20.0
    READ_TIMEOUT: float = 30.0
    
    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = 9
    MAX_PAGE_SIZE: int = 50
    
    # Brand Configuration
    BRAND_NAME: str = "Nannyfy"
    BRAND_EMOJI: str = "🧸"
    BRAND_TAGLINE: str = "Tu plataforma de cuidado infantil de confianza"
    
    @property
    def is_production(self) -> bool:
        """Determina si estamos en producción"""
        return os.getenv("ENVIRONMENT", "development").lower() == "production"
    
    @classmethod
    def get_butter_token(cls) -> Optional[str]:
        """Obtiene el token de ButterCMS con validación"""
        token = cls.BUTTER_API_TOKEN.strip()
        return token if token else None

# Instancia global de configuración
settings = Settings()

# Validación inicial
if not settings.get_butter_token():
    import logging
    logging.warning("⚠️ BUTTER_API_TOKEN no está configurado. La aplicación puede no funcionar correctamente.")
