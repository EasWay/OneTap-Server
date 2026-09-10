import unittest
from unittest.mock import patch

import httpx
from litestar.testing import TestClient

import server
from provider_errors import ProviderOriginUnavailable, check_provider_origin


class ProviderOutageTest(unittest.IsolatedAsyncioTestCase):
    async def test_handshake_preserves_origin_status(self):
        real_client = httpx.AsyncClient
        for status in (522, 523):
            with self.subTest(status=status):
                transport = httpx.MockTransport(
                    lambda request: httpx.Response(status, headers={"cf-ray": "test-ray"})
                )
                with patch.object(server.httpx, "AsyncClient",
                                  side_effect=lambda **kwargs: real_client(transport=transport, **kwargs)):
                    with self.assertRaises(ProviderOriginUnavailable) as caught:
                        await server.AsyncJ2Extractor().extract_download_url(
                            "https://www.tiktok.com/@example/video/123"
                        )
                self.assertEqual(caught.exception.status, status)
                self.assertEqual(caught.exception.ray_id, "test-ray")

    async def test_origin_check_does_not_misclassify_authentication(self):
        for status in (200, 401, 403, 429, 500, 503):
            check_provider_origin(status)



if __name__ == "__main__":
    unittest.main()
