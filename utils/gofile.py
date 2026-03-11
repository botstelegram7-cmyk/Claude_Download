"""
Serena Bot - GoFile Uploader
Uploads large files to GoFile.io and returns a share link.
"""
import os
import asyncio
import logging
import aiohttp

logger = logging.getLogger("SerenaBot.GoFile")

GOFILE_API = "https://api.gofile.io"


async def get_best_server() -> str:
    """Get the best GoFile upload server."""
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{GOFILE_API}/servers", timeout=aiohttp.ClientTimeout(total=10)) as r:
            data = await r.json()
            if data.get("status") == "ok":
                servers = data["data"].get("servers", [])
                if servers:
                    # Pick server with lowest load
                    best = min(servers, key=lambda x: x.get("zone","") != "eu")
                    return best["name"]
    return "store1"  # fallback


async def upload_to_gofile(
    filepath: str,
    token: str = "",
    folder_id: str = "",
    progress_cb=None,
) -> dict:
    """
    Upload file to GoFile.io
    Returns: {"status": "ok", "link": "...", "download_page": "...", "file_id": "..."}
    """
    server = await get_best_server()
    upload_url = f"https://{server}.gofile.io/contents/uploadfile"

    file_size = os.path.getsize(filepath)
    filename  = os.path.basename(filepath)
    uploaded  = 0

    class _ProgressReader:
        def __init__(self, f):
            self._f = f
        def read(self, size=-1):
            nonlocal uploaded
            chunk = self._f.read(size)
            uploaded += len(chunk)
            if progress_cb and file_size > 0:
                asyncio.get_event_loop().call_soon_threadsafe(
                    lambda: asyncio.ensure_future(progress_cb(uploaded, file_size))
                )
            return chunk

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with aiohttp.ClientSession(headers=headers) as s:
        with open(filepath, "rb") as f:
            form = aiohttp.FormData()
            form.add_field("file", f, filename=filename,
                           content_type="application/octet-stream")
            if folder_id:
                form.add_field("folderId", folder_id)

            async with s.post(
                upload_url,
                data=form,
                timeout=aiohttp.ClientTimeout(total=3600),
            ) as resp:
                data = await resp.json()

    if data.get("status") != "ok":
        raise RuntimeError(f"GoFile upload failed: {data}")

    d = data["data"]
    code = d.get("parentFolder") or d.get("code","")
    return {
        "status": "ok",
        "file_id": d.get("id",""),
        "filename": d.get("name", filename),
        "size": d.get("size", file_size),
        "link": f"https://gofile.io/d/{code}",
        "direct_link": d.get("downloadPage",""),
        "code": code,
    }
