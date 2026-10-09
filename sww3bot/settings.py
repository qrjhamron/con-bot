"""One validated configuration for Telegram and CLI entrypoints."""
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr

MODEL = "muse-spark-1.3-contributor"
META_URL = "https://api.meta.ai/v1/chat/completions"


class Settings(BaseModel):
    model_api_key: SecretStr
    bot_user: SecretStr
    bot_pass: SecretStr
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_owner_id: int = Field(default=0, ge=0)
    game_id: int = Field(default=0, ge=0)
    player_id: int = Field(default=0, ge=0)
    db_path: str = "data/con-bot.sqlite3"
    max_rounds: int = Field(default=15, ge=1, le=100)
    max_tools: int = Field(default=30, ge=1, le=200)
    auto_interval: int = Field(default=30, ge=1)

    @classmethod
    def load(cls, telegram=False):
        load_dotenv(Path.cwd() / ".env", override=False)
        values = {
            "model_api_key": os.getenv("MODEL_API_KEY", ""),
            "bot_user": os.getenv("BOT_USER", ""),
            "bot_pass": os.getenv("BOT_PASS", ""),
            "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "telegram_owner_id": os.getenv("TELEGRAM_OWNER_ID", "0"),
            "game_id": os.getenv("GAME_ID", "0"),
            "player_id": os.getenv("PLAYER_ID", "0"),
            "db_path": os.getenv("BOT_DB_PATH", "data/con-bot.sqlite3"),
            "max_rounds": os.getenv("BOT_MAX_ROUNDS", "15"),
            "max_tools": os.getenv("BOT_MAX_TOOLS", "30"),
            "auto_interval": os.getenv("BOT_AUTO_INTERVAL", "30"),
        }
        # Validate individual fields without exposing their input in exceptions.
        try:
            settings = cls(**values)
        except ValueError:
            raise ValueError("Konfigurasi numerik tidak valid. Periksa .env.") from None
        required = ["model_api_key", "bot_user", "bot_pass"]
        if telegram:
            required.append("telegram_bot_token")
        if any(not getattr(settings, k).get_secret_value() for k in required):
            raise ValueError("Isi MODEL_API_KEY, BOT_USER, BOT_PASS dan token Telegram di .env.")
        if telegram and not settings.telegram_owner_id:
            raise ValueError("TELEGRAM_OWNER_ID wajib diisi.")
        return settings

    def redact(self, value):
        text = str(value)
        for field in (self.model_api_key, self.bot_user, self.bot_pass, self.telegram_bot_token):
            secret = field.get_secret_value()
            if secret:
                text = text.replace(secret, "[redacted]")
        return text

    def sanitize(self, value):
        """Redact before serialization, including secrets containing quotes/backslashes."""
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, dict):
            return {self.redact(k): self.sanitize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.sanitize(v) for v in value]
        if value is None or isinstance(value, (int, float, bool)):
            return value
        return self.redact(value)
