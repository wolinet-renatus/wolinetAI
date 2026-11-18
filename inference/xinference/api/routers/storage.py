"""Storage, checkpoint market, and custom model drive operations router."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fastapi import Body, File, Form, HTTPException, Request, Security, UploadFile

from ..responses import JSONResponse

if TYPE_CHECKING:
    from ..restful_api import RESTfulAPI

logger = logging.getLogger(__name__)


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _get_models_root() -> Path:
    candidates = [
        os.environ.get("WOLINET_MODELS_DIR"),
        os.path.join(os.environ.get("WORKSPACE_ROOT", ""), "inference", "models"),
        os.path.join(os.environ.get("WORKSPACE_ROOT", ""), "models"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "models")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "models")),
        "/models",
        os.path.expanduser("~/models"),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return Path(c).resolve()
    fallback = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "models")))
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


async def list_storage_models(request: Request) -> JSONResponse:
    """List local model files on disk (LLMs, DFlash drafts, LoRAs) and their live status."""
    api = request.app.state.api
    models_root = _get_models_root()
    supervisor_ref = await api._get_supervisor_ref()

    # Query running models
    running_models = {}
    try:
        raw_running = await supervisor_ref.list_models()
        if isinstance(raw_running, dict):
            running_models = raw_running
    except Exception as exc:
        logger.warning("Could not query supervisor running models: %s", exc)

    # Query Rust Defense-RS Core (:8088) acceleration & resident status
    accelerated_models = {}
    try:
        accel_req = urllib.request.Request(
            "http://127.0.0.1:8088/v1/acceleration/status",
            headers={"User-Agent": "Mitambo-Storage/1.0"},
        )
        with urllib.request.urlopen(accel_req, timeout=0.3) as resp:
            if resp.status == 200:
                accel_data = json.loads(resp.read().decode("utf-8"))
                for cm in accel_data.get("cached_models", []):
                    cname = cm.get("name")
                    cpath = cm.get("path")
                    if cm.get("status") == "RESIDENT_WARMED":
                        if cname:
                            accelerated_models[cname] = cm
                        if cpath:
                            accelerated_models[os.path.basename(cpath)] = cm
    except Exception:
        pass

    # Query registered custom models
    registered_specs: Dict[str, Dict[str, Any]] = {}
    try:
        registrations = await supervisor_ref.list_model_registrations("LLM", detailed=True)
        if isinstance(registrations, list):
            for reg in registrations:
                name = reg.get("model_name")
                if name:
                    registered_specs[name] = reg
    except Exception as exc:
        logger.warning("Could not query supervisor registrations: %s", exc)

    model_files: List[Dict[str, Any]] = []
    allowed_extensions = {".gguf", ".bin", ".safetensors", ".pt", ".onnx"}

    # Search folders
    subdirs = ["llm", "dflash", "checkpoints", "custom"]
    for subdir in subdirs:
        dir_path = models_root / subdir
        if not dir_path.exists():
            continue

        for root, _, files in os.walk(dir_path):
            for file in sorted(files):
                ext = os.path.splitext(file)[1].lower()
                if ext not in allowed_extensions:
                    continue

                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(models_root.parent))
                size_bytes = full_path.stat().st_size
                mtime = full_path.stat().st_mtime

                # Match with registered models
                registered_name = None
                registered_type = None
                for reg_name, reg_spec in registered_specs.items():
                    specs = reg_spec.get("model_specs", [])
                    for s in specs:
                        fn = str(s.get("model_file_name_template") or "")
                        uri = str(s.get("model_uri") or "")
                        if (fn and (fn == file or str(full_path).endswith(fn))) or (uri and file in uri):
                            registered_name = reg_name
                            registered_type = "LLM"
                            break
                    if registered_name:
                        break

                # Match with running instances
                is_running = False
                running_uid = None
                for uid, info in running_models.items():
                    m_name = info.get("model_name", "")
                    if registered_name and m_name == registered_name:
                        is_running = True
                        running_uid = uid
                        break
                    if file in str(info):
                        is_running = True
                        running_uid = uid
                        break

                if not is_running:
                    if registered_name and registered_name in accelerated_models:
                        is_running = True
                        running_uid = f"{registered_name} (Defense-RS :8088)"
                    elif file in accelerated_models:
                        is_running = True
                        running_uid = f"{accelerated_models[file].get('name', registered_name or 'accelerated')} (Defense-RS :8088)"

                model_files.append(
                    {
                        "filename": file,
                        "rel_path": rel_path,
                        "abs_path": str(full_path),
                        "size_bytes": size_bytes,
                        "size_human": _human_size(size_bytes),
                        "category": subdir,
                        "format": "ggufv2" if ext == ".gguf" else ext.lstrip("."),
                        "modified_at": datetime.datetime.fromtimestamp(
                            mtime, tz=datetime.timezone.utc
                        ).isoformat(),
                        "is_registered": registered_name is not None,
                        "registered_model_name": registered_name,
                        "registered_model_type": registered_type,
                        "is_running": is_running,
                        "running_model_uid": running_uid,
                    }
                )

    return JSONResponse(
        content={
            "models_root": str(models_root),
            "total_files": len(model_files),
            "total_disk_bytes": sum(f["size_bytes"] for f in model_files),
            "total_disk_human": _human_size(sum(f["size_bytes"] for f in model_files)),
            "files": model_files,
        }
    )


async def list_checkpoints(request: Request) -> JSONResponse:
    """List sovereign self-trained model checkpoints from models/checkpoints."""
    api = request.app.state.api
    models_root = _get_models_root()
    checkpoints_dir = models_root / "checkpoints"
    supervisor_ref = await api._get_supervisor_ref()

    running_models = {}
    try:
        raw_running = await supervisor_ref.list_models()
        if isinstance(raw_running, dict):
            running_models = raw_running
    except Exception:
        pass

    results: List[Dict[str, Any]] = []
    if checkpoints_dir.exists():
        for item in sorted(checkpoints_dir.iterdir()):
            if not item.is_dir():
                continue

            meta_file = item / "training_meta.json"
            adapter_file = item / "adapter_config.json"
            readme_file = item / "README.md"

            meta: Dict[str, Any] = {}
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception as exc:
                    logger.warning("Error reading %s: %s", meta_file, exc)

            adapter_meta: Dict[str, Any] = {}
            if adapter_file.exists():
                try:
                    with open(adapter_file, "r", encoding="utf-8") as f:
                        adapter_meta = json.load(f)
                except Exception:
                    pass

            readme_text = ""
            if readme_file.exists():
                try:
                    readme_text = readme_file.read_text(encoding="utf-8")
                except Exception:
                    pass

            ckpt_id = meta.get("model_id", item.name)
            is_running = any(
                ckpt_id in uid or info.get("model_name") == ckpt_id
                for uid, info in running_models.items()
            )
            running_uid = next(
                (uid for uid, info in running_models.items() if ckpt_id in uid or info.get("model_name") == ckpt_id),
                None,
            )

            results.append(
                {
                    "checkpoint_id": ckpt_id,
                    "model_name": meta.get("model_name", item.name),
                    "model_family": meta.get("model_family", "deepseek-r1-distill-qwen"),
                    "base_checkpoint": meta.get("base_checkpoint", "wolinet-brain-r1-1.5b.gguf"),
                    "target_device": meta.get("target_device", "mps"),
                    "training_samples": meta.get("training_samples", 0),
                    "initial_loss": meta.get("initial_loss", 0.0),
                    "final_loss": meta.get("final_loss", 0.0),
                    "loss_reduction_pct": meta.get("loss_reduction_pct", 0.0),
                    "training_time_seconds": meta.get("training_time_seconds", 0.0),
                    "timestamp": meta.get("timestamp", ""),
                    "lora_parameters": meta.get(
                        "lora_parameters",
                        {
                            "r": adapter_meta.get("r", 8),
                            "lora_alpha": adapter_meta.get("lora_alpha", 16),
                            "lora_dropout": adapter_meta.get("lora_dropout", 0.05),
                            "target_modules": adapter_meta.get("target_modules", []),
                        },
                    ),
                    "status": meta.get("status", "ready_for_deployment"),
                    "dir_path": str(item),
                    "readme": readme_text,
                    "is_running": is_running,
                    "running_model_uid": running_uid,
                }
            )

    return JSONResponse(content={"checkpoints": results})


async def launch_checkpoint(request: Request, body: Dict[str, Any] = Body(...)) -> JSONResponse:
    """1-Click launch a self-trained checkpoint into live Mitambo inference."""
    api = request.app.state.api
    supervisor_ref = await api._get_supervisor_ref()
    checkpoint_id = body.get("checkpoint_id", "wolinet-coder-v2")
    model_uid = body.get("model_uid", checkpoint_id)

    # Check if already registered
    try:
        registered = await supervisor_ref.get_model_registration("LLM", checkpoint_id)
    except Exception:
        registered = None

    if not registered:
        # Check registration files in registrations/
        models_root = _get_models_root()
        reg_file = models_root / "registrations" / f"{checkpoint_id}.json"
        if not reg_file.exists():
            # Try wolinex-coder
            reg_file = models_root / "registrations" / "wolinex-coder.json"

        if reg_file.exists():
            with open(reg_file, "r", encoding="utf-8") as f:
                spec_data = json.load(f)
                spec_data["model_name"] = checkpoint_id
                await supervisor_ref.register_model("LLM", json.dumps(spec_data), persist=True)
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Registration template for {checkpoint_id} not found",
            )

    # Launch model
    try:
        launched_uid = await supervisor_ref.launch_model(
            model_type="LLM",
            model_name=checkpoint_id,
            model_uid=model_uid,
        )
        return JSONResponse(
            content={
                "message": f"Successfully launched self-trained checkpoint: {checkpoint_id}",
                "model_uid": launched_uid,
                "status": "running",
            }
        )
    except Exception as exc:
        logger.exception("Failed to launch checkpoint: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


async def upload_storage_file(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("llm"),
    filename: Optional[str] = Form(None),
) -> JSONResponse:
    """Upload model weight or checkpoint file directly to disk storage."""
    models_root = _get_models_root()
    clean_cat = category.replace("..", "").strip("/\\") or "llm"
    target_dir = models_root / clean_cat
    target_dir.mkdir(parents=True, exist_ok=True)

    dest_filename = (filename or file.filename or "model.gguf").replace("..", "").strip("/\\")
    target_file = target_dir / dest_filename

    total_bytes = 0
    with open(target_file, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            buffer.write(chunk)
            total_bytes += len(chunk)

    return JSONResponse(
        content={
            "message": f"Successfully uploaded {dest_filename}",
            "filename": dest_filename,
            "category": clean_cat,
            "path": str(target_file),
            "size_bytes": total_bytes,
            "size_human": _human_size(total_bytes),
        }
    )


async def download_storage_file(
    request: Request, body: Dict[str, Any] = Body(...)
) -> JSONResponse:
    """Download model weight file from remote URL (HuggingFace / ModelScope / HTTPS)."""
    url = body.get("url", "").strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="A valid HTTP or HTTPS URL is required.")

    category = body.get("category", "llm").replace("..", "").strip("/\\") or "llm"
    models_root = _get_models_root()
    target_dir = models_root / category
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = body.get("filename")
    if not filename:
        parsed_url = urllib.parse.urlparse(url)
        filename = os.path.basename(parsed_url.path) or "downloaded_model.gguf"
    filename = filename.replace("..", "").strip("/\\")

    target_path = target_dir / filename

    def _sync_download():
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Wolinet-Storage-Manager/1.0"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp, open(target_path, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)

    try:
        await asyncio.to_thread(_sync_download)
        size_bytes = target_path.stat().st_size
        return JSONResponse(
            content={
                "message": f"Successfully downloaded {filename}",
                "filename": filename,
                "category": category,
                "path": str(target_path),
                "size_bytes": size_bytes,
                "size_human": _human_size(size_bytes),
            }
        )
    except Exception as exc:
        logger.exception("Download failed from %s: %s", url, exc)
        raise HTTPException(status_code=500, detail=f"Download failed: {exc}")


async def stop_model_instance(
    request: Request, body: Dict[str, Any] = Body(...)
) -> JSONResponse:
    """Stop/terminate running model instance(s) by model_uid or model_name."""
    api = request.app.state.api
    supervisor_ref = await api._get_supervisor_ref()
    model_uid = body.get("model_uid")
    model_name = body.get("model_name")

    if not model_uid and not model_name:
        raise HTTPException(status_code=400, detail="model_uid or model_name required.")

    stopped_uids: List[str] = []
    running = await supervisor_ref.list_models()
    for uid, info in (running or {}).items():
        if (model_uid and uid == model_uid) or (model_name and info.get("model_name") == model_name):
            try:
                await supervisor_ref.terminate_model(uid)
                stopped_uids.append(uid)
            except Exception as exc:
                logger.warning("Error stopping model %s: %s", uid, exc)

    return JSONResponse(
        content={
            "message": f"Stopped {len(stopped_uids)} instance(s)",
            "stopped_uids": stopped_uids,
        }
    )


async def purge_model(request: Request, body: Dict[str, Any] = Body(...)) -> JSONResponse:
    """Unregister model AND optionally purge its disk files to reclaim space."""
    api = request.app.state.api
    supervisor_ref = await api._get_supervisor_ref()
    model_type = body.get("model_type", "LLM")
    model_name = body.get("model_name", "")
    purge_disk_files = bool(body.get("purge_disk_files", False))
    file_path = body.get("file_path", "")

    freed_bytes = 0
    freed_files: List[str] = []

    # 1. Unregister from supervisor if registered
    if model_name:
        try:
            await supervisor_ref.unregister_model(model_type, model_name)
        except Exception as exc:
            logger.info("Unregister model note: %s", exc)

    # 2. Terminate any running instances
    try:
        running = await supervisor_ref.list_models()
        for uid, info in (running or {}).items():
            if info.get("model_name") == model_name:
                await supervisor_ref.terminate_model(uid)
    except Exception:
        pass

    # 3. Purge disk files if requested
    if purge_disk_files:
        models_root = _get_models_root()
        target_paths_to_delete: List[Path] = []

        if file_path:
            p = Path(file_path).resolve()
            # Security: ensure inside models_root or ~/.xinference/cache
            xinference_cache = Path(os.path.expanduser("~/.xinference")).resolve()
            if models_root in p.parents or xinference_cache in p.parents:
                target_paths_to_delete.append(p)
        elif model_name:
            # Search for files matching model_name in models_root
            for root, _, files in os.walk(models_root):
                for f in files:
                    if model_name in f or f in model_name:
                        target_paths_to_delete.append(Path(root) / f)

        for p in target_paths_to_delete:
            if p.exists():
                try:
                    if p.is_file():
                        sz = p.stat().st_size
                        p.unlink()
                        freed_bytes += sz
                        freed_files.append(str(p))
                    elif p.is_dir():
                        sz = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                        shutil.rmtree(p)
                        freed_bytes += sz
                        freed_files.append(str(p))
                except Exception as exc:
                    logger.warning("Could not delete %s: %s", p, exc)

    return JSONResponse(
        content={
            "message": f"Successfully deleted model {model_name}",
            "unregistered": True,
            "purged_disk": purge_disk_files,
            "freed_bytes": freed_bytes,
            "freed_human": _human_size(freed_bytes),
            "deleted_paths": freed_files,
        }
    )


async def update_custom_model_config(
    request: Request, body: Dict[str, Any] = Body(...)
) -> JSONResponse:
    """Update custom model registration (weight file, context length, chat template, tags)."""
    api = request.app.state.api
    supervisor_ref = await api._get_supervisor_ref()
    model_type = body.get("model_type", "LLM")
    model_name = body.get("model_name", "")
    new_spec = body.get("spec", {})

    if not model_name or not new_spec:
        raise HTTPException(status_code=400, detail="model_name and spec required.")

    # In Xinference, update is performed by unregistering then re-registering with new spec
    try:
        await supervisor_ref.unregister_model(model_type, model_name)
    except Exception:
        pass

    try:
        await supervisor_ref.register_model(model_type, json.dumps(new_spec), persist=True)
    except Exception as exc:
        logger.exception("Failed to re-register updated model: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse(
        content={
            "message": f"Successfully updated model {model_name}",
            "model_name": model_name,
            "model_type": model_type,
        }
    )


def register_routes(api: "RESTfulAPI") -> None:
    """Bind storage and checkpoint management routes."""
    router = api._router
    auth = api._auth_service
    is_auth = api.is_authenticated()

    read_dep = [Security(auth, scopes=["models:list"])] if is_auth else None
    write_dep = [Security(auth, scopes=["models:write"])] if is_auth else None
    reg_dep = [Security(auth, scopes=["models:register"])] if is_auth else None

    # Storage and drive inspection
    router.add_api_route(
        "/v1/storage/models",
        list_storage_models,
        methods=["GET"],
        dependencies=read_dep,
    )
    router.add_api_route(
        "/v1/storage/checkpoints",
        list_checkpoints,
        methods=["GET"],
        dependencies=read_dep,
    )
    router.add_api_route(
        "/v1/storage/checkpoints/launch",
        launch_checkpoint,
        methods=["POST"],
        dependencies=write_dep,
    )
    router.add_api_route(
        "/v1/storage/upload",
        upload_storage_file,
        methods=["POST"],
        dependencies=write_dep,
    )
    router.add_api_route(
        "/v1/storage/download",
        download_storage_file,
        methods=["POST"],
        dependencies=write_dep,
    )
    router.add_api_route(
        "/v1/storage/models/stop",
        stop_model_instance,
        methods=["POST"],
        dependencies=write_dep,
    )
    router.add_api_route(
        "/v1/storage/models/purge",
        purge_model,
        methods=["DELETE"],
        dependencies=reg_dep,
    )
    router.add_api_route(
        "/v1/storage/models/update",
        update_custom_model_config,
        methods=["POST"],
        dependencies=reg_dep,
    )
