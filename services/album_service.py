from datetime import timedelta

from sqlalchemy import asc, desc

from config import Config
from extensions import db
from models import Album, Client, Notification, Photo
from services import drive_service
from utils.timefmt import utcnow


def check_expired_albums() -> int:
    now = utcnow()
    changed = 0
    q = Album.query.filter(Album.status == "active", Album.expires_at.isnot(None), Album.expires_at < now)
    for album in q.all():
        album.status = "expired"
        album.updated_at = utcnow()
        exists = Notification.query.filter_by(album_id=album.id, type="storage_expired").first()
        if not exists:
            db.session.add(
                Notification(
                    album_id=album.id,
                    type="storage_expired",
                    message=f"Срок хранения альбома «{album.title}» истёк.",
                    is_read=False,
                )
            )
        changed += 1
    if changed:
        db.session.commit()
    return changed


def ensure_album_expiry(album: Album) -> None:
    if album.expires_at is None:
        base = album.created_at or utcnow()
        album.expires_at = base + timedelta(days=int(album.storage_days or 20))
        album.updated_at = utcnow()


def sync_photos_from_drive(album: Album) -> tuple[int, str | None]:
    if not album.drive_folder_id:
        return 0, "Не указан ID папки Google Drive."
    max_p = max(1, int(getattr(Config, "MAX_PHOTOS_PER_ALBUM", 5000)))
    try:
        existing_ids = {p.drive_file_id for p in Photo.query.filter_by(album_id=album.id).all()}
        added = 0
        current_total = len(existing_ids)
        hit_limit = False
        max_sort = db.session.query(db.func.max(Photo.sort_order)).filter_by(album_id=album.id).scalar() or 0
        for f in drive_service.iter_all_images_in_folder(album.drive_folder_id):
            if current_total >= max_p:
                hit_limit = True
                break
            fid = f.get("id")
            if not fid or fid in existing_ids:
                continue
            ct = drive_service.parse_drive_datetime(f.get("createdTime"))
            thumb = f.get("thumbnailLink")
            if thumb and "=" in thumb:
                thumb = thumb.split("=")[0] + "=s400"
            max_sort += 1
            photo = Photo(
                album_id=album.id,
                drive_file_id=fid,
                filename=f.get("name") or f"photo-{fid}.jpg",
                mime_type=f.get("mimeType"),
                photo_url=None,
                thumb_url=thumb,
                created_time_drive=ct,
                sort_order=max_sort,
            )
            db.session.add(photo)
            existing_ids.add(fid)
            added += 1
            current_total += 1
        if not album.cover_photo_url:
            first = (
                Photo.query.filter_by(album_id=album.id)
                .order_by(desc(Photo.created_time_drive), desc(Photo.id))
                .first()
            )
            if first and first.thumb_url:
                album.cover_photo_url = first.thumb_url
        album.updated_at = utcnow()
        db.session.commit()
        note = None
        if hit_limit:
            note = f"Достигнут лимит {max_p} фото в альбоме. Остальные файлы из папки не импортированы."
        return added, note
    except Exception as e:
        db.session.rollback()
        return 0, str(e)


def photos_query(album_id: int, sort: str):
    q = Photo.query.filter_by(album_id=album_id)
    if sort == "old":
        return q.order_by(asc(Photo.created_time_drive), asc(Photo.id))
    return q.order_by(desc(Photo.created_time_drive), desc(Photo.id))


def album_public_or_404(slug: str) -> Album | None:
    check_expired_albums()
    album = Album.query.filter_by(slug=slug).first()
    if not album or album.status == "hidden":
        return None
    return album


def album_public_or_404_by_id(album_id: int) -> Album | None:
    check_expired_albums()
    album = db.session.get(Album, album_id)
    if not album or album.status == "hidden":
        return None
    return album


def resolve_whatsapp(client: Client | None) -> str | None:
    """Только из карточки клиента — для всех галерей одно и то же."""
    if client and client.whatsapp:
        return client.whatsapp.strip()
    return None


def resolve_instagram(client: Client | None) -> str | None:
    """Только из карточки клиента — для всех галерей одно и то же."""
    if client and client.instagram:
        return client.instagram.strip()
    return None


def instagram_url(handle: str) -> str:
    if not handle:
        return ""
    h = handle.strip().lstrip("@")
    if not h:
        return ""
    if h.startswith("http"):
        return h
    return f"https://instagram.com/{h}"


def whatsapp_url(phone: str) -> str:
    if not phone:
        return ""
    p = phone.strip()
    if p.lower().startswith("http"):
        return p
    digits = "".join(c for c in p if c.isdigit() or c == "+")
    if not digits:
        return ""
    if digits.startswith("+"):
        num = digits[1:].replace("+", "")
    else:
        num = digits
    return f"https://wa.me/{num}"


def contact_links_for_clients(clients: list[Client]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Кнопки контактов по клиентам; одинаковые URL не дублируются."""
    wa_items: list[dict[str, str]] = []
    ig_items: list[dict[str, str]] = []
    seen_wa: set[str] = set()
    seen_ig: set[str] = set()
    for c in clients:
        wa = resolve_whatsapp(c)
        if wa:
            url = whatsapp_url(wa)
            if url and url not in seen_wa:
                seen_wa.add(url)
                wa_items.append({"label": c.full_name, "url": url})
        ig = resolve_instagram(c)
        if ig:
            url = instagram_url(ig)
            if url and url not in seen_ig:
                seen_ig.add(url)
                ig_items.append({"label": c.full_name, "url": url})
    return wa_items, ig_items
