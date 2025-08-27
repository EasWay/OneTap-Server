from flask import Flask, request, jsonify, send_from_directory
# TikTok download helper
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
except Exception:
return False
return False


# Generic yt-dlp downloader
def download_with_yt_dlp(url, outpath):
ydl_opts = {
'outtmpl': outpath,
'format': 'bestvideo+bestaudio/best',
'merge_output_format': 'mp4',
'quiet': True
}
with YoutubeDL(ydl_opts) as ydl:
ydl.download([url])


@app.route('/download', methods=['POST'])
def download():
data = request.get_json(force=True)
url = data.get('url')
if not url:
return 'No URL provided', 400


uid = str(uuid.uuid4())
filename = f'{uid}.mp4'
outpath = os.path.join(OUT_DIR, filename)


# Try TikTok no watermark first
if 'tiktok.com' in url:
ok = download_tiktok_no_watermark(url, outpath)
if not ok:
temp_out = os.path.join(OUT_DIR, f'{uid}.temp.%(ext)s')
download_with_yt_dlp(url, temp_out)
for f in os.listdir(OUT_DIR):
if f.startswith(uid) and not f.endswith('.temp'):
os.rename(os.path.join(OUT_DIR, f), outpath)
break
else:
temp_out = os.path.join(OUT_DIR, f'{uid}.temp.%(ext)s')
download_with_yt_dlp(url, temp_out)
for f in os.listdir(OUT_DIR):
if f.startswith(uid) and not f.endswith('.temp'):
os.rename(os.path.join(OUT_DIR, f), outpath)
break


download_url = f'{request.host_url.rstrip("/")}/files/{filename}'
return jsonify({'filename': filename, 'download_url': download_url})


@app.route('/files/<path:filename>')
def files(filename):
return send_from_directory(OUT_DIR, filename, as_attachment=True)


if __name__ == '__main__':
port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port)