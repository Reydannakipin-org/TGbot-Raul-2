from gspread import Client
# import re  может понадобится
from config import config
from oauth2client.service_account import ServiceAccountCredentials



def get_sheet():
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    googleclient = ServiceAccountCredentials.from_json_keyfile_dict(config.serialize_sheet_token_file(), scopes)
    gc = Client(auth=googleclient)
    try:
        wrks = gc.open_by_key(config.SHEET_ID).worksheet('Лист1')
        print('Соединение с Google Sheets установлено')
        return wrks
    except Exception as e:
        print(f'Ошибка соединения с Google Sheets: {e}')







