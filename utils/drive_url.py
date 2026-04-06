import re
from urllib.parse import parse_qs, urlparse


def extract_drive_folder_id(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None
    s = url.strip()
    m = re.search(r"/folders/([a-zA-Z0-9_-]+)", s)
    if m:
        return m.group(1)
    parsed = urlparse(s)
    qs = parse_qs(parsed.query)
    if "id" in qs and qs["id"]:
        return qs["id"][0]
    if "/open" in parsed.path and "id" in qs:
        return qs["id"][0]
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", s)
    if m:
        return m.group(1)
    return None
