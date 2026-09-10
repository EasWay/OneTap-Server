import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import extraction
from litestar.testing import TestClient
import server

class NormalizeTest(unittest.TestCase):
    def test_single_audio(self):
        rows = extraction.normalize_cobalt({'status':'tunnel','url':'https://media.example/audio','filename':'song.mp3'})
        self.assertEqual(rows[0]['type'], 'audio')
    def test_collection_preserves_images_video_and_audio(self):
        rows = extraction.normalize_cobalt({'status':'picker','picker':[
            {'type':'photo','url':'https://media.example/photo'},
            {'type':'video','url':'https://media.example/video'}],
            'audio':'https://media.example/audio','audioFilename':'sound.mp3'})
        self.assertEqual([r['type'] for r in rows], ['image','video','audio'])
    def test_components_are_not_mislabeled_as_playable_video(self):
        for payload in [{'status':'local-processing'}, {'status':'picker','picker':[]},
                        {'status':'redirect','url':'file:///etc/passwd'}]:
            with self.assertRaises(extraction.ExtractionUnavailable):
                extraction.normalize_cobalt(payload)

class RoutingTest(unittest.IsolatedAsyncioTestCase):
    async def test_platform_specific_primary_providers(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(extraction, 'instagram', return_value=[{'type':'image'}]) as instagram, patch.object(extraction, 'cobalt') as cobalt:
                name, _ = await extraction.extract('https://www.instagram.com/p/Dc_uf6kysp4/',Path(directory))
                self.assertEqual(name,'instagram')
                instagram.assert_awaited_once()
                cobalt.assert_not_called()
            with patch.object(extraction, 'ytdlp', return_value=[{'type':'video'}]) as ytdlp, patch.object(extraction, 'cobalt') as cobalt:
                name, _ = await extraction.extract('https://youtu.be/vPwaXytZcgI',Path(directory))
                self.assertEqual(name,'ytdlp')
                ytdlp.assert_awaited_once()
                cobalt.assert_not_called()
    async def test_fallback_and_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(extraction, 'cobalt', side_effect=extraction.ExtractionUnavailable()), \
                 patch.object(extraction, 'ytdlp', return_value=[{'local':'video.mp4'}]) as backup:
                name, rows = await extraction.extract('https://vimeo.com/123', Path(directory))
                self.assertEqual(name, 'ytdlp')
                backup.assert_awaited_once()
            with patch.object(extraction, 'cobalt', side_effect=asyncio.CancelledError()), \
                 patch.object(extraction, 'ytdlp') as backup:
                with self.assertRaises(asyncio.CancelledError):
                    await extraction.extract('https://vimeo.com/123', Path(directory))
                backup.assert_not_called()
    async def test_spoofed_source_domain_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(extraction, 'cobalt') as provider:
                with self.assertRaises(extraction.ExtractionUnavailable):
                    await extraction.extract('https://tiktok.com.evil.example/video', Path(directory))
                provider.assert_not_called()

class ContractTest(unittest.TestCase):
    def test_local_file_and_collection_contract(self):
        for items in [[{'local':'test.mp4','filename':'test.mp4','title':'Test','type':'video','ext':'mp4','size':10}],
                      [{'url':'https://media.example/photo','filename':'photo.jpg','title':'Photo','type':'image','ext':'jpg'},
                       {'url':'https://media.example/audio','filename':'sound.mp3','title':'Sound','type':'audio','ext':'mp3'}]]:
            with patch.object(extraction,'extract',return_value=('cobalt', items)), TestClient(server.app) as client:
                response=client.post('/download',json={'url':'https://www.instagram.com/p/example/'})
            self.assertEqual(response.status_code,201)
            body=response.json()
            if len(items)==1:
                self.assertEqual(body['download_url'],'/files/test.mp4')
            else:
                self.assertEqual([f['type'] for f in body['files']],['image','audio'])
                self.assertTrue(all(f['download_url'].startswith('/stream/') for f in body['files']))
    def test_exhausted_providers_return_structured_error(self):
        with patch.object(extraction,'extract',side_effect=extraction.ExtractionUnavailable('Unavailable')), TestClient(server.app) as client:
            response=client.post('/download',json={'url':'https://vimeo.com/123'})
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['extra']['code'],'EXTRACTION_UNAVAILABLE')


class CacheTest(unittest.IsolatedAsyncioTestCase):
    async def test_actual_image_format_and_audio_are_preserved(self):
        import httpx
        real_client = httpx.AsyncClient
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200, headers={'content-type':{'/photo':'image/webp','/audio':'audio/ogg','/soundtrack':'video/mp4'}[request.url.path]}, content=b'media-bytes'))
        with tempfile.TemporaryDirectory() as directory, patch.object(extraction.httpx,'AsyncClient',side_effect=lambda **kwargs: real_client(transport=transport,**kwargs)), patch.object(extraction,'verify_media',new_callable=AsyncMock):
            rows = await extraction.cache_cobalt([
                {'url':'https://media.example/photo','ext':'jpg','type':'image'},
                {'url':'https://media.example/audio','ext':'mp3','type':'audio'},
                {'url':'https://media.example/soundtrack','ext':'mp3','type':'audio'}],Path(directory))
            self.assertEqual([r['ext'] for r in rows],['webp','ogg','mp3'])
            self.assertEqual([r['type'] for r in rows],['image','audio','audio'])
            self.assertTrue(all((Path(directory)/r['local']).read_bytes()==b'media-bytes' for r in rows))
    async def test_later_failed_item_cleans_the_whole_collection(self):
        import httpx
        real_client = httpx.AsyncClient
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200 if request.url.path=='/photo' else 503, headers={'content-type':'image/webp'}, content=b'media'))
        with tempfile.TemporaryDirectory() as directory, patch.object(extraction.httpx,'AsyncClient',side_effect=lambda **kwargs: real_client(transport=transport,**kwargs)), patch.object(extraction,'verify_media',new_callable=AsyncMock):
            with self.assertRaises(httpx.HTTPStatusError):
                await extraction.cache_cobalt([
                    {'url':'https://media.example/photo','ext':'jpg'},
                    {'url':'https://media.example/fail','ext':'mp3'}],Path(directory))
            self.assertEqual(list(Path(directory).iterdir()),[])
    async def test_html_is_not_saved_as_media(self):
        import httpx
        real_client = httpx.AsyncClient
        transport = httpx.MockTransport(lambda request: httpx.Response(200,headers={'content-type':'text/html'},content=b'error'))
        with tempfile.TemporaryDirectory() as directory, patch.object(extraction.httpx,'AsyncClient',side_effect=lambda **kwargs: real_client(transport=transport,**kwargs)), patch.object(extraction,'verify_media',new_callable=AsyncMock):
            with self.assertRaises(extraction.ExtractionUnavailable):
                await extraction.cache_cobalt([{'url':'https://media.example/error','ext':'mp4'}],Path(directory))
            self.assertEqual(list(Path(directory).iterdir()),[])

class ReelTest(unittest.IsolatedAsyncioTestCase):
    async def test_thumbnail_is_not_accepted_as_reel(self):
        import httpx
        real_client = httpx.AsyncClient
        transport = httpx.MockTransport(lambda request: httpx.Response(200,json={
            'status':'tunnel','url':'https://media.example/thumb','filename':'thumbnail.jpg'}))
        with tempfile.TemporaryDirectory() as directory, patch.object(extraction.httpx,'AsyncClient',side_effect=lambda **kwargs: real_client(transport=transport,**kwargs)), patch.object(extraction,'cache_cobalt') as cache:
            with self.assertRaises(extraction.ExtractionUnavailable):
                await extraction.cobalt('https://www.instagram.com/reel/example/',Path(directory))
            cache.assert_not_called()

class MediaValidationTest(unittest.IsolatedAsyncioTestCase):
    async def test_nonempty_error_file_is_not_accepted_as_media(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.mp4'
            path.write_bytes(b'not a playable media file')
            with self.assertRaises(extraction.ExtractionUnavailable):
                await extraction.verify_media(path,'video')

class PublicPhotosTest(unittest.IsolatedAsyncioTestCase):
    async def test_short_link_preserves_photo_and_soundtrack(self):
        import httpx, json
        real_client = httpx.AsyncClient
        item={'id':'123','imagePost':{'images':[{'imageURL':{'urlList':['https://p16.tiktokcdn.com/photo']}}]},'music':{'playUrl':'https://music.tiktokcdn.com/audio'}}
        html='<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">'+json.dumps({'__DEFAULT_SCOPE__':{'webapp.video-detail':{'statusCode':0,'itemInfo':{'itemStruct':item}}}})+'</script>'
        def handle(request):
            if request.url.host=='vt.tiktok.com':
                return httpx.Response(301,headers={'location':'https://www.tiktok.com/@example/photo/123'})
            return httpx.Response(200,text=html)
        with tempfile.TemporaryDirectory() as directory, patch.object(extraction.httpx,'AsyncClient',side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handle),**kwargs)), patch.object(extraction,'cache_cobalt',new_callable=AsyncMock) as cache:
            await extraction.public_photos('https://vt.tiktok.com/example/',Path(directory))
            self.assertEqual([r['type'] for r in cache.call_args.args[0]],['image','audio'])
            item['id']='456'
            html='<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">'+json.dumps({'__DEFAULT_SCOPE__':{'webapp.video-detail':{'statusCode':0,'itemInfo':{'itemStruct':item}}}})+'</script>'
            with self.assertRaises(extraction.ExtractionUnavailable):
                await extraction.public_photos('https://vt.tiktok.com/example/',Path(directory))

class InstagramWorkerTest(unittest.TestCase):
    def test_collection_keeps_video_instead_of_its_thumbnail(self):
        from types import SimpleNamespace
        from instagram_worker import post_items
        nodes=[SimpleNamespace(is_video=False,display_url='photo',video_url=None),
               SimpleNamespace(is_video=True,display_url='thumbnail',video_url='video')]
        post=SimpleNamespace(caption='Mixed post',typename='GraphSidecar',get_sidecar_nodes=lambda:nodes)
        rows=post_items(post)
        self.assertEqual([r['url'] for r in rows],['photo','video'])
        self.assertEqual([r['type'] for r in rows],['image','video'])
    def test_single_photo_uses_post_image(self):
        from types import SimpleNamespace
        from instagram_worker import post_items
        rows=post_items(SimpleNamespace(caption=None,typename='GraphImage',is_video=False,url='photo'))
        self.assertEqual(rows[0]['url'],'photo')
        self.assertEqual(rows[0]['type'],'image')

if __name__ == '__main__': unittest.main()
