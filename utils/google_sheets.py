from gspread import service_account
# import re  может понадобится
from config import config



def get_sheet():
    gc = service_account(filename=config.serialize_sheet_token_file())
    worksheet = gc.open_by_key(config.SHEET_NAME)
    return worksheet
