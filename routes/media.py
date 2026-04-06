from flask import Blueprint, Response, abort, request, stream_with_context

from config import Config
from models import Album, Photo
from services import album_service, drive_service

bp = Blueprint("media", __name__)


@bp.route("/media/a/<int:album_id>/<file_id>")
def album_media(album_id: int, file_id: str):
    album = album_service.album_public_or_404_by_id(album_id)
    if not album:
        abort(404)
    photo = Photo.query.filter_by(album_id=album_id, drive_file_id=file_id).first()
    if not photo:
        abort(404)
    mime = photo.mime_type or drive_service.get_file_mime(file_id) or "application/octet-stream"

    def gen():
        try:
            for chunk in drive_service.stream_file_chunks(file_id):
                yield chunk
        except Exception:
            abort(502)

    headers = {"Cache-Control": f"public, max-age={Config.MEDIA_CACHE_SECONDS}"}
    if request.args.get("download"):
        from werkzeug.utils import secure_filename

        name = secure_filename(photo.filename) or f"photo-{photo.id}.jpg"
        headers["Content-Disposition"] = f'attachment; filename="{name}"'

    return Response(stream_with_context(gen()), mimetype=mime, headers=headers)
