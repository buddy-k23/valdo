"""File Downloader API router.

Provides browse, download, and archive-inspection endpoints.
All endpoints require a valid API key and path must be under a
configured allowed path (from file-downloader.yml).
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.auth import require_api_key
from src.services import downloader_service as svc
from src.services.downloader_logger import log_activity, resolve_client_info

router = APIRouter()


def _allowed_paths(request: Request) -> list:
    """Extract allowed path strings from app state fd_config.

    Args:
        request: Current FastAPI request.

    Returns:
        List of allowed path strings from file-downloader.yml config.
    """
    return [p["path"] for p in getattr(request.app.state, "fd_config", {}).get("paths", [])]


def _safe_filename(name: str) -> str:
    """Ensure *name* is a plain filename with no path components.

    Args:
        name: User-supplied filename or archive name.

    Returns:
        The original name if safe.

    Raises:
        HTTPException: 400 if the name contains path separators or is absolute.
    """
    if Path(name).name != name:
        raise HTTPException(status_code=400, detail=f"Invalid filename: {name!r}")
    return name


def _validate(requested: str, request: Request) -> Path:
    """Validate *requested* against the allowed paths in app state.

    Args:
        requested: Path string from query parameter or request body.
        request: Current FastAPI request (used to read app state).

    Returns:
        Resolved and validated ``Path``.

    Raises:
        HTTPException: 403 if path is outside all configured allowed paths.
    """
    try:
        return svc.validate_path(requested, _allowed_paths(request))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


class DownloadRequest(BaseModel):
    """POST /download request body."""

    path: str
    filename: str
    archive: Optional[str] = None


class SearchFilesRequest(BaseModel):
    """POST /search-files request body."""

    path: str
    filename_pattern: str
    search_string: str


class SearchArchiveRequest(BaseModel):
    """POST /search-archive request body."""

    path: str
    archive_pattern: str
    file_pattern: str
    search_string: str


@router.get("/paths")
async def get_paths(request: Request, _: object = Depends(require_api_key)):
    """Return configured paths from file-downloader.yml.

    Args:
        request: Current FastAPI request.
        _: Unused auth context (validates API key).

    Returns:
        Dict with ``paths`` list from app state fd_config.
    """
    return {"paths": getattr(request.app.state, "fd_config", {}).get("paths", [])}


@router.get("/browse")
async def browse(
    path: str,
    request: Request,
    pattern: Optional[str] = None,
    _: object = Depends(require_api_key),
):
    """List files in *path*, optionally filtered by *pattern*.

    Args:
        path: Directory to list (must be under an allowed configured path).
        request: Current FastAPI request.
        pattern: Optional fnmatch wildcard to filter filenames.
        _: Unused auth context (validates API key).

    Returns:
        Dict with ``entries`` list, each having ``name``, ``type``, ``size_bytes``.

    Raises:
        HTTPException: 403 if path is not under an allowed configured path.
        HTTPException: 404 if directory does not exist.
    """
    resolved = _validate(path, request)
    try:
        entries = svc.browse_path(resolved, pattern)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "entries": [
            {"name": e.name, "type": e.type, "size_bytes": e.size_bytes}
            for e in entries
        ]
    }


@router.get("/archive-contents")
async def archive_contents(
    path: str,
    archive: str,
    request: Request,
    _: object = Depends(require_api_key),
):
    """List files inside *archive* found in *path*.

    Args:
        path: Directory containing the archive (must be under an allowed path).
        archive: Archive filename (relative to *path*).
        request: Current FastAPI request.
        _: Unused auth context (validates API key).

    Returns:
        Dict with ``files`` list of inner file paths.

    Raises:
        HTTPException: 403 if path is not under an allowed configured path.
        HTTPException: 404 if archive file is not found.
        HTTPException: 400 if archive format is unsupported.
    """
    _safe_filename(archive)
    resolved = _validate(path, request)
    arc_path = resolved / archive
    if not arc_path.is_file():
        raise HTTPException(status_code=404, detail=f"Archive '{archive}' not found")
    try:
        return {"files": svc.list_archive_contents(arc_path)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/download")
async def download_file(
    body: DownloadRequest,
    request: Request,
    _: object = Depends(require_api_key),
):
    """Stream a single file from disk or extracted from an archive.

    Args:
        body: Download request with ``path``, ``filename``, and optional ``archive``.
        request: Current FastAPI request.
        _: Unused auth context (validates API key).

    Returns:
        ``StreamingResponse`` with ``application/octet-stream`` content type.

    Raises:
        HTTPException: 403 if path is not under an allowed configured path.
        HTTPException: 404 if file or archive is not found.
        HTTPException: 400 if archive format is unsupported.
    """
    _safe_filename(body.filename)
    if body.archive:
        _safe_filename(body.archive)
    resolved = _validate(body.path, request)
    client_ip, client_host = resolve_client_info(request)

    if body.archive:
        arc_path = resolved / body.archive
        if not arc_path.is_file():
            raise HTTPException(status_code=404, detail=f"Archive '{body.archive}' not found")
        try:
            stream = svc.extract_file(arc_path, body.filename)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        file_path = resolved / body.filename
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"File '{body.filename}' not found")

        def _plain():
            with open(file_path, "rb") as fh:
                while True:
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    yield chunk

        stream = _plain()

    log_activity(
        operation="download",
        client_ip=client_ip,
        client_host=client_host,
        path=body.path,
        filename=body.filename,
        archive=body.archive,
        status="success",
    )

    download_name = Path(body.filename).name
    # Sanitize filename for Content-Disposition header (strip chars unsafe in quoted-string)
    safe_name = download_name.replace("\\", "").replace('"', "").replace("\r", "").replace("\n", "")
    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
