# /var/www/arcade/server.py

from __future__ import annotations

import asyncio
import html as html_module
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess
import sys
from collections import deque
from contextlib import asynccontextmanager
import multiprocessing as mp
from multiprocessing import Queue
from pathlib import Path
from queue import Empty
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, Response

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from arcade_remote_worker import remote_game_main
LOG_DIR = BASE_DIR / "logs"
ERROR_LOG_FILE = LOG_DIR / "arcade-error.log"

GAMES_DIR = Path(
    os.environ.get("ARCADE_GAMES_DIR", str(BASE_DIR / "games"))
).resolve()

# Lobby metadata: ``repo_url``, ``sync_url``, optional ``start_script``, ``creator``, ``title``.
GAMES_CATALOG_PATH = Path(
    os.environ.get("ARCADE_GAMES_CATALOG", str(BASE_DIR / "games_catalog.json"))
).resolve()

# Shown on the lobby info panel (mailto link).
ARCADE_MAINTAINER_EMAIL = "luda1266@outlook.cz"

# Written by sync_one_repo when you use URL:entry (e.g. .../Projekt:hra or ...:základ hry)
ARCADE_ENTRY_MARKER = ".arcade-entry"

_GITHUB_SYNC_ENTRY_RE = re.compile(
    r"^(https?://(?:www\.)?github\.com/[\w.-]+/[\w.-]+)(?:\.git)?:(.+)\s*$",
    re.IGNORECASE,
)

def _is_safe_entry_segment(seg: str) -> bool:
    """Single path segment: no separators, no traversal."""
    if not seg or seg in (".", ".."):
        return False
    if "/" in seg or "\\" in seg or "\x00" in seg:
        return False
    return True


def _compact_entry_name_key(name: str) -> str:
    """Compare names ignoring case and all whitespace (``Pstros.py`` vs ``Pstros .py``)."""
    return "".join(name.lower().split())


def _normalize_sync_entry_suffix(suffix: str) -> str:
    """
    Normalize the part after ``:`` to a repo-relative path (POSIX ``/``).
    Final segment may be ``hra``, ``hra.py``, ``základ hry``, Unicode, spaces, etc.
    Resolution tries the exact name, then ``<name>.py`` when the name has no ``.py`` suffix.
    Rejects ``..`` and absolute-style segments.
    """
    raw = suffix.strip().replace("\\", "/")
    if not raw:
        raise ValueError("Empty entry path after ':' in sync URL")
    parts = [p for p in raw.split("/") if p]
    if not parts:
        raise ValueError(f"Invalid entry path: {suffix!r}")
    for p in parts:
        if not _is_safe_entry_segment(p):
            raise ValueError(f"Invalid entry path segment in {suffix!r}")
    return "/".join(parts)


def _entry_names_match(want: str, actual: str, *, is_dir: bool) -> bool:
    if want == actual:
        return True
    if want.lower() == actual.lower():
        return True
    if _compact_entry_name_key(want) == _compact_entry_name_key(actual):
        return True
    return False


def _find_entry_child(cur: Path, want: str, *, need_dir: bool) -> Optional[Path]:
    """Pick a child of ``cur`` whose name matches ``want`` (exact, case, or whitespace-tolerant)."""
    try:
        entries = list(cur.iterdir())
    except OSError:
        return None
    direct = cur / want
    try:
        if need_dir and direct.is_dir():
            return direct.resolve()
        if not need_dir and direct.is_file():
            return direct.resolve()
    except OSError:
        pass
    pool = [e for e in entries if e.is_dir()] if need_dir else [e for e in entries if e.is_file()]
    matches = [e for e in pool if _entry_names_match(want, e.name, is_dir=need_dir)]
    if not matches:
        return None
    matches.sort(key=lambda p: p.name.lower())
    return matches[0].resolve()


def _find_entry_file_optional_py(cur: Path, want: str) -> Optional[Path]:
    """
    Resolve a file under ``cur``: try ``want``, then ``want + ".py"`` if ``want`` does not
    already end with ``.py`` (case-insensitive).
    """
    found = _find_entry_child(cur, want, need_dir=False)
    if found is not None:
        return found
    if not want.lower().endswith(".py"):
        return _find_entry_child(cur, want + ".py", need_dir=False)
    return None


def _resolve_repo_entry_file(dest: Path, parts: List[str]) -> Tuple[Optional[Path], str]:
    """
    Resolve ``parts`` under ``dest`` to an existing file. Directories and the final
    filename may differ by case or internal spaces from the clone; the last segment may
    be extensionless or ``.py``.
    Returns (absolute_path, posix_rel_from_dest) or (None, "").
    """
    root = dest.resolve()
    cur = root
    for seg in parts[:-1]:
        nxt = _find_entry_child(cur, seg, need_dir=True)
        if nxt is None:
            return None, ""
        cur = nxt
    want_name = parts[-1]
    found = _find_entry_file_optional_py(cur, want_name)
    if found is None:
        return None, ""
    try:
        rel = str(found.relative_to(root)).replace("\\", "/")
    except ValueError:
        return None, ""
    return found, rel


def parse_github_sync_spec(raw: str) -> Tuple[str, Optional[str]]:
    """
    Split a sync line into (repo_url_for_git, optional_entry_relative_path).

    Optional suffix after the GitHub repo path:

    - Root script: ``https://github.com/stiburekf25/Projekt:hra`` or ``…:hra.py`` or ``…:základ hry``
    - Nested script: ``https://github.com/lorencm25/Pstros:source/Pstros`` or ``…:source/Pstros.py``
    """
    s = raw.strip()
    if not s:
        return s, None
    m = _GITHUB_SYNC_ENTRY_RE.match(s.split("#", 1)[0].strip())
    if m:
        base = m.group(1).rstrip("/")
        if base.lower().endswith(".git"):
            base = base[:-4]
        ent = _normalize_sync_entry_suffix(m.group(2))
        return _normalize_repo_url(base), ent
    return _normalize_repo_url(s.split("#", 1)[0].strip()), None


def _read_arcade_entry_override(game_root: Path) -> Optional[Path]:
    """If .arcade-entry exists, use that path (repo-relative, POSIX ``/``) under game_root."""
    marker = game_root / ARCADE_ENTRY_MARKER
    if not marker.is_file():
        return None
    try:
        text = marker.read_text(encoding="utf-8")
        line = text.strip().splitlines()[0].strip() if text.strip() else ""
    except OSError:
        return None
    if not line or ".." in line:
        return None
    line = line.replace("\\", "/")
    parts = [p for p in line.split("/") if p]
    if not parts:
        return None
    for p in parts:
        if not _is_safe_entry_segment(p):
            return None
    root = game_root.resolve()
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    found, _ = _resolve_repo_entry_file(game_root, parts)
    return found


# Skip when searching subfolders for main.py / index.py (Tower_defense: slozka_hry/main.py, etc.)
_ENTRY_SCRIPT_SUBDIR_SKIP = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        "build",
        "web-cache",
        "ignore",
        ".github",
        ".idea",
        "dist",
        "tests",
        "test",
    }
)


def _find_entry_script_in_subfolders(
    game_root: Path, *, max_depth: int = 5
) -> Optional[Path]:
    """
    Breadth-first search under game_root (not including the root itself) for
    directories containing main.py, then (if none) index.py.

    Prefer the shallowest depth; if several candidates share that depth, return
    None (ambiguous). Skips typical non-game folders.
    """
    root = game_root.resolve()
    if not root.is_dir():
        return None

    def scan_for(
        basename: str,
    ) -> Optional[Path]:
        found: List[Tuple[int, Path]] = []
        q: deque[Tuple[Path, int]] = deque()
        try:
            for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
                if (
                    child.is_dir()
                    and not child.name.startswith(".")
                    and child.name not in _ENTRY_SCRIPT_SUBDIR_SKIP
                ):
                    q.append((child, 1))
        except OSError:
            return None
        while q:
            dpath, depth = q.popleft()
            try:
                candidate = (dpath / basename).resolve()
                if candidate.is_file():
                    try:
                        candidate.relative_to(root)
                    except ValueError:
                        pass
                    else:
                        found.append((depth, candidate))
                if depth < max_depth:
                    for sub in sorted(dpath.iterdir(), key=lambda p: p.name.lower()):
                        if (
                            sub.is_dir()
                            and not sub.name.startswith(".")
                            and sub.name not in _ENTRY_SCRIPT_SUBDIR_SKIP
                        ):
                            q.append((sub, depth + 1))
            except OSError:
                continue
        if not found:
            return None
        min_d = min(d for d, _ in found)
        at_min = sorted({p for d, p in found if d == min_d})
        if len(at_min) == 1:
            return at_min[0]
        return None

    main_hit = scan_for("main.py")
    if main_hit is not None:
        return main_hit
    return scan_for("index.py")


def resolve_game_entry_script(game_root: Path) -> Optional[Path]:
    """
    Pick the Python entry file for a server-run game directory:
    .arcade-entry (from sync ``URL:script`` or ``URL:dir/script``) if present and valid,
    else main.py, else index.py at repo root, else the only *.py file at the repo root,
    else main.py / index.py in a subfolder (bounded depth search; unique match).
    """
    root = game_root.resolve()
    if not root.is_dir():
        return None
    pinned = _read_arcade_entry_override(root)
    if pinned is not None:
        return pinned
    main_py = (root / "main.py").resolve()
    if main_py.is_file():
        return main_py
    index_py = (root / "index.py").resolve()
    if index_py.is_file():
        return index_py
    py_files = sorted(
        p.resolve()
        for p in root.iterdir()
        if p.is_file() and p.suffix.lower() == ".py"
    )
    if len(py_files) == 1:
        return py_files[0]
    return _find_entry_script_in_subfolders(root)


def get_game_scripts() -> Dict[str, Path]:
    """Each games/<folder>/ with a resolvable entry script → slug (folder name) → path.

    Play URL for slug ``foo`` is ``/foo/``. WebSocket: prefer ``/play-ws/foo`` (avoids nginx
    ``^~ /foo/`` blocks stealing ``/foo/ws``); ``/foo/ws`` is also supported.
    """
    out: Dict[str, Path] = {}
    if not GAMES_DIR.is_dir():
        return out
    try:
        entries = sorted(GAMES_DIR.iterdir())
    except OSError as e:
        logger.warning("Cannot list games directory %s: %s", GAMES_DIR, e)
        return out
    for d in entries:
        try:
            if not d.is_dir() or d.name.startswith("."):
                continue
        except OSError:
            continue
        try:
            entry = resolve_game_entry_script(d)
        except OSError:
            continue
        try:
            if entry is not None and entry.is_file():
                out[d.name] = entry
        except OSError:
            continue
    return out


_TEXTURE_FILE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
_SOUND_FILE_SUFFIXES = frozenset(
    {".wav", ".ogg", ".opus", ".mp3", ".flac", ".m4a", ".aac"}
)
_TEXTURE_MANIFEST_SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        "build",
        "web-cache",
        "ignore",
    }
)


def _native_remote_game_root(slug: str) -> Optional[Path]:
    entry = get_game_scripts().get(slug)
    if entry is None or not entry.is_file():
        return None
    return entry.parent.resolve()


def _game_files_public_url(slug: str, rel_posix: str) -> str:
    enc = "/".join(quote(p, safe="") for p in rel_posix.split("/") if p)
    return f"/{quote(slug, safe='')}/files/{enc}"


def _native_texture_manifest(slug: str) -> Dict[str, Any]:
    root = _native_remote_game_root(slug)
    if root is None:
        raise HTTPException(status_code=404, detail="Native remote game not found")
    textures: List[Dict[str, str]] = []
    sounds: List[Dict[str, str]] = []
    seen_tex: set[str] = set()
    seen_snd: set[str] = set()
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        suf = f.suffix.lower()
        if suf not in _TEXTURE_FILE_SUFFIXES and suf not in _SOUND_FILE_SUFFIXES:
            continue
        try:
            rel_path = f.relative_to(root)
        except ValueError:
            continue
        parts = rel_path.parts
        if parts and parts[0] in _TEXTURE_MANIFEST_SKIP_DIRS:
            continue
        if any(p in _TEXTURE_MANIFEST_SKIP_DIRS for p in parts):
            continue
        rel = rel_path.as_posix()
        if suf in _TEXTURE_FILE_SUFFIXES:
            if rel in seen_tex:
                continue
            seen_tex.add(rel)
            textures.append({"id": rel, "url": _game_files_public_url(slug, rel)})
        else:
            if rel in seen_snd:
                continue
            seen_snd.add(rel)
            sounds.append({"id": rel, "url": _game_files_public_url(slug, rel)})
    return {"v": 2, "slug": slug, "textures": textures, "sounds": sounds}

ARCADE_REMOTE_MAX_FRAME_WIDTH = int(os.environ.get("ARCADE_REMOTE_MAX_FRAME_WIDTH", "720"))

# "spawn" avoids fork + SDL/pygame in the child (common cause of instant exit / 410 on first frame).
_MP_CTX = mp.get_context("spawn")


def _start_native_game_process(
    main_py: Path,
    record_wh: Optional[Tuple[int, int]] = None,
) -> Tuple[mp.Process, Queue, Queue]:
    frame_q: Queue = _MP_CTX.Queue(maxsize=1)
    cmd_q: Queue = _MP_CTX.Queue()
    proc = _MP_CTX.Process(
        target=remote_game_main,
        args=(
            str(main_py.resolve()),
            frame_q,
            cmd_q,
            ARCADE_REMOTE_MAX_FRAME_WIDTH,
            record_wh,
        ),
    )
    proc.start()
    return proc, frame_q, cmd_q


def _cleanup_native_process(proc: mp.Process, cmd_q: Queue) -> None:
    try:
        cmd_q.put({"t": "quit"})
    except Exception:
        pass
    proc.join(timeout=2.0)
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=1.5)


def _setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        root.addHandler(sh)

    abs_err = ERROR_LOG_FILE.resolve()

    def _already_logging_errors_to_file() -> bool:
        for h in root.handlers:
            if isinstance(h, logging.handlers.RotatingFileHandler):
                bn = getattr(h, "baseFilename", None)
                if bn and Path(bn).resolve() == abs_err:
                    return True
        return False

    if _already_logging_errors_to_file():
        return
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        fh.setLevel(logging.ERROR)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as e:
        print(f"arcade: cannot open error log {ERROR_LOG_FILE}: {e}", file=sys.stderr)


_setup_logging()
logger = logging.getLogger("arcade")

# Tells browsers and CDNs (e.g. Cloudflare) not to reuse stale lobby/play pages.
ARCADE_HTTP_CACHE_CONTROL = os.environ.get(
    "ARCADE_HTTP_CACHE_CONTROL",
    "private, no-cache, no-store, max-age=0, must-revalidate",
)


def _cache_headers() -> dict[str, str]:
    return {"Cache-Control": ARCADE_HTTP_CACHE_CONTROL}


# Game PNG/JPEG/etc. can be cached aggressively; URLs are stable per file path.
ARCADE_GAME_FILE_CACHE_CONTROL = os.environ.get(
    "ARCADE_GAME_FILE_CACHE_CONTROL",
    "public, max-age=604800, stale-while-revalidate=86400",
)
# Manifest lists current textures; shorter cache so new assets show up without waiting days.
ARCADE_TEXTURE_MANIFEST_CACHE_CONTROL = os.environ.get(
    "ARCADE_TEXTURE_MANIFEST_CACHE_CONTROL",
    "public, max-age=120, stale-while-revalidate=600",
)


def _game_file_cache_headers() -> dict[str, str]:
    return {"Cache-Control": ARCADE_GAME_FILE_CACHE_CONTROL}


def _texture_manifest_cache_headers() -> dict[str, str]:
    return {"Cache-Control": ARCADE_TEXTURE_MANIFEST_CACHE_CONTROL}


def _lobby_headers() -> dict[str, str]:
    """Stronger no-cache for HTML lobby (some proxies ignore Cache-Control alone)."""
    h = dict(_cache_headers())
    h["Pragma"] = "no-cache"
    h["Expires"] = "0"
    return h


def _default_lobby_title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def load_games_catalog() -> Dict[str, Dict[str, Any]]:
    """Per-folder display metadata (see GAMES_CATALOG_PATH)."""
    if not GAMES_CATALOG_PATH.is_file():
        return {}
    try:
        raw = json.loads(GAMES_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Cannot read %s: %s", GAMES_CATALOG_PATH, e)
        return {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, dict):
            out[k] = v
    return out


def _record_surface_size_from_catalog(slug: str) -> Optional[Tuple[int, int]]:
    """
    Optional games_catalog.json key ``record_surface_size`` (or ``arcade_record_surface_size``):
    \"WxH\" e.g. \"1280x720\". Matches the game's main off-screen buffer size so
    pygame.draw/blit on that surface are streamed; otherwise only display-sized
    blits are recorded and may collapse to a single averaged-color rectangle.
    """
    meta = load_games_catalog().get(slug)
    if not isinstance(meta, dict):
        return None
    raw = meta.get("record_surface_size") or meta.get("arcade_record_surface_size")
    if not isinstance(raw, str):
        return None
    s = raw.replace(",", "x").replace("*", "x")
    parts = [p.strip() for p in s.split("x") if p.strip()]
    if len(parts) < 2:
        return None
    try:
        w, h = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if w < 1 or h < 1 or w > 8192 or h > 8192:
        return None
    return (w, h)


def save_games_catalog(catalog: Dict[str, Dict[str, Any]]) -> None:
    """Write catalog atomically (indent for hand-editing)."""
    GAMES_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    tmp = GAMES_CATALOG_PATH.with_suffix(GAMES_CATALOG_PATH.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(GAMES_CATALOG_PATH)


def canonical_github_repo_page_url(owner: str, repo: str) -> str:
    """Stable https://github.com/owner/repo (no .git) for the catalog."""
    return f"https://github.com/{owner}/{repo}"


def posix_py_path_to_start_script_suffix(rel_posix: str) -> str:
    """
    Repo-relative path → sync URL ``:suffix``: ``.py`` stripped from the final segment
    only when present (extensionless names are kept as-is).
    """
    s = rel_posix.strip().replace("\\", "/")
    parts = [p for p in s.split("/") if p]
    if not parts:
        return ""
    last = parts[-1]
    if last.lower().endswith(".py"):
        last = last[:-3]
    parts[-1] = last
    return "/".join(parts)


def _catalog_start_script_from_game_dir(
    game_root: Path, url_entry_normalized: Optional[str]
) -> Optional[str]:
    """``:suffix`` for ``sync_repos.py`` / ``sync_url``, or ``None`` for default main/index."""
    if url_entry_normalized and url_entry_normalized.strip():
        suf = posix_py_path_to_start_script_suffix(url_entry_normalized.strip())
        return suf if suf else None
    marker = game_root / ARCADE_ENTRY_MARKER
    if not marker.is_file():
        return None
    try:
        text = marker.read_text(encoding="utf-8")
        line = text.strip().splitlines()[0].strip() if text.strip() else ""
    except OSError:
        return None
    if not line or ".." in line:
        return None
    suf = posix_py_path_to_start_script_suffix(line.replace("\\", "/"))
    return suf if suf else None


def record_synced_game_catalog_meta(
    github_owner: str,
    slug: str,
    *,
    repo_url: str,
    start_script: Optional[str] = None,
) -> None:
    """Set ``repo_url``, ``sync_url``, optional ``start_script``, ``creator``; ``title`` if unset."""
    catalog = load_games_catalog()
    prev = catalog.get(slug)
    entry: Dict[str, Any] = dict(prev) if isinstance(prev, dict) else {}
    ru = _normalize_repo_url(repo_url)
    entry["repo_url"] = ru
    if start_script and start_script.strip():
        ss = start_script.strip()
        entry["start_script"] = ss
        entry["sync_url"] = f"{ru}:{ss}"
    else:
        entry.pop("start_script", None)
        entry["sync_url"] = ru
    entry["creator"] = f"@{github_owner}"
    auto_title = _default_lobby_title_from_slug(slug)
    prev_title = entry.get("title")
    if not (isinstance(prev_title, str) and prev_title.strip()):
        entry["title"] = auto_title
    catalog[slug] = entry
    try:
        save_games_catalog(catalog)
    except OSError as e:
        logger.warning("Could not write %s: %s", GAMES_CATALOG_PATH, e)


def list_games() -> List[Dict[str, Any]]:
    games: List[Dict[str, Any]] = []
    catalog = load_games_catalog()
    for slug, entry in sorted(get_game_scripts().items()):
        if entry.is_file():
            meta = catalog.get(slug) or {}
            title_raw = meta.get("title")
            if isinstance(title_raw, str) and title_raw.strip():
                title = title_raw.strip()
            else:
                title = _default_lobby_title_from_slug(slug)
            creator_raw = meta.get("creator")
            creator = (
                creator_raw.strip()
                if isinstance(creator_raw, str) and creator_raw.strip()
                else None
            )
            games.append(
                {
                    "name": slug,
                    "title": title,
                    "creator": creator,
                    "path": f"/{quote(slug, safe='')}/",
                }
            )
    return games


def _lobby_card_html(g: Dict[str, Any]) -> str:
    sub = ""
    if g.get("creator"):
        sub = (
            f'\n          <div class="sub">{html_module.escape(g["creator"])}</div>'
        )
    return f"""        <a class="card" href="{html_module.escape(g["path"], quote=True)}">
          <div class="title">{html_module.escape(g["title"])}</div>{sub}
        </a>"""


def _lobby_info_section_html() -> str:
    email = ARCADE_MAINTAINER_EMAIL
    contact_html = html_module.escape(email)
    mailto_href = html_module.escape(f"mailto:{email}", quote=True)
    contact_block = (
        f"<p>If a game misbehaves (textures, sound, buttons, or anything else), if you have updated your "
        f"project, or you would like a new game added here, contact me at "
        f'<strong><a class="lobby-contact" href="{mailto_href}">{contact_html}</a></strong> '
        f"and I will try to fix it or set it up.</p>"
    )
    return f"""  <section class="lobby-info" aria-label="About this arcade">
    <p>We aim to run every game at the best quality we can and to keep it working in the browser. Python does not run natively in the browser, so these games execute on the server and you see them through a custom page that draws to an HTML canvas and streams video-style frames over a live WebSocket. Because of that stack, a game might not load, might look or feel wrong, or might differ from how it runs on your own PC. A slow or unstable connection can also cause lag or disconnects.</p>
    <p>Your game files are not edited for the arcade: they stay exactly as in the repository. We only use a thin compatibility layer so the same Python code can drive what you see and hear in the browser, without converting the project into a separate hand-written HTML or JavaScript game.</p>
{contact_block}  </section>
"""


def render_arcade_home_html() -> str:
    """Server-rendered lobby page (no embedded JavaScript)."""
    games = list_games()
    if games:
        hint_html = ""
        cards = "\n".join(_lobby_card_html(g) for g in games)
        grid_inner = cards
    else:
        status = (
            "No games yet. Run <code>python3 sync_repos.py https://github.com/owner/repo</code> "
            "— or <code>…/repo:your_game</code> / <code>…/repo:folder/game.py</code> when the entry is not main/index "
            "(names may include spaces and Unicode; <code>.py</code> is optional). "
            "Otherwise each <code>games/&lt;slug&gt;/</code> folder needs <code>main.py</code> or "
            "<code>index.py</code> at the root or in one subfolder (e.g. <code>slozka_hry/main.py</code>), "
            "or a single root <code>.py</code>."
        )
        hint_html = f'  <p class="hint">{html_module.escape(status)}</p>\n'
        grid_inner = (
            '        <div class="hint">Multi-file repos: <code>sync_repos.py …/Projekt:hra</code> '
            "writes <code>.arcade-entry</code>. Textures: optional <code>assets/</code> or images in the tree.</div>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"/>
  <meta http-equiv="Pragma" content="no-cache"/>
  <title>Arcade</title>
  <style>
    body {{ font-family: system-ui, Arial, sans-serif; margin: 24px; background: #0b0f1a; color: #e8eefc; }}
    h1 {{ margin: 0 0 16px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }}
    .card {{ display:block; padding: 14px; border-radius: 14px; background: #121a2c;
            text-decoration:none; color:inherit; border:1px solid #1f2a44; }}
    .card:hover {{ border-color:#2f7cff; }}
    .title {{ font-weight: 800; font-size: 18px; }}
    .card .sub {{ font-size: 13px; opacity: .72; margin-top: 6px; font-weight: 500; }}
    p {{ margin: 10px 0 0; opacity: .9; font-size: 13px; }}
    .hint {{ opacity: .8; font-size: 13px; margin-top: 8px; }}
    code {{ background:#0e1526; padding:2px 6px; border-radius:8px; }}
    .lobby-info {{ max-width: 52rem; margin: 22px auto 0; padding: 14px 16px; border-radius: 12px;
      background: #0e1526; border: 1px solid #1f2a44; font-size: 13px; line-height: 1.55; color: #c5d0e8; }}
    .lobby-info p {{ margin: 0 0 12px; opacity: 1; }}
    .lobby-info p:last-child {{ margin-bottom: 0; }}
    .lobby-info a.lobby-contact {{ color: #7eb8ff; text-decoration: none; }}
    .lobby-info a.lobby-contact:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Arcade</h1>
{hint_html}  <div class="grid">
{grid_inner}
  </div>
{_lobby_info_section_html()}
</body>
</html>
"""


def _normalize_repo_url(url: str) -> str:
    u = url.strip().split("#", 1)[0].strip()
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u


def parse_github_repo(url: str) -> Tuple[str, str]:
    """
    Return (owner, repo) for https://github.com/owner/repo[/...]
    """
    u = _normalize_repo_url(url)
    parsed = urlparse(u)
    host = (parsed.netloc or "").lower()
    if "github.com" not in host:
        raise ValueError("URL must be a github.com repository link")
    path = (parsed.path or "").strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("Expected https://github.com/owner/repo")
    owner, repo = parts[0], parts[1]
    if not re.match(r"^[A-Za-z0-9_.-]+$", owner) or not re.match(
        r"^[A-Za-z0-9_.-]+$", repo
    ):
        raise ValueError("Invalid owner or repo name")
    return owner, repo


def _git_trust_repo_arg(repo_dir: Path) -> List[str]:
    """Avoid 'dubious ownership' when service user != owner of games/ (e.g. root vs www-data)."""
    return ["-c", f"safe.directory={repo_dir.resolve()}"]


def _looks_like_git_permission_denied(combined: str) -> bool:
    s = combined.lower()
    return (
        "permission denied" in s
        or "cannot open '.git" in s
        or "operation not permitted" in s
    )


def _git_clone_shallow(clone_url: str, dest: Path) -> None:
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, str(dest)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if r.returncode != 0:
        logger.error("git clone failed: %s", r.stderr or r.stdout)
        raise RuntimeError(f"git clone failed: {r.stderr or r.stdout}")


def git_clone_or_update(url: str, dest: Path) -> None:
    clone_url = url if url.endswith(".git") else url + ".git"
    if dest.is_dir() and (dest / ".git").is_dir():
        r = subprocess.run(
            ["git", *_git_trust_repo_arg(dest), "-C", str(dest), "pull", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if r.returncode == 0:
            return
        err = (r.stderr or "") + (r.stdout or "")
        logger.warning("git pull failed in %s: %s", dest, (r.stderr or r.stdout or "").strip()[:800])
        if _looks_like_git_permission_denied(err):
            logger.info(
                "Pull blocked by filesystem permissions; removing checkout and cloning fresh: %s",
                dest,
            )
            try:
                shutil.rmtree(dest)
            except OSError as e:
                raise RuntimeError(
                    "git cannot update this repo (permission denied) and this process "
                    "cannot remove it for a fresh clone. Either: chown the checkout to "
                    f"the uvicorn user, or remove {dest} as root so a fresh clone can be "
                    f"created. (games={GAMES_DIR}.) "
                    f"Original error: {err.strip()[:500]}"
                ) from e
            _git_clone_shallow(clone_url, dest)
            return
        raise RuntimeError(f"git pull failed: {r.stderr or r.stdout}")

    if dest.exists():
        shutil.rmtree(dest)
    _git_clone_shallow(clone_url, dest)


def _write_arcade_entry_marker(dest: Path, entry_rel_posix: str) -> None:
    (dest / ARCADE_ENTRY_MARKER).write_text(
        entry_rel_posix.strip().replace("\\", "/") + "\n", encoding="utf-8"
    )


def _apply_game_checkout_permissions(dest: Path) -> None:
    """
    sync_repos.py is often run as root; the arcade service runs as a normal user.
    Git may create a tree that other users cannot traverse (e.g. 700), so the lobby
    scan would skip the folder until a restart changed nothing — chmod fixes that.

    Set ARCADE_SYNC_SKIP_CHMOD=1 to skip. Set ARCADE_GAMES_OWNER=user:group (or user)
    to chown -R before chmod (optional).
    """
    if os.name != "posix":
        return
    if os.environ.get("ARCADE_SYNC_SKIP_CHMOD", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return
    root = dest.resolve()
    owner = os.environ.get("ARCADE_GAMES_OWNER", "").strip()
    if owner:
        cr = subprocess.run(
            ["chown", "-R", owner, str(root)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if cr.returncode != 0:
            logger.warning(
                "chown -R %s %s failed: %s",
                owner,
                root,
                (cr.stderr or cr.stdout or "").strip()[:400],
            )
    cr = subprocess.run(
        ["chmod", "-R", "a+rX", str(root)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if cr.returncode != 0:
        logger.warning(
            "chmod -R a+rX %s failed: %s",
            root,
            (cr.stderr or cr.stdout or "").strip()[:400],
        )
    else:
        logger.info("Adjusted permissions on %s for service-user readability", root)


def sync_one_repo(url: str, entry_script: Optional[str] = None) -> None:
    owner, repo = parse_github_repo(url)
    slug = repo
    dest = GAMES_DIR / slug
    logger.info("Sync %s/%s -> games/%s (WebSocket server game)", owner, repo, slug)
    git_clone_or_update(url, dest)
    _apply_game_checkout_permissions(dest)
    if entry_script:
        rel = _normalize_sync_entry_suffix(entry_script)
        parts = rel.split("/")
        candidate, rel_on_disk = _resolve_repo_entry_file(dest, parts)
        if candidate is None or not candidate.is_file():
            raise FileNotFoundError(
                f"After sync, entry script {rel!r} not found in {dest} "
                f"(tried case/whitespace-insensitive match for each path segment)."
            )
        _write_arcade_entry_marker(dest, rel_on_disk)
        logger.info(
            "Recorded entry script in %s: %s",
            ARCADE_ENTRY_MARKER,
            rel_on_disk,
        )
    entry = resolve_game_entry_script(dest)
    if entry is None or not entry.is_file():
        raise FileNotFoundError(
            f"After sync, no entry script found in {dest}. "
            "Use URL:path/to/script when syncing (e.g. .../Projekt:hra, "
            ".../repo:základ hry, .../Pstros:source/Pstros); .py is optional. "
            "Or add main.py, index.py, or exactly one .py at the repository root."
        )
    logger.info(
        "OK games/%s — entry %s (lobby rescans each request; permissions fixed for "
        "non-root service user — restart only if you changed server.py or "
        "arcade_remote_worker.py).",
        slug,
        entry.name,
    )
    start_suf = _catalog_start_script_from_game_dir(dest, entry_script)
    record_synced_game_catalog_meta(
        owner,
        slug,
        repo_url=canonical_github_repo_page_url(owner, repo),
        start_script=start_suf,
    )


def sync_repo_urls(urls: List[str]) -> int:
    """
    Clone or pull each GitHub URL into games/<repo-folder>/.

    The lobby lists each game; play URL is ``/<repo-folder>/`` (WebSocket ``/play-ws/<repo-folder>``).
    Lines may include an entry script: https://github.com/owner/repo:hra
    or https://github.com/owner/repo:hra.py or a nested path with Unicode/spaces.
    Same repo listed twice: last line wins (including entry override).
    Returns the number of repos that failed (0 if all succeeded).
    """
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
    if not urls:
        return 0
    by_repo: Dict[str, Tuple[str, Optional[str]]] = {}
    failures = 0
    for raw in urls:
        try:
            base_url, ent = parse_github_sync_spec(raw)
            parse_github_repo(base_url)
        except ValueError as e:
            logger.error("Invalid sync line %r: %s", raw, e)
            failures += 1
            continue
        k = _normalize_repo_url(base_url).lower()
        by_repo[k] = (base_url, ent)
    for url, ent in by_repo.values():
        try:
            sync_one_repo(url, ent)
        except Exception:
            logger.exception("Failed to sync %s", url)
            failures += 1
    return failures


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Arcade under %s — games=%s — errors also logged to %s "
        "(git sync is manual; games/ is rescanned each request — no restart needed for new repos)",
        BASE_DIR,
        GAMES_DIR,
        ERROR_LOG_FILE,
    )
    yield


app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(
        content=render_arcade_home_html(),
        headers=_lobby_headers(),
    )


def _github_profile_url_from_game_meta(meta: Dict[str, Any]) -> Optional[str]:
    """Profile URL like https://github.com/owner from ``creator`` (@handle) or ``repo_url``."""
    creator_raw = meta.get("creator")
    if isinstance(creator_raw, str) and creator_raw.strip():
        c = creator_raw.strip()
        if c.startswith("@"):
            handle = c[1:]
            if handle and re.match(r"^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$", handle):
                return f"https://github.com/{handle}"
    repo_url = meta.get("repo_url")
    if isinstance(repo_url, str) and repo_url.strip():
        try:
            owner, _ = parse_github_repo(repo_url.strip())
            return f"https://github.com/{owner}"
        except ValueError:
            pass
    return None


def _native_remote_play_html(slug: str) -> str:
    """Canvas client: JSON vector frames over WebSocket only."""
    slug_js = json.dumps(slug)
    meta = load_games_catalog().get(slug) or {}
    title_raw = meta.get("title")
    if isinstance(title_raw, str) and title_raw.strip():
        display_title = title_raw.strip()
    else:
        display_title = _default_lobby_title_from_slug(slug)
    page_title = html_module.escape(display_title)
    creator_raw = meta.get("creator")
    creator = (
        creator_raw.strip()
        if isinstance(creator_raw, str) and creator_raw.strip()
        else None
    )
    profile_url = _github_profile_url_from_game_meta(meta)
    credit_inner: str
    if creator and profile_url:
        credit_inner = (
            f'<span class="game-title">{html_module.escape(display_title)}</span>'
            f' · by <a class="credit-link" href="{html_module.escape(profile_url, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">{html_module.escape(creator)}</a>'
        )
    elif creator:
        credit_inner = (
            f'<span class="game-title">{html_module.escape(display_title)}</span>'
            f" · by {html_module.escape(creator)}"
        )
    elif profile_url:
        credit_inner = (
            f'<span class="game-title">{html_module.escape(display_title)}</span>'
            f' · by <a class="credit-link" href="{html_module.escape(profile_url, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">GitHub</a>'
        )
    else:
        credit_inner = f'<span class="game-title">{html_module.escape(display_title)}</span>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no"/>
  <title>{page_title}</title>
  <style>
    html, body {{ margin: 0; background: #000; color: #ccc; font-family: system-ui, sans-serif;
      min-height: 100vh; display: flex; flex-direction: column; align-items: center; }}
    .wrap {{ flex: 1 1 auto; min-height: 0; display: flex; align-items: center; justify-content: center;
      width: 100%; padding: 8px; box-sizing: border-box; position: relative; z-index: 1; }}
    canvas {{ display: block; max-width: 100%; max-height: calc(100vh - 120px); background: #111;
      touch-action: none; cursor: crosshair; user-select: none; -webkit-user-select: none;
      -webkit-touch-callout: none; position: relative; }}
    .footer {{ flex-shrink: 0; position: relative; z-index: 2; padding: 12px 16px 20px; text-align: center;
      max-width: 640px; width: 100%; box-sizing: border-box;
      background: linear-gradient(to top, #000 0%, #000 70%, rgba(0,0,0,0.92) 100%); }}
    .credit {{ font-size: 14px; color: #9aa3b8; margin-bottom: 14px; line-height: 1.45; }}
    .credit .game-title {{ font-weight: 700; color: #e8eefc; }}
    .credit .credit-link {{ color: #6eb3ff; text-decoration: none; }}
    .credit .credit-link:hover {{ text-decoration: underline; }}
    .exit-btn {{ display: inline-block; padding: 10px 22px; border-radius: 10px; background: #1a2744;
      color: #e8eefc; text-decoration: none; font-size: 14px; font-weight: 600;
      border: 1px solid #2f7cff; }}
    .exit-btn:hover {{ background: #243356; }}
  </style>
</head>
<body>
  <div class="wrap">
    <canvas id="c" width="800" height="600" oncontextmenu="return false;"></canvas>
  </div>
  <div class="footer">
    <div class="credit">{credit_inner}</div>
    <a class="exit-btn" href="/">Exit</a>
  </div>
  <script>
(function () {{
  const slug = {slug_js};
  let GW = 800, GH = 600;
  const canvas = document.getElementById("c");
  const ctx = canvas.getContext("2d");
  const wsProto = location.protocol === "https:" ? "wss:" : "ws:";
  const pendingCmd = [];
  let remoteByeRedirect = false;
  let remoteStopNotified = false;
  let ws = null;
  let frameTimeout = null;
  let firstFrameSlowHintTimer = null;
  const texImages = {{}};
  const soundUrls = {{}};
  let musicEl = null;
  let lastMusicSrc = null;
  let toneAudioCtx = null;
  const FIRST_FRAME_MS = 90000;
  const FIRST_FRAME_HINT_MS = 8000;

  function ensureToneContext() {{
    if (!toneAudioCtx)
      toneAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
    return toneAudioCtx;
  }}

  function resumeWebAudio() {{
    try {{
      const ac = ensureToneContext();
      if (ac.state === "suspended") ac.resume();
    }} catch (e) {{}}
  }}

  window.addEventListener("keydown", function () {{ resumeWebAudio(); }}, true);

  function clearFrameTimeout() {{
    if (frameTimeout) {{
      clearTimeout(frameTimeout);
      frameTimeout = null;
    }}
    if (firstFrameSlowHintTimer) {{
      clearTimeout(firstFrameSlowHintTimer);
      firstFrameSlowHintTimer = null;
    }}
  }}

  function drawOverlay(msg) {{
    ctx.fillStyle = "#111";
    ctx.fillRect(0, 0, GW, GH);
    ctx.fillStyle = "#bbb";
    ctx.font = "18px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(msg, GW / 2, GH / 2);
    ctx.textAlign = "start";
  }}

  function drawLoadingProgress(title, loaded, total) {{
    ctx.fillStyle = "#111";
    ctx.fillRect(0, 0, GW, GH);
    ctx.fillStyle = "#bbb";
    ctx.font = "17px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(title, GW / 2, GH / 2 - 36);
    const barW = Math.min(420, GW - 48);
    const barH = 14;
    const bx = (GW - barW) / 2;
    const by = GH / 2 - 4;
    ctx.fillStyle = "#2a2a2a";
    ctx.strokeStyle = "#444";
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (typeof ctx.roundRect === "function") ctx.roundRect(bx, by, barW, barH, 6);
    else ctx.rect(bx, by, barW, barH);
    ctx.fill();
    ctx.stroke();
    const frac = total > 0 ? Math.min(1, loaded / total) : 0;
    const fillW = Math.max(0, Math.floor(barW * frac));
    if (fillW > 0) {{
      ctx.fillStyle = "#2f7cff";
      ctx.beginPath();
      if (typeof ctx.roundRect === "function") {{
        const r = 5;
        ctx.roundRect(bx + 1, by + 1, fillW - 2, barH - 2, r);
      }} else ctx.rect(bx + 1, by + 1, fillW - 2, barH - 2);
      ctx.fill();
    }}
    ctx.fillStyle = "#888";
    ctx.font = "14px system-ui, sans-serif";
    const sub = total > 0 ? (loaded + " / " + total) : "…";
    ctx.fillText(sub, GW / 2, by + barH + 22);
    ctx.textAlign = "start";
  }}

  drawLoadingProgress("Loading…", 0, 0);

  function playTone(freqHz, durationMs, vol) {{
    try {{
      const ac = ensureToneContext();
      if (ac.state === "suspended") ac.resume();
      const f = Math.max(20, Math.min(20000, Number(freqHz) || 440));
      const ms = Math.max(1, Math.min(60000, Number(durationMs) || 200));
      const v = Math.max(0, Math.min(1, Number(vol)));
      const osc = ac.createOscillator();
      const g = ac.createGain();
      osc.type = "sine";
      osc.frequency.value = f;
      g.gain.value = v;
      osc.connect(g);
      g.connect(ac.destination);
      const t0 = ac.currentTime;
      osc.start(t0);
      osc.stop(t0 + ms / 1000);
    }} catch (e) {{}}
  }}

  function ensureMusicEl() {{
    if (!musicEl) {{
      musicEl = new Audio();
      musicEl.preload = "auto";
    }}
    return musicEl;
  }}

  function preloadTextures(done) {{
    drawLoadingProgress("Fetching asset list…", 0, 0);
    fetch("/" + encodeURIComponent(slug) + "/texture-manifest.json", {{ cache: "default" }})
      .then(function (r) {{ return r.ok ? r.json() : Promise.reject(); }})
      .then(function (m) {{
        const tlist = (m && m.textures) ? m.textures : [];
        const slist = (m && m.sounds) ? m.sounds : [];
        for (let s = 0; s < slist.length; s++) {{
          const se = slist[s];
          if (se && se.id && se.url) soundUrls[se.id] = se.url;
        }}
        const total = tlist.length + slist.length;
        if (!total) {{ done(); return; }}
        let loaded = 0;
        function tick() {{
          loaded++;
          drawLoadingProgress("Loading images & sounds…", loaded, total);
          if (loaded >= total) done();
        }}
        drawLoadingProgress("Loading images & sounds…", 0, total);
        for (let i = 0; i < tlist.length; i++) {{
          const e = tlist[i];
          const im = new Image();
          im.decoding = "async";
          im.onload = tick;
          im.onerror = tick;
          im.src = e.url;
          texImages[e.id] = im;
        }}
        for (let j = 0; j < slist.length; j++) {{
          const e = slist[j];
          if (!e || !e.url) {{ tick(); continue; }}
          const a = new Audio();
          a.preload = "auto";
          const fin = tick;
          a.addEventListener("canplaythrough", fin, {{ once: true }});
          a.addEventListener("error", fin, {{ once: true }});
          a.src = e.url;
          try {{ a.load(); }} catch (err) {{ fin(); }}
        }}
      }})
      .catch(function () {{ done(); }});
  }}

  function canvasCoords(clientX, clientY) {{
    const r = canvas.getBoundingClientRect();
    const x = Math.floor((clientX - r.left) / r.width * GW);
    const y = Math.floor((clientY - r.top) / r.height * GH);
    return [Math.max(0, Math.min(GW - 1, x)), Math.max(0, Math.min(GH - 1, y))];
  }}

  function arcadeKeyToken(e) {{
    if (!e) return null;
    const code = e.code;
    if (code) {{
      if (code === "ShiftLeft") return "ShiftLeft";
      if (code === "ShiftRight") return "ShiftRight";
      if (code === "ControlLeft") return "ControlLeft";
      if (code === "ControlRight") return "ControlRight";
      if (code === "AltLeft") return "AltLeft";
      if (code === "AltRight") return "AltRight";
      if (code === "MetaLeft" || code === "OSLeft") return "MetaLeft";
      if (code === "MetaRight" || code === "OSRight") return "MetaRight";
      if (code === "Numpad0") return "Numpad0";
      if (code === "Numpad1") return "Numpad1";
      if (code === "Numpad2") return "Numpad2";
      if (code === "Numpad3") return "Numpad3";
      if (code === "Numpad4") return "Numpad4";
      if (code === "Numpad5") return "Numpad5";
      if (code === "Numpad6") return "Numpad6";
      if (code === "Numpad7") return "Numpad7";
      if (code === "Numpad8") return "Numpad8";
      if (code === "Numpad9") return "Numpad9";
      if (code === "NumpadDecimal") return "NumpadDecimal";
      if (code === "NumpadEnter") return "NumpadEnter";
      if (code === "NumpadAdd") return "NumpadAdd";
      if (code === "NumpadSubtract") return "NumpadSubtract";
      if (code === "NumpadMultiply") return "NumpadMultiply";
      if (code === "NumpadDivide") return "NumpadDivide";
      if (code === "NumpadEqual") return "NumpadEqual";
      if (code === "Space") return " ";
      if (code.length === 6 && code.indexOf("Digit") === 0) return code.charAt(5);
      if (code.length === 4 && code.indexOf("Key") === 0) return code.charAt(3).toLowerCase();
      if (code === "Minus") return "-";
      if (code === "Equal") return "=";
      if (code === "BracketLeft") return "[";
      if (code === "BracketRight") return "]";
      if (code === "Backslash") return "\\\\";
      if (code === "Semicolon") return ";";
      if (code === "Quote") return "'";
      if (code === "Backquote") return "`";
      if (code === "Comma") return ",";
      if (code === "Period") return ".";
      if (code === "Slash") return "/";
      if (code === "IntlBackslash") return "\\\\";
      if (code === "ArrowLeft") return "ArrowLeft";
      if (code === "ArrowRight") return "ArrowRight";
      if (code === "ArrowUp") return "ArrowUp";
      if (code === "ArrowDown") return "ArrowDown";
      if (code === "Enter") return "Enter";
      if (code === "Escape") return "Escape";
      if (code === "Tab") return "Tab";
      if (code === "Backspace") return "Backspace";
      if (code === "Insert") return "Insert";
      if (code === "Delete") return "Delete";
      if (code === "Home") return "Home";
      if (code === "End") return "End";
      if (code === "PageUp") return "PageUp";
      if (code === "PageDown") return "PageDown";
      if (code === "Pause") return "Pause";
      if (code === "PrintScreen") return "PrintScreen";
      if (code === "ContextMenu") return "ContextMenu";
      if (code === "CapsLock") return "CapsLock";
      if (code === "NumLock") return "NumLock";
      if (code === "ScrollLock") return "ScrollLock";
    }}
    const k = e.key;
    if (k === " " || k === "Space") return " ";
    if (k === "Enter" || k === "Escape" || k === "Tab" || k === "Backspace") return k;
    if (k === "ArrowLeft" || k === "ArrowRight" || k === "ArrowUp" || k === "ArrowDown") return k;
    if (k === "Delete" || k === "Insert" || k === "Home" || k === "End" || k === "PageUp" || k === "PageDown")
      return k;
    if (k === "CapsLock" || k === "NumLock" || k === "ScrollLock") return k;
    if (k === "Pause" || k === "PrintScreen" || k === "ContextMenu") return k;
    if (/^F([1-9]|1\\d|2[0-4])$/.test(k)) return k;
    if (k.length === 1) return k;
    return null;
  }}

  function sendCmd(o) {{
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(o));
    else pendingCmd.push(o);
  }}

  /** PointerEvent.button → pygame (1=left, 2=middle, 3=right). */
  function pointerButtonToPygame(btn) {{
    if (btn === 0) return 1;
    if (btn === 1) return 2;
    if (btn === 2) return 3;
    return 0;
  }}

  var mouseButtonDownCount = {{ 1: 0, 2: 0, 3: 0 }};

  function eventPathContainsCanvas(e) {{
    if (e.target === canvas) return true;
    try {{
      var p = typeof e.composedPath === "function" ? e.composedPath() : null;
      if (p) {{
        for (var i = 0; i < p.length; i++) if (p[i] === canvas) return true;
      }}
    }} catch (err) {{}}
    return false;
  }}

  function suppressCanvasContextMenu(e) {{
    if (!eventPathContainsCanvas(e)) return;
    e.preventDefault();
    e.stopPropagation();
    if (typeof e.stopImmediatePropagation === "function") e.stopImmediatePropagation();
  }}
  document.addEventListener("contextmenu", suppressCanvasContextMenu, true);
  window.addEventListener("contextmenu", suppressCanvasContextMenu, true);

  document.addEventListener("mousedown", function (e) {{
    if (e.button !== 2) return;
    if (!eventPathContainsCanvas(e)) return;
    e.preventDefault();
  }}, true);

  document.addEventListener("mouseup", function (e) {{
    if (e.button !== 2) return;
    if (!eventPathContainsCanvas(e)) return;
    e.preventDefault();
  }}, true);

  window.addEventListener("keydown", function (e) {{
    if (e.repeat) return;
    const k = arcadeKeyToken(e);
    if (k) {{ e.preventDefault(); sendCmd({{ t: "keydown", k: k }}); }}
  }}, true);
  window.addEventListener("keyup", function (e) {{
    const k = arcadeKeyToken(e);
    if (k) {{ e.preventDefault(); sendCmd({{ t: "keyup", k: k }}); }}
  }}, true);
  canvas.addEventListener("pointermove", function (e) {{
    const xy = canvasCoords(e.clientX, e.clientY);
    sendCmd({{ t: "move", x: xy[0], y: xy[1] }});
  }}, {{ passive: true }});
  canvas.addEventListener("contextmenu", function (e) {{
    suppressCanvasContextMenu(e);
  }}, true);
  canvas.addEventListener("pointerdown", function (e) {{
    const b = pointerButtonToPygame(e.button);
    if (!b) return;
    e.preventDefault();
    resumeWebAudio();
    try {{ canvas.setPointerCapture(e.pointerId); }} catch (err) {{}}
    const xy = canvasCoords(e.clientX, e.clientY);
    sendCmd({{ t: "move", x: xy[0], y: xy[1] }});
    mouseButtonDownCount[b] = (mouseButtonDownCount[b] || 0) + 1;
    if (mouseButtonDownCount[b] === 1) sendCmd({{ t: "mousedown", b: b }});
  }});
  canvas.addEventListener("pointerup", function (e) {{
    const b = pointerButtonToPygame(e.button);
    if (!b) return;
    if (mouseButtonDownCount[b] > 0) mouseButtonDownCount[b]--;
    if (mouseButtonDownCount[b] === 0) sendCmd({{ t: "mouseup", b: b }});
  }});
  canvas.addEventListener("pointercancel", function (e) {{
    [1, 2, 3].forEach(function (bb) {{
      while (mouseButtonDownCount[bb] > 0) {{
        mouseButtonDownCount[bb]--;
        sendCmd({{ t: "mouseup", b: bb }});
      }}
    }});
  }});
  canvas.addEventListener("lostpointercapture", function (e) {{
    [1, 2, 3].forEach(function (bb) {{
      while (mouseButtonDownCount[bb] > 0) {{
        mouseButtonDownCount[bb]--;
        sendCmd({{ t: "mouseup", b: bb }});
      }}
    }});
  }});

  function rgba(c) {{
    const a = c.length > 3 ? (c[3] / 255) : 1;
    return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")";
  }}

  function roundPath(x, y, w, h, rad) {{
    if (rad <= 0) {{ ctx.rect(x, y, w, h); return; }}
    if (typeof ctx.roundRect === "function") {{
      ctx.roundRect(x, y, w, h, Math.min(rad, w / 2, h / 2));
      return;
    }}
    const r = Math.min(rad, w / 2, h / 2);
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }}

  function syncCanvasSize(w, h) {{
    const nw = Math.max(1, Math.min(8192, parseInt(w, 10) || GW));
    const nh = Math.max(1, Math.min(8192, parseInt(h, 10) || GH));
    if (nw === GW && nh === GH) return;
    GW = nw;
    GH = nh;
    canvas.width = GW;
    canvas.height = GH;
    try {{
      canvas.style.aspectRatio = GW + " / " + GH;
    }} catch (e) {{}}
  }}

  function replayFrame(j) {{
    if (!j || j.v !== 2 || !Array.isArray(j.cmds)) return;
    if (j.w != null && j.h != null) syncCanvasSize(j.w, j.h);
    if (j.snd && typeof j.snd === "object") {{
      for (var sk in j.snd) {{
        if (Object.prototype.hasOwnProperty.call(j.snd, sk))
          soundUrls[sk] = "data:audio/wav;base64," + j.snd[sk];
      }}
    }}
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, GW, GH);
    function tblitClampSrc(img, sx, sy, sw, sh) {{
      const iw = img.naturalWidth;
      const ih = img.naturalHeight;
      if (iw < 1 || ih < 1) return null;
      let x = Math.floor(Number(sx) || 0);
      let y = Math.floor(Number(sy) || 0);
      let w = Math.max(1, Math.floor(Number(sw) || 1));
      let h = Math.max(1, Math.floor(Number(sh) || 1));
      if (x < 0) {{ w += x; x = 0; }}
      if (y < 0) {{ h += y; y = 0; }}
      if (x >= iw || y >= ih) return null;
      if (x + w > iw) w = iw - x;
      if (y + h > ih) h = ih - y;
      if (w < 1 || h < 1) return null;
      return [x, y, w, h];
    }}
    for (let i = 0; i < j.cmds.length; i++) {{
      const row = j.cmds[i];
      const op = row[0];
      const p = row[1];
      if (op === "rect") {{
        const r = p.r;
        ctx.beginPath();
        roundPath(r[0], r[1], r[2], r[3], p.br || 0);
        if (p.w > 0) {{
          ctx.strokeStyle = rgba(p.c);
          ctx.lineWidth = p.w;
          ctx.stroke();
        }} else {{
          ctx.fillStyle = rgba(p.c);
          ctx.fill();
        }}
      }} else if (op === "circle") {{
        ctx.beginPath();
        ctx.arc(p.cx, p.cy, p.rad, 0, Math.PI * 2);
        if (p.w > 0) {{
          ctx.strokeStyle = rgba(p.c);
          ctx.lineWidth = p.w;
          ctx.stroke();
        }} else {{
          ctx.fillStyle = rgba(p.c);
          ctx.fill();
        }}
      }} else if (op === "polygon") {{
        const pts = p.p;
        if (pts.length < 4) continue;
        ctx.beginPath();
        ctx.moveTo(pts[0], pts[1]);
        for (let k = 2; k < pts.length; k += 2) ctx.lineTo(pts[k], pts[k + 1]);
        ctx.closePath();
        if (p.w > 0) {{
          ctx.strokeStyle = rgba(p.c);
          ctx.lineWidth = p.w;
          ctx.stroke();
        }} else {{
          ctx.fillStyle = rgba(p.c);
          ctx.fill();
        }}
      }} else if (op === "line") {{
        ctx.beginPath();
        ctx.moveTo(p.x1, p.y1);
        ctx.lineTo(p.x2, p.y2);
        ctx.strokeStyle = rgba(p.c);
        ctx.lineWidth = p.w;
        ctx.stroke();
      }} else if (op === "lines") {{
        const pts = p.p;
        if (pts.length < 4) continue;
        ctx.beginPath();
        ctx.moveTo(pts[0], pts[1]);
        for (let k = 2; k < pts.length; k += 2) ctx.lineTo(pts[k], pts[k + 1]);
        if (p.closed) ctx.closePath();
        ctx.strokeStyle = rgba(p.c);
        ctx.lineWidth = p.w;
        ctx.stroke();
      }} else if (op === "ellipse") {{
        const r = p.r;
        const cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2;
        const rx = Math.max(0.5, r[2] / 2), ry = Math.max(0.5, r[3] / 2);
        ctx.beginPath();
        ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        if (p.w > 0) {{
          ctx.strokeStyle = rgba(p.c);
          ctx.lineWidth = p.w;
          ctx.stroke();
        }} else {{
          ctx.fillStyle = rgba(p.c);
          ctx.fill();
        }}
      }} else if (op === "arc") {{
        const r = p.r;
        const cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2;
        const rx = Math.max(0.5, r[2] / 2), ry = Math.max(0.5, r[3] / 2);
        ctx.beginPath();
        ctx.ellipse(cx, cy, rx, ry, 0, p.a0, p.a1);
        ctx.strokeStyle = rgba(p.c);
        ctx.lineWidth = p.w;
        ctx.stroke();
      }} else if (op === "tblit") {{
        const img = texImages[p.id];
        if (!img || !img.complete || img.naturalWidth < 1) continue;
        const cr = tblitClampSrc(img, p.sx, p.sy, p.sw, p.sh);
        if (!cr) continue;
        try {{
          ctx.drawImage(img, cr[0], cr[1], cr[2], cr[3], p.dx, p.dy, p.dw, p.dh);
        }} catch (e) {{}}
      }} else if (op === "tblit_rot") {{
        const img = texImages[p.id];
        const deg = typeof p.deg === "number" ? p.deg : 0;
        const cx = typeof p.cx === "number" ? p.cx : (p.dx + p.dw / 2);
        const cy = typeof p.cy === "number" ? p.cy : (p.dy + p.dh / 2);
        if (!img || !img.complete || img.naturalWidth < 1) continue;
        const cr = tblitClampSrc(img, p.sx, p.sy, p.sw, p.sh);
        if (!cr) continue;
        try {{
          ctx.save();
          ctx.translate(cx, cy);
          ctx.rotate(-(deg * Math.PI / 180));
          ctx.drawImage(
            img,
            cr[0],
            cr[1],
            cr[2],
            cr[3],
            -p.dw / 2,
            -p.dh / 2,
            p.dw,
            p.dh
          );
          ctx.restore();
        }} catch (e) {{}}
      }} else if (op === "blit") {{
        ctx.fillStyle = rgba(p.c);
        ctx.fillRect(p.x, p.y, p.w, p.h);
      }} else if (op === "text") {{
        ctx.font = "bold " + (p.px || 20) + "px system-ui, sans-serif";
        ctx.fillStyle = rgba(p.c);
        ctx.textBaseline = "top";
        ctx.fillText(p.t, p.x, p.y);
      }} else if (op === "play_sound") {{
        const url = soundUrls[p.id];
        if (!url) continue;
        const loops = typeof p.loops === "number" ? p.loops : 0;
        const vol = typeof p.v === "number" ? p.v : 1;
        try {{
          const a = new Audio(url);
          a.volume = Math.max(0, Math.min(1, vol));
          a.loop = loops === -1;
          a.play().catch(function () {{}});
        }} catch (e) {{}}
      }} else if (op === "music_play") {{
        const url = soundUrls[p.id];
        if (!url) continue;
        const loops = typeof p.loops === "number" ? p.loops : -1;
        try {{
          const m = ensureMusicEl();
          m.loop = loops === -1;
          if (lastMusicSrc !== url) {{
            lastMusicSrc = url;
            m.src = url;
            try {{ m.load(); }} catch (e) {{}}
          }}
          m.currentTime = 0;
          m.play().catch(function () {{}});
        }} catch (e) {{}}
      }} else if (op === "music_stop") {{
        try {{
          if (musicEl) {{
            musicEl.pause();
            musicEl.currentTime = 0;
          }}
        }} catch (e) {{}}
      }} else if (op === "tone") {{
        playTone(p.f, p.ms, typeof p.v === "number" ? p.v : 0.2);
      }}
    }}
  }}

  function showDead(msg) {{
    ctx.fillStyle = "#400";
    ctx.font = "16px sans-serif";
    const lines = (msg || "WebSocket failed.").split("\\n");
    const y0 = Math.max(24, Math.floor(GH / 2) - Math.floor(lines.length * 11));
    lines.forEach(function (line, i) {{ ctx.fillText(line, 16, y0 + i * 22); }});
  }}

  function handleRemotePayload(t) {{
    try {{
      const data = JSON.parse(t);
      if (data && data.fatal) {{
        clearFrameTimeout();
        remoteStopNotified = true;
        showDead((data.detail || "Game stopped unexpectedly.") + "\\nUse the browser back button or open / for the lobby.");
        return;
      }}
      if (data && data.bye) {{
        clearFrameTimeout();
        remoteByeRedirect = true;
        window.location.href = data.redirect || "/";
        return;
      }}
      replayFrame(data);
      clearFrameTimeout();
    }} catch (e) {{
      clearFrameTimeout();
      showDead("Bad frame from server.\\nTry hard-refresh; if it persists, check uvicorn logs.");
    }}
  }}

  function connectWebSocket() {{
    drawOverlay("Connecting…");
    clearFrameTimeout();
    const wsPath = "/play-ws/" + encodeURIComponent(slug);
    ws = new WebSocket(wsProto + "//" + location.host + wsPath);
    let wsOpened = false;

    ws.onopen = function () {{
      wsOpened = true;
      while (pendingCmd.length && ws.readyState === WebSocket.OPEN)
        ws.send(JSON.stringify(pendingCmd.shift()));
      firstFrameSlowHintTimer = setTimeout(function () {{
        if (!remoteByeRedirect && !remoteStopNotified)
          drawOverlay("Still starting… heavy games can take a minute.");
      }}, FIRST_FRAME_HINT_MS);
      frameTimeout = setTimeout(function () {{
        if (!remoteByeRedirect && !remoteStopNotified)
          showDead("No frames from server (timeout).\\nIf the game never appears, check nginx WebSocket proxy for /play-ws/ — see nginx-arcade.conf.example.\\nTest: curl -i -N -H 'Connection: Upgrade' -H 'Upgrade: websocket' …/play-ws/" + encodeURIComponent(slug));
      }}, FIRST_FRAME_MS);
    }};

    ws.onmessage = function (ev) {{
      try {{
        if (typeof ev.data === "string") handleRemotePayload(ev.data);
        else if (ev.data && ev.data.text) ev.data.text().then(handleRemotePayload);
      }} catch (e) {{}}
    }};

    ws.onerror = function () {{
      clearFrameTimeout();
      showDead("WebSocket error.\\nServer: pip install -r requirements.txt (needs websockets).\\nProxy: Upgrade + Connection upgrade for /play-ws/ — see nginx-arcade.conf.example.");
    }};

    ws.onclose = function () {{
      clearFrameTimeout();
      if (remoteByeRedirect || remoteStopNotified) return;
      if (!wsOpened)
        showDead("WebSocket closed before connect.\\nCheck proxy (Cloudflare: WebSockets on).\\nNginx: location for ^/play-ws/ with Upgrade — see nginx-arcade.conf.example.\\nUse: uvicorn … --workers 1");
    }};
  }}

  preloadTextures(connectWebSocket);
}})();
  </script>
</body>
</html>
"""


@app.get("/{slug}/texture-manifest.json")
def native_remote_texture_manifest(slug: str):
    body = json.dumps(_native_texture_manifest(slug), separators=(",", ":"))
    return Response(
        content=body,
        media_type="application/json",
        headers=_texture_manifest_cache_headers(),
    )


@app.get("/{slug}/files/{path:path}")
def native_remote_game_file(slug: str, path: str):
    root = _native_remote_game_root(slug)
    if root is None:
        raise HTTPException(status_code=404, detail="Native remote game not found")
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(target, headers=_game_file_cache_headers())


@app.get("/{slug}/", response_class=HTMLResponse)
def native_remote_page(slug: str):
    entry = get_game_scripts().get(slug)
    if entry is None or not entry.is_file():
        raise HTTPException(status_code=404, detail="Native remote game not found")
    return HTMLResponse(content=_native_remote_play_html(slug), headers=_cache_headers())


@app.get("/{slug}", include_in_schema=False)
def native_remote_page_redirect_slash(slug: str):
    entry = get_game_scripts().get(slug)
    if entry is None or not entry.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return RedirectResponse(url=f"/{quote(slug, safe='')}/", status_code=307)


async def _native_game_websocket_impl(slug: str, websocket: WebSocket) -> None:
    entry = get_game_scripts().get(slug)
    if entry is None or not entry.is_file():
        await websocket.close(code=4404)
        return

    await websocket.accept()
    record_wh = _record_surface_size_from_catalog(slug)
    proc, frame_q, cmd_q = _start_native_game_process(entry, record_wh=record_wh)

    async def pump_frames() -> None:
        try:
            while proc.is_alive():
                try:
                    payload: bytes = frame_q.get_nowait()
                except Empty:
                    await asyncio.sleep(0.002)
                    continue
                try:
                    await websocket.send_text(payload.decode("utf-8"))
                except Exception:
                    break
        except asyncio.CancelledError:
            raise
        if proc.is_alive():
            return
        proc.join(timeout=5.0)
        code = proc.exitcode
        try:
            if code == 0:
                await websocket.send_text(
                    json.dumps(
                        {"v": 2, "bye": True, "redirect": "/"},
                        separators=(",", ":"),
                    )
                )
            else:
                await websocket.send_text(
                    json.dumps(
                        {
                            "v": 2,
                            "fatal": True,
                            "detail": (
                                "The game process exited unexpectedly (server exit code "
                                f"{code}).\\nCheck logs/remote-child.log and restart "
                                "uvicorn after upgrading arcade code."
                            ),
                        },
                        separators=(",", ":"),
                    )
                )
        except Exception:
            pass
        await asyncio.sleep(0.05)
        try:
            await websocket.close()
        except Exception:
            pass

    pump = asyncio.create_task(pump_frames())
    try:
        while True:
            try:
                msg = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            if isinstance(msg, dict):
                cmd_q.put(msg)
    finally:
        pump.cancel()
        try:
            await pump
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        _cleanup_native_process(proc, cmd_q)


@app.websocket("/play-ws/{slug}")
async def native_game_ws_play(slug: str, websocket: WebSocket):
    """Preferred WS URL: avoids nginx ``location ^~ /<game>/`` stealing ``/<game>/ws``."""
    await _native_game_websocket_impl(slug, websocket)


@app.websocket("/{slug}/ws")
async def native_game_ws(slug: str, websocket: WebSocket):
    await _native_game_websocket_impl(slug, websocket)
