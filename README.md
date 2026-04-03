# pygame-to-html

FastAPI server that runs Pygame games **headlessly** on the server, encodes frames, and streams them to the browser over **WebSockets**. The client uses an **HTML5 canvas** (and JavaScript) to display the stream and send keyboard/mouse input back to the game process.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/` for the lobby. Use **one** uvicorn worker for WebSocket play routes.

## Layout

| Path | Role |
|------|------|
| `server.py` | FastAPI app, lobby HTML, WebSocket play endpoints |
| `arcade_remote_worker.py` | Worker process that runs a game and talks to the server |
| `games_catalog.json` | Lobby metadata per game (title, creator, upstream repo URL, optional `start_script`) |
| `games/` | Game trees; this repo ships **only** `games/space-shooter` as a sample |
| `sync_repos.py` | Clone or update games from GitHub into `games/<repo-name>/` |

## Environment variables

- `ARCADE_GAMES_DIR` — directory containing game folders (default: `./games`).
- `ARCADE_GAMES_CATALOG` — path to the catalog JSON (default: `./games_catalog.json`).

## Sample game and upstream source

The included sample is **Space Shooter** under `games/space-shooter/`. Upstream game project:

[github.com/dobryl25/space-shooter](https://github.com/dobryl25/space-shooter)

Other games are intentionally **not** committed here (see `.gitignore`). Add more by cloning with `sync_repos.py` and extending `games_catalog.json`.

## License

This arcade harness is licensed under the MIT License; see [LICENSE](LICENSE). Third-party games under `games/` keep their own licenses from their respective repositories.
