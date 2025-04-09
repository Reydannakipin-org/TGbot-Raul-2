from pprint import pprint
import json
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    SHEETS_TOKEN_FILE: str
    SHEET_NAME: str

    model_config = SettingsConfigDict(env_file='.env')

    def serialize_sheet_token_file(self):
        serialize = json.loads(self.SHEETS_TOKEN_FILE)
        return serialize


config = Settings()
