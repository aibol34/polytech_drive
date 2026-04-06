import secrets

from flask import abort, request, session


def ensure_csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf() -> None:
    if request.method not in ("POST", "PUT", "DELETE"):
        return
    token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not token or token != session.get("csrf_token"):
        abort(400)
