"""
Keelway Dual-Mode Sovereign IDE: External Editor Sync API Endpoints
Exposes controls for launching VS Code / Cursor and resolving concurrent edit conflicts.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from core.api import routes
from core.security.auth import current_principal, require
from core.security.rbac import Permission
from core.sync.bridge import ExternalEditorSyncBridge

router = APIRouter(prefix="/v1/editor-sync", tags=["External Editor Sync"], dependencies=[Depends(current_principal)])

# Global bridge instance bound to current active workspace
_sync_bridge: Optional[ExternalEditorSyncBridge] = None


def get_sync_bridge() -> ExternalEditorSyncBridge:
    global _sync_bridge
    if _sync_bridge is None:
        _sync_bridge = ExternalEditorSyncBridge(
            workspace_root=routes._workspace_fs.root,
            debounce_ms=150,
        )
    return _sync_bridge


class OpenInEditorRequest(BaseModel):
    editor: str = Field(default="vscode", description="Editor ID: 'vscode', 'cursor', 'vscodium', 'sublime'")
    relative_path: str = Field(default="", description="Relative file path or empty for workspace root")


class ResolveConflictRequest(BaseModel):
    file_path: str = Field(..., description="Relative file path with pending conflict")
    resolution: str = Field(..., description="'keep_agent' to apply agent proposal, 'keep_external' to keep external edit")


@router.get("/status", tags=["External Editor Sync"])
async def get_sync_status(bridge: ExternalEditorSyncBridge = Depends(get_sync_bridge)):
    """Returns the external editor sync watcher status, detected editors, and pending conflicts."""
    return bridge.get_status()


@router.post("/open-in-editor", tags=["External Editor Sync"])
async def open_in_external_editor(
    req: OpenInEditorRequest,
    bridge: ExternalEditorSyncBridge = Depends(get_sync_bridge),
    _=Depends(require(Permission.EXECUTE_AGENT)),
):
    """
    Launches the workspace or active file in an external editor (VS Code, Cursor, etc.).
    Returns HTTP 422 if the external editor binary is not installed on the system.
    """
    try:
        res = bridge.open_in_editor(editor=req.editor, relative_path=req.relative_path)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to launch editor: {str(e)}")


@router.post("/resolve-conflict", tags=["External Editor Sync"])
async def resolve_concurrent_conflict(
    req: ResolveConflictRequest,
    bridge: ExternalEditorSyncBridge = Depends(get_sync_bridge),
    _=Depends(require(Permission.EXECUTE_AGENT)),
):
    """Resolves a concurrent edit conflict between an agent and an external editor."""
    try:
        return bridge.resolve_conflict(file_path=req.file_path, resolution=req.resolution)
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
