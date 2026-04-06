#!/usr/bin/env python3
"""
Вставляет в конфиги nginx строку include для polytech_drive сразу после строки
server_name, где встречается aspc (aspc.kz и т.д.).

Обрабатывает sites-enabled и conf.d — чтобы include попал и в блок HTTPS после
certbot (иначе SPA с try_files отдаёт index.html вместо прокси на gunicorn).

Делает бэкап .bak_polytech перед правкой.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SNIPPET = "    include /etc/nginx/snippets/polytech_drive.conf;"
MARKER = "polytech_drive.conf"


def should_patch_line(line: str) -> bool:
    if "server_name" not in line or MARKER in line:
        return False
    return "aspc" in line.lower()


def _block_has_include(lines: list[str], start: int) -> bool:
    """Есть ли include polytech в следующих строках блока (без парсинга вложенных {})."""
    for j in range(start + 1, min(start + 22, len(lines))):
        if MARKER in lines[j]:
            return True
        if lines[j].strip().startswith("server {") and j > start + 1:
            break
    return False


def patch_file(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[str] = []
    changed = False
    for i, line in enumerate(lines):
        out.append(line)
        if should_patch_line(line) and not _block_has_include(lines, i):
            out.append(SNIPPET)
            changed = True
    if not changed:
        return False
    bak = path.with_suffix(path.suffix + ".bak_polytech")
    shutil.copy2(path, bak)
    path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
    print(f"Patched: {path} (backup: {bak})")
    return True


def _iter_nginx_config_files() -> list[Path]:
    roots = [Path("/etc/nginx/sites-enabled"), Path("/etc/nginx/conf.d")]
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for f in sorted(root.iterdir()):
            if not f.is_file():
                continue
            try:
                real = f.resolve()
            except OSError:
                continue
            out.append(real)
    return out


def main() -> int:
    candidates = _iter_nginx_config_files()
    if not candidates:
        print("No nginx config dirs (sites-enabled / conf.d)", file=sys.stderr)
        return 1
    patched = 0
    seen: set[Path] = set()
    for real in candidates:
        if real in seen:
            continue
        try:
            content = real.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"Skip {real}: {e}", file=sys.stderr)
            continue
        if "aspc" not in content.lower():
            continue
        if patch_file(real):
            seen.add(real)
            patched += 1
    if patched == 0:
        print(
            "Нет новых вставок (уже есть include или нет server_name с aspc). "
            "При необходимости добавьте вручную: " + SNIPPET.strip()
        )
    r = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    print(r.stdout + r.stderr)
    if r.returncode != 0:
        print("nginx -t failed — откатите из .bak_polytech или исправьте конфиг", file=sys.stderr)
        return r.returncode
    if patched > 0:
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
        print("nginx reloaded OK")
    else:
        print("nginx -t OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
