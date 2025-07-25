import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()


SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
SCOPES = [os.getenv("GOOGLE_DRIVE_SCOPES", "https://www.googleapis.com/auth/drive.file")]

def upload_file_to_drive(filepath: str, filename: str, mimetype: str = 'image/jpeg', folder_id: str = None) -> str:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=credentials, cache_discovery=False)

    file_metadata = {'name': filename}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(filepath, mimetype=mimetype)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    # Делаем файл доступным по ссылке
    service.permissions().create(
        fileId=file['id'],
        body={'role': 'reader', 'type': 'anyone'},
    ).execute()

    return file['id']
