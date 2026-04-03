#!/usr/bin/env python3
"""
Manual sync only: the arcade server never clones or pulls repos by itself.

Run this when you want to add or update games. Clones into games/<repo>/ or runs
git pull --ff-only if that folder already exists. repos.txt is not read anywhere;
use it only as your own URL cheat sheet.

The running arcade process rescans games/ on every lobby and play request — no restart
is required for new games. After each clone/pull, server.sync applies chmod -R a+rX on the
checkout so the service user (not root) can read it; otherwise folders cloned as root could
be invisible until you restarted for unrelated reasons.

Optional: chown checkouts to the service user:
  export ARCADE_GAMES_OWNER=arcade:arcade

Optional automatic restart after a successful sync (all repos OK), e.g. after code deploys:
  export ARCADE_SYSTEMD_UNIT=arcade          # runs: systemctl restart arcade.service
  export ARCADE_SYNC_RESTART_CMD='sudo systemctl restart arcade'   # or any shell command
  export ARCADE_SYNC_AUTO_RESTART=1          # same as passing --restart every time

  sync_repos.py --restart …   # shorthand: same as ARCADE_SYSTEMD_UNIT=arcade

Use --no-restart to skip even when env vars / ARCADE_SYNC_AUTO_RESTART would restart.

Usage:
  sync_repos.py https://github.com/owner/repo
  sync_repos.py --restart https://github.com/owner/repo:main
  sync_repos.py URL [URL ...]

Optional ``:path`` after the repo URL picks the entry script: root name only (``…/repo:game``
resolves ``game`` or ``game.py``) or a repo-relative path. The ``.py`` suffix is optional;
segments may include spaces and non-ASCII characters (e.g. ``…/repo:source/game``).
Names may differ in case or internal whitespace on disk (e.g. ``Game Project .py``).
Stored as ``games/<repo>/.arcade-entry`` (actual filename as cloned).

After sync, each game is playable at https://your-host/<repository-folder-name>/
(same name as the directory under games/, e.g. games/space-shooter → /space-shooter/).
The browser opens a WebSocket to /play-ws/<folder-name>.

Lobby: games_catalog.json (keys = folder names under games/). Each successful sync updates
"repo_url", "sync_url" (full line for sync_repos.py, including ":entry" when needed),
"start_script" (the :suffix or omitted when using default main/index), "creator" (@owner),
and sets "title" from the folder name when "title" is missing or empty (custom titles persist).

With no arguments on a TTY, prompts for URLs (one per line; empty line runs sync).
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _collect_urls_interactive() -> list[str]:
    if not sys.stdin.isatty():
        print(
            "No URLs given and stdin is not a TTY. Pass URLs as arguments, e.g.\n"
            "  python3 sync_repos.py https://github.com/owner/repo",
            file=sys.stderr,
        )
        return []
    print("Enter GitHub repo URLs, one per line. Empty line starts the sync.")
    urls: list[str] = []
    while True:
        try:
            line = input("URL: ").strip()
        except EOFError:
            break
        if not line:
            break
        urls.append(line)
    return urls


def _parse_argv(argv: list[str]) -> tuple[list[str], bool, bool]:
    """Return (url_args, want_restart_flag, no_restart_flag)."""
    urls: list[str] = []
    want_restart = False
    no_restart = False
    for a in argv:
        if a == "--restart":
            want_restart = True
        elif a == "--no-restart":
            no_restart = True
        else:
            urls.append(a)
    return urls, want_restart, no_restart


def _run_optional_post_sync_restart(
    failures: int, *, cli_restart: bool, no_restart: bool
) -> None:
    if failures or no_restart:
        return
    cmd = os.environ.get("ARCADE_SYNC_RESTART_CMD", "").strip()
    if not cmd:
        unit = os.environ.get("ARCADE_SYSTEMD_UNIT", "").strip()
        if cli_restart and not unit:
            unit = "arcade"
        if unit:
            if not unit.endswith(".service"):
                unit = f"{unit}.service"
            cmd = f"systemctl restart {unit}"
    if not cmd:
        return
    log = logging.getLogger("arcade.sync")
    log.info("Post-sync restart: %s", cmd)
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("Post-sync restart could not run: %s", e)
        print(f"Warning: post-sync restart failed: {e}", file=sys.stderr)
        return
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()[:800]
        log.warning("Post-sync restart failed (%s): %s", r.returncode, err)
        print(
            "Warning: post-sync restart command failed. "
            "Fix permissions (often: sudo) or set ARCADE_SYNC_RESTART_CMD. "
            f"Output: {err}",
            file=sys.stderr,
        )
    else:
        print("Post-sync: restart command completed.", file=sys.stderr)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    from server import get_game_scripts, sync_repo_urls

    url_args, cli_restart, no_restart = _parse_argv(sys.argv[1:])
    if os.environ.get("ARCADE_SYNC_AUTO_RESTART", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        cli_restart = True
    urls = [u.strip() for u in url_args if u.strip()]
    if not urls:
        urls = _collect_urls_interactive()

    if not urls:
        print("No URLs — nothing to do.", file=sys.stderr)
        return 2

    failures = sync_repo_urls(urls)
    _run_optional_post_sync_restart(
        failures, cli_restart=cli_restart, no_restart=no_restart
    )
    n = len(get_game_scripts())
    if failures:
        print(
            f"Finished with {failures} repo failure(s). "
            f"{n} game(s) found under games/ (entry: .arcade-entry, main.py / index.py, or one root .py). "
            "Play each at https://YOUR_HOST/<folder-name>/",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK. {n} game(s) under games/ "
        "(optional :path on the URL for custom names; else main.py / index.py or one root .py). "
        "Play at https://YOUR_HOST/<folder-name>/ (see lobby at /). "
        "Hard-refresh the lobby (Ctrl+F5) if your browser cached it; "
        "sync applied chmod on new checkouts so the service user can see them without restart."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130) from None
