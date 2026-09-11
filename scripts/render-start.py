"""Run the private Cobalt API and OneTap as one supervised Render service."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    env = os.environ.copy()
    env['PATH'] = str(ROOT / '.runtime/node/bin') + os.pathsep + env['PATH']
    env['COBALT_API_URL'] = 'http://127.0.0.1:9000/'
    cobalt_env = env | {
        'API_URL': env['COBALT_API_URL'], 'API_PORT': '9000',
        'API_LISTEN_ADDRESS': '127.0.0.1', 'FFMPEG_BIN': shutil.which('ffmpeg', path=env['PATH']) or 'ffmpeg',
    }
    potprovider_url = 'http://127.0.0.1:4416/ping'
    children = []
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    def await_ready(child, url, label, timeout_seconds):
        deadline = time.monotonic() + timeout_seconds
        while not stopping:
            if child.poll() is not None:
                raise RuntimeError(f'{label} exited before becoming ready')
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        return
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f'{label} readiness timed out')
            time.sleep(.5)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(subprocess.Popen(['node', 'src/cobalt.js'], cwd=ROOT / '.runtime/cobalt/api', env=cobalt_env, start_new_session=True))
        await_ready(children[0], env['COBALT_API_URL'], 'Cobalt', 60)
        if stopping:
            return 0
        # Mints yt-dlp PO tokens locally so YouTube's bot check doesn't block
        # extraction from Render's datacenter IP; no cookies or browser involved.
        children.append(subprocess.Popen(
            ['node', 'build/main.js', '-p', '4416', '-H', '127.0.0.1'],
            cwd=ROOT / '.runtime/potprovider/server', env=env, start_new_session=True))
        await_ready(children[-1], potprovider_url, 'PO token provider', 30)
        if stopping:
            return 0
        children.append(subprocess.Popen([sys.executable, 'server.py'], env=env, start_new_session=True))
        while not stopping:
            for child in children:
                if child.poll() is not None:
                    raise RuntimeError(f'Service process exited with code {child.returncode}')
            time.sleep(.5)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        deadline = time.monotonic() + 10
        for child in children:
            try:
                child.wait(timeout=max(.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == '__main__':
    sys.exit(main())
