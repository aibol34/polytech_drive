import io
import logging
import os
import socket
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import httplib2
from dotenv import load_dotenv
from google.oauth2 import service_account
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from config import Config

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _drive_api_key() -> str:
    """Читаем ключ из окружения после повторной подгрузки .env (удобно без перезапуска после правки файла)."""
    load_dotenv(_PROJECT_ROOT / ".env", encoding="utf-8-sig", override=True)
    return (os.environ.get("GOOGLE_DRIVE_API_KEY") or "").strip()

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _http_timeout() -> int:
    return max(30, int(getattr(Config, "GOOGLE_HTTP_TIMEOUT", 120)))


def _httplib2_http() -> httplib2.Http:
    return httplib2.Http(timeout=_http_timeout())


def _should_retry_google(exc: BaseException) -> bool:
    if isinstance(exc, HttpError):
        return False
    if isinstance(exc, (ssl.SSLError, socket.timeout, TimeoutError, ConnectionAbortedError, ConnectionResetError)):
        return True
    if isinstance(exc, OSError):
        return True
    s = str(exc).lower()
    return any(x in s for x in ("handshake", "timed out", "timeout", "ssl", "connection reset", "connection aborted"))


def _execute_with_retry(request):
    """Повтор при обрыве SSL/таймаута (медленный интернет, VPN, блокировки)."""
    for attempt in range(3):
        try:
            return request.execute()
        except HttpError:
            raise
        except Exception as e:
            if attempt < 2 and _should_retry_google(e):
                wait = 2 * (attempt + 1)
                logger.warning("Google API: повтор через %ss после ошибки: %s", wait, e)
                time.sleep(wait)
                continue
            raise


def _mime_allowed(mime: str) -> bool:
    if not mime:
        return False
    m = mime.lower().strip()
    if not m.startswith("image/"):
        return False
    sub = m.split("/", 1)[1]
    return sub in ("jpeg", "jpg", "png", "webp")


def _credentials_path() -> str | None:
    p = Config.GOOGLE_SERVICE_ACCOUNT_JSON or Config.GOOGLE_APPLICATION_CREDENTIALS
    if p and os.path.isfile(p):
        return p
    return None


def get_drive_service():
    path = _credentials_path()
    http = _httplib2_http()
    if path:
        creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
        authed = AuthorizedHttp(creds, http=http)
        return build("drive", "v3", http=authed, cache_discovery=False)
    api_key = _drive_api_key()
    if api_key:
        return build("drive", "v3", developerKey=api_key, http=http, cache_discovery=False)
    raise RuntimeError(
        "Google Drive не настроен. Укажите в .env один из вариантов:\n"
        "• GOOGLE_DRIVE_API_KEY — ключ API (папки в Drive должны быть «доступны по ссылке» для просмотра);\n"
        "• GOOGLE_SERVICE_ACCOUNT_JSON — путь к JSON сервисного аккаунта (приватные папки: расшарить на email из JSON)."
    )


def _is_api_key_mode() -> bool:
    return bool(_drive_api_key()) and not _credentials_path()


def list_images_in_folder(folder_id: str, page_token: str | None = None) -> tuple[list[dict[str, Any]], str | None]:
    service = get_drive_service()
    q = f"'{folder_id}' in parents and trashed = false"
    # API key works only for publicly accessible items; shared drives need OAuth/service account.
    extra = {}
    if not _is_api_key_mode():
        extra["supportsAllDrives"] = True
        extra["includeItemsFromAllDrives"] = True
    resp = _execute_with_retry(
        service.files().list(
            q=q,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, createdTime, thumbnailLink, webContentLink, size)",
            pageToken=page_token or None,
            **extra,
        )
    )
    items = resp.get("files", [])
    images: list[dict[str, Any]] = []
    for f in items:
        mt = f.get("mimeType") or ""
        if _mime_allowed(mt):
            images.append(f)
    next_token = resp.get("nextPageToken")
    return images, next_token


def iter_all_images_in_folder(folder_id: str) -> Iterator[dict[str, Any]]:
    token = None
    while True:
        batch, token = list_images_in_folder(folder_id, token)
        for img in batch:
            yield img
        if not token:
            break


def parse_drive_datetime(iso_str: str | None):
    if not iso_str:
        return None
    s = iso_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def _download_file_bytes_once(file_id: str) -> tuple[bytes, str | None]:
    service = get_drive_service()
    meta = _files_get_meta(service, file_id)
    mime = meta.get("mimeType")
    request = _files_get_media(service, file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue(), mime


def download_file_bytes(file_id: str) -> tuple[bytes, str | None]:
    """Полная загрузка с повтором при сетевых сбоях (SSL / таймаут)."""
    for attempt in range(3):
        try:
            return _download_file_bytes_once(file_id)
        except HttpError:
            raise
        except Exception as e:
            if attempt < 2 and _should_retry_google(e):
                wait = 3 * (attempt + 1)
                logger.warning("Google API: повтор полной загрузки файла через %ss: %s", wait, e)
                time.sleep(wait)
                continue
            raise


def _files_get_meta(service, file_id: str):
    kw = {"fileId": file_id, "fields": "mimeType,name"}
    if not _is_api_key_mode():
        kw["supportsAllDrives"] = True
    return _execute_with_retry(service.files().get(**kw))


def _files_get_media(service, file_id: str):
    kw = {"fileId": file_id}
    if not _is_api_key_mode():
        kw["supportsAllDrives"] = True
    return service.files().get_media(**kw)


def stream_file_chunks(file_id: str, chunk_size: int = 256 * 1024) -> Iterator[bytes]:
    service = get_drive_service()
    request = _files_get_media(service, file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
        buf.seek(0)
        chunk = buf.read()
        buf.seek(0)
        buf.truncate(0)
        if chunk:
            yield chunk


def get_folder_name(folder_id: str) -> str | None:
    """Имя папки по ID (как в Google Drive). Для режима API key папка должна быть доступна."""
    service = get_drive_service()
    kw = {"fileId": folder_id, "fields": "name,mimeType"}
    if not _is_api_key_mode():
        kw["supportsAllDrives"] = True
    meta = _execute_with_retry(service.files().get(**kw))
    name = (meta.get("name") or "").strip()
    return name or None


def get_file_mime(file_id: str) -> str | None:
    service = get_drive_service()
    kw = {"fileId": file_id, "fields": "mimeType"}
    if not _is_api_key_mode():
        kw["supportsAllDrives"] = True
    meta = _execute_with_retry(service.files().get(**kw))
    return meta.get("mimeType")


def drive_http_error_message(exc: HttpError) -> str:
    try:
        err = getattr(exc, "error_details", None)
        if err and isinstance(err, list) and err:
            return err[0].get("message", str(exc))
    except Exception:
        pass
    return str(exc)
