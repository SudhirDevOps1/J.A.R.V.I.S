"""Smart Home plugin (additive). tinytuya LAN control, config/smart_home.json guided."""

PLUGIN = {
    "name": "smart_home",
    "description": (
        "Control Tuya/SmartLife lights and plugs by voice: on, off, brightness, color, scene. "
        "Trigger on 'light jalao', 'room movie mode', 'plug band karo'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "device": {"type": "STRING", "description": "Device name from config/smart_home.json"},
            "action": {"type": "STRING", "description": "on | off | brightness | color | scene"},
            "value": {"type": "STRING", "description": "0-100 / color name / scene name"},
        },
        "required": ["device", "action"],
    },
}

_PRESETS = {"warm": (255, 200, 120), "red": (255, 60, 40), "gold": (255, 180, 60),
            "blue": (80, 140, 255), "green": (80, 255, 140), "white": (255, 255, 255)}


def run(parameters: dict, player=None, session_memory=None) -> str:
    import json as _j, sys as _s
    from pathlib import Path as _P
    params = parameters or {}
    device = str(params.get("device", "") or "").strip().lower()
    action = str(params.get("action", "") or "").strip().lower()
    value = str(params.get("value", "") or "").strip()
    base = _P(_s.executable).parent if getattr(_s, "frozen", False) else _P(__file__).resolve().parent.parent
    cfgf = base / "config" / "smart_home.json"
    if not cfgf.exists():
        try:
            cfgf.write_text(_j.dumps({"_note": "Tuya devices: {name: {id, key, ip}}",
                                      "bedroom light": {"id": "", "key": "", "ip": ""}},
                                     indent=2), encoding="utf-8")
        except Exception:
            pass
        return ("Smart home setup nahi hai — config/smart_home.json me device id/key/ip dalo "
                "(Tuya app se), phir bolo.")
    try:
        devs = _j.loads(cfgf.read_text(encoding="utf-8"))
    except Exception:
        return "smart_home.json corrupt hai."
    match = None
    for k, v in devs.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        if device in k.lower() or k.lower() in device:
            match = (k, v)
            break
    if not match:
        known = ", ".join(k for k in devs if not k.startswith("_")) or "none"
        return f"'{device}' nahi mila. Devices: {known}."
    name, dev = match
    if not dev.get("id") or not dev.get("key"):
        return f"'{name}' me id/key missing hai smart_home.json me."
    try:
        import tinytuya as _t
        d = _t.BulbDevice(dev["id"], dev.get("ip", ""), dev["key"])
        d.set_version(3.3)
        if action == "on":
            d.turn_on()
        elif action == "off":
            d.turn_off()
        elif action == "brightness":
            try:
                b = max(1, min(100, int(value or "70")))
            except Exception:
                b = 70
            d.set_brightness(b)
        elif action == "color":
            r, g, b = _PRESETS.get(value.lower(), (255, 255, 255))
            d.set_colour(r, g, b)
        elif action == "scene":
            if "movie" in value.lower():
                d.set_brightness(30)
                d.set_colour(255, 180, 60)
            else:
                return f"Scene '{value}' nahi pata. movie try karo."
        else:
            return "Action on/off/brightness/color/scene me se do."
        if player:
            try:
                player.write_log(f"JARVIS: {name} {action} done.")
            except Exception:
                pass
        try:
            from core.audit import log_event as _ae
            _ae("smart_home", f"{name} {action}")
        except Exception:
            pass
        return f"'{name}' {action} ho gaya."
    except Exception as e:
        return f"Sir, smart home failed: {e}"
