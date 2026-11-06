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
        assert "Offline (setting)" in resp_root.text
        assert "sent: unmeasured" in resp_root.text
        assert "Air-Gapped: Zero-Egress" not in resp_root.text
        assert "/studio/assets/studio.js" in resp_root.text
        assert "Content-Security-Policy" in resp_root.headers
        assert "default-src 'self'" in resp_root.headers["Content-Security-Policy"]
        for cdn in ("cdn.tailwindcss.com", "cdnjs.cloudflare.com", "fonts.googleapis.com"):
            assert cdn not in resp_root.text

        # Check /studio
        resp_studio = await client.get("/studio")
        assert resp_studio.status_code == 200
        assert "Keelway Studio" in resp_studio.text
        assert "Diffs (Unified &amp; Split)" in resp_studio.text
        assert "Local Team Mesh &amp; GPU Resource Pooling" in resp_studio.text
        assert "Two-Human Quorum Governance (ADR-045 / ADR-046)" in resp_studio.text
        assert "669 / 669" not in resp_studio.text
        assert "2.74x VERIFIED" not in resp_studio.text

        # Check studio.js static asset
        resp_js = await client.get("/studio/assets/studio.js")
        assert resp_js.status_code == 200
        assert "dispatchMeshDelegation" in resp_js.text
        assert "submitQuorumSign" in resp_js.text
        assert "loadSyncStatusInStudio" in resp_js.text
        assert "showMobilePairingInStudio" in resp_js.text
        assert "renderSpeculativeTokenStream" in resp_js.text

        # Check /console and /web-console
        resp_console = await client.get("/console")
        assert resp_console.status_code == 200
        assert "KEELWAY" in resp_console.text
        assert "Cross-Machine" in resp_console.text

        resp_web_console = await client.get("/web-console")
        assert resp_web_console.status_code == 200
        assert "Vector Clocks" in resp_web_console.text
