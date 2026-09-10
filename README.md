# OneTap self-hosted extraction trial

Litestar/ASGI backend for the OneTap Android app. `/download` routes Instagram to Instaloader first and YouTube to local yt-dlp first. Other sources try a private Cobalt API, then yt-dlp, with a public TikTok photo metadata adapter as the final fallback. No J2 session or client WebView is used by this route. The legacy J2 extractor remains in the source for comparison but is not in the provider order.

## Local setup

Requires Python 3.11+, FFmpeg/ffprobe, Node 22 and a running private Cobalt instance.

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
export COBALT_API_URL=http://127.0.0.1:9000/
export EXTRACTION_PROVIDERS=cobalt,ytdlp,public_photos
.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 10000
```

`.env.example` is a reference; the backend reads process environment variables, not a dotenv file. The general order is `EXTRACTION_PROVIDERS`; Instagram and YouTube use separate overrides: `INSTAGRAM_PROVIDERS=instagram,ytdlp,cobalt` and `YOUTUBE_PROVIDERS=ytdlp,cobalt`. Set all three to `ytdlp` to test yt-dlp alone. `COBALT_API_KEY` is optional for an authenticated private Cobalt instance. It stays on the backend.

Cobalt source: https://github.com/imputnet/cobalt. Follow its `docs/run-an-instance.md`. On this Mac it is checked out at `../cobalt`, version 11.7.1, commit a636575b09de1fc55d9b8cd98cac88f5f2f16b42. Its dependencies were installed with Node 22.23.2 and pnpm 9.6.0. Global Node 26 failed the native module build, so an isolated runtime was used.

Working Mac startup command, from `../cobalt/api`:

```sh
FFMPEG_BIN=/opt/homebrew/bin/ffmpeg \
API_URL=http://127.0.0.1:9000/ API_LISTEN_ADDRESS=127.0.0.1 API_PORT=9000 \
../../.onetap-runtime/node-v22.23.2-darwin-arm64/bin/node src/cobalt.js
```

Use the tested Homebrew FFmpeg on this machine: the package's downloaded ffmpeg-static binary did not execute successfully. Cobalt code is AGPL-3.0; see its upstream LICENSE.

## Docker configuration

`docker compose up --build` starts private Cobalt and OneTap, publishing only OneTap on `127.0.0.1:10000`. Cobalt tunnels stay internal. Compose is provided but not tested here because Docker is not installed. The backend image includes Python, Node 22, FFmpeg and pinned yt-dlp. Validate on the target host before deployment. The Cobalt `:11` image tag is a major-version tag; pin an evaluated digest for a release.

## API contract

- `POST /download`, JSON `{"url":"https://…"}`: returns 201 with the existing Android `status`, `download_url`, `filename`, `type`, `title`, `platform`, `size` fields.
- Collections include `files`, each with its own `type` (`image`, `audio`, `video`). A provider-returned photo soundtrack remains an audio item. Instaloader currently returns Instagram photos/videos only, without a separate photo soundtrack. Top-level `multi_video` is the legacy collection envelope for mixed items; it does not mean every item is video.
- `GET /files/{filename}`: downloads a cached file. All providers finish the transfer before declaring it ready, allowing yt-dlp fallback when Cobalt returns a broken tunnel. Image/audio content types help determine extensions; conflicting CDN headers do not change a soundtrack into a video. FFprobe verifies a usable media stream before any file is reported ready.
- Exhausted providers or the 150-second request deadline: 503 with `extra.code=EXTRACTION_UNAVAILABLE`, `Retry-After: 60`.
- `/` and `/version` retain the app's historical platform list. That is **not verified coverage**; consult [PLATFORM_COVERAGE.md](PLATFORM_COVERAGE.md).

The `public_photos` fallback handles TikTok photo posts and short links only. It checks the post ID and public status, preserves every image and the soundtrack, and uses the same full-file validation. It is not additional coverage for other platforms.

## Trial boundaries

Two concurrent extractions per backend process, 250 MiB per cached item, up to 30 Cobalt items / 20 yt-dlp items. Cobalt/Instagram media caching has a 65-second limit, Instagram metadata has a 30-second limit, and yt-dlp has a 90-second limit; the full request including waiting is capped at 150 seconds. Cancellation kills the yt-dlp process group and removes incomplete job files. Generated files become eligible for cleanup after one hour; cleanup currently runs on the next extraction request. There is no global disk quota or background cleanup job yet.

Cobalt selects up to 1080p. YouTube via yt-dlp defaults to 720p to fit the request deadline; `YOUTUBE_MAX_HEIGHT` accepts 360, 480, 720, or 1080. Other yt-dlp sources select best video+audio and merge to MP4 where possible. Higher YouTube resolutions may exceed the deadline. User-selectable quality and audio-only extraction from arbitrary videos are not implemented by this trial. Music/audio sources and provider-returned slideshow soundtracks are supported when the extractor provides them. Do not confuse soundtrack preservation with extracting every video's audio as a separate file.

This is a local integration trial, not a full 56-platform release. The audit found 16 platforms without a dedicated extractor in either provider; other platforms still need live/media-type verification. Authentication, source availability, regional restrictions and extractor changes can affect results. There is no CAPTCHA automation in this replacement flow.

Before exposing the service publicly, add deployment-appropriate authentication/rate limits, storage quotas, bounded job scheduling, and network egress restrictions. Source domain validation is not a complete SSRF boundary for provider redirects. Use one process for the trial or provide shared job storage when scaling.

## Validation and rollout

```sh
.venv/bin/python -m unittest discover -q
```

`end-to-end-trial-results.json` records complete TikTok video, Bluesky single/multiple images, and SoundCloud audio downloads verified with ffprobe. `cobalt-trial-results.json` records broader provider probes; sampled bytes are not full-file verification. `user-url-trial-results.json` records tests from the supplied Render logs. Its initial Instagram reel image results were incorrect thumbnail responses, not successful reel downloads; `reel-retest-results.json` supersedes those after the thumbnail rejection fix. `public-photo-retest-results.json` records the additional photo adapter tests. These are snapshots, not promises about future availability.

The Android changes remove the mandatory J2 WebView wait, recognize exhausted provider responses without rerunning the whole chain, preserve audio inside collections, add Ogg/Opus handling, and allow 180 seconds for the backend's bounded request. Unit tests compile the affected code. Device/gallery UI testing is still required.

Deploy and verify this backend and private Cobalt **before** distributing the changed Android app. The existing live Render service has not been updated by this trial. Building/signing an app alone would still point users at the old backend.

## Alternative provider trials (2026-09-10)

Instaloader 4.15.3 downloaded both supplied Instagram photos (`DcOvI0Myrci`, `Dc_uf6kysp4`) without login cookies. The integrated adapter preserves ordered carousel images and videos and rejects unexpected post IDs/types and asset hosts. See `alternative-api-results.json` for full API downloads and codec checks.

Gallery-dl 1.32.11 redirected both photos to the Instagram login page, so it is not enabled. Lux 0.24.1 downloaded the newer Instagram photo, but its old binary did not have the current source's Threads adapter; its Miaopai fixture timed out. These results do not establish current-source Threads support or a universal Miaopai failure. PyTubeFix trials are isolated from production dependencies; the initial progressive-only test found no progressive stream, so adaptive video/audio are tested separately in `pytubefix-adaptive-results.json`.

These additions do not verify every advertised platform or every media type. Instagram photo soundtracks, authenticated/private posts, and the remaining platform gaps still require separate work.

YouTube `vPwaXytZcgI` now passes through `/download` and `/files` via yt-dlp at 720p (27,241,763 bytes, AV1 + Opus, 200.474 seconds). The earlier `youtube-end-to-end-results.json` failure is superseded for this URL/configuration by `alternative-api-results.json`. PyTubeFix 11.1.0 independently downloaded adaptive H.264/AAC streams and merged a valid 30,285,239-byte MP4; it remains a tested optional candidate rather than an enabled production dependency.

`instagram-collection-api-results.json` verifies `CvYrSgnsKjv`: nine images and one video, all ten downloaded through OneTap and validated. The video in this fixture has no audio stream; this test does not establish soundtrack preservation for Instagram photo posts.

## Existing Render native Python service

Build command: `bash scripts/render-build.sh`

Start command: `python scripts/render-start.py`

The build pins Node 22.23.2 and unmodified [Cobalt source](https://github.com/imputnet/cobalt/tree/a636575b09de1fc55d9b8cd98cac88f5f2f16b42) (AGPL-3.0), installs the API workspace, and requires FFmpeg/ffprobe. The supervisor starts Cobalt on loopback port 9000, waits for readiness, then starts OneTap on Render's PORT. It stops both process groups on shutdown and exits if either service dies, allowing Render to restart them. No public Cobalt instance or J2 session is needed.

Downloads are temporary and disappear on deploy/restart. Free-instance CPU/memory and source-site datacenter restrictions can affect extraction; local successes are not a guarantee of Render success. See the coverage audit for media-type gaps.
