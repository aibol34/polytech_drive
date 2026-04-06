from datetime import timedelta

from extensions import db
from utils.timefmt import utcnow

album_clients = db.Table(
    "album_clients",
    db.Column("album_id", db.Integer, db.ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True),
    db.Column("client_id", db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
)


class Album(db.Model):
    __tablename__ = "albums"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(320), unique=True, nullable=False, index=True)
    drive_folder_url = db.Column(db.String(1024), nullable=True)
    drive_folder_id = db.Column(db.String(128), nullable=True, index=True)
    cover_photo_url = db.Column(db.String(1024), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active", index=True)
    storage_days = db.Column(db.Integer, nullable=False, default=20)
    contact_whatsapp = db.Column(db.String(64), nullable=True)
    contact_instagram = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    clients = db.relationship(
        "Client",
        secondary=album_clients,
        back_populates="galleries",
        order_by="Client.full_name",
    )
    photos = db.relationship("Photo", back_populates="album", lazy="dynamic", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="album", lazy="dynamic")

    def ensure_expires_at(self) -> None:
        if self.expires_at is None and self.created_at:
            self.expires_at = self.created_at + timedelta(days=int(self.storage_days or 20))
