import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app


@pytest.mark.asyncio
async def test_keelway_dev_studio_html_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check /
        resp_root = await client.get("/")
        assert resp_root.status_code == 200
        assert "Keelway Studio" in resp_root.text
        assert "Air-Gapped: Zero-Egress" in resp_root.text
        assert "/studio/assets/studio.js" in resp_root.text
        for cdn in ("cdn.tailwindcss.com", "cdnjs.cloudflare.com", "fonts.googleapis.com"):
            assert cdn not in resp_root.text

        # Check /studio
        resp_studio = await client.get("/studio")
        assert resp_studio.status_code == 200
        assert "Keelway Studio" in resp_studio.text
        assert "Diffs (Unified &amp; Split)" in resp_studio.text
