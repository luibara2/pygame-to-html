"""
Headless pygame: patches pygame to stream each frame as compact JSON draw commands
(no PNG). The game main.py is unchanged.

Records pygame.draw.* on the main back-buffer size (default 800x800) and on the
display surface; blits onto those targets become color placeholders, ``tblit`` for
loaded images, or ``text`` commands from Font.render. Multi-glyph surfaces (several
``render`` results blitted onto a temp surface, then blitted to the screen) keep
per-character metadata and expand to multiple ``text`` commands so titles like
``VOID SURVIVOR`` are not replaced by a single averaged-color rectangle.
Full-screen blit from back-buffer → display is skipped when it would duplicate
recorded content.

Requires SDL dummy video on the server. Use multiprocessing "spawn" in the parent
(uvicorn) so the child does not inherit a fork-broken SDL state.

The child prepends the entry script's directory to sys.path so sibling modules
(e.g. main.py + tridy.py) import like `python main.py` from that folder.

Rotated sprites: pygame.transform.rotate/rotozoom accumulate `rot_deg` on surface_tex;
display blits with non-zero deg emit `tblit_rot` so the browser canvas can rotate
the source texture (pygame angles are CCW; the client maps to canvas).
``scale_by`` / ``smoothscale_by`` (pygame 2) also propagate ``surface_tex``, or scaled
sprites would fall back to flat color rectangles in the stream. ``Surface.copy()`` must
propagate the same metadata: games often use ``texture.copy()`` per sprite; without it,
``tblit`` falls back to a single-pixel ``blit`` color (often transparent for PNG ships).
C-returned surfaces from ``transform.*`` are wrapped in the recording subclass when they
carry texture ids so ``.copy()`` keeps working.
``pygame.sprite.Group.draw`` uses ``Surface.blits()`` when available (pygame 2+), which
would bypass a patched ``blit``; ``RecordingSurface.blits`` delegates per item to ``blit``.
When a surface carries accumulated ``surface_glyphs`` (text drawn to an off-screen buffer the same size as the
record surface), ``scale`` / ``smoothscale`` / ``scale_by`` move those glyphs to the
output surface so a later ``transform.scale`` → display (e.g. letterboxed viewport)
still streams menu text.

``pygame.image.load``, ``pygame.mixer.music.load``, and ``pygame.mixer.Sound``
normalize Windows-style path strings (backslash separators) to POSIX on the Linux
server, and resolve a missing path to a same-directory file with the same name ignoring
case, so Windows-authored games keep working without editing files under ``games/``.

**Frame byte cap:** If a JSON frame exceeds ``ARCADE_REMOTE_MAX_FRAME_BYTES``, commands are
truncated from the **end** (prefix kept) so background and sprites still replay; older
behavior kept a suffix and hid the whole playfield on busy frames.

**Writable saves:** Opens under the game directory in write/append modes are redirected to
``~/.cache/arcade-remote-writable/<hash>/`` (override with ``ARCADE_REMOTE_WRITABLE_ROOT``)
so ``PermissionError`` on ``high_score.json`` and similar files does not exit the child;
``os.path.exists`` / ``os.path.isfile`` honor the redirected copy.

**Audio (browser):** Sound files listed in the texture manifest's ``sounds`` array are
preloaded; ``ArcadeRemoteSound.play`` (``pygame.mixer.Sound`` subclass) emits
``play_sound``. ``Sound(buffer=…)`` is wrapped as WAV, base64-embedded once per frame
key ``snd`` for the browser. Code that uses ``Channel.play(sound)`` without calling
``sound.play()`` still does not emit browser events (pygame 2.6+). ``mixer.music``
emits ``music_play`` / ``music_stop``. For tones without buffers, use
``pygame.arcade_web.tone(freq_hz, duration_ms, volume)`` (Web Audio on the client).
"""

from __future__ import annotations

import array
import base64
import builtins
import hashlib
import io
import json
import math
import os
import runpy
import sys
import wave
import weakref
from pathlib import Path
from multiprocessing import Queue
from queue import Empty
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

_KEY_MAP: Dict[str, int] = {}


def _install_remote_writable_game_tree_redirect(game_root: Path) -> None:
    """
    Native remote games often ``chdir`` into ``games/<slug>/``, which is not writable
    when the arcade runs as a non-owner (e.g. www-data). Redirect file opens that
    target paths inside that tree so writes go to a cache dir (per game root hash).

    Reads prefer the redirected copy when present so scores/saves persist; otherwise
    the original path is used (shipped assets, read-only tree).
    """
    root = game_root.resolve()
    key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:24]
    base = Path(
        os.environ.get(
            "ARCADE_REMOTE_WRITABLE_ROOT",
            str(Path.home() / ".cache" / "arcade-remote-writable"),
        )
    ).expanduser()
    data_dir = (base / key).resolve()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    real_open = builtins.open
    real_exists = os.path.exists
    real_isfile = os.path.isfile

    def _mapped_alt(path: Any) -> Tuple[Optional[Path], Optional[Path]]:
        try:
            path_str = os.fsdecode(path) if isinstance(path, bytes) else os.fspath(path)
        except (TypeError, ValueError):
            return None, None
        p = Path(path_str)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        else:
            p = p.resolve()
        try:
            rel = p.relative_to(root)
        except ValueError:
            return None, None
        alt = (data_dir / rel).resolve()
        try:
            alt.relative_to(data_dir)
        except ValueError:
            return None, None
        return p, alt

    def _exists_hook(path: Any) -> bool:
        _p, alt = _mapped_alt(path)
        if alt is None:
            return bool(real_exists(path))
        try:
            if alt.is_file():
                return True
        except OSError:
            pass
        return bool(real_exists(path))

    def _isfile_hook(path: Any) -> bool:
        _p, alt = _mapped_alt(path)
        if alt is None:
            return bool(real_isfile(path))
        try:
            if alt.is_file():
                return True
        except OSError:
            pass
        return bool(real_isfile(path))

    os.path.exists = _exists_hook  # type: ignore[assignment]
    os.path.isfile = _isfile_hook  # type: ignore[assignment]

    def _mode_writes(m: str) -> bool:
        if not isinstance(m, str):
            return False
        for ch in m:
            if ch in "wax":
                return True
        return "+" in m

    def _wrapped_open(
        file: Any,
        mode: str = "r",
        buffering: int = -1,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
        closefd: bool = True,
        opener: Optional[Any] = None,
    ) -> Any:
        if isinstance(file, int):
            return real_open(
                file, mode, buffering, encoding, errors, newline, closefd, opener
            )
        try:
            path_str = os.fsdecode(file) if isinstance(file, bytes) else os.fspath(file)
        except (TypeError, ValueError):
            return real_open(
                file, mode, buffering, encoding, errors, newline, closefd, opener
            )
        p = Path(path_str)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        else:
            p = p.resolve()
        try:
            rel = p.relative_to(root)
        except ValueError:
            return real_open(
                file, mode, buffering, encoding, errors, newline, closefd, opener
            )

        alt = (data_dir / rel).resolve()
        try:
            alt.relative_to(data_dir)
        except ValueError:
            return real_open(
                file, mode, buffering, encoding, errors, newline, closefd, opener
            )

        if _mode_writes(mode):
            try:
                alt.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            return real_open(
                alt, mode, buffering, encoding, errors, newline, closefd, opener
            )

        if alt.is_file():
            return real_open(
                alt, mode, buffering, encoding, errors, newline, closefd, opener
            )
        return real_open(
            file, mode, buffering, encoding, errors, newline, closefd, opener
        )

    builtins.open = _wrapped_open  # type: ignore[assignment]
    io.open = _wrapped_open  # type: ignore[assignment]


def _normalize_posix_path_separators(path: Any) -> Any:
    """
    On POSIX servers, backslashes in path strings are literal characters, not separators.
    Games written on Windows often use ``load("img\\\\tile.png")``; normalize to
    ``img/tile.png`` so the same code works on Linux. No-op on Windows (avoids breaking
    UNC paths). Handles str, bytes, and pathlib.Path.
    """
    if os.name == "nt":
        return path
    if isinstance(path, str):
        return path.replace("\\", "/") if "\\" in path else path
    if isinstance(path, bytes):
        return path.replace(b"\\", b"/") if b"\\" in path else path
    if isinstance(path, Path):
        ps = str(path)
        return Path(ps.replace("\\", "/")) if "\\" in ps else path
    return path


def _resolve_case_insensitive_image_path(file_path: Any) -> Any:
    """
    Linux/macOS (APFS case-sensitive): if the path is missing but another file in the
    same directory matches the basename case-insensitively, use that file. Repos edited
    on Windows often commit ``Horici_mesto.png`` while code loads ``horici_mesto.png``.
    """
    file_path = _normalize_posix_path_separators(file_path)
    try:
        if isinstance(file_path, Path):
            p = file_path.expanduser()
            if not p.is_absolute():
                p = (Path.cwd() / p).resolve()
            else:
                p = p.resolve()
        else:
            if isinstance(file_path, bytes):
                raw_s = os.fsdecode(file_path)
            else:
                raw_s = str(file_path)
            p = Path(raw_s).expanduser()
            if not p.is_absolute():
                p = (Path.cwd() / p).resolve()
            else:
                p = p.resolve()
    except Exception:
        return file_path

    try:
        if p.is_file():
            return p
    except OSError:
        return file_path

    if os.name == "nt":
        return file_path

    parent, name = p.parent, p.name
    try:
        if not parent.is_dir():
            return file_path
    except OSError:
        return file_path

    want = name.lower()
    try:
        for entry in parent.iterdir():
            try:
                if entry.is_file() and entry.name.lower() == want:
                    return entry
            except OSError:
                continue
    except OSError:
        return file_path
    return file_path


def _arcade_sound_rel_id(file_path: Any, game_root: Optional[Path]) -> Optional[str]:
    """Game-root-relative POSIX id for preload URLs (same convention as texture ``id``)."""
    if game_root is None:
        return None
    try:
        if isinstance(file_path, Path):
            p = file_path.expanduser()
            if not p.is_absolute():
                p = (Path.cwd() / p).resolve()
            else:
                p = p.resolve()
        else:
            if isinstance(file_path, bytes):
                raw_s = os.fsdecode(file_path)
            else:
                raw_s = str(file_path)
            p = Path(raw_s).expanduser()
            if not p.is_absolute():
                p = (Path.cwd() / p).resolve()
            else:
                p = p.resolve()
        rel = p.relative_to(game_root.resolve())
        return str(rel).replace("\\", "/")
    except Exception:
        return None


def _sampwidth_from_pygame_format(format_bits: int) -> int:
    b = abs(int(format_bits))
    if b <= 8:
        return 1
    if b <= 16:
        return 2
    if b <= 24:
        return 3
    if b <= 32:
        return 4
    return 2


def _pcm_bytes_to_wav(pcm: bytes, sample_rate: int, channels: int, sampwidth: int) -> bytes:
    ch = max(1, min(8, int(channels)))
    sw = sampwidth if sampwidth in (1, 2, 3, 4) else 2
    frame = sw * ch
    if frame <= 0:
        return b""
    data = pcm[: len(pcm) - (len(pcm) % frame)]
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(ch)
        wf.setsampwidth(sw)
        wf.setframerate(max(1, int(sample_rate)))
        wf.writeframes(data)
    return bio.getvalue()


def _build_key_map(pg: Any) -> Dict[str, int]:
    """
    Map browser-sent key tokens (from KeyboardEvent.code / key) to pygame key constants.
    Letters are lowercase tokens; digits are "0".."9"; numpad uses "Numpad0" etc.
    """

    def reg(*names: str) -> Optional[int]:
        for nm in names:
            if not nm:
                continue
            obj = pg
            for part in nm.split("."):
                obj = getattr(obj, part, None)
                if obj is None:
                    break
            else:
                return int(obj)
        return None

    m: Dict[str, int] = {}

    def add(const_names: str, *tokens: str) -> None:
        v = reg(const_names)
        if v is None:
            return
        for t in tokens:
            if t:
                m[t] = v

    # Letters a–z (token is always lowercase; games use K_a etc.)
    for c in "abcdefghijklmnopqrstuvwxyz":
        add(f"K_{c}", c, c.upper())
    # Top-row digits
    for d in "0123456789":
        add(f"K_{d}", d)
    # Space
    add("K_SPACE", " ", "Space")
    # Arrows & navigation
    add("K_LEFT", "ArrowLeft")
    add("K_RIGHT", "ArrowRight")
    add("K_UP", "ArrowUp")
    add("K_DOWN", "ArrowDown")
    add("K_RETURN", "Enter")
    add("K_ESCAPE", "Escape")
    add("K_TAB", "Tab")
    add("K_BACKSPACE", "Backspace")
    add("K_DELETE", "Delete")
    add("K_INSERT", "Insert")
    add("K_HOME", "Home")
    add("K_END", "End")
    add("K_PAGEUP", "PageUp")
    add("K_PAGEDOWN", "PageDown")
    add("K_PAUSE", "Pause")
    add("K_PRINT", "PrintScreen")
    add("K_MENU", "ContextMenu")
    # Lock keys
    add("K_CAPSLOCK", "CapsLock")
    add("K_NUMLOCK", "NumLock")
    add("K_SCROLLLOCK", "ScrollLock")
    # Function keys
    for i in range(1, 25):
        v = reg(f"K_F{i}")
        if v is not None:
            m[f"F{i}"] = v
    # Modifiers (left/right from code; generic fallbacks from e.key)
    add("K_LSHIFT", "ShiftLeft", "Shift")
    add("K_RSHIFT", "ShiftRight")
    add("K_LCTRL", "ControlLeft", "Control")
    add("K_RCTRL", "ControlRight")
    add("K_LALT", "AltLeft", "Alt")
    add("K_RALT", "AltRight")
    add("K_LMETA", "MetaLeft", "Meta")
    add("K_RMETA", "MetaRight", "OS", "Super")
    add("K_LGUI", "MetaLeft", "OSLeft")
    add("K_RGUI", "MetaRight", "OSRight")
    # US layout punctuation (tokens match what the browser client sends)
    add("K_MINUS", "-")
    add("K_EQUALS", "=")
    add("K_LEFTBRACKET", "[", "{")
    add("K_RIGHTBRACKET", "]", "}")
    add("K_BACKSLASH", "\\", "|")
    add("K_SEMICOLON", ";", ":")
    add("K_QUOTE", "'", '"')
    add("K_BACKQUOTE", "`", "~")
    add("K_COMMA", ",", "<")
    add("K_PERIOD", ".", ">")
    add("K_SLASH", "/", "?")
    vu = reg("K_UNDERSCORE")
    if vu is not None:
        m["_"] = vu
    vp = reg("K_PLUS")
    if vp is not None:
        m["+"] = vp
    # Numpad (tokens from client event.code)
    for i in range(10):
        kp = reg(f"K_KP{i}", f"K_KP_{i}")
        if kp is not None:
            m[f"Numpad{i}"] = kp
    add("K_KP_PERIOD", "NumpadDecimal")
    add("K_KP_ENTER", "NumpadEnter")
    add("K_KP_PLUS", "NumpadAdd")
    add("K_KP_MINUS", "NumpadSubtract")
    add("K_KP_MULTIPLY", "NumpadMultiply")
    add("K_KP_DIVIDE", "NumpadDivide")
    add("K_KP_EQUALS", "NumpadEqual", "NumpadEquals")
    return m


def _sdl2_keycode_to_scancode_map(pg: Any) -> Dict[int, int]:
    """Map SDL2 key codes (often >512) to get_pressed() indices. See pygame K_RIGHT vs KSCAN_RIGHT."""
    m: Dict[int, int] = {}
    for name in dir(pg):
        if not name.startswith("KSCAN_"):
            continue
        kn = "K_" + name[6:]
        if not hasattr(pg, kn):
            continue
        kv = int(getattr(pg, kn))
        if kv < 512:
            continue
        m[kv] = int(getattr(pg, name))
    return m


class _GetPressedView:
    """Supports keys[pygame.K_RIGHT] where K_RIGHT does not fit in the 512-slot SDL2 pressed array."""

    __slots__ = ("_base", "_held", "_k2s")

    def __init__(
        self, base: Tuple[bool, ...], held: Set[int], k2s: Dict[int, int]
    ) -> None:
        self._base = base
        self._held = held
        self._k2s = k2s

    def __getitem__(self, k: int) -> bool:
        if k in self._held:
            return True
        if isinstance(k, int) and 0 <= k < len(self._base):
            if self._base[k]:
                return True
        sc = self._k2s.get(int(k))
        if sc is not None and 0 <= sc < len(self._base):
            return bool(self._base[sc])
        return False

    def __len__(self) -> int:
        return len(self._base)


def _parse_record_size() -> Tuple[int, int]:
    raw = os.environ.get("ARCADE_RECORD_SURFACE_SIZE", "800x800").replace(",", "x")
    parts = [p for p in raw.split("x") if p.strip()]
    if len(parts) >= 2:
        return int(parts[0].strip()), int(parts[1].strip())
    return 800, 800


def _color_to_list(c: Any, pg: Optional[Any] = None) -> List[int]:
    """Normalize pygame draw/font colors for JSON; supports names, hex, tuples, Color."""
    if hasattr(c, "r") and hasattr(c, "g") and hasattr(c, "b"):
        a = getattr(c, "a", 255)
        return [int(c.r), int(c.g), int(c.b), int(a)]
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        t = [int(x) for x in c[:4]]
        if len(t) == 3:
            t.append(255)
        return t[:4]
    if pg is not None:
        try:
            col = pg.Color(c)
            return [int(col.r), int(col.g), int(col.b), int(col.a)]
        except (ValueError, TypeError, AttributeError):
            pass
    return [128, 128, 128, 255]


def _rect_to_list(r: Any) -> List[int]:
    if hasattr(r, "x"):
        return [int(r.x), int(r.y), int(r.w), int(r.h)]
    return [int(r[0]), int(r[1]), int(r[2]), int(r[3])]


def _blit_dest_xy(dest: Any) -> Tuple[int, int]:
    if hasattr(dest, "x"):
        return int(dest.x), int(dest.y)
    return int(dest[0]), int(dest[1])


def _blit_dest_box(dest: Any, fallback_w: int, fallback_h: int) -> Tuple[int, int, int, int]:
    """Destination (x,y,w,h) for a blit; use fallback size when dest is only a position."""
    if hasattr(dest, "x"):
        dx, dy = int(dest.x), int(dest.y)
        if hasattr(dest, "w") and hasattr(dest, "h"):
            dw, dh = int(dest.w), int(dest.h)
            if dw > 0 and dh > 0:
                return dx, dy, dw, dh
        return dx, dy, fallback_w, fallback_h
    if isinstance(dest, (list, tuple)) and len(dest) >= 2:
        return int(dest[0]), int(dest[1]), fallback_w, fallback_h
    return 0, 0, fallback_w, fallback_h


def _area_xywh(area: Any) -> Tuple[int, int, int, int]:
    if area is None:
        return 0, 0, 0, 0
    if hasattr(area, "x"):
        return int(area.x), int(area.y), int(area.w), int(area.h)
    return int(area[0]), int(area[1]), int(area[2]), int(area[3])


def _subsurface_propagate_tex(
    bridge: "_Bridge",
    self_surf: Any,
    rect: Any,
    real_sub: Callable[[Any, Any], Any],
) -> Any:
    """Call C subsurface, then copy texture metadata (pygame 2.6+ cannot use surface._arcade_tex)."""
    sub = real_sub(self_surf, rect)
    tex = bridge.surface_tex.get(self_surf)
    if isinstance(tex, dict) and tex.get("id"):
        rx, ry, rw, rh = _rect_to_list(rect)
        # Subsurface pixels may be a crop of an already-rotated raster; do not re-apply rot_deg.
        bridge.surface_tex[sub] = {
            "id": tex["id"],
            "sx": int(tex["sx"]) + rx,
            "sy": int(tex["sy"]) + ry,
            "sw": rw,
            "sh": rh,
        }
    return sub


def _surface_glyphs_add(
    bridge: "_Bridge",
    dest_surf: Any,
    gx: int,
    gy: int,
    text: str,
    col: List[int],
    px: int,
) -> None:
    lst = bridge.surface_glyphs.setdefault(dest_surf, [])
    lst.append((gx, gy, text, col, px))


def _surface_glyphs_merge_chunk(
    bridge: "_Bridge", dest_surf: Any, ox: int, oy: int, chunk: List[Tuple[int, int, str, List[int], int]]
) -> None:
    lst = bridge.surface_glyphs.setdefault(dest_surf, [])
    for gx, gy, text, col, px in chunk:
        lst.append((ox + gx, oy + gy, text, col, px))


def _glyphs_rescale_positions(
    chunk: List[Tuple[int, int, str, List[int], int]],
    sx: float,
    sy: float,
) -> List[Tuple[int, int, str, List[int], int]]:
    """Scale glyph x,y and font px when a surface is scaled (e.g. game → viewport)."""
    if sx <= 0 or sy <= 0:
        return list(chunk)
    fac = min(sx, sy)
    out: List[Tuple[int, int, str, List[int], int]] = []
    for gx, gy, text, col, px in chunk:
        npx = max(8, int(round(px * fac)))
        out.append((int(round(gx * sx)), int(round(gy * sy)), text, col, npx))
    return out


def _migrate_glyphs_after_resize(
    bridge: "_Bridge",
    src: Any,
    dst: Any,
    sw: int,
    sh: int,
    dw: int,
    dh: int,
) -> None:
    """
    Move accumulated Font.render metadata from src to dst with new coordinates.
    Used when pygame.transform.scale*(src) produces dst; otherwise a final blit to
    the display would target dst, which had no glyphs (they stayed on src).
    """
    chunk = bridge.surface_glyphs.pop(src, None)
    if not chunk:
        return
    if sw <= 0 or sh <= 0:
        bridge.surface_glyphs[dst] = list(chunk)
        return
    sx = dw / float(sw)
    sy = dh / float(sh)
    bridge.surface_glyphs[dst] = _glyphs_rescale_positions(chunk, sx, sy)


def _tex_region_for_blit(
    bridge: "_Bridge", source: Any, area: Any
) -> Optional[Dict[str, Any]]:
    """Map a blitted surface (+ optional sub-rect) to texture file coordinates."""
    tex = bridge.surface_tex.get(source)
    if tex is None or not isinstance(tex, dict):
        return None
    tid = tex.get("id")
    if not tid or not isinstance(tid, str):
        return None
    try:
        gw = max(1, int(source.get_width()))
        gh = max(1, int(source.get_height()))
    except Exception:
        return None
    tsx = int(tex["sx"])
    tsy = int(tex["sy"])
    tsw = max(1, int(tex["sw"]))
    tsh = max(1, int(tex["sh"]))
    if area is None:
        return {"id": tid, "sx": tsx, "sy": tsy, "sw": tsw, "sh": tsh}
    ax, ay, aw, ah = _area_xywh(area)
    if aw <= 0 or ah <= 0:
        return None
    fsx = tsx + (ax / gw) * tsw
    fsy = tsy + (ay / gh) * tsh
    fsw = (aw / gw) * tsw
    fsh = (ah / gh) * tsh
    return {
        "id": tid,
        "sx": int(round(fsx)),
        "sy": int(round(fsy)),
        "sw": max(1, int(round(fsw))),
        "sh": max(1, int(round(fsh))),
    }


def _ensure_recording_surface(pg: Any, bridge: "_Bridge", out: Any) -> Any:
    """
    pygame.transform.* often returns a plain C Surface. Those cannot use our subclass
    ``copy()`` hook (immutable base type), so ``surface.copy()`` drops ``surface_tex`` and
    streamed frames lose ``tblit``. Wrap textured plain outputs in ``pg.Surface`` (the
    patched RecordingSurface) and move weak-key metadata to the wrapper.
    """
    RS = pg.Surface
    if isinstance(out, RS):
        return out
    t0 = bridge.surface_tex.get(out)
    if not (isinstance(t0, dict) and t0.get("id")):
        return out
    try:
        w, h = int(out.get_width()), int(out.get_height())
        if w <= 0 or h <= 0:
            return out
        wrapped = RS((w, h), out.get_flags())
        wrapped.blit(out, (0, 0))
        t = bridge.surface_tex.pop(out, None)
        if t:
            bridge.surface_tex[wrapped] = t
        return wrapped
    except Exception:
        return out


def _sample_surface_rgba(surf: Any, pg: Any) -> List[int]:
    try:
        w, h = surf.get_size()
        if w <= 0 or h <= 0:
            return [0, 0, 0, 255]
        px = surf.get_at((min(w - 1, w // 2), min(h - 1, h // 2)))
        return _color_to_list(px, pg)
    except Exception:
        return [40, 40, 50, 255]


MAX_CMDS_PER_FRAME = int(os.environ.get("ARCADE_REMOTE_MAX_CMDS", "8000"))
MAX_FRAME_JSON_BYTES = int(os.environ.get("ARCADE_REMOTE_MAX_FRAME_BYTES", "6_000_000").replace("_", ""))


def _sanitize_for_json(obj: Any) -> Any:
    """Avoid invalid JSON (NaN) and cap recursion depth from weird objects."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    if isinstance(obj, (int, str)) or obj is None or obj is True or obj is False:
        return obj
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    return str(obj)


class _Bridge:
    def __init__(
        self,
        frame_q: Queue,
        cmd_q: Queue,
        record_wh: Tuple[int, int],
    ) -> None:
        self.frame_q = frame_q
        self.cmd_q = cmd_q
        self.record_w, self.record_h = record_wh
        self.keys_held: Set[int] = set()
        self.mouse_buttons_held: Set[int] = set()
        self.mouse_pos: Tuple[int, int] = (400, 400)
        self._pg: Any = None
        self._real_update: Any = None
        self._real_get_pressed: Any = None
        self._real_mouse_get_pressed: Any = None
        self._real_get_pos: Any = None
        self._real_set_mode: Any = None
        self.display_surface_ref: Any = None
        self.draw_cmds: List[List[Any]] = []
        self.text_meta: Dict[int, Tuple[str, List[int], int]] = {}
        # Surfaces built from font.render blits (e.g. multi-color titles): glyphs in local coords.
        self.surface_glyphs: "weakref.WeakKeyDictionary[Any, List[Tuple[int, int, str, List[int], int]]]" = (
            weakref.WeakKeyDictionary()
        )
        self._patched_get_pressed: Any = None
        self.surface_tex: "weakref.WeakKeyDictionary[Any, Dict[str, Any]]" = (
            weakref.WeakKeyDictionary()
        )
        self.music_rel_id: Optional[str] = None
        self._dyn_sound_seq = 0
        self._dyn_sound_blobs: Dict[str, str] = {}
        self._dyn_sound_sent: Set[str] = set()

    def _register_dynamic_wav(self, wav: bytes) -> str:
        sid = f"__arcDyn/{self._dyn_sound_seq}"
        self._dyn_sound_seq += 1
        self._dyn_sound_blobs[sid] = base64.b64encode(wav).decode("ascii")
        return sid

    def _sound_id_from_buffer_kw(self, buf: Any) -> Optional[str]:
        """WAV-encode PCM from ``Sound(buffer=…)`` for one-time delivery in ``snd``."""
        try:
            if buf is None:
                return None
            if isinstance(buf, array.array):
                pcm = buf.tobytes()
            elif isinstance(buf, (bytes, bytearray, memoryview)):
                pcm = bytes(buf)
            else:
                return None
            if not pcm:
                return None
            pg = self._pg
            freq, fmt, chans = 44100, -16, 1
            if pg is not None:
                try:
                    gi = pg.mixer.get_init()
                    if gi is not None and gi[0]:
                        freq = int(gi[0])
                        fmt = int(gi[1])
                        chans = int(gi[2])
                except Exception:
                    pass
            sw = _sampwidth_from_pygame_format(fmt)
            wav = _pcm_bytes_to_wav(pcm, freq, chans, sw)
            if not wav:
                return None
            return self._register_dynamic_wav(wav)
        except Exception:
            return None

    def _should_record_surface(self, surf: Any) -> bool:
        if surf is None:
            return False
        if self.display_surface_ref is not None and surf is self.display_surface_ref:
            return True
        try:
            return surf.get_size() == (self.record_w, self.record_h)
        except Exception:
            return False

    def _append_cmd(self, cmd: List[Any]) -> None:
        if len(self.draw_cmds) >= MAX_CMDS_PER_FRAME:
            return
        self.draw_cmds.append(cmd)

    def process_commands(self) -> None:
        while True:
            try:
                msg: Dict[str, Any] = self.cmd_q.get_nowait()
            except Empty:
                break
            t = msg.get("t") or msg.get("type")
            if t in ("quit", "stop"):
                self._post_quit()
                continue
            pg = self._pg
            if t == "keydown":
                k = _KEY_MAP.get(msg.get("k") or msg.get("key"), None)
                if k is not None:
                    self.keys_held.add(k)
                    pg.event.post(pg.event.Event(pg.KEYDOWN, key=k))
            elif t == "keyup":
                k = _KEY_MAP.get(msg.get("k") or msg.get("key"), None)
                if k is not None:
                    self.keys_held.discard(k)
                    pg.event.post(pg.event.Event(pg.KEYUP, key=k))
            elif t == "move":
                x = int(msg.get("x", 0))
                y = int(msg.get("y", 0))
                self.mouse_pos = (x, y)
                pg.event.post(
                    pg.event.Event(pg.MOUSEMOTION, pos=self.mouse_pos, rel=(0, 0))
                )
            elif t == "mousedown":
                b = int(msg.get("b", 1))
                if 1 <= b <= 3:
                    self.mouse_buttons_held.add(b)
                pg.event.post(
                    pg.event.Event(
                        pg.MOUSEBUTTONDOWN,
                        button=b,
                        pos=self.mouse_pos,
                    )
                )
            elif t == "mouseup":
                b = int(msg.get("b", 1))
                if 1 <= b <= 3:
                    self.mouse_buttons_held.discard(b)
                pg.event.post(
                    pg.event.Event(
                        pg.MOUSEBUTTONUP,
                        button=b,
                        pos=self.mouse_pos,
                    )
                )

    def _post_quit(self) -> None:
        pg = self._pg
        pg.event.post(pg.event.Event(pg.QUIT))

    def emit_frame(self, surf: Any) -> None:
        if surf is None:
            return
        w, h = surf.get_size()
        if w <= 0 or h <= 0:
            return
        snap = list(self.draw_cmds)
        self.draw_cmds.clear()
        max_n = min(len(snap), MAX_CMDS_PER_FRAME)
        payload: Optional[bytes] = None
        while max_n >= 0:
            # Prefix: keep early cmds (clear, bg, sprites). Suffix would drop them and
            # leave only HUD — looks like “no enemies” / missing world on busy frames.
            use = snap[:max_n] if max_n < len(snap) else snap
            body: Dict[str, Any] = {
                "v": 2,
                "w": w,
                "h": h,
                "cmds": _sanitize_for_json(use),
            }
            body2 = body
            snd_mark: List[str] = []
            for sid in sorted(self._dyn_sound_blobs.keys()):
                if sid in self._dyn_sound_sent:
                    continue
                trial = dict(body2)
                tsnd = dict(trial.get("snd", {}))
                tsnd[sid] = self._dyn_sound_blobs[sid]
                trial["snd"] = tsnd
                try:
                    raw_try = json.dumps(
                        trial, separators=(",", ":"), allow_nan=False
                    ).encode("utf-8")
                except (TypeError, ValueError, OverflowError):
                    break
                if len(raw_try) <= MAX_FRAME_JSON_BYTES:
                    body2 = trial
                    snd_mark.append(sid)
                else:
                    break
            try:
                raw = json.dumps(
                    body2, separators=(",", ":"), allow_nan=False
                ).encode("utf-8")
            except (TypeError, ValueError, OverflowError):
                max_n = max(0, max_n // 2)
                if max_n == 0:
                    break
                continue
            if len(raw) <= MAX_FRAME_JSON_BYTES or max_n <= 200:
                for sid in snd_mark:
                    self._dyn_sound_sent.add(sid)
                payload = raw
                break
            max_n = max(200, max_n * 2 // 3)
        if not payload:
            try:
                payload = json.dumps(
                    {"v": 2, "w": w, "h": h, "cmds": [], "drop": 1},
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            except (TypeError, ValueError):
                return
        if len(payload) > MAX_FRAME_JSON_BYTES:
            try:
                payload = json.dumps(
                    {"v": 2, "w": w, "h": h, "cmds": [], "drop": 1},
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            except (TypeError, ValueError):
                return
        try:
            while True:
                try:
                    self.frame_q.get_nowait()
                except Empty:
                    break
            self.frame_q.put_nowait(payload)
        except Exception:
            pass

    def install(self, pg: Any, game_root: Optional[Path] = None) -> None:
        self._pg = pg
        global _KEY_MAP
        _KEY_MAP = _build_key_map(pg)
        bridge = self

        _base_surface = pg.Surface
        _real_sub = _base_surface.subsurface

        def _universal_subsurface(self: Any, rect: Any) -> Any:
            return _subsurface_propagate_tex(bridge, self, rect, _real_sub)

        try:
            _base_surface.subsurface = _universal_subsurface  # type: ignore[method-assign]
        except TypeError:
            # pygame 2.6+: Surface is immutable; RecordingSurface.subsurface handles subclass instances.
            pass

        _real_load = pg.image.load

        _real_scale = pg.transform.scale
        _real_smoothscale = pg.transform.smoothscale
        _real_scale_by = getattr(pg.transform, "scale_by", None)
        _real_smoothscale_by = getattr(pg.transform, "smoothscale_by", None)

        def _copy_tex(dst: Any, src: Any, *, add_rot: float = 0.0) -> None:
            t = bridge.surface_tex.get(src)
            if isinstance(t, dict) and t.get("id"):
                nd = dict(t)
                nd["rot_deg"] = float(nd.get("rot_deg", 0.0)) + float(add_rot)
                bridge.surface_tex[dst] = nd

        def _scale_wrapped(surf: Any, size: Any, *a: Any, **kw: Any) -> Any:
            out = _real_scale(surf, size, *a, **kw)
            _copy_tex(out, surf, add_rot=0.0)
            out = _ensure_recording_surface(pg, bridge, out)
            try:
                sw, sh = int(surf.get_width()), int(surf.get_height())
                dw, dh = int(out.get_width()), int(out.get_height())
                _migrate_glyphs_after_resize(bridge, surf, out, sw, sh, dw, dh)
            except Exception:
                pass
            return out

        def _smoothscale_wrapped(surf: Any, size: Any, *a: Any, **kw: Any) -> Any:
            out = _real_smoothscale(surf, size, *a, **kw)
            _copy_tex(out, surf, add_rot=0.0)
            out = _ensure_recording_surface(pg, bridge, out)
            try:
                sw, sh = int(surf.get_width()), int(surf.get_height())
                dw, dh = int(out.get_width()), int(out.get_height())
                _migrate_glyphs_after_resize(bridge, surf, out, sw, sh, dw, dh)
            except Exception:
                pass
            return out

        pg.transform.scale = _scale_wrapped
        pg.transform.smoothscale = _smoothscale_wrapped

        if _real_scale_by is not None:

            def _scale_by_wrapped(surf: Any, factor: Any, *a: Any, **kw: Any) -> Any:
                out = _real_scale_by(surf, factor, *a, **kw)
                _copy_tex(out, surf, add_rot=0.0)
                out = _ensure_recording_surface(pg, bridge, out)
                try:
                    sw, sh = int(surf.get_width()), int(surf.get_height())
                    dw, dh = int(out.get_width()), int(out.get_height())
                    _migrate_glyphs_after_resize(bridge, surf, out, sw, sh, dw, dh)
                except Exception:
                    pass
                return out

            pg.transform.scale_by = _scale_by_wrapped  # type: ignore[method-assign]

        if _real_smoothscale_by is not None:

            def _smoothscale_by_wrapped(surf: Any, factor: Any, *a: Any, **kw: Any) -> Any:
                out = _real_smoothscale_by(surf, factor, *a, **kw)
                _copy_tex(out, surf, add_rot=0.0)
                out = _ensure_recording_surface(pg, bridge, out)
                try:
                    sw, sh = int(surf.get_width()), int(surf.get_height())
                    dw, dh = int(out.get_width()), int(out.get_height())
                    _migrate_glyphs_after_resize(bridge, surf, out, sw, sh, dw, dh)
                except Exception:
                    pass
                return out

            pg.transform.smoothscale_by = _smoothscale_by_wrapped  # type: ignore[method-assign]

        _real_tr_rotate = getattr(pg.transform, "rotate", None)
        _real_tr_rotozoom = getattr(pg.transform, "rotozoom", None)
        _real_tr_flip = getattr(pg.transform, "flip", None)
        if _real_tr_rotate is not None:

            def _rotate_wrapped(surface: Any, angle: Any, *a: Any, **kw: Any) -> Any:
                out = _real_tr_rotate(surface, angle, *a, **kw)
                _copy_tex(out, surface, add_rot=float(angle))
                return _ensure_recording_surface(pg, bridge, out)

            pg.transform.rotate = _rotate_wrapped
        if _real_tr_rotozoom is not None:

            def _rotozoom_wrapped(surface: Any, angle: Any, scale: Any, *a: Any, **kw: Any) -> Any:
                out = _real_tr_rotozoom(surface, angle, scale, *a, **kw)
                _copy_tex(out, surface, add_rot=float(angle))
                return _ensure_recording_surface(pg, bridge, out)

            pg.transform.rotozoom = _rotozoom_wrapped
        if _real_tr_flip is not None:

            def _transform_flip_wrapped(
                surface: Any, flip_x: Any, flip_y: Any, *a: Any, **kw: Any
            ) -> Any:
                out = _real_tr_flip(surface, flip_x, flip_y, *a, **kw)
                _copy_tex(out, surface, add_rot=0.0)
                return _ensure_recording_surface(pg, bridge, out)

            pg.transform.flip = _transform_flip_wrapped

        display = pg.display
        key = pg.key
        mouse = pg.mouse

        self._real_set_mode = display.set_mode
        self._real_get_surface = display.get_surface
        self._real_update = display.update
        self._real_flip = display.flip
        self._real_get_pressed = key.get_pressed
        self._real_mouse_get_pressed = mouse.get_pressed
        self._real_get_pos = mouse.get_pos
        _kcode_scan = _sdl2_keycode_to_scancode_map(pg)

        def set_mode(*a: Any, **kw: Any):
            a = list(a)
            if a:
                if hasattr(a[0], "__iter__") and not isinstance(a[0], (str, bytes)):
                    sz = tuple(a[0])
                    if len(sz) == 2 and sz[0] == 0 and sz[1] == 0:
                        a[0] = (bridge.record_w, bridge.record_h)
                if len(a) >= 2:
                    a[1] = int(a[1]) & ~pg.FULLSCREEN
            if "flags" in kw:
                kw["flags"] = int(kw["flags"]) & ~pg.FULLSCREEN
            surf = bridge._real_set_mode(*a, **kw)
            RS = pg.Surface
            if not isinstance(surf, RS):
                try:
                    w, h = surf.get_width(), surf.get_height()
                    wrapped = RS((w, h), surf.get_flags())
                    wrapped.blit(surf, (0, 0))
                    surf = wrapped
                except Exception:
                    pass
            bridge.display_surface_ref = surf
            _rehook_after_pg_init()
            return surf

        def get_surface() -> Any:
            if bridge.display_surface_ref is not None:
                return bridge.display_surface_ref
            return bridge._real_get_surface()

        def get_pressed():
            base = bridge._real_get_pressed()
            return _GetPressedView(tuple(base), bridge.keys_held, _kcode_scan)

        bridge._patched_get_pressed = get_pressed

        def get_pos():
            return bridge.mouse_pos

        def mouse_get_pressed(*args: Any, **kwargs: Any) -> Any:
            """
            Headless SDL has no real pointer; games that poll pygame.mouse.get_pressed()
            (common for menus) would always see no buttons. Merge browser mousedown/up
            into the tuple pygame returns.
            """
            real = bridge._real_mouse_get_pressed(*args, **kwargs)
            syn = bridge.mouse_buttons_held
            lst = list(real)
            for i, btn in enumerate((1, 2, 3, 4, 5)):
                if i >= len(lst):
                    break
                if btn in syn:
                    lst[i] = True
            return tuple(lst)

        bridge._patched_mouse_get_pressed = mouse_get_pressed

        def _pump_input_and_cmds() -> None:
            if bridge._patched_get_pressed is not None:
                if pg.key.get_pressed is not bridge._patched_get_pressed:
                    pg.key.get_pressed = bridge._patched_get_pressed
            if getattr(bridge, "_patched_mouse_get_pressed", None) is not None:
                if pg.mouse.get_pressed is not bridge._patched_mouse_get_pressed:
                    pg.mouse.get_pressed = bridge._patched_mouse_get_pressed
            bridge.process_commands()

        def update(*args: Any, **kwargs: Any):
            _pump_input_and_cmds()
            if args or kwargs:
                r = bridge._real_update(*args, **kwargs)
            else:
                r = bridge._real_update()
            bridge.emit_frame(pg.display.get_surface())
            return r

        def flip() -> Any:
            _pump_input_and_cmds()
            r = bridge._real_flip()
            bridge.emit_frame(pg.display.get_surface())
            return r

        _real_init = pg.init

        def init(*a: Any, **kw: Any):
            r = _real_init(*a, **kw)
            if bridge._patched_get_pressed is not None:
                pg.key.get_pressed = bridge._patched_get_pressed
            _rehook_after_pg_init()
            return r

        pg.init = init

        display.set_mode = set_mode
        display.get_surface = get_surface
        display.update = update
        display.flip = flip
        key.get_pressed = get_pressed
        mouse.get_pos = get_pos
        mouse.get_pressed = mouse_get_pressed
        _real_set_cursor = getattr(mouse, "set_cursor", None)

        try:
            _cursors_mod = pg.cursors
            _real_cursors_set_cursor = getattr(_cursors_mod, "set_cursor", None)
        except Exception:
            _cursors_mod = None
            _real_cursors_set_cursor = None

        def cursors_set_cursor_safe(*a: Any, **kw: Any) -> Any:
            if _real_cursors_set_cursor is None:
                return None
            try:
                return _real_cursors_set_cursor(*a, **kw)
            except Exception:
                return None

        def set_cursor_safe(*a: Any, **kw: Any) -> Any:
            if _real_set_cursor is None:
                return None
            try:
                return _real_set_cursor(*a, **kw)
            except Exception:
                return None

        def _rehook_after_pg_init() -> None:
            """pygame.init() / set_mode can restore bindings; headless SDL errors on system cursors."""
            key.get_pressed = get_pressed
            mouse.get_pos = get_pos
            mouse.get_pressed = mouse_get_pressed
            if _real_set_cursor is not None:
                mouse.set_cursor = set_cursor_safe
            if _cursors_mod is not None and _real_cursors_set_cursor is not None:
                _cursors_mod.set_cursor = cursors_set_cursor_safe

        if _cursors_mod is not None and _real_cursors_set_cursor is not None:
            _cursors_mod.set_cursor = cursors_set_cursor_safe

        if _real_set_cursor is not None:
            mouse.set_cursor = set_cursor_safe

        _install_draw_recording(pg, bridge)
        _install_blit_and_font(pg, bridge, base_surface_class=_base_surface)

        def _load_wrapped(file_path: Any, *a: Any, **kw: Any) -> Any:
            file_path = _resolve_case_insensitive_image_path(file_path)
            raw = _real_load(file_path, *a, **kw)
            RS = pg.Surface
            try:
                w, h = raw.get_width(), raw.get_height()
                out = RS((w, h), raw.get_flags())
                out.blit(raw, (0, 0))
                target = out
            except Exception:
                target = raw
            if game_root is not None:
                try:
                    p = Path(str(file_path)).expanduser()
                    if not p.is_absolute():
                        p = (Path.cwd() / p).resolve()
                    else:
                        p = p.resolve()
                    rel = p.relative_to(game_root.resolve())
                    tw, th = target.get_width(), target.get_height()
                    bridge.surface_tex[target] = {
                        "id": str(rel).replace("\\", "/"),
                        "sx": 0,
                        "sy": 0,
                        "sw": int(tw),
                        "sh": int(th),
                    }
                except Exception:
                    pass
            return target

        pg.image.load = _load_wrapped

        class _ArcadeWebTone:
            __slots__ = ()

            def tone(
                self,
                freq_hz: float = 440.0,
                duration_ms: int = 200,
                volume: float = 0.2,
            ) -> None:
                try:
                    fh = max(20.0, min(20000.0, float(freq_hz)))
                    ms = max(1, min(60000, int(duration_ms)))
                    v = max(0.0, min(1.0, float(volume)))
                    bridge._append_cmd(["tone", {"f": fh, "ms": ms, "v": v}])
                except Exception:
                    pass

        try:
            setattr(pg, "arcade_web", _ArcadeWebTone())
        except Exception:
            pass

        _mixer_mod = getattr(pg, "mixer", None)
        if _mixer_mod is not None:
            _music_mod = getattr(_mixer_mod, "music", None)
            if _music_mod is not None:
                _real_music_load = getattr(_music_mod, "load", None)
                if _real_music_load is not None:

                    def _music_load_wrapped(filename: Any, *a: Any, **kw: Any) -> Any:
                        fn = _resolve_case_insensitive_image_path(filename)
                        bridge.music_rel_id = _arcade_sound_rel_id(fn, game_root)
                        return _real_music_load(fn, *a, **kw)

                    _music_mod.load = _music_load_wrapped  # type: ignore[method-assign]

                _real_music_play = getattr(_music_mod, "play", None)
                if _real_music_play is not None:

                    def _music_play_wrapped(*a: Any, **kw: Any) -> Any:
                        r = _real_music_play(*a, **kw)
                        try:
                            mid = bridge.music_rel_id
                            if mid:
                                # pygame.mixer.music.play(loops=-1, start=0.0, fade_ms=0)
                                loops = -1
                                if a:
                                    loops = int(a[0])
                                elif "loops" in kw:
                                    loops = int(kw["loops"])
                                bridge._append_cmd(
                                    ["music_play", {"id": mid, "loops": loops}]
                                )
                        except Exception:
                            pass
                        return r

                    _music_mod.play = _music_play_wrapped  # type: ignore[method-assign]

                _real_music_stop = getattr(_music_mod, "stop", None)
                if _real_music_stop is not None:

                    def _music_stop_wrapped(*a: Any, **kw: Any) -> Any:
                        r = _real_music_stop(*a, **kw)
                        try:
                            bridge._append_cmd(["music_stop", {}])
                        except Exception:
                            pass
                        return r

                    _music_mod.stop = _music_stop_wrapped  # type: ignore[method-assign]

            # pygame 2.6+: ``mixer.Sound`` and ``mixer.Channel`` are immutable — cannot
            # monkey-patch ``Channel.play``. Subclassing ``Sound`` and overriding ``play``
            # covers ``sound.play()`` (``Channel.play`` does not call the Python method).
            _real_sound_ctor = getattr(_mixer_mod, "Sound", None)
            if _real_sound_ctor is not None:
                _SoundBase: Any = _real_sound_ctor

                class _ArcadeRemoteSound(_SoundBase):
                    def __init__(self, *a: Any, **kw: Any) -> None:
                        kwd = dict(kw)
                        aa = a
                        if aa:
                            aa = (_resolve_case_insensitive_image_path(aa[0]),) + tuple(
                                aa[1:]
                            )
                        super().__init__(*aa, **kwd)
                        self._arcade_sound_id: Optional[str] = None
                        if aa:
                            self._arcade_sound_id = _arcade_sound_rel_id(
                                aa[0], game_root
                            )
                        elif kwd.get("buffer") is not None:
                            self._arcade_sound_id = bridge._sound_id_from_buffer_kw(
                                kwd.get("buffer")
                            )

                    def play(self, *a: Any, **kw: Any) -> Any:
                        r = super().play(*a, **kw)
                        try:
                            rid = self._arcade_sound_id
                            if rid:
                                loops = 0
                                if a:
                                    loops = int(a[0])
                                elif "loops" in kw:
                                    loops = int(kw["loops"])
                                vol = 1.0
                                try:
                                    vol = float(self.get_volume())
                                except Exception:
                                    vol = 1.0
                                bridge._append_cmd(
                                    ["play_sound", {"id": rid, "loops": loops, "v": vol}]
                                )
                        except Exception:
                            pass
                        return r

                _mixer_mod.Sound = _ArcadeRemoteSound  # type: ignore[misc]

def _install_draw_recording(pg: Any, bridge: _Bridge) -> None:
    d = pg.draw
    names = (
        "rect",
        "circle",
        "polygon",
        "line",
        "lines",
        "ellipse",
        "arc",
        "aaline",
        "aalines",
    )
    for name in names:
        orig = getattr(d, name, None)
        if orig is None:
            continue
        setattr(d, name, _wrap_draw(name, orig, bridge, pg))


def _wrap_draw(
    name: str, orig: Callable[..., Any], bridge: _Bridge, pg: Any
) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        r = orig(*args, **kwargs)
        if not args:
            return r
        surf = args[0]
        if not bridge._should_record_surface(surf):
            return r
        try:
            if name == "rect":
                c = _color_to_list(args[1], pg)
                rect = _rect_to_list(args[2])
                width = int(kwargs["width"]) if "width" in kwargs else (
                    int(args[3]) if len(args) > 3 else 0
                )
                br = int(kwargs.get("border_radius", -1))
                bridge._append_cmd(["rect", {"c": c, "r": rect, "w": width, "br": max(0, br)}])
            elif name == "circle":
                c = _color_to_list(args[1], pg)
                center = args[2]
                rad = int(args[3])
                width = int(kwargs["width"]) if "width" in kwargs else (
                    int(args[4]) if len(args) > 4 else 0
                )
                cx, cy = int(center[0]), int(center[1])
                bridge._append_cmd(
                    ["circle", {"c": c, "cx": cx, "cy": cy, "rad": rad, "w": width}]
                )
            elif name == "polygon":
                c = _color_to_list(args[1], pg)
                pts = args[2]
                width = int(kwargs["width"]) if "width" in kwargs else (
                    int(args[3]) if len(args) > 3 else 0
                )
                flat: List[int] = []
                for p in pts:
                    flat.extend((int(p[0]), int(p[1])))
                bridge._append_cmd(["polygon", {"c": c, "p": flat, "w": width}])
            elif name == "line":
                c = _color_to_list(args[1], pg)
                a, b = args[2], args[3]
                width = int(kwargs["width"]) if "width" in kwargs else (
                    int(args[4]) if len(args) > 4 else 1
                )
                bridge._append_cmd(
                    [
                        "line",
                        {
                            "c": c,
                            "x1": int(a[0]),
                            "y1": int(a[1]),
                            "x2": int(b[0]),
                            "y2": int(b[1]),
                            "w": width,
                        },
                    ]
                )
            elif name == "lines":
                # lines(surface, color, closed, points, width=1)
                c = _color_to_list(args[1], pg)
                closed = bool(args[2])
                pts = args[3]
                width = int(kwargs["width"]) if "width" in kwargs else (
                    int(args[4]) if len(args) > 4 else 1
                )
                flat: List[int] = []
                for p in pts:
                    flat.extend((int(p[0]), int(p[1])))
                bridge._append_cmd(["lines", {"c": c, "p": flat, "closed": closed, "w": width}])
            elif name == "ellipse":
                c = _color_to_list(args[1], pg)
                rect = _rect_to_list(args[2])
                width = int(kwargs["width"]) if "width" in kwargs else (
                    int(args[3]) if len(args) > 3 else 0
                )
                bridge._append_cmd(["ellipse", {"c": c, "r": rect, "w": width}])
            elif name == "arc":
                c = _color_to_list(args[1], pg)
                rect = _rect_to_list(args[2])
                start = float(args[3])
                stop = float(args[4])
                width = int(kwargs["width"]) if "width" in kwargs else (
                    int(args[5]) if len(args) > 5 else 1
                )
                bridge._append_cmd(
                    ["arc", {"c": c, "r": rect, "a0": start, "a1": stop, "w": width}]
                )
            elif name == "aaline":
                c = _color_to_list(args[1], pg)
                a, b = args[2], args[3]
                bridge._append_cmd(
                    [
                        "line",
                        {
                            "c": c,
                            "x1": int(a[0]),
                            "y1": int(a[1]),
                            "x2": int(b[0]),
                            "y2": int(b[1]),
                            "w": 1,
                        },
                    ]
                )
            elif name == "aalines":
                # aalines(surface, color, closed, points, blend=1)
                c = _color_to_list(args[1], pg)
                closed = bool(args[2])
                pts = args[3]
                flat: List[int] = []
                for p in pts:
                    flat.extend((int(p[0]), int(p[1])))
                bridge._append_cmd(["lines", {"c": c, "p": flat, "closed": closed, "w": 1}])
        except Exception:
            pass
        return r

    return wrapped


def _install_blit_and_font(
    pg: Any, bridge: _Bridge, base_surface_class: Any = None
) -> None:
    # pygame 2: cannot assign Surface.blit (immutable); replace Surface with a subclass.
    _BaseSurface = base_surface_class if base_surface_class is not None else pg.Surface

    class RecordingSurface(_BaseSurface):
        def __init__(self, *a: Any, **kw: Any) -> None:
            super().__init__(*a, **kw)

        def fill(self, color: Any, rect: Any = None, special_flags: int = 0) -> Any:
            r = _BaseSurface.fill(self, color, rect, special_flags)
            try:
                if bridge._should_record_surface(self):
                    c = _color_to_list(color, pg)
                    disp = bridge.display_surface_ref
                    # present_frame() often does display.fill(black) after drawing to the
                    # back buffer, then blits — that blit is skipped in recording as duplicate.
                    # If we still record the fill, it is appended *after* back-buffer cmds and
                    # the browser paints a full-screen black rect on top of the whole frame.
                    if (
                        disp is not None
                        and self is disp
                        and rect is None
                        and len(c) >= 3
                        and int(c[0]) == 0
                        and int(c[1]) == 0
                        and int(c[2]) == 0
                        and (len(c) < 4 or int(c[3]) >= 255)
                    ):
                        return r
                    if rect is None:
                        w, h = self.get_width(), self.get_height()
                        box = [0, 0, w, h]
                    else:
                        box = _rect_to_list(rect)
                    bridge._append_cmd(
                        ["rect", {"c": c, "r": box, "w": 0, "br": 0}]
                    )
            except Exception:
                pass
            return r

        def subsurface(self, rect: Any) -> Any:
            return _subsurface_propagate_tex(bridge, self, rect, _BaseSurface.subsurface)

        def convert(self, *a: Any, **kw: Any) -> Any:
            out = _BaseSurface.convert(self, *a, **kw)
            t = bridge.surface_tex.get(self)
            if isinstance(t, dict) and t.get("id"):
                bridge.surface_tex[out] = dict(t)
            return out

        def convert_alpha(self, *a: Any, **kw: Any) -> Any:
            out = _BaseSurface.convert_alpha(self, *a, **kw)
            t = bridge.surface_tex.get(self)
            if isinstance(t, dict) and t.get("id"):
                bridge.surface_tex[out] = dict(t)
            return out

        def copy(self) -> Any:
            raw = _BaseSurface.copy(self)
            t = bridge.surface_tex.get(self)
            if isinstance(t, dict) and t.get("id"):
                bridge.surface_tex[raw] = dict(t)
                return _ensure_recording_surface(bridge._pg, bridge, raw)
            return raw

        def blits(self, blit_sequence: Any, doreturn: Any = 1) -> Any:
            """pygame 2+ ``Group.draw`` calls ``surface.blits()``; record each like ``blit``."""
            dr = bool(doreturn)
            rects: List[Any] = []
            for item in blit_sequence:
                if len(item) == 2:
                    r = self.blit(item[0], item[1])
                elif len(item) == 3:
                    r = self.blit(item[0], item[1], item[2])
                else:
                    r = self.blit(item[0], item[1], item[2], item[3])
                if dr:
                    rects.append(r)
            return rects if dr else None

        def blit(
            self,
            source: Any,
            dest: Any,
            area: Any = None,
            special_flags: int = 0,
        ) -> Any:
            r = _BaseSurface.blit(self, source, dest, area, special_flags)
            try:
                disp = bridge.display_surface_ref
                sw, sh = source.get_width(), source.get_height()
                if (
                    disp is not None
                    and self is disp
                    and sw == bridge.record_w
                    and sh == bridge.record_h
                ):
                    # Skip recording this blit when it is the usual "present full
                    # back-buffer" copy (already streamed as draw cmds). If the source
                    # holds deferred text (Font.render → surface_glyphs), we must NOT
                    # return early — Space Shooter draws to okno 800×800 then blits to
                    # the 800×800 display; same dimensions triggered a silent drop of
                    # all menu text every frame.
                    pending = bridge.surface_glyphs.get(source)
                    if not pending:
                        return r
            except Exception:
                pass

            dx, dy = _blit_dest_xy(dest)
            disp = bridge.display_surface_ref

            # Font.render surfaces: either stream one "text" cmd to the display, or keep
            # glyph positions on an intermediate surface (e.g. VOID SURVIVOR built char-by-char).
            meta = bridge.text_meta.pop(id(source), None)
            if meta is not None:
                text, col, px = meta
                if disp is not None and self is disp:
                    bridge._append_cmd(
                        ["text", {"t": text, "c": col, "x": dx, "y": dy, "px": px}]
                    )
                else:
                    _surface_glyphs_add(bridge, self, dx, dy, text, col, px)
                return r

            chunk = bridge.surface_glyphs.pop(source, None)
            if chunk:
                if disp is not None and self is disp:
                    for gx, gy, gtext, col, px in chunk:
                        bridge._append_cmd(
                            [
                                "text",
                                {
                                    "t": gtext,
                                    "c": col,
                                    "x": dx + gx,
                                    "y": dy + gy,
                                    "px": px,
                                },
                            ]
                        )
                else:
                    _surface_glyphs_merge_chunk(bridge, self, dx, dy, chunk)
                return r

            if not bridge._should_record_surface(self):
                return r

            try:
                aw = source.get_width()
                ah = source.get_height()
                if area is not None:
                    if hasattr(area, "w"):
                        aw, ah = int(area.w), int(area.h)
                    else:
                        aw, ah = int(area[2]), int(area[3])
            except Exception:
                aw, ah = 1, 1

            tr = _tex_region_for_blit(bridge, source, area)
            if tr is not None:
                bx, by, bw, bh = _blit_dest_box(dest, aw, ah)
                src_tex = bridge.surface_tex.get(source)
                rot_deg = 0.0
                if isinstance(src_tex, dict):
                    rot_deg = float(src_tex.get("rot_deg", 0.0))
                if abs(rot_deg) > 1e-3:
                    bridge._append_cmd(
                        [
                            "tblit_rot",
                            {
                                "id": tr["id"],
                                "sx": tr["sx"],
                                "sy": tr["sy"],
                                "sw": tr["sw"],
                                "sh": tr["sh"],
                                "dx": bx,
                                "dy": by,
                                "dw": bw,
                                "dh": bh,
                                "deg": rot_deg,
                                "cx": bx + bw / 2.0,
                                "cy": by + bh / 2.0,
                            },
                        ]
                    )
                else:
                    bridge._append_cmd(
                        [
                            "tblit",
                            {
                                "id": tr["id"],
                                "sx": tr["sx"],
                                "sy": tr["sy"],
                                "sw": tr["sw"],
                                "sh": tr["sh"],
                                "dx": bx,
                                "dy": by,
                                "dw": bw,
                                "dh": bh,
                            },
                        ]
                    )
                return r

            c = _sample_surface_rgba(source, pg)
            bridge._append_cmd(["blit", {"x": dx, "y": dy, "w": aw, "h": ah, "c": c}])
            return r

    pg.Surface = RecordingSurface

    _RealFont = pg.font.Font
    _RealSysFont = pg.font.SysFont

    class _FontWrap:
        __slots__ = ("_inner",)

        def __init__(self, inner: Any) -> None:
            object.__setattr__(self, "_inner", inner)

        def render(
            self,
            text: Any,
            antialias: Any,
            color: Any,
            background: Any = None,
        ) -> Any:
            s = self._inner.render(text, antialias, color, background)
            try:
                bridge.text_meta[id(s)] = (
                    str(text),
                    _color_to_list(color, bridge._pg),
                    int(self._inner.get_height()),
                )
            except Exception:
                pass
            return s

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

        def __setattr__(self, name: str, value: Any) -> None:
            if name == "_inner":
                object.__setattr__(self, name, value)
            else:
                setattr(self._inner, name, value)

    def _Font_ctor(*args: Any, **kwargs: Any) -> _FontWrap:
        return _FontWrap(_RealFont(*args, **kwargs))

    def _SysFont_ctor(*args: Any, **kwargs: Any) -> _FontWrap:
        return _FontWrap(_RealSysFont(*args, **kwargs))

    pg.font.Font = _Font_ctor
    pg.font.SysFont = _SysFont_ctor


def remote_game_main(
    main_py: str,
    frame_q: Queue,
    cmd_q: Queue,
    max_frame_width: int = 720,
    record_wh: Optional[Tuple[int, int]] = None,
) -> None:
    del max_frame_width  # vector mode: unused, kept for API compat with parent Process args
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    os.environ.setdefault("PYTHONFAULTHANDLER", "1")

    _lf = os.environ.get("ARCADE_REMOTE_CHILD_LOG", "").strip()
    if not _lf:
        _lf = str(Path(__file__).resolve().parent / "logs" / "remote-child.log")
    try:
        Path(_lf).parent.mkdir(parents=True, exist_ok=True)
        _logfh = open(_lf, "a", encoding="utf-8", buffering=1)
        sys.stderr = _logfh
        sys.stdout = _logfh
    except OSError:
        pass

    import pygame

    main_path = Path(main_py).resolve()
    main_dir = main_path.parent
    try:
        os.chdir(str(main_dir))
    except OSError:
        pass

    # With multiprocessing "spawn", runpy.run_path does not reliably put the entry
    # script's directory first on sys.path, so imports like `from tridy import ...`
    # (sibling .py next to main) fail with ModuleNotFoundError. Running `python main.py`
    # from that folder always works — mirror that here.
    main_root = str(main_dir)
    try:
        while main_root in sys.path:
            sys.path.remove(main_root)
    except ValueError:
        pass
    sys.path.insert(0, main_root)

    _install_remote_writable_game_tree_redirect(main_dir)

    if record_wh is not None and len(record_wh) == 2:
        try:
            rw = max(1, min(8192, int(record_wh[0])))
            rh = max(1, min(8192, int(record_wh[1])))
        except (TypeError, ValueError):
            rw, rh = _parse_record_size()
    else:
        rw, rh = _parse_record_size()
    bridge = _Bridge(frame_q, cmd_q, record_wh=(rw, rh))
    bridge.install(pygame, game_root=main_dir)

    try:
        runpy.run_path(str(main_path), run_name="__main__")
    except SystemExit:
        pass
    except BaseException:
        import traceback

        traceback.print_exc(file=sys.stderr)
    finally:
        try:
            pygame.quit()
        except Exception:
            pass
