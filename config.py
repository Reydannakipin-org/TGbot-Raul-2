import json
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки для переменных окружения"""

    BOT_TOKEN: str
    SHEETS_TOKEN_FILE: str
    SHEET_ID: str
    CHAT_ID: int

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    def serialize_sheet_token_file(self):
        """Метод для преобразования файла с токеном для доступа к таблице"""
        serialize = json.loads(self.SHEETS_TOKEN_FILE)
        return serialize


config = Settings()
