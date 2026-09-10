"""Keep provider outages distinct from authentication and application failures."""
from __future__ import annotations


class ProviderOriginUnavailable(Exception):
    def __init__(self, status: int, ray_id: str | None = None):
        self.status = status
        self.ray_id = ray_id
        super().__init__(f"J2Download origin unavailable (HTTP {status})")


def check_provider_origin(status: int, ray_id: str | None = None) -> None:
    # These statuses describe Cloudflare-to-origin failures, not a bad user token.
    if status in (521, 522, 523, 524, 525, 526):
        raise ProviderOriginUnavailable(status, ray_id)
