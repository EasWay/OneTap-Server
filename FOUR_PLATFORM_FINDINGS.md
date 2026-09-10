# Four-platform follow-up — 2026-09-10

All successful cases below completed downloads and passed the existing FFprobe validation. These are local extractor tests, not Render or device tests.

| Case | Result |
|---|---|
| Twitter/X video 1697304622749086011 | Cobalt: 75,418 bytes |
| Twitter/X four photos 1877880433242771717 | Cobalt: all four images |
| Facebook video 588631943886661 | Cobalt: 40,071,678 bytes |
| Snapchat older Cobalt Spotlight fixture | Both Cobalt and yt-dlp failed; cause not established |
| Snapchat Spotlight from yt-dlp issue 12015 | Cobalt: 1,634,530 bytes |
| Snapchat @khalidalota9193 Spotlight | Cobalt failed; yt-dlp fallback: 1,393,909 bytes |

See four-platform-results.json and snapchat-followup-results.json for exact URLs.

## Instagram photo background music

Gallery-dl supports extractor.instagram.audio=true (default false) and REST API extraction. Installed 1.32.11 source handles music_metadata.music_info.music_asset_info.progressive_download_url and separately original_sound_info. This is actual audio retrieval, not just title metadata. Maintainer discussion confirms implementation: https://github.com/mikf/gallery-dl/discussions/9297
Configuration: https://github.com/mikf/gallery-dl/blob/master/docs/configuration.rst#extractorinstagramaudio

Candidate command in the isolated environment:

```sh
.trial-venv/bin/python -m gallery_dl --config-ignore -o extractor.instagram.api=rest -o extractor.instagram.audio=true 'PHOTO_POST_URL'
```

Not enabled in OneTap yet: earlier unauthenticated trials redirected to Instagram login. A known photo post with audible music is requested to validate the actual track and selected start/duration. A full soundtrack asset is not automatically the selected clip. No browser/account sessions have been read. Instagram image success alone is insufficient evidence of soundtrack success.

## Other free options

Twitter/X photos: Gallery-dl; videos: yt-dlp. Current Cobalt path already works on both tested media types.
Facebook photos/albums: Gallery-dl candidate, not live verified. Its facebook.videos=ytdl option delegates video/audio merging to yt-dlp. https://github.com/mikf/gallery-dl/blob/master/docs/configuration.rst
Snapchat Spotlight: Cobalt and yt-dlp both demonstrated success above. Public Stories: snapchat-dl is a candidate with separate coverage; not tested here. https://snapchat-dl.readthedocs.io/en/latest/snapchat_dl.html

No new provider was enabled in this follow-up; existing fallback behavior handled the successful cases.
