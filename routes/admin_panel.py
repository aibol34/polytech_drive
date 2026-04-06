from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from googleapiclient.errors import HttpError

from extensions import db
from models import Album, Client, Notification, Photo
from services import album_service, drive_service
from utils.client_avatar import delete_avatar_file, replace_client_avatar, save_client_avatar
from utils.csrf import validate_csrf
from utils.drive_url import extract_drive_folder_id
from utils.slug import unique_slug
from utils.timefmt import album_progress

bp = Blueprint("admin_panel", __name__, template_folder="../templates")


def _flash_sync_result(added: int, msg: str | None, ok_prefix: str) -> None:
    """msg — ошибка API или информация о лимите 5000 фото."""
    if msg:
        if "лимит" in msg.lower():
            flash(f"{ok_prefix}{msg}", "success")
        else:
            flash(f"{ok_prefix}Импорт: {msg}", "error")
    else:
        flash(f"{ok_prefix}Добавлено новых фото: {added}.", "success")


@bp.route("/")
@login_required
def dashboard():
    album_service.check_expired_albums()
    albums = Album.query.order_by(Album.created_at.desc()).all()
    rows = []
    for a in albums:
        prog = album_progress(a, a.storage_days or 20)
        rows.append({"album": a, "clients": list(a.clients), "progress": prog})
    total = len(albums)
    active = sum(1 for a in albums if a.status == "active")
    expired = sum(1 for a in albums if a.status == "expired")
    unread = Notification.query.filter_by(is_read=False).count()
    notes = Notification.query.order_by(Notification.created_at.desc()).limit(20).all()
    return render_template(
        "admin/dashboard.html",
        rows=rows,
        stats={"total": total, "active": active, "expired": expired},
        unread_notifications=unread,
        notifications=notes,
    )


@bp.route("/notifications/<int:nid>/read", methods=["POST"])
@login_required
def notification_read(nid: int):
    validate_csrf()
    n = db.session.get(Notification, nid)
    if n:
        n.is_read = True
        db.session.commit()
    return redirect(request.referrer or url_for("admin_panel.dashboard"))


@bp.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    if request.method == "POST":
        validate_csrf()
        full_name = (request.form.get("full_name") or "").strip()
        if not full_name:
            flash("Укажите имя клиента.", "error")
        else:
            c = Client(full_name=full_name, whatsapp=None, instagram=None)
            db.session.add(c)
            db.session.flush()
            try:
                fn = save_client_avatar(request.files.get("avatar"), c.id)
                if fn:
                    c.avatar_filename = fn
            except ValueError as e:
                flash(str(e), "error")
            db.session.commit()
            flash("Клиент добавлен.", "success")
        return redirect(url_for("admin_panel.clients"))
    q = (request.args.get("q") or "").strip()
    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(Client.full_name.ilike(like))
    items = query.order_by(Client.created_at.desc()).all()
    return render_template("admin/clients.html", items=items, q=q)


@bp.route("/clients/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def client_edit(cid: int):
    client = db.session.get(Client, cid)
    if not client:
        abort(404)
    if request.method == "POST":
        validate_csrf()
        client.full_name = (request.form.get("full_name") or "").strip() or client.full_name
        client.whatsapp = (request.form.get("whatsapp") or "").strip() or None
        client.instagram = (request.form.get("instagram") or "").strip() or None
        if request.form.get("remove_avatar"):
            delete_avatar_file(client.avatar_filename)
            client.avatar_filename = None
        else:
            try:
                fn = replace_client_avatar(client.avatar_filename, request.files.get("avatar"), client.id)
                if fn:
                    client.avatar_filename = fn
            except ValueError as e:
                flash(str(e), "error")
        db.session.commit()
        flash("Сохранено.", "success")
        return redirect(url_for("admin_panel.clients"))
    return render_template("admin/client_edit.html", client=client)


@bp.route("/albums/new", methods=["GET", "POST"])
@login_required
def album_new():
    clients = Client.query.order_by(Client.full_name.asc()).all()
    if not clients:
        flash("Сначала добавьте клиента в разделе «Клиенты».", "error")
        return redirect(url_for("admin_panel.clients"))
    if request.method == "POST":
        validate_csrf()
        return _album_save(None, clients)
    return render_template(
        "admin/album_form.html",
        album=None,
        clients=clients,
        album_client_ids=[],
        preview_photos=[],
    )


@bp.route("/albums/<int:aid>/edit", methods=["GET", "POST"])
@login_required
def album_edit(aid: int):
    album = db.session.get(Album, aid)
    if not album:
        abort(404)
    clients = Client.query.order_by(Client.full_name.asc()).all()
    preview = Photo.query.filter_by(album_id=album.id).order_by(Photo.sort_order.asc()).limit(12).all()
    if request.method == "POST":
        validate_csrf()
        return _album_save(album, clients)
    return render_template(
        "admin/album_form.html",
        album=album,
        clients=clients,
        album_client_ids=[c.id for c in album.clients],
        preview_photos=preview,
    )


def _parse_client_ids() -> list[int]:
    out: list[int] = []
    for x in request.form.getlist("client_ids"):
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    seen: set[int] = set()
    res: list[int] = []
    for i in out:
        if i not in seen:
            seen.add(i)
            res.append(i)
    return res


def _clients_ordered(client_ids: list[int]) -> list[Client]:
    if not client_ids:
        return []
    by_id = {c.id: c for c in Client.query.filter(Client.id.in_(set(client_ids))).all()}
    return [by_id[i] for i in client_ids if i in by_id]


def _album_save(album: Album | None, clients: list):
    client_ids = _parse_client_ids()
    drive_url = (request.form.get("drive_folder_url") or "").strip()
    action = request.form.get("action") or "save"

    if not client_ids:
        flash("Выберите хотя бы одного клиента.", "error")
        return redirect(request.url)

    folder_id = extract_drive_folder_id(drive_url) if drive_url else None
    if not folder_id:
        flash("Укажите ссылку на папку Google Drive. Название альбома берётся из имени этой папки.", "error")
        return redirect(request.url)

    try:
        title = drive_service.get_folder_name(folder_id)
    except HttpError as e:
        flash(f"Google Drive: {drive_service.drive_http_error_message(e)}", "error")
        return redirect(request.url)
    except Exception as e:
        flash(f"Ошибка Google Drive: {e}", "error")
        return redirect(request.url)

    if not title:
        flash("Не удалось прочитать имя папки на Google Drive.", "error")
        return redirect(request.url)

    if action == "connect":
        try:
            imgs, _ = drive_service.list_images_in_folder(folder_id)
            if album is not None:
                flash(f"Папка «{title}» доступна. Изображений на первой странице: {len(imgs)}.", "success")
        except Exception as e:
            flash(f"Ошибка Google Drive: {e}", "error")
            return redirect(request.url)

    if album is None:
        slug = unique_slug(title)
        album = Album(
            title=title,
            slug=slug,
            drive_folder_url=drive_url or None,
            drive_folder_id=folder_id,
            storage_days=20,
            status="active",
            contact_whatsapp=None,
            contact_instagram=None,
        )
        db.session.add(album)
        db.session.flush()
        album.clients = _clients_ordered(client_ids)
        album_service.ensure_album_expiry(album)
        db.session.commit()
        if folder_id and action in ("save", "connect"):
            added, err = album_service.sync_photos_from_drive(album)
            _flash_sync_result(added, err, "Альбом создан. ")
        else:
            flash("Альбом создан.", "success")
        return redirect(url_for("admin_panel.album_edit", aid=album.id))

    album.clients = _clients_ordered(client_ids)
    album.title = title
    album.drive_folder_url = drive_url or None
    if folder_id:
        album.drive_folder_id = folder_id
    album.contact_whatsapp = None
    album.contact_instagram = None
    album.updated_at = album_service.utcnow()
    db.session.commit()

    if folder_id and action in ("save", "connect"):
        added, err = album_service.sync_photos_from_drive(album)
        _flash_sync_result(added, err, "Сохранено. ")
    else:
        flash("Сохранено.", "success")

    return redirect(url_for("admin_panel.album_edit", aid=album.id))


@bp.route("/albums/validate-drive", methods=["POST"])
@login_required
def validate_drive():
    validate_csrf()
    url = (request.form.get("drive_folder_url") or "").strip()
    folder_id = extract_drive_folder_id(url) if url else None
    if not folder_id:
        return jsonify({"ok": False, "error": "Не удалось извлечь ID папки из ссылки."}), 400
    try:
        folder_name = drive_service.get_folder_name(folder_id)
        imgs, _ = drive_service.list_images_in_folder(folder_id)
        preview = []
        for im in imgs[:8]:
            preview.append(
                {
                    "id": im.get("id"),
                    "thumb": im.get("thumbnailLink"),
                    "name": im.get("name"),
                }
            )
        return jsonify({"ok": True, "count": len(imgs), "preview": preview, "folder_name": folder_name})
    except HttpError as e:
        return jsonify({"ok": False, "error": drive_service.drive_http_error_message(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.route("/albums/<int:aid>/refresh", methods=["POST"])
@login_required
def album_refresh(aid: int):
    validate_csrf()
    album = db.session.get(Album, aid)
    if not album:
        abort(404)
    added, err = album_service.sync_photos_from_drive(album)
    _flash_sync_result(added, err, "Обновлено. ")
    return redirect(url_for("admin_panel.dashboard"))


@bp.route("/albums/<int:aid>/delete", methods=["POST"])
@login_required
def album_delete(aid: int):
    validate_csrf()
    album = db.session.get(Album, aid)
    if album:
        Notification.query.filter_by(album_id=album.id).delete(synchronize_session=False)
        Photo.query.filter_by(album_id=album.id).delete(synchronize_session=False)
        db.session.delete(album)
        db.session.commit()
        flash("Альбом удалён.", "success")
    return redirect(url_for("admin_panel.dashboard"))


@bp.route("/albums/<int:aid>/toggle-hidden", methods=["POST"])
@login_required
def album_toggle_hidden(aid: int):
    validate_csrf()
    album = db.session.get(Album, aid)
    if not album:
        abort(404)
    now = album_service.utcnow()
    exp = album.expires_at
    if exp and exp.tzinfo is None:
        from datetime import timezone

        exp = exp.replace(tzinfo=timezone.utc)
    if album.status == "hidden":
        if exp and now >= exp:
            album.status = "expired"
        else:
            album.status = "active"
    else:
        album.status = "hidden"
    album.updated_at = now
    db.session.commit()
    flash("Галерея обновлена.", "success")
    return redirect(url_for("admin_panel.dashboard"))
