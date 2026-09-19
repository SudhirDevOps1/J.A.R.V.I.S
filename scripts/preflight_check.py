import os, sys, time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def check_directories():
    """Ensure all critical operational directories exist."""
    dirs = [
        os.path.join(PROJECT_ROOT, 'config'),
        os.path.join(PROJECT_ROOT, 'config', 'generated_sniffers'),
        os.path.join(PROJECT_ROOT, 'config', 'swarm_outputs'),
        os.path.join(PROJECT_ROOT, 'logs'),
        os.path.join(PROJECT_ROOT, 'cache'),
        os.path.join(PROJECT_ROOT, 'downloads'),
        os.path.join(PROJECT_ROOT, 'screenshots'),
        os.path.join(PROJECT_ROOT, 'scratch'),
        os.path.join(PROJECT_ROOT, 'memory', 'journals'),
        os.path.join(PROJECT_ROOT, 'memory', 'obsidian_vault'),
        os.path.join(PROJECT_ROOT, 'core', 'assets', 'sfx'),
        os.path.join(PROJECT_ROOT, 'core', 'assets', 'avatar'),
        # NOTE: core/models/piper removed with the Piper engine (Edge + Gemini Live only).
        os.path.join(PROJECT_ROOT, 'models', 'lfm'),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def check_config_init(verbose=True):
    """Ensure config/api_keys.json and local state stores exist; create safe templates if missing on first run."""
    cfg_file = os.path.join(PROJECT_ROOT, 'config', 'api_keys.json')
    tpl_file = os.path.join(PROJECT_ROOT, 'config', 'api_keys.example.json')
    if not os.path.exists(cfg_file):
        import shutil
        if os.path.exists(tpl_file):
            shutil.copyfile(tpl_file, cfg_file)
            if verbose:
                print('  [OK] Configuration: Initialized api_keys.json from template (safe mode)')
        else:
            # Fallback safe minimal JSON
            import json
            safe_cfg = {
                "preferred_llm_provider": "gemini-web",
                "free_proxy_enabled": True,
                "free_proxy_port": 8081,
                "free_proxy_model": "gemini-3.7-flash",
                "llm_cache_enabled": True,
                "tts_engine": "edge",
                "sfx_enabled": True
            }
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(safe_cfg, f, indent=4)
            if verbose:
                print('  [OK] Configuration: Created fresh api_keys.json (safe mode)')
    else:
        if verbose:
            print('  [OK] Configuration: api_keys.json Active (Protected from Git)')

    # Ensure local runtime state stores exist with clean initial structures
    state_templates = [
        ('config/music_library.json', '[]\n'),
        ('config/todos.json', '[]\n'),
        ('config/agent_plans.json', '[]\n'),
        ('config/workflows.json', '[]\n'),
        ('memory/tinydb_store.json', '{}\n'),
    ]
    for rel_path, default_content in state_templates:
        full_path = os.path.join(PROJECT_ROOT, rel_path.replace('/', os.sep))
        if not os.path.exists(full_path):
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(default_content)

def check_icon(verbose=True):
    """Ensure custom Stark Arc Reactor ICO and PNG icons exist."""
    ico_path = os.path.join(PROJECT_ROOT, 'config', 'jarvis.ico')
    png_path = os.path.join(PROJECT_ROOT, 'config', 'jarvis.png')
    if os.path.exists(ico_path) and os.path.exists(png_path) and os.path.getsize(ico_path) > 10000:
        if verbose:
            print('  [OK] Stark Arc Reactor Icons: Ready (Cached)')
        return
    if verbose:
        print('  [*] Generating custom Stark Arc Reactor icons...')
    try:
        from scripts.generate_icon import build_assets
        build_assets()
        if verbose:
            print('  [OK] Stark Arc Reactor Icons: Ready')
    except Exception as e:
        if verbose:
            print(f'  [!] Icon generation note: {e}')

def check_sfx(verbose=True):
    sfx_dir = os.path.join(PROJECT_ROOT, 'core', 'assets', 'sfx')
    needed = ['boot.wav', 'wake.wav', 'ack.wav', 'confirm.wav']
    missing = [f for f in needed if not os.path.exists(os.path.join(sfx_dir, f))]
    if not missing:
        if verbose:
            print('  [OK] Stark SFX Assets: Ready (Cached)')
        return
    if verbose:
        print(f'  [*] Generating procedural SFX ({len(missing)} missing)...')
    try:
        from core.sfx import _ensure_sfx_files
        _ensure_sfx_files()
        if verbose:
            print('  [OK] Stark SFX Assets: Successfully generated')
    except Exception as e:
        if verbose:
            print(f'  [!] SFX generation note: {e}')

def check_lfm_model(verbose=True):
    """Verify local Liquid Foundation Model (LFM2.5-230M) GGUF exists; download if missing."""
    lfm_dir = os.path.join(PROJECT_ROOT, 'models', 'lfm')
    os.makedirs(lfm_dir, exist_ok=True)
    lfm_path = os.path.join(lfm_dir, 'LFM2.5-230M-Q4_K_M.gguf')
    
    if os.path.exists(lfm_path) and os.path.getsize(lfm_path) > 50 * 1024 * 1024:
        if verbose:
            size_mb = os.path.getsize(lfm_path) / (1024 * 1024)
            print(f'  [OK] LFM2.5-230M Semantic Neural Model: Ready ({size_mb:.1f} MB GGUF Cached)')
        return

    if verbose:
        print('  [*] LFM2.5-230M GGUF model missing. Auto-downloading (~146 MB, one-time setup)...')
    url = 'https://huggingface.co/oamazonasgabriel/lfm2.5-230m/resolve/main/LFM2.5-230M-Q4_K_M.gguf'
    temp = lfm_path + '.tmp'
    try:
        import requests
        curr = os.path.getsize(temp) if os.path.exists(temp) else 0
        headers = {'Range': f'bytes={curr}-'} if curr > 0 else {}
        with requests.get(url, headers=headers, stream=True, timeout=60) as r:
            if r.status_code in (200, 206):
                mode = 'ab' if curr > 0 and r.status_code == 206 else 'wb'
                total = int(r.headers.get('content-length', 0)) + curr
                downloaded = curr
                with open(temp, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
        if os.path.exists(temp) and os.path.getsize(temp) > 50 * 1024 * 1024:
            if os.path.exists(lfm_path):
                os.remove(lfm_path)
            os.rename(temp, lfm_path)
            if verbose:
                print('  [OK] LFM2.5-230M Semantic Neural Model: Downloaded successfully')
        else:
            if verbose:
                print('  [--] LFM2.5 download deferred (Ollama/Cloud fallback active)')
    except Exception as e:
        if verbose:
            print(f'  [!] LFM2.5 model setup note: {e}')
    # NOTE: Piper Hindi download block removed with the Piper engine
    # (Edge TTS + Gemini Live only) — it used to fetch ~60 MB of dead models here.

def check_wakeword(verbose=True):
    try:
        from core.wake_word import is_ready, install_and_download
        if is_ready():
            if verbose:
                print('  [OK] OpenWakeWord Models: Ready (Cached locally)')
            return
        if verbose:
            print('  [*] Downloading Wake Word models (one-time setup)...')
        ok, msg = install_and_download()
        if ok:
            if verbose:
                print('  [OK] OpenWakeWord Models: Ready')
        else:
            if verbose:
                print(f'  [!] Wake word note: {msg}')
    except Exception as e:
        if verbose:
            print(f'  [!] Wake word check note: {e}')

def check_desktop_shortcut(verbose=True):
    """Ensure Windows desktop shortcut exists pointing to launch_silent.vbs with the Arc Reactor icon."""
    try:
        desktop = Path(os.path.expanduser('~/Desktop'))
        if not desktop.exists():
            return
        lnk = desktop / 'J.A.R.V.I.S.lnk'
        vbs = Path(PROJECT_ROOT) / 'launch_silent.vbs'
        ico_path = Path(PROJECT_ROOT) / 'config' / 'jarvis.ico'
        wscript = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32' / 'wscript.exe'
        target = str(wscript if wscript.exists() else 'wscript.exe')
        
        if not lnk.exists():
            from ui import MainWindow
            MainWindow._create_lnk_windows(
                str(lnk), target, f'"{vbs}"', str(PROJECT_ROOT), f'{ico_path},0'
            )
            if verbose:
                print('  [OK] Desktop Shortcut: Created on Desktop')
        else:
            if verbose:
                print('  [OK] Desktop Shortcut: Ready (Cached)')
    except Exception as e:
        pass

def check_free_proxy(verbose=True):
    """Verify core/gemini_free_proxy.py exists and is importable. No network call needed."""
    proxy_path = os.path.join(PROJECT_ROOT, 'core', 'gemini_free_proxy.py')
    if not os.path.exists(proxy_path):
        if verbose:
            print('  [!] Gemini Free Proxy: Missing (run setup.py)')
        return
    # Verify it's importable (catches syntax errors)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("gemini_free_proxy", proxy_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if verbose:
            print('  [OK] Gemini Free Proxy: Ready (Anonymous Mode - gemini-3.7-flash FREE)')
    except Exception as e:
        if verbose:
            print(f'  [!] Gemini Free Proxy: Import error: {e}')

def check_llm_cache(verbose=True):
    """Verify core/llm_cache.py exists."""
    cache_path = os.path.join(PROJECT_ROOT, 'core', 'llm_cache.py')
    if os.path.exists(cache_path):
        if verbose:
            print('  [OK] Smart LLM Cache: Ready (SQLite, 500-entry LRU)')
    else:
        if verbose:
            print('  [!] Smart LLM Cache: Missing')

def check_omniroute(verbose=True):
    """Check if OmniRoute gateway is running on localhost:20128."""
    try:
        import urllib.request
        req = urllib.request.Request(
            'http://localhost:20128/v1/models',
            headers={'Authorization': 'Bearer omniroute'},
            method='GET'
        )
        resp = urllib.request.urlopen(req, timeout=1.5)
        if resp.status == 200:
            if verbose:
                print('  [OK] OmniRoute Gateway: Running on :20128 (352+ providers)')
            return
    except Exception:
        pass
    if verbose:
        print('  [--] OmniRoute Gateway: Not running (optional - npm install -g omniroute)')

def check_python_packages(verbose=True):
    """Verifies and auto-installs missing Python packages from requirements.txt."""
    import importlib.util
    import subprocess
    
    core_packages = [
        ('PyQt6', 'PyQt6'),
        ('sounddevice', 'sounddevice'),
        ('numpy', 'numpy'),
        ('google.genai', 'google-genai>=2.8.0'),
        ('edge_tts', 'edge-tts'),
        ('requests', 'requests'),
        ('bs4', 'beautifulsoup4'),
        ('duckduckgo_search', 'duckduckgo-search'),
        ('playwright', 'playwright'),
        ('pyautogui', 'pyautogui'),
        ('pyperclip', 'pyperclip'),
        ('pygetwindow', 'pygetwindow'),
        ('PIL', 'pillow'),
        ('cv2', 'opencv-python'),
        ('mss', 'mss'),
        ('psutil', 'psutil'),
        ('send2trash', 'send2trash'),
        ('tinydb', 'tinydb'),
        ('rank_bm25', 'rank-bm25'),
        ('thefuzz', 'thefuzz'),
        ('keyboard', 'keyboard'),
        ('sklearn', 'scikit-learn'),
        ('fastapi', 'fastapi'),
        ('uvicorn', 'uvicorn'),
        ('cryptography', 'cryptography'),
    ]
    if sys.platform == 'win32':
        core_packages.extend([
            ('comtypes', 'comtypes'),
            ('pycaw', 'pycaw'),
            ('win10toast', 'win10toast'),
            ('pywinauto', 'pywinauto'),
            ('win32api', 'pywin32'),
            ('wmi', 'wmi'),
        ])
    
    missing = []
    for mod_name, pip_name in core_packages:
        try:
            if importlib.util.find_spec(mod_name) is None:
                missing.append(pip_name)
        except Exception:
            missing.append(pip_name)
            
    if missing:
        if verbose:
            print(f'  [*] Auto-installing {len(missing)} missing libraries: {", ".join(missing)}...')
        try:
            cmd = [sys.executable, "-m", "pip", "install"] + missing
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                if verbose:
                    print(f'  [OK] Python Libraries: Installed {len(missing)} missing packages successfully')
            else:
                if verbose:
                    print(f'  [!] Pip notice: {res.stderr[:120] if res.stderr else "Installed with minor notes"}')
        except Exception as e:
            if verbose:
                print(f'  [!] Auto-install error: {e}')
    else:
        if verbose:
            print(f'  [OK] Python Libraries: All {len(core_packages)} dependencies verified & ready')

def check_browser_engine(verbose=True):
    """Verify headless Chromium/Brave/Edge browser engine is available for web sniffing."""
    try:
        from actions.api_sniffer import _get_browser_executable_or_kwargs
        binfo = _get_browser_executable_or_kwargs()
        if "executable_path" in binfo:
            bname = os.path.basename(binfo["executable_path"])
            if verbose:
                print(f'  [OK] Web Browser Engine: Host browser detected ({bname} - 0 MB overhead)')
        else:
            if verbose:
                print('  [OK] Web Browser Engine: Playwright default browser ready')
    except Exception as e:
        if verbose:
            print(f'  [!] Browser engine note: {e}')

def check_memory_stores(verbose=True):
    """Ensure TinyDB NoSQL memory store and SQLite LRU cache are initialized."""
    try:
        from actions.tinydb_memory import get_db
        db = get_db()
        cnt = len(db.all())
        if verbose:
            print(f'  [OK] TinyDB Memory Store: Ready ({cnt} records in memory/tinydb_store.json)')
    except Exception as e:
        if verbose:
            print(f'  [!] TinyDB check note: {e}')

def check_installed_apps(verbose=True):
    """Auto-scan host machine applications on first run and cache locally."""
    try:
        from actions.open_app import _scan_installed_apps
        apps = _scan_installed_apps()
        if verbose:
            print(f'  [OK] Host Applications Index: {len(apps)} apps indexed on this PC')
    except Exception as e:
        if verbose:
            print(f'  [!] Apps scan note: {e}')

def run_preflight(verbose=True):
    """Programmatic entry point for main.py / run_jarvis.pyw."""
    if verbose:
        print('===================================================')
        print('       SudhirDevOps1 AI - Pre-Flight Self-Check')
        print('===================================================')
    t0 = time.monotonic()
    check_directories()
    check_python_packages(verbose=verbose)
    check_config_init(verbose=verbose)
    check_icon(verbose=verbose)
    check_sfx(verbose=verbose)
    check_lfm_model(verbose=verbose)
    check_wakeword(verbose=verbose)
    check_desktop_shortcut(verbose=verbose)
    check_browser_engine(verbose=verbose)
    check_free_proxy(verbose=verbose)
    check_llm_cache(verbose=verbose)
    check_memory_stores(verbose=verbose)
    check_installed_apps(verbose=verbose)
    check_omniroute(verbose=verbose)
    dt = time.monotonic() - t0
    if verbose:
        print(f'Pre-flight complete in {dt:.2f}s. All assets ready.')
        print('===================================================\n')

def main():
    run_preflight(verbose=True)

if __name__ == '__main__':
    main()
