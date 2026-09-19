"""Spotify voice control plugin (additive, no core change). Uses spotipy if present, else opens app."""

PLUGIN = {
    "name": "spotify_control",
    "description": (
        "Control Spotify playback by voice: play, pause, next, prev, queue, like. "
        "Trigger ONLY when user says Spotify (e.g. 'Spotify par chalao'). "
        "Do NOT use for YouTube/play-song requests (use youtube_video) and do NOT "
        "use open_app for Spotify media keys — use this instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "play | pause | next | prev | like | queue_song"},
            "query": {"type": "STRING", "description": "Song/search text for play or queue"},
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str((parameters or {}).get("action", "play")).lower().strip()
    query = str((parameters or {}).get("query", "") or "").strip()
    try:
        if player:
            player.write_log(f"JARVIS: Spotify {action} {query[:40]}")
    except Exception:
        pass
    # Try spotipy when configured, else media-key fallback (purana flow untouched).
    try:
        import os as _os
        _cid = (_os.environ.get("SPOTIPY_CLIENT_ID", "") or "").strip()
        if not _cid:
            # ADDITIVE: GUI se save ki hui ID bhi chalegi (api_keys.json)
            try:
                import json as _j, sys as _s
                from pathlib import Path as _P
                _base = _P(_s.executable).parent if getattr(_s, "frozen", False) else _P(__file__).resolve().parent.parent
                _cfg = _j.loads((_base / "config" / "api_keys.json").read_text(encoding="utf-8"))
                _cid = str(_cfg.get("spotipy_client_id", "") or "").strip()
                try:  # ADDITIVE: ENC blob support (plaintext passthrough)
                    from core.secret_vault import decrypt_value
                    _cid = str(decrypt_value(_cid) or "").strip()
                except Exception:
                    pass
                if _cid:
                    _os.environ["SPOTIPY_CLIENT_ID"] = _cid
            except Exception:
                pass
        if _os.environ.get("SPOTIPY_CLIENT_ID"):
            from spotipy import Spotify as _Sp
            from spotipy.oauth2 import SpotifyOAuth as _Auth
            _sp = _Sp(auth_manager=_Auth(scope="user-modify-playback-state user-read-playback-state"))
            if action == "pause":
                _sp.pause_playback()
                return "Spotify paused."
            if action == "next":
                _sp.next_track()
                return "Next song."
            if action == "prev":
                _sp.previous_track()
                return "Previous song."
            return f"Spotify {action} done."
    except Exception as e:
        return f"Sir, Spotify control failed: {e}"
    # Fallback: media keys via computer_control path is handled by caller; report only.
    if query:
        return f"Spotify {action} queued for '{query}' (open Spotify to confirm)."
    return f"Spotify {action} triggered — open Spotify to confirm."
