from extensions import db
from utils.timefmt import utcnow

from models.album import album_clients


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    whatsapp = db.Column(db.String(64), nullable=True)
    instagram = db.Column(db.String(200), nullable=True)
    avatar_filename = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    galleries = db.relationship("Album", secondary=album_clients, back_populates="clients")
