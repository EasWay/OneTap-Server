# OneTap: 56-platform provider audit

2026-09-10. Cobalt 11.7.1; yt-dlp 2026.8.19. “Listed” means a dedicated provider extractor exists, not a successful live download. Generic extraction is not counted as platform support. Media types vary by platform; this matrix does not certify images, collections, or full music tracks.

| Platform | Cobalt listed | yt-dlp dedicated extractor | Coverage assessment |
|---|---|---|---|
| TikTok | Yes | tiktok:collection, tiktok:effect, TikTok | Candidate; live/media-type verification required |
| Douyin | — | Douyin | Candidate; live/media-type verification required |
| CapCut | — | — | Gap: no dedicated extractor found |
| YouTube | Yes | youtube:clip, youtube:consent, youtube:favorites | Candidate; live/media-type verification required |
| Vimeo | Yes | vimeo:album, vimeo:channel, vimeo:event | Candidate; live/media-type verification required |
| Dailymotion | Yes | dailymotion, dailymotion:playlist, dailymotion:search | Candidate; live/media-type verification required |
| Bilibili | Yes | BiliBiliBangumi, BiliBiliBangumiMedia, BiliBiliBangumiSeason | Candidate; live/media-type verification required |
| Rumble | — | RumbleChannel, RumbleEmbed, Rumble | Candidate; live/media-type verification required |
| Streamable | Yes | Streamable | Candidate; live/media-type verification required |
| TED | — | TedEmbed, TedPlaylist, TedSeries | Candidate; live/media-type verification required |
| Sohu TV | — | Sohu, SohuV | Candidate; live/media-type verification required |
| BitChute | — | BitChuteChannel, BitChute | Candidate; live/media-type verification required |
| Instagram | Yes | Instagram, InstagramIOS, instagram:story | Candidate; live/media-type verification required |
| Facebook | Yes | facebook:ads, facebook, FacebookPluginsVideo | Candidate; live/media-type verification required |
| Threads | — | — | Gap: no dedicated extractor found |
| Twitter/X | Yes | twitter:amplify, twitter:broadcast, twitter:card | Candidate; live/media-type verification required |
| Snapchat | Yes | SnapchatSpotlight | Candidate; live/media-type verification required |
| Pinterest | Yes | PinterestCollection, Pinterest | Candidate; live/media-type verification required |
| Reddit | Yes | Reddit | Candidate; live/media-type verification required |
| Tumblr | Yes | Tumblr | Candidate; live/media-type verification required |
| LinkedIn | — | linkedin:events, LinkedIn, linkedin:learning:course | Candidate; live/media-type verification required |
| Bluesky | Yes | Bluesky | Candidate; live/media-type verification required |
| Telegram | — | telegram:embed | Candidate; live/media-type verification required |
| Kuaishou | — | — | Gap: no dedicated extractor found |
| Xiaohongshu | — | XiaoHongShu | Candidate; live/media-type verification required |
| Ixigua | — | Ixigua | Candidate; live/media-type verification required |
| Weibo | — | Weibo, WeiboUser, WeiboVideo | Candidate; live/media-type verification required |
| Miaopai | — | — | Gap: no dedicated extractor found |
| Meipai | — | Meipai | Candidate; live/media-type verification required |
| Xiaoying | — | — | Gap: no dedicated extractor found |
| Yingke | — | — | Gap: no dedicated extractor found |
| Sina | — | Sina | Candidate; live/media-type verification required |
| QQ | — | vqq:series, vqq:video | Candidate; live/media-type verification required |
| ShareChat | — | — | Gap: no dedicated extractor found |
| Likee | — | likee, likee:user | Candidate; live/media-type verification required |
| Hipi | — | — | Gap: no dedicated extractor found |
| SoundCloud | Yes | SoundcloudEmbed, soundcloud, soundcloud:playlist | Candidate; live/media-type verification required |
| Mixcloud | — | mixcloud, mixcloud:playlist, mixcloud:user | Candidate; live/media-type verification required |
| Spotify | — | — | Gap: no dedicated extractor found |
| Deezer | — | — | Gap: no dedicated extractor found |
| Zing MP3 | — | zingmp3:album, zingmp3:chart-home, zingmp3:chart-music-video | Candidate; live/media-type verification required |
| Bandcamp | — | Bandcamp, Bandcamp:album, Bandcamp:user | Candidate; live/media-type verification required |
| Castbox | — | — | Gap: no dedicated extractor found |
| ESPN | — | ESPNArticle, ESPNCricInfo, ESPN | Candidate; live/media-type verification required |
| IMDb | — | imdb, imdb:list | Candidate; live/media-type verification required |
| Imgur | — | imgur:album, imgur:gallery, Imgur | Candidate; live/media-type verification required |
| iFunny | — | — | Gap: no dedicated extractor found |
| Izlesene | — | — | Gap: no dedicated extractor found |
| 9GAG | — | 9gag | Candidate; live/media-type verification required |
| oke.ru | Yes | Odnoklassniki | Candidate; live/media-type verification required |
| Febspot | — | — | Gap: no dedicated extractor found |
| GetStickerPack | — | — | Gap: no dedicated extractor found |
| MediaFire | — | — | Gap: no dedicated extractor found |
| Pornbox | — | Pornbox | Candidate; live/media-type verification required |
| XVideos | — | XVideos, xvideos:quickies | Candidate; live/media-type verification required |
| XNXX | — | XNXX | Candidate; live/media-type verification required |

## Known limitations

- `oke.ru` is the spelling in the existing product list; Cobalt and yt-dlp target **ok.ru**. An alias in validation does not prove the alternate domain works.
- Spotify/Deezer full-track downloading is not provided by this stack; do not advertise metadata, previews or podcasts as full-track support.
- yt-dlp is primarily an audio/video extractor, not a general image-gallery downloader. Cobalt covers some images and mixed posts, not every platform’s media types.
- Public fixture failures can mean a removed post, regional restriction, authentication requirement or extractor breakage; they do not by themselves prove a platform is universally unavailable.
- Live results: see `cobalt-trial-results.json` (sampled media bytes, not complete downloads) and `end-to-end-trial-results.json` (complete downloads and ffprobe).

Dedicated-extractor gaps (16): CapCut, Threads, Kuaishou, Miaopai, Xiaoying, Yingke, ShareChat, Hipi, Spotify, Deezer, Castbox, iFunny, Izlesene, Febspot, GetStickerPack, MediaFire.
