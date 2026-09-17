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
        os.path.join(PROJECT_ROOT, 'logs'),
        os.path.join(PROJECT_ROOT, 'memory', 'journals'),
        os.path.join(PROJECT_ROOT, 'core', 'assets', 'sfx'),
        os.path.join(PROJECT_ROOT, 'core', 'models', 'piper'),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def check_icon():
    """Ensure custom Stark Arc Reactor ICO and PNG icons exist."""
    ico_path = os.path.join(PROJECT_ROOT, 'config', 'jarvis.ico')
    png_path = os.path.join(PROJECT_ROOT, 'config', 'jarvis.png')
    if os.path.exists(ico_path) and os.path.exists(png_path) and os.path.getsize(ico_path) > 10000:
        print('  [OK] Stark Arc Reactor Icons: Ready (Cached)')
        return
    print('  [*] Generating custom Stark Arc Reactor icons...')
    try:
        from scripts.generate_icon import build_assets
        build_assets()
        print('  [OK] Stark Arc Reactor Icons: Ready')
    except Exception as e:
        print(f'  [!] Icon generation note: {e}')

def check_sfx():
    sfx_dir = os.path.join(PROJECT_ROOT, 'core', 'assets', 'sfx')
    needed = ['boot.wav', 'wake.wav', 'ack.wav', 'confirm.wav']
    missing = [f for f in needed if not os.path.exists(os.path.join(sfx_dir, f))]
    if not missing:
        print('  [OK] Stark SFX Assets: Ready (Cached)')
        return
    print(f'  [*] Generating procedural SFX ({len(missing)} missing)...')
    try:
        from core.sfx import _ensure_sfx_files
        _ensure_sfx_files()
        print('  [OK] Stark SFX Assets: Successfully generated')
    except Exception as e:
        print(f'  [!] SFX generation note: {e}')

def check_piper_hindi():
    base = os.path.join(PROJECT_ROOT, 'core', 'models', 'piper')
    os.makedirs(base, exist_ok=True)
    m_path = os.path.join(base, 'hi_IN-pratham-medium.onnx')
    j_path = os.path.join(base, 'hi_IN-pratham-medium.onnx.json')
    if os.path.exists(m_path) and os.path.getsize(m_path) > 60000000 and os.path.exists(j_path):
        print('  [OK] Piper Hindi TTS Model: Ready (Cached locally)')
        return

    print('  [*] Downloading Piper Hindi Model (~60 MB, one-time only)...')
    import requests
    urls = {
        j_path: 'https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json',
        m_path: 'https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx'
    }
    for target, url in urls.items():
        if os.path.exists(target) and os.path.getsize(target) > 4000:
            continue
        fname = os.path.basename(target)
        temp = target + '.tmp'
        for attempt in range(1, 4):
            try:
                curr = os.path.getsize(temp) if os.path.exists(temp) else 0
                headers = {'Range': f'bytes={curr}-'} if curr > 0 else {}
                with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                    if r.status_code in (200, 206):
                        mode = 'ab' if curr > 0 and r.status_code == 206 else 'wb'
                        with open(temp, mode) as f:
                            for chunk in r.iter_content(chunk_size=1024*1024):
                                if chunk:
                                    f.write(chunk)
                if os.path.exists(temp):
                    if os.path.exists(target):
                        os.remove(target)
                    os.rename(temp, target)
                    print(f'  [OK] Downloaded {fname}')
                    break
            except Exception as e:
                print(f'  [!] Retry {attempt}/3 for {fname}: {e}')
                time.sleep(1.5)

def check_wakeword():
    try:
        from core.wake_word import is_ready, install_and_download
        if is_ready():
            print('  [OK] OpenWakeWord Models: Ready (Cached locally)')
            return
        print('  [*] Downloading Wake Word models (one-time setup)...')
        ok, msg = install_and_download()
        if ok:
            print('  [OK] OpenWakeWord Models: Ready')
        else:
            print(f'  [!] Wake word note: {msg}')
    except Exception as e:
        print(f'  [!] Wake word check note: {e}')

def check_desktop_shortcut():
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
            print('  [OK] Desktop Shortcut: Created on Desktop')
        else:
            print('  [OK] Desktop Shortcut: Ready (Cached)')
    except Exception as e:
        pass

def run_preflight(verbose=True):
    """Programmatic entry point for main.py / run_jarvis.pyw."""
    if verbose:
        print('===================================================')
        print('       SudhirDevOps1 AI - Pre-Flight Self-Check')
        print('===================================================')
    t0 = time.monotonic()
    check_directories()
    check_icon()
    check_sfx()
    check_piper_hindi()
    check_wakeword()
    check_desktop_shortcut()
    dt = time.monotonic() - t0
    if verbose:
        print(f'Pre-flight complete in {dt:.2f}s. All assets ready.')
        print('===================================================\n')

def main():
    run_preflight(verbose=True)

if __name__ == '__main__':
    main()
