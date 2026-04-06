import os
import tempfile
import zipfile

from flask import Blueprint, abort, after_this_request, jsonify, make_response, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from config import Config
from models import Album, Photo
from services import album_service, drive_service
from utils.timefmt import album_progress

bp = Blueprint("gallery", __name__, template_folder="../templates")


@bp.route("/favicon.ico")
def favicon():
    return "", 204


@bp.route("/")
def index():
    return render_template("site/index.html")


@bp.route("/g/<slug>")
def gallery_page(slug: str):
    album = album_service.album_public_or_404(slug)
    if not album:
        abort(404)
    gallery_clients = list(album.clients)
    prog = album_progress(album, album.storage_days or 20)
    wa_links, ig_links = album_service.contact_links_for_clients(gallery_clients)
    sort = request.args.get("sort") or "new"
    if sort not in ("new", "old"):
        sort = "new"
    per = Config.PHOTOS_PER_PAGE
    q = album_service.photos_query(album.id, sort)
    total = q.count()
    photos = q.limit(per).all()
    photo_payload = []
    for p in photos:
        photo_payload.append(_photo_json(album, p))

    canonical_url = url_for("gallery.gallery_page", slug=album.slug, _external=True)
    og_image = None
    if album.cover_photo_url and str(album.cover_photo_url).startswith(("http://", "https://")):
        og_image = album.cover_photo_url
    elif photos:
        og_image = url_for(
            "media.album_media",
            album_id=album.id,
            file_id=photos[0].drive_file_id,
            _external=True,
        )
    og_title = f"{album.title} · polytech_drive"
    if gallery_clients:
        names = ", ".join(c.full_name for c in gallery_clients)
        og_description = f"{album.title} — {names}. {total} фото."
    else:
        og_description = f"{album.title} — {total} фото. Галерея polytech_drive."
    if len(og_description) > 200:
        og_description = og_description[:197] + "…"

    return render_template(
        "gallery/view.html",
        album=album,
        gallery_clients=gallery_clients,
        progress=prog,
        wa_links=wa_links,
        ig_links=ig_links,
        photos=photo_payload,
        total_photos=total,
        sort=sort,
        per_page=per,
        canonical_url=canonical_url,
        og_title=og_title,
        og_description=og_description,
        og_image=og_image,
    )


@bp.route("/g/<slug>/photos")
def gallery_photos_api(slug: str):
    album = album_service.album_public_or_404(slug)
    if not album:
        abort(404)
    page = request.args.get("page", default=1, type=int) or 1
    sort = request.args.get("sort") or "new"
    if sort not in ("new", "old"):
        sort = "new"
    per = Config.PHOTOS_PER_PAGE
    q = album_service.photos_query(album.id, sort)
    total = q.count()
    items = q.offset((page - 1) * per).limit(per).all()
    payload = [_photo_json(album, p) for p in items]
    return jsonify(
        {
            "page": page,
            "per_page": per,
            "total": total,
            "has_more": page * per < total,
            "photos": payload,
        }
    )


def _photo_json(album: Album, p: Photo) -> dict:
    full = url_for("media.album_media", album_id=album.id, file_id=p.drive_file_id)
    dl = full + "?download=1"
    thumb = p.thumb_url or full
    return {
        "id": p.id,
        "drive_file_id": p.drive_file_id,
        "filename": p.filename,
        "thumb_url": thumb,
        "full_url": full,
        "download_url": dl,
    }


@bp.route("/g/<slug>/download-all")
def download_all(slug: str):
    album = album_service.album_public_or_404(slug)
    if not album:
        abort(404)
    sort = request.args.get("sort") or "new"
    if sort not in ("new", "old"):
        sort = "new"
    q = album_service.photos_query(album.id, sort)
    photos = q.all()
    if len(photos) > Config.ZIP_MAX_FILES:
        return make_response(
            (
                f"Слишком много файлов для одного архива (>{Config.ZIP_MAX_FILES}). "
                "Скачайте фото по отдельности или обратитесь к администратору."
            ),
            413,
            {"Content-Type": "text/plain; charset=utf-8"},
        )
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    path = tf.name
    tf.close()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, p in enumerate(photos):
            data, _mime = drive_service.download_file_bytes(p.drive_file_id)
            name = secure_filename(p.filename) or f"photo-{p.id}.jpg"
            arc = f"{i + 1:04d}_{name}"
            zf.writestr(arc, data)
    base = secure_filename(album.slug) or "gallery"

    @after_this_request
    def _cleanup(resp):
        try:
            os.unlink(path)
        except OSError:
            pass
        return resp

    return send_file(
        path,
        as_attachment=True,
        download_name=f"{base}.zip",
        mimetype="application/zip",
        max_age=0,
        conditional=False,
    )
