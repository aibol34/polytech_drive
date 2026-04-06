from extensions import db
from utils.timefmt import utcnow


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"), nullable=False, index=True)
    type = db.Column(db.String(64), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    album = db.relationship("Album", back_populates="notifications")
