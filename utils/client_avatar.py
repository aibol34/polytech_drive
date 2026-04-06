from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 5 * 1024 * 1024


def _upload_dir() -> Path:
    return Path(current_app.root_path) / "static" / "uploads" / "client_avatars"


def ensure_upload_dir() -> None:
    _upload_dir().mkdir(parents=True, exist_ok=True)


def save_client_avatar(upload: FileStorage | None, client_id: int) -> str | None:
    """Сохраняет файл; возвращает имя файла для БД или None. ValueError при неверном формате."""
    if not upload or not upload.filename:
        return None
    raw = secure_filename(upload.filename)
    if not raw:
        raise ValueError("Некорректное имя файла.")
    ext = Path(raw).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Аватар: допустимы JPG, PNG, WEBP.")
    ensure_upload_dir()
    fname = f"{client_id}{ext}"
    path = _upload_dir() / fname
    upload.save(str(path))
    if path.stat().st_size > MAX_BYTES:
        try:
            path.unlink()
        except OSError:
            pass
        raise ValueError("Аватар: файл больше 5 МБ.")
    return fname


def delete_avatar_file(filename: str | None) -> None:
    if not filename:
        return
    p = _upload_dir() / filename
    try:
        if p.is_file():
            p.unlink()
    except OSError:
        pass


def replace_client_avatar(old_filename: str | None, upload: FileStorage | None, client_id: int) -> str | None:
    """Новый файл; старый удаляется, если имя изменилось (другой формат)."""
    fn = save_client_avatar(upload, client_id)
    if fn and old_filename and old_filename != fn:
        delete_avatar_file(old_filename)
    return fn
