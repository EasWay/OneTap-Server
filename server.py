from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import uuid
import glob
import requests
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
import yt_dlp
print("yt-dlp path:", yt_dlp.__file__)

app = Flask(__name__)
CORS(app)

OUT_DIR = os.path.abspath('downloads')
os.makedirs(OUT_DIR, exist_ok=True)
COOKIES_FILE = os.path.join(os.path.dirname(__file__), 'cookies.txt')

# helper: build yt-dlp options
def build_ydl_opts(outtmpl, cookies_file=None, fmt='bestvideo+bestaudio/best', quiet=False):
    opts = {
        'outtmpl': outtmpl,
        'format': fmt,
        'merge_output_format': 'mp4',
        'noprogress': quiet,
        'quiet': False,
        'ignoreerrors': True,
        'retries': 3,
        'fragment_retries': 3,
        'verbose': True,   # <-- fixed comma here
        'concurrent_fragment_downloads': 3,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
        },
        'progress_hooks': [_progress_hook]  # borrow from your working script
    }
    if cookies_file and os.path.isfile(cookies_file):
        opts['cookiefile'] = cookies_file
    return opts


# TikTok helper (unchanged)
def download_tiktok_no_watermark(url, outpath):
    try:
        api = f'https://www.tikwm.com/api/?url={url}'
        r = requests.get(api, timeout=15)
        r.raise_for_status()
        j = r.json()
        if 'data' in j and 'play' in j['data']:
            vurl = j['data']['play']
            rr = requests.get(vurl, timeout=30)
            rr.raise_for_status()
            with open(outpath, 'wb') as f:
                f.write(rr.content)
            return True
    except Exception as e:
        app.logger.debug('TikTok helper error: %s', e)
        return False
    return False

# generic downloader using yt-dlp
def download_with_yt_dlp(url, outtmpl, cookies_file=None):
    ydl_opts = build_ydl_opts(outtmpl, cookies_file=cookies_file)
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except DownloadError as e:
        # propagate a clear message to caller
        raise RuntimeError(str(e))
    except Exception as e:
        raise RuntimeError(str(e))

# find the downloaded file that matches uid prefix
def find_downloaded_file(uid):
    pattern = os.path.join(OUT_DIR, f'{uid}*')
    matches = sorted(glob.glob(pattern))
    for path in matches:
        # ignore temporary fragments
        if path.endswith('.part') or path.endswith('.tmp'):
            continue
        return path
    return None

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json(force=True)
    url = data.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    uid = str(uuid.uuid4())
    filename = f'{uid}.mp4'
    outpath = os.path.join(OUT_DIR, filename)

    # prepare outtmpl for yt-dlp so it writes files with the uid prefix
    temp_outtmpl = os.path.join(OUT_DIR, f'{uid}.%(ext)s')


    try:
        if 'tiktok.com' in url:
            ok = download_tiktok_no_watermark(url, outpath)
            if not ok:
                # fallback to yt-dlp
                # use cookies for instagram/facebook if available
                cookies = COOKIES_FILE if ('instagram.com' in url or 'facebook.com' in url) and os.path.isfile(COOKIES_FILE) else None
                download_with_yt_dlp(url, temp_outtmpl, cookies_file=cookies)
        else:
            cookies = COOKIES_FILE if ('instagram.com' in url or 'facebook.com' in url) and os.path.isfile(COOKIES_FILE) else None
            download_with_yt_dlp(url, temp_outtmpl, cookies_file=cookies)

        # find the created file
        found = find_downloaded_file(uid)
        if not found:
            app.logger.error('No downloaded file found for uid %s', uid)
            return jsonify({'error': 'Download finished but output file not found'}), 500

        # move/rename to final name if needed
        if os.path.abspath(found) != os.path.abspath(outpath):
            os.replace(found, outpath)

    except RuntimeError as e:
        msg = str(e)
        app.logger.error('Download error: %s', msg)
        # give a helpful hint for maintainers
        if 'facebook' in msg.lower():
            hint = 'Facebook parsing failed. Try updating yt-dlp or enable cookies.'
            return jsonify({'error': msg, 'hint': hint}), 500
        if 'login' in msg.lower() or 'cookie' in msg.lower():
            return jsonify({'error': msg, 'hint': 'Use cookies.txt for authenticated downloads'}), 403
        return jsonify({'error': msg}), 500
    except Exception as e:
        app.logger.exception('Unexpected error')
        return jsonify({'error': str(e)}), 500

    download_url = f'{request.host_url.rstrip('/')}/files/{filename}'
    return jsonify({'filename': filename, 'download_url': download_url})

@app.route('/files/<path:filename>')
def files(filename):
    return send_from_directory(OUT_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
