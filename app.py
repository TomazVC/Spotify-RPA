import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5000/callback")
TOKEN_FILE = Path(".spotify_token.json")
SCOPES = "user-read-playback-state user-modify-playback-state"
TRANSIENT_SPOTIFY_STATUS_CODES = ("500", "502", "503", "504")

PLAYLISTS = [
    {
        "id": "playlist1",
        "name": os.getenv("PLAYLIST_1_NAME", "Focus Instrumental"),
        "uri": os.getenv("PLAYLIST_1_URI", ""),
        "description": "Playlist sem conteúdo explícito para estudo e concentração.",
    },
    {
        "id": "playlist2",
        "name": os.getenv("PLAYLIST_2_NAME", "Lo-fi Clean"),
        "uri": os.getenv("PLAYLIST_2_URI", ""),
        "description": "Playlist leve, preferencialmente instrumental e sem palavrões.",
    },
    {
        "id": "playlist3",
        "name": os.getenv("PLAYLIST_3_NAME", "Acoustic Clean"),
        "uri": os.getenv("PLAYLIST_3_URI", ""),
        "description": "Playlist acústica selecionada previamente, sem conteúdo explícito.",
    },
]


def save_token(token_data: dict):
    token_data["expires_at"] = int(time.time()) + int(token_data.get("expires_in", 3600)) - 60
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")


def load_token():
    if not TOKEN_FILE.exists():
        return None
    return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))


def refresh_access_token(token_data: dict):
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": token_data["refresh_token"],
            "client_id": CLIENT_ID,
        },
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=15,
    )
    response.raise_for_status()
    refreshed = response.json()
    if "refresh_token" not in refreshed:
        refreshed["refresh_token"] = token_data["refresh_token"]
    save_token(refreshed)
    return refreshed


def get_access_token():
    token_data = load_token()
    if not token_data:
        return None
    if int(time.time()) >= int(token_data.get("expires_at", 0)):
        token_data = refresh_access_token(token_data)
    return token_data["access_token"]


def spotify_request(method, path, token, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    response = requests.request(
        method,
        f"https://api.spotify.com/v1{path}",
        headers=headers,
        timeout=15,
        **kwargs,
    )
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "alguns")
        raise RuntimeError(f"Spotify limitou temporariamente as requisições. Tente novamente em {retry_after}s.")
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise RuntimeError(f"Spotify API retornou {response.status_code} em {method} {path}: {detail}")
    return response


def is_transient_spotify_error(exc: Exception):
    message = str(exc)
    return any(f"Spotify API retornou {status}" in message for status in TRANSIENT_SPOTIFY_STATUS_CODES)


def start_playlist_playback(token, device_id, playlist_uri):
    last_error = None
    for attempt in range(3):
        try:
            return spotify_request(
                "PUT",
                "/me/player/play",
                token,
                params={"device_id": device_id},
                json={"context_uri": playlist_uri, "offset": {"position": 0}, "position_ms": 0},
            )
        except RuntimeError as exc:
            last_error = exc
            if not is_transient_spotify_error(exc) or attempt == 2:
                raise
            time.sleep(1 + attempt)
    raise last_error


def get_devices(token):
    data = spotify_request("GET", "/me/player/devices", token).json()
    devices = [d for d in data.get("devices", []) if not d.get("is_restricted") and d.get("id")]
    return devices


@app.route("/")
def index():
    token = None
    auth_error = None
    try:
        token = get_access_token()
    except Exception as exc:
        auth_error = str(exc)

    devices = []
    if token:
        try:
            devices = get_devices(token)
        except Exception as exc:
            auth_error = str(exc)

    return render_template(
        "index.html",
        playlists=PLAYLISTS,
        devices=devices,
        authenticated=bool(token),
        auth_error=auth_error,
    )


@app.route("/login")
def login():
    if not CLIENT_ID or not CLIENT_SECRET:
        return "Configure SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no arquivo .env.", 500
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "show_dialog": "true",
    }
    return redirect("https://accounts.spotify.com/authorize?" + urlencode(params))


@app.route("/callback")
def callback():
    if request.args.get("state") != session.get("oauth_state"):
        return "Estado OAuth inválido. Tente autenticar novamente.", 400
    if request.args.get("error"):
        return f"Autorização negada: {request.args['error']}", 400

    code = request.args.get("code")
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=15,
    )
    response.raise_for_status()
    save_token(response.json())
    return redirect(url_for("index", status="Spotify conectado com sucesso"))


@app.post("/play")
def play():
    token = get_access_token()
    if not token:
        return redirect(url_for("login"))

    selected_id = request.form.get("playlist")
    device_id = request.form.get("device_id") or None
    playlist = next((p for p in PLAYLISTS if p["id"] == selected_id), None)

    if not playlist or not playlist["uri"]:
        return render_template("result.html", success=False, message="Playlist não configurada no arquivo .env."), 400

    try:
        devices = get_devices(token)
        if not devices:
            return render_template(
                "result.html",
                success=False,
                message="Nenhum dispositivo Spotify disponível. Abra o Spotify no notebook/celular e toque qualquer faixa uma vez.",
            ), 409

        if not device_id:
            active = next((d for d in devices if d.get("is_active")), None)
            chosen = active or devices[0]
            device_id = chosen["id"]

        # Garante que a reprodução está direcionada ao dispositivo escolhido.
        spotify_request(
            "PUT",
            "/me/player",
            token,
            json={"device_ids": [device_id], "play": False},
        )

        # Inicia a playlist selecionada a partir do começo.
        start_playlist_playback(token, device_id, playlist["uri"])

        return render_template(
            "result.html",
            success=True,
            message=f"Reprodução iniciada: {playlist['name']}",
        )
    except Exception as exc:
        return render_template("result.html", success=False, message=str(exc)), 500


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
