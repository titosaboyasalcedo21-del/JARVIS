"""JARVIS Configuration - centralized management."""

import os
from pathlib import Path
from dataclasses import dataclass

@dataclass
class JarvisConfig:
    # Server
    host: str = os.getenv("JARVIS_HOST", "127.0.0.1")
    port: int = int(os.getenv("JARVIS_PORT", "8340"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # API Keys
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    fish_api_key: str = os.getenv("FISH_API_KEY", "")
    fish_voice_id: str = os.getenv("FISH_VOICE_ID", "fish-speech-1")

    # User
    user_name: str = os.getenv("USER_NAME", "Sir")

    # Weather
    weather_location: str = os.getenv("WEATHER_LOCATION", "")
    weather_timeout: float = float(os.getenv("WEATHER_TIMEOUT", "5.0"))
    weather_cache_ttl: int = int(os.getenv("WEATHER_CACHE_TTL", "1800"))

    # Paths
    ssl_certfile: str = "cert.pem"
    ssl_keyfile: str = "key.pem"
    models_dir: Path = None

    # Groq settings
    groq_max_retries: int = 3
    groq_retry_delay: float = 1.0
    groq_timeout: float = 60.0

    def __post_init__(self):
        if self.models_dir is None:
            self.models_dir = Path(__file__).parent / "models"

    def is_valid(self) -> tuple:
        """Validate configuration."""
        errors = []
        if not self.anthropic_api_key and not self.groq_api_key:
            errors.append("Either ANTHROPIC_API_KEY or GROQ_API_KEY must be set")
        if not self.fish_api_key:
            errors.append("FISH_API_KEY must be set for TTS synthesis")
        return len(errors) == 0, errors

config = JarvisConfig()