from gspread import Client
from config import config
from oauth2client.service_account import ServiceAccountCredentials


def get_sheet():
    """Функция для подключения к Google Sheets к config.SHEET_ID"""
    scopes = [
        'https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive'
    ]
    gc = Client(auth=ServiceAccountCredentials.from_json_keyfile_dict(
        config.serialize_sheet_token_file(), scopes)
    )
    worksheet = gc.open_by_key(config.SHEET_ID)
    print('Соединение с Google Sheets установлено')
    return worksheet










