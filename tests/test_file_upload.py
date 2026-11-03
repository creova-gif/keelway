import base64
import io
import zipfile
import pytest
from httpx import AsyncClient, ASGITransport

from core.main import app
from core.security.auth import launch_token
from core.storage.database import init_db


@pytest.fixture(autouse=True)
async def setup_and_cleanup():
    await init_db()
    yield
    import shutil
    from pathlib import Path
    for item in ["my_custom_code.py", "developer_project"]:
        p = Path(item)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()


@pytest.mark.asyncio
async def test_upload_single_file():
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {launch_token()}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "filename": "my_custom_code.py",
            "content": "def hello_world(): return 'Hello from developer'",
        }
        res = await client.post("/v1/files/upload", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["type"] == "single_file"
        assert data["path"] == "my_custom_code.py"

        # Verify content can be read back
        content_res = await client.get("/v1/files/content?path=my_custom_code.py", headers=headers)
        assert content_res.status_code == 200
        assert "Hello from developer" in content_res.json()["content"]


@pytest.mark.asyncio
async def test_upload_and_extract_zip_project():
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {launch_token()}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Build in-memory zip archive
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("developer_project/main.py", "print('Project root')")
            z.writestr("developer_project/utils/helper.py", "def helper(): return 42")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        res = await client.post("/v1/files/upload", json={"filename": "project.zip", "content_base64": b64}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["type"] == "zip_archive"
        assert data["extracted_count"] == 2

        # Verify extracted files are readable
        f1 = await client.get("/v1/files/content?path=developer_project/main.py", headers=headers)
        assert f1.status_code == 200
        assert "Project root" in f1.json()["content"]

        f2 = await client.get("/v1/files/content?path=developer_project/utils/helper.py", headers=headers)
        assert f2.status_code == 200
        assert "42" in f2.json()["content"]


@pytest.mark.asyncio
async def test_upload_zip_slip_traversal_blocked():
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {launch_token()}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Build malicious zip archive attempting directory traversal
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("../../etc/passwd", "malicious_content")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        res = await client.post("/v1/files/upload", json={"filename": "evil.zip", "content_base64": b64}, headers=headers)
        # Should fail with 400 or 403 preventing directory traversal
        assert res.status_code in (400, 403)
