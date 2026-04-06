from extensions import db
from utils.timefmt import utcnow


class Photo(db.Model):
    __tablename__ = "photos"

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"), nullable=False, index=True)
    drive_file_id = db.Column(db.String(128), nullable=False, index=True)
    filename = db.Column(db.String(512), nullable=False)
    mime_type = db.Column(db.String(128), nullable=True)
    photo_url = db.Column(db.String(1024), nullable=True)
    thumb_url = db.Column(db.String(1024), nullable=True)
    created_time_drive = db.Column(db.DateTime, nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    album = db.relationship("Album", back_populates="photos")

    __table_args__ = (db.UniqueConstraint("album_id", "drive_file_id", name="uq_photo_album_drive_file"),)
