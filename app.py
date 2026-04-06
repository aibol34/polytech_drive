from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from config import config_by_name
from extensions import db, login_manager
from routes import register_blueprints


def _migrate_sqlite_album_clients() -> None:
    """Связь альбом ↔ несколько клиентов: таблица album_clients и перенос из client_id."""
    try:
        from sqlalchemy import inspect, text

        insp = inspect(db.engine)
        tables = insp.get_table_names()
        if "albums" not in tables:
            return
        if "album_clients" not in tables:
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE album_clients (
                            album_id INTEGER NOT NULL,
                            client_id INTEGER NOT NULL,
                            PRIMARY KEY (album_id, client_id),
                            FOREIGN KEY (album_id) REFERENCES albums (id) ON DELETE CASCADE,
                            FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
                        )
                        """
                    )
                )
        cols = [c["name"] for c in insp.get_columns("albums")]
        if "client_id" in cols:
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO album_clients (album_id, client_id) "
                        "SELECT id, client_id FROM albums WHERE client_id IS NOT NULL"
                    )
                )
            try:
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE albums DROP COLUMN client_id"))
            except Exception:
                pass
    except Exception:
        pass


def _migrate_sqlite_client_avatar() -> None:
    """Добавляет колонку avatar_filename в существующую SQLite-БД без Alembic."""
    try:
        from sqlalchemy import inspect, text

        insp = inspect(db.engine)
        if "clients" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("clients")]
        if "avatar_filename" in cols:
            return
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE clients ADD COLUMN avatar_filename VARCHAR(512)"))
    except Exception:
        pass


def create_app(config_name: str | None = None) -> Flask:
    name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name.get(name, config_by_name["default"]))

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    register_blueprints(app)

    @app.context_processor
    def inject_helpers():
        from utils.csrf import ensure_csrf_token

        return {"csrf_token": ensure_csrf_token}

    with app.app_context():
        from models import Admin, Album, Client, Notification, Photo  # noqa: F401

        db.create_all()
        _migrate_sqlite_album_clients()
        _migrate_sqlite_client_avatar()

    @app.template_global()
    def client_avatar_url(client):
        from flask import url_for

        if not client or not getattr(client, "avatar_filename", None):
            return None
        return url_for("static", filename=f"uploads/client_avatars/{client.avatar_filename}")

    @app.cli.command("create-admin")
    def create_admin():
        """Create an admin user: flask --app app create-admin"""
        from getpass import getpass

        from models import Admin

        username = input("Username: ").strip()
        if not username:
            print("Username required.")
            return
        pw = getpass("Password: ")
        if not pw:
            print("Password required.")
            return
        if Admin.query.filter_by(username=username).first():
            print("User already exists.")
            return
        u = Admin(username=username, password_hash="x")
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        print("Admin created.")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
