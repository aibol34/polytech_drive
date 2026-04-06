from datetime import datetime, timezone


def utcnow():
    """Naive UTC for SQLite-friendly storage and comparisons."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def album_progress(album, total_days: int = 20):
    now = utcnow()
    created = album.created_at or now
    expires = album.expires_at
    total = float(total_days or album.storage_days or 20)
    elapsed_days = max(0.0, (now - created).total_seconds() / 86400.0)
    remaining_days = 0.0
    if expires:
        remaining_days = max(0.0, (expires - now).total_seconds() / 86400.0)
    pct = min(100.0, (elapsed_days / total) * 100.0) if total else 0.0
    if expires and now >= expires:
        pct = 100.0
        remaining_days = 0.0
    return {
        "elapsed_days": int(elapsed_days),
        "remaining_days": max(0, int(remaining_days + 0.999)),
        "remaining_days_raw": remaining_days,
        "percent": round(pct, 1),
        "is_expired": bool(expires and now >= expires),
    }
