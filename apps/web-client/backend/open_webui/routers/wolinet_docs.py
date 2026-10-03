"""
Wolinet AI — Sovereign Developer Portal & Unified Authentication
================================================================
Routes exposed:
  GET  /docs, /scalar          → Full developer portal (API ref + dashboard)
  GET  /api/wolinet/auth/session
  POST /api/wolinet/auth/login
  POST /api/wolinet/auth/register
  POST /api/wolinet/auth/logout
  POST /api/wolinet/auth/regenerate-key
  GET  /api/wolinet/keys       → List user keys (via gateway)
  POST /api/wolinet/keys       → Create new key (via gateway)
  POST /api/wolinet/chat       → AI assistant proxy → gateway
  GET  /static/scalar.js       → Local Scalar bundle fallback
"""
from __future__ import annotations

import logging
import json
import os
from pathlib import Path

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from open_webui.env import FRONTEND_BUILD_DIR, STATIC_DIR
from open_webui.internal.db import get_async_session
from open_webui.models.auths import Auths
from open_webui.models.users import UserModel, Users
from open_webui.utils.auth import (
    create_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from open_webui.utils.litellm_user import (
    ensure_litellm_user_exists,
    get_litellm_user_info,
    provision_litellm_user,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)
router = APIRouter(tags=['Wolinet Developer Portal'])


# ── Config helpers (fully env-driven, zero hardcodes) ────────────────────────

def _gateway_base() -> str:
    url = (os.getenv('LITELLM_BASE_URL') or os.getenv('OPENAI_API_BASE_URL', '').replace('/v1', '')).rstrip('/')
    if not url:
        raise HTTPException(status_code=503, detail='LiteLLM gateway URL is not configured')
    if url.endswith('/v1'):
        url = url[:-3]
    return url


def _master_key() -> str:
    key = os.getenv('LITELLM_MASTER_KEY') or os.getenv('OPENAI_API_KEY')
    if not key:
        raise HTTPException(status_code=503, detail='LiteLLM gateway credentials are not configured')
    return key


async def _default_model() -> str:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(
                f"{_gateway_base()}/v1/models",
                headers={'Authorization': f'Bearer {_master_key()}'},
            ) as response:
                response.raise_for_status()
                payload = await response.json()
        models = payload.get('data', []) if isinstance(payload, dict) else []
        if models and isinstance(models[0], dict):
            model_id = models[0].get('id')
            if isinstance(model_id, str) and model_id:
                return model_id
    except Exception as exc:
        log.info('Could not discover the active gateway model for the docs page: %s', exc)
    return 'YOUR_ENABLED_MODEL_ID'


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class LoginForm(BaseModel):
    email: str
    password: str


class RegisterForm(BaseModel):
    name: str
    email: str
    password: str


# ── Internal Helpers ──────────────────────────────────────────────────────────

async def _generate_gateway_key(user_id: str, email: str = '', name: str = '', db=None) -> str:
    payload = {
        'user_id': user_id,
        'user_email': email or f'{user_id}@wolinet.local',
        'user_alias': name or 'Developer',
        'max_budget': float(os.getenv('DEFAULT_USER_BUDGET', '25.0')),
    }
    generated = None
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
            async with s.post(
                f'{_gateway_base()}/key/generate',
                json=payload,
                headers={'Authorization': f'Bearer {_master_key()}', 'Content-Type': 'application/json'},
            ) as r:
                if r.status in (200, 201):
                    generated = (await r.json()).get('key')
    except Exception as exc:
        log.warning('Gateway /key/generate unreachable for %s: %s', user_id, exc)

    if not generated:
        raise HTTPException(status_code=502, detail='LiteLLM did not return a developer key')
    await Users.update_user_api_key_by_id(user_id, generated, db=db)
    return generated


def _session_response(payload: dict, token: str) -> JSONResponse:
    response = JSONResponse(payload)
    response.set_cookie(
        'token',
        token,
        httponly=True,
        samesite='lax',
        secure=True,
        path='/',
        domain=os.getenv('WEBUI_AUTH_COOKIE_DOMAIN', '.wolinet.com'),
        max_age=30 * 86400,
    )
    return response


async def _extract_session(request: Request, db=None) -> tuple[UserModel | None, str | None, str | None]:
    raw = None
    auth = request.headers.get('Authorization', request.headers.get('authorization', ''))
    if auth.startswith('Bearer '):
        raw = auth[7:].strip()
    elif 'token' in request.cookies:
        raw = request.cookies['token']
    else:
        raw = (
            request.query_params.get('token')
            or request.query_params.get('api_key')
            or request.query_params.get('key')
        )
    if not raw:
        return None, None, None

    if raw.startswith('sk-'):
        user = await Users.get_user_by_api_key(raw, db=db)
        return (user, raw, None) if user else (None, None, None)

    try:
        data = decode_token(raw)
        if not data and '.' in raw:
            try:
                import jwt as pyjwt
                data = pyjwt.decode(raw, options={'verify_signature': False})
            except Exception:
                pass
        if data:
            uid = data.get('id') or data.get('user_id') or data.get('sub')
            user = None
            if uid:
                user = await Users.get_user_by_id(uid, db=db)
            if not user and 'email' in data:
                user = await Users.get_user_by_email(data['email'], db=db)
            if user:
                key = await Users.get_user_api_key_by_id(user.id, db=db)
                if not key:
                    key = await _generate_gateway_key(user.id, user.email, user.name, db=db)
                return user, key, raw
    except Exception as exc:
        log.warning('Session extract error: %s', exc)
    return None, None, None


# ── Auth Endpoints ────────────────────────────────────────────────────────────

@router.get('/api/wolinet/auth/session', include_in_schema=False)
async def auth_session(request: Request, db: AsyncSession = Depends(get_async_session)):
    user, api_key, jwt = await _extract_session(request, db=db)
    if not user:
        return JSONResponse({'authenticated': False, 'user': None, 'api_key': None, 'credits': None})

    credits = {'allocated': 25.0, 'spent': 0.0, 'remaining': 25.0, 'currency': 'USD'}
    try:
        info = await get_litellm_user_info(user.id)
        if info:
            u = info.get('user_info', {})
            alloc = float(u.get('max_budget') or 25.0)
            spent = float(u.get('spend') or 0.0)
            credits = {'allocated': alloc, 'spent': spent, 'remaining': max(0.0, round(alloc - spent, 4)), 'currency': 'USD'}
    except Exception:
        pass

    return JSONResponse({
        'authenticated': True,
        'user': {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role},
        'api_key': api_key,
        'token': jwt,
        'credits': credits,
    })


@router.post('/api/wolinet/auth/login', include_in_schema=False)
async def auth_login(request: Request, form: LoginForm, db: AsyncSession = Depends(get_async_session)):
    user = await Auths.authenticate_user(form.email.strip().lower(), lambda pw: verify_password(form.password, pw), db=db)
    if not user:
        return JSONResponse(status_code=401, content={'error': 'Invalid email or password.'})
    try:
        await ensure_litellm_user_exists(user)
    except Exception:
        pass
    key = await Users.get_user_api_key_by_id(user.id, db=db) or await _generate_gateway_key(user.id, user.email, user.name, db=db)
    token = create_token(data={'id': user.id})
    return _session_response({
        'authenticated': True, 'token': token,
        'user': {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role},
        'api_key': key,
    }, token)


@router.post('/api/wolinet/auth/register', include_in_schema=False)
async def auth_register(request: Request, form: RegisterForm, db: AsyncSession = Depends(get_async_session)):
    name, email, password = form.name.strip(), form.email.strip().lower(), form.password.strip()
    if not all([name, email, password]):
        return JSONResponse(status_code=400, content={'error': 'Name, email, and password are required.'})
    if await Users.get_user_by_email(email, db=db):
        return JSONResponse(status_code=400, content={'error': 'Account already exists. Please sign in.'})
    user = None
    try:
        from open_webui.routers.auths import signup_handler
        user = await signup_handler(request, email=email, password=password, name=name, db=db)
    except Exception:
        hashed = get_password_hash(password)
        user = await Auths.insert_new_auth(email=email, password=hashed, name=name, role='user', db=db)
        if user:
            try:
                await provision_litellm_user(user.id, email, name, role='user')
            except Exception:
                pass
    if not user:
        return JSONResponse(status_code=500, content={'error': 'Account creation failed. Please try again.'})
    key = await _generate_gateway_key(user.id, email, name, db=db)
    token = create_token(data={'id': user.id})
    return _session_response({
        'authenticated': True, 'token': token,
        'user': {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role},
        'api_key': key,
    }, token)


@router.post('/api/wolinet/auth/regenerate-key', include_in_schema=False)
async def auth_regenerate_key(request: Request, db: AsyncSession = Depends(get_async_session)):
    user, _, _ = await _extract_session(request, db=db)
    if not user:
        return JSONResponse(status_code=401, content={'error': 'Authentication required.'})
    key = await _generate_gateway_key(user.id, user.email, user.name, db=db)
    return JSONResponse({'authenticated': True, 'api_key': key})


@router.post('/api/wolinet/auth/logout', include_in_schema=False)
async def auth_logout():
    cookie_domain = os.getenv('WEBUI_AUTH_COOKIE_DOMAIN', '.wolinet.com')
    response = JSONResponse({'authenticated': False})
    response.delete_cookie('token', path='/', domain=cookie_domain)
    response.delete_cookie('token', path='/')
    return response


# ── Key Management Proxy ──────────────────────────────────────────────────────

@router.get('/api/wolinet/keys', include_in_schema=False)
async def list_keys(request: Request, db: AsyncSession = Depends(get_async_session)):
    user, api_key, _ = await _extract_session(request, db=db)
    if not user:
        return JSONResponse(status_code=401, content={'error': 'Authentication required.'})
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
            async with s.get(
                f'{_gateway_base()}/key/list',
                headers={'Authorization': f'Bearer {_master_key()}'},
                params={'user_id': user.id},
            ) as r:
                return JSONResponse(await r.json(), status_code=r.status)
    except Exception as exc:
        return JSONResponse(status_code=502, content={'error': str(exc)})


@router.post('/api/wolinet/keys', include_in_schema=False)
async def create_key(request: Request, db: AsyncSession = Depends(get_async_session)):
    user, _, _ = await _extract_session(request, db=db)
    if not user:
        return JSONResponse(status_code=401, content={'error': 'Authentication required.'})
    body = await request.json()
    body.setdefault('user_id', user.id)
    body.setdefault('user_email', user.email)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
            async with s.post(
                f'{_gateway_base()}/key/generate',
                json=body,
                headers={'Authorization': f'Bearer {_master_key()}', 'Content-Type': 'application/json'},
            ) as r:
                return JSONResponse(await r.json(), status_code=r.status)
    except Exception as exc:
        return JSONResponse(status_code=502, content={'error': str(exc)})


# ── AI Assistant Chat Proxy ───────────────────────────────────────────────────

@router.post('/api/wolinet/chat', include_in_schema=False)
async def assistant_chat(request: Request, db: AsyncSession = Depends(get_async_session)):
    user, _, _ = await _extract_session(request, db=db)
    body = await request.body()
    hdrs = {'Authorization': f'Bearer {_master_key()}', 'Content-Type': 'application/json'}
    if user:
        hdrs.update({
            'x-openwebui-user-id': user.id,
            'x-openwebui-user-email': user.email,
            'x-openwebui-user-name': user.name,
            'x-litellm-user-id': user.id,
        })
    else:
        hdrs['x-litellm-user-id'] = 'docs-assistant'
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
            async with s.post(f'{_gateway_base()}/v1/chat/completions', data=body, headers=hdrs) as r:
                return Response(content=await r.read(), status_code=r.status, media_type=r.content_type)
    except Exception as exc:
        return JSONResponse(status_code=502, content={'error': f'Gateway unreachable: {exc}'})


# ── Scalar JS Bundle Fallback ─────────────────────────────────────────────────

@router.get('/static/scalar.js', include_in_schema=False)
@router.get('/swagger/scalar.js', include_in_schema=False)
async def scalar_bundle():
    for candidate in [
        Path(STATIC_DIR) / 'scalar.js',
        Path(FRONTEND_BUILD_DIR) / 'static' / 'scalar.js',
        Path(__file__).parents[4] / 'gateway' / 'litellm' / 'proxy' / 'swagger' / 'scalar.js',
    ]:
        if candidate.exists():
            return FileResponse(str(candidate), media_type='text/javascript')
    return Response(status_code=404)


# ── Developer Portal HTML ─────────────────────────────────────────────────────

def _build_portal_html(title: str, openapi_url: str, scalar_js_url: str, favicon_url: str, default_model: str) -> str:
    # Uses {{ and }} for literal braces inside f-string
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <link rel="icon" type="image/png" href="{favicon_url}" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg-0:#08080f;--bg-1:#0d0d16;--bg-2:#111120;--bg-3:#171728;
      --border:rgba(124,109,250,.18);--accent:#7c6dfa;--accent-h:#9b8ffb;
      --text-1:#e8e8f2;--text-2:#a8a6c8;--text-3:#6b6990;
      --green:#50fa7b;--red:#ff5555;--yellow:#f1fa8c;--cyan:#8be9fd;
      --font:'Inter',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;
      --sidebar-w:220px;--header-h:48px;
      --scalar-background-1:#08080f;--scalar-background-2:#0d0d16;--scalar-background-3:#111120;
      --scalar-color-accent:#7c6dfa;--scalar-color-1:#e8e8f2;--scalar-color-2:#a8a6c8;
      --scalar-font:'Inter',system-ui,sans-serif;--scalar-font-code:'JetBrains Mono',monospace;
    }}
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
    html,body{{width:100%;height:100%;background:var(--bg-0);font-family:var(--font);color:var(--text-1);overflow-x:hidden;}}

    /* Header */
    #header{{position:fixed;top:0;left:0;right:0;height:var(--header-h);z-index:10000;
      display:flex;align-items:center;justify-content:space-between;padding:0 16px;
      background:rgba(8,8,15,.96);border-bottom:1px solid var(--border);backdrop-filter:blur(16px);gap:12px;}}
    .hdr-brand{{display:flex;align-items:center;gap:9px;text-decoration:none;}}
    .hdr-brand img{{height:26px;width:auto;}}
    .hdr-brand-name{{font-size:14px;font-weight:700;color:#fff;
      background:linear-gradient(135deg,#c4b5fd,#7c6dfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
    .hdr-brand-sub{{font-size:11px;color:var(--text-3);font-weight:500;margin-left:2px;}}
    .hdr-right{{display:flex;align-items:center;gap:8px;}}
    .status-dot{{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);}}
    .status-label{{font-size:11px;color:var(--green);font-weight:600;}}
    .badge{{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:9999px;font-size:11px;font-weight:500;}}
    .badge-guest{{background:rgba(241,250,140,.1);border:1px solid rgba(241,250,140,.25);color:var(--yellow);}}
    .badge-user{{background:rgba(80,250,123,.1);border:1px solid rgba(80,250,123,.25);color:var(--green);}}
    .btn{{display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border-radius:6px;font-size:12px;font-weight:600;
      cursor:pointer;transition:all .18s ease;text-decoration:none;border:1px solid transparent;font-family:var(--font);}}
    .btn-primary{{background:var(--accent);border-color:var(--accent);color:#fff;}}
    .btn-primary:hover{{background:var(--accent-h);box-shadow:0 0 12px rgba(124,109,250,.4);}}
    .btn-outline{{background:rgba(124,109,250,.1);border-color:rgba(124,109,250,.3);color:#c4b5fd;}}
    .btn-outline:hover{{background:rgba(124,109,250,.2);color:#fff;border-color:var(--accent);}}
    .btn-ghost{{background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.1);color:var(--text-2);}}
    .btn-ghost:hover{{background:rgba(255,255,255,.12);color:#fff;}}
    .btn-sm{{padding:4px 9px;font-size:11px;}}

    /* Layout */
    #shell{{display:flex;margin-top:var(--header-h);height:calc(100vh - var(--header-h));}}
    #sidebar{{width:var(--sidebar-w);min-width:var(--sidebar-w);background:var(--bg-1);
      border-right:1px solid var(--border);display:flex;flex-direction:column;overflow-y:auto;flex-shrink:0;}}
    .nav-section{{padding:14px 12px 6px;}}
    .nav-section-label{{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
      color:var(--text-3);padding:0 4px;margin-bottom:4px;}}
    .nav-item{{display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:6px;cursor:pointer;
      font-size:12.5px;font-weight:500;color:var(--text-2);transition:all .15s;margin-bottom:2px;
      border:none;background:none;width:100%;text-align:left;font-family:var(--font);}}
    .nav-item:hover{{background:rgba(124,109,250,.1);color:var(--text-1);}}
    .nav-item.active{{background:rgba(124,109,250,.18);color:#fff;font-weight:600;}}
    .nav-icon{{width:15px;height:15px;opacity:.65;flex-shrink:0;}}
    .nav-item.active .nav-icon{{opacity:1;}}
    .sidebar-footer{{margin-top:auto;padding:12px;border-top:1px solid var(--border);font-size:11px;color:var(--text-3);}}
    #main{{flex:1;overflow-y:auto;overflow-x:hidden;}}
    .panel{{display:none;padding:24px;flex-direction:column;gap:18px;min-height:100%;}}
    .panel.active{{display:flex;}}
    .panel-title{{font-size:18px;font-weight:700;color:#fff;margin-bottom:2px;}}
    .panel-sub{{font-size:13px;color:var(--text-2);}}
    .card{{background:var(--bg-2);border:1px solid var(--border);border-radius:12px;padding:18px 20px;}}
    .card-title{{font-size:13px;font-weight:600;color:#fff;margin-bottom:10px;display:flex;align-items:center;gap:7px;}}
    .g2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;}}
    .g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}}
    @media(max-width:900px){{.g2,.g3{{grid-template-columns:1fr;}}}}
    .stat-card{{background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:16px;}}
    .stat-label{{font-size:11px;color:var(--text-3);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;}}
    .stat-value{{font-size:22px;font-weight:700;color:#fff;}}
    .stat-sub{{font-size:11px;color:var(--text-2);margin-top:3px;}}
    .key-bar{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}}
    .key-code{{flex:1;font-family:var(--mono);font-size:12px;color:var(--cyan);
      background:var(--bg-0);border:1px solid rgba(255,255,255,.1);padding:8px 12px;border-radius:6px;
      letter-spacing:.03em;min-width:0;word-break:break-all;}}
    .form-group{{margin-bottom:14px;}}
    .form-label{{display:block;font-size:11px;font-weight:600;color:#c4b5fd;margin-bottom:6px;letter-spacing:.02em;}}
    .form-input{{width:100%;padding:9px 12px;background:var(--bg-0);border:1px solid rgba(255,255,255,.12);
      border-radius:7px;color:#fff;font-size:12px;outline:none;transition:border-color .15s;font-family:var(--font);}}
    .form-input:focus{{border-color:var(--accent);box-shadow:0 0 0 3px rgba(124,109,250,.18);}}
    .form-input::placeholder{{color:var(--text-3);}}
    .btn-full{{width:100%;justify-content:center;padding:10px;}}
    .alert{{padding:10px 14px;border-radius:7px;font-size:12px;margin-bottom:12px;display:none;}}
    .alert.error{{display:block;background:rgba(255,85,85,.1);border:1px solid rgba(255,85,85,.3);color:#ff8585;}}
    .alert.success{{display:block;background:rgba(80,250,123,.1);border:1px solid rgba(80,250,123,.3);color:var(--green);}}
    .key-table{{width:100%;border-collapse:collapse;font-size:12px;}}
    .key-table th{{color:var(--text-3);font-weight:600;text-align:left;padding:8px 10px;border-bottom:1px solid var(--border);font-size:11px;text-transform:uppercase;letter-spacing:.05em;}}
    .key-table td{{padding:10px;border-bottom:1px solid rgba(255,255,255,.05);color:var(--text-2);vertical-align:middle;}}
    .key-table tr:last-child td{{border:none;}}
    .key-table td:first-child{{font-family:var(--mono);color:var(--cyan);font-size:11px;}}
    .tag{{display:inline-flex;align-items:center;padding:2px 7px;border-radius:9999px;font-size:10px;font-weight:600;}}
    .tag-green{{background:rgba(80,250,123,.12);border:1px solid rgba(80,250,123,.25);color:var(--green);}}
    .model-item{{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-radius:8px;
      background:var(--bg-3);border:1px solid var(--border);margin-bottom:8px;}}
    .model-name{{font-family:var(--mono);font-size:12px;color:var(--cyan);}}
    .model-meta{{font-size:11px;color:var(--text-3);}}

    /* Scalar panel */
    #panel-reference{{padding:0;flex:1;overflow:hidden;}}
    #panel-reference.active{{display:flex;flex-direction:column;height:100%;}}
    #scalar-mount{{flex:1;overflow:auto;}}

    /* AI Assistant Drawer */
    #asst-drawer{{position:fixed;right:0;top:var(--header-h);width:420px;max-width:95vw;
      height:calc(100vh - var(--header-h));background:var(--bg-1);
      border-left:1px solid rgba(124,109,250,.3);box-shadow:-12px 0 40px rgba(0,0,0,.7);
      z-index:99999;display:flex;flex-direction:column;
      transform:translateX(105%);transition:transform .26s cubic-bezier(.16,1,.3,1);}}
    #asst-drawer.open{{transform:translateX(0);}}
    .asst-hdr{{padding:12px 16px;background:var(--bg-2);border-bottom:1px solid var(--border);
      display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}}
    .asst-title{{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:700;color:#fff;}}
    .asst-title img{{height:20px;width:auto;}}
    .asst-subtitle{{font-size:10px;color:var(--green);display:flex;align-items:center;gap:4px;margin-top:2px;}}
    .asst-cls{{width:28px;height:28px;border-radius:6px;border:1px solid rgba(255,255,255,.12);
      background:rgba(255,255,255,.06);color:var(--text-2);cursor:pointer;font-size:14px;
      display:flex;align-items:center;justify-content:center;transition:all .15s;}}
    .asst-cls:hover{{background:rgba(255,255,255,.15);color:#fff;}}
    .asst-chips{{display:flex;gap:5px;padding:8px 14px;overflow-x:auto;
      border-bottom:1px solid rgba(255,255,255,.05);background:var(--bg-2);flex-shrink:0;}}
    .asst-chip{{padding:4px 10px;font-size:11px;white-space:nowrap;border-radius:9999px;
      border:1px solid rgba(124,109,250,.22);background:rgba(124,109,250,.07);color:#c4b5fd;
      cursor:pointer;transition:all .15s;font-family:var(--font);}}
    .asst-chip:hover{{background:rgba(124,109,250,.18);border-color:var(--accent);color:#fff;}}
    .asst-msgs{{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;}}
    .asst-msg{{max-width:92%;padding:11px 13px;border-radius:10px;font-size:12px;line-height:1.55;word-break:break-word;}}
    .asst-msg.assistant{{align-self:flex-start;background:var(--bg-3);border:1px solid rgba(124,109,250,.18);color:var(--text-1);}}
    .asst-msg.user{{align-self:flex-end;background:var(--accent);color:#fff;}}
    .asst-msg pre{{background:var(--bg-0);border:1px solid rgba(255,255,255,.08);padding:8px 10px;border-radius:6px;
      font-family:var(--mono);font-size:11px;overflow-x:auto;margin:7px 0;color:var(--cyan);}}
    .asst-msg code{{font-family:var(--mono);background:rgba(255,255,255,.07);padding:1px 5px;border-radius:3px;font-size:11px;}}
    .asst-msg-hdr{{font-weight:700;color:#c4b5fd;margin-bottom:5px;display:flex;align-items:center;gap:6px;}}
    .asst-msg-hdr img{{height:15px;width:auto;}}
    .ep-btn{{display:inline-flex;align-items:center;gap:5px;margin:5px 3px 0 0;padding:4px 10px;border-radius:5px;
      background:rgba(80,250,123,.12);border:1px solid rgba(80,250,123,.3);color:var(--green);
      font-size:11px;font-weight:600;cursor:pointer;text-decoration:none;transition:all .15s;}}
    .ep-btn:hover{{background:rgba(80,250,123,.22);}}
    .asst-inp-row{{padding:10px 14px;background:var(--bg-2);border-top:1px solid var(--border);display:flex;gap:7px;flex-shrink:0;}}
    .asst-inp{{flex:1;padding:9px 11px;background:var(--bg-0);border:1px solid rgba(255,255,255,.1);
      border-radius:7px;color:#fff;font-size:12px;outline:none;transition:border-color .15s;font-family:var(--font);}}
    .asst-inp:focus{{border-color:var(--accent);}}
    .asst-send{{padding:9px 14px;background:var(--accent);border:none;border-radius:7px;color:#fff;
      font-size:12px;font-weight:600;cursor:pointer;transition:background .15s;font-family:var(--font);}}
    .asst-send:hover{{background:var(--accent-h);}}
    .asst-send:disabled{{opacity:.5;cursor:not-allowed;}}

    /* Auth Modal */
    #auth-modal{{position:fixed;inset:0;z-index:1000000;background:rgba(5,5,10,.85);
      backdrop-filter:blur(14px);display:flex;align-items:center;justify-content:center;
      opacity:0;pointer-events:none;transition:opacity .2s ease;padding:16px;}}
    #auth-modal.open{{opacity:1;pointer-events:auto;}}
    .modal-box{{width:420px;max-width:100%;background:var(--bg-2);border:1px solid rgba(124,109,250,.3);
      border-radius:14px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.8),0 0 30px rgba(124,109,250,.12);
      animation:mpop .2s cubic-bezier(.16,1,.3,1);}}
    @keyframes mpop{{from{{transform:scale(.95);opacity:0;}}to{{transform:scale(1);opacity:1;}}}}
    .modal-hd{{padding:16px 20px 12px;background:var(--bg-3);border-bottom:1px solid rgba(255,255,255,.07);
      display:flex;align-items:flex-start;justify-content:space-between;}}
    .modal-hd h3{{font-size:14px;font-weight:700;color:#fff;display:flex;align-items:center;gap:7px;margin:0;}}
    .modal-hd h3 img{{height:18px;width:auto;}}
    .modal-hd p{{margin:4px 0 0;font-size:11px;color:var(--text-2);}}
    .modal-tabs{{display:flex;background:var(--bg-0);border-bottom:1px solid rgba(255,255,255,.07);padding:4px 16px;gap:6px;}}
    .modal-tab{{padding:7px 12px;font-size:12px;font-weight:600;color:var(--text-2);background:transparent;
      border:none;border-bottom:2px solid transparent;cursor:pointer;transition:all .15s;font-family:var(--font);}}
    .modal-tab.active{{color:#fff;border-bottom-color:var(--accent);}}
    .modal-body{{padding:18px 20px;}}
    .credit-note{{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--green);
      background:rgba(80,250,123,.08);border:1px solid rgba(80,250,123,.2);border-radius:6px;padding:7px 10px;margin-bottom:12px;}}

    /* FAB */
    #asst-fab{{position:fixed;bottom:22px;right:22px;z-index:99998;display:flex;align-items:center;gap:8px;
      background:linear-gradient(135deg,#1a1836,#0f0c22);border:1px solid rgba(124,109,250,.5);
      border-radius:9999px;padding:10px 18px;color:#fff;font-size:13px;font-weight:600;cursor:pointer;
      box-shadow:0 8px 28px rgba(124,109,250,.35);transition:all .22s cubic-bezier(.16,1,.3,1);font-family:var(--font);}}
    #asst-fab:hover{{transform:translateY(-2px);box-shadow:0 12px 36px rgba(124,109,250,.5);}}
    #asst-fab img{{height:18px;width:auto;}}
    .fab-pulse{{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 2s infinite;}}
    @keyframes pulse{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.4;transform:scale(1.3);}}}}

    /* Misc */
    a[href*="scalar.com"],.scalar-version-number{{display:none!important;}}
    ::-webkit-scrollbar{{width:5px;height:5px;}}
    ::-webkit-scrollbar-track{{background:transparent;}}
    ::-webkit-scrollbar-thumb{{background:rgba(124,109,250,.25);border-radius:9999px;}}
    .loading{{display:flex;align-items:center;gap:8px;color:var(--text-3);font-size:12px;padding:16px 0;}}
    .spinner{{width:14px;height:14px;border:2px solid rgba(124,109,250,.3);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite;}}
    @keyframes spin{{to{{transform:rotate(360deg);}}}}
    .empty-state{{text-align:center;color:var(--text-3);font-size:13px;padding:40px 20px;}}
    .empty-state p{{margin-top:8px;font-size:12px;}}
  </style>
</head>
<body>

<header id="header">
  <a class="hdr-brand" href="/">
    <img src="{favicon_url}" alt="Wolinet AI" />
    <span>
      <span class="hdr-brand-name">Wolinet AI</span>
      <span class="hdr-brand-sub">Developer Portal</span>
    </span>
  </a>
  <div style="display:flex;align-items:center;gap:6px;">
    <div id="badge-guest" class="badge badge-guest" style="display:none;">Guest Mode</div>
    <div id="badge-user" class="badge badge-user" style="display:none;">
      <span style="width:5px;height:5px;border-radius:50%;background:var(--green);display:inline-block;"></span>
      <span id="hdr-uname">Developer</span>
    </div>
  </div>
  <div class="hdr-right">
    <span class="status-dot"></span>
    <span class="status-label">Gateway Active</span>
    <span id="hdr-guest-btns" style="display:flex;gap:6px;">
      <a href="/auth" class="btn btn-primary btn-sm" id="hdr-btn-signin" style="text-decoration:none;display:inline-flex;align-items:center;">Sign In</a>
      <a href="/auth" class="btn btn-outline btn-sm" id="hdr-btn-signup" style="text-decoration:none;display:inline-flex;align-items:center;">Register</a>
    </span>
    <button id="hdr-signout" class="btn btn-ghost btn-sm" style="display:none;" onclick="doLogout()">Sign Out</button>
    <button class="btn btn-outline btn-sm" onclick="toggleAsst()">
      <img src="{favicon_url}" alt="" style="height:13px;width:auto;" /> AI Assistant
    </button>
  </div>
</header>

<div id="shell">
  <nav id="sidebar">
    <div class="nav-section">
      <div class="nav-section-label">Platform</div>
      <button class="nav-item active" onclick="navTo('overview',this)">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
        Overview
      </button>
      <button class="nav-item" onclick="navTo('keys',this)">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
        API Keys
      </button>
      <button class="nav-item" onclick="navTo('models',this)">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
        Models
      </button>
      <button class="nav-item" onclick="navTo('status',this)">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        Cluster Status
      </button>
    </div>
    <div class="nav-section">
      <div class="nav-section-label">Reference</div>
      <button class="nav-item" onclick="navTo('reference',this)">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        API Reference
      </button>
    </div>
    <div class="nav-section">
      <div class="nav-section-label">Tools</div>
      <button class="nav-item" onclick="toggleAsst()">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        AI Assistant
      </button>
      <a class="nav-item" href="/" target="_blank">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        Studio Dashboard
      </a>
    </div>
    <div class="sidebar-footer">Wolinet AI &bull; Sovereign Platform</div>
  </nav>

  <main id="main">

    <!-- Overview -->
    <section id="panel-overview" class="panel active">
      <div><div class="panel-title">Developer Overview</div><div class="panel-sub">Your sovereign AI platform at a glance</div></div>
      <div id="ov-guest" class="card">
        <div class="card-title">Get Started — Obtain Your Sovereign API Key</div>
        <p style="font-size:13px;color:var(--text-2);margin-bottom:14px;">Sign in or register to receive a personal API key with $25 sovereign inference credits.</p>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-primary" onclick="openAuth('signin')">Sign In</button>
          <button class="btn btn-outline" onclick="openAuth('signup')">Create Account</button>
        </div>
      </div>
      <div id="ov-key" class="card" style="display:none;">
        <div class="card-title">Personal API Key</div>
        <div class="key-bar">
          <code class="key-code" id="ov-key-code">sk-&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;</code>
          <button class="btn btn-ghost btn-sm" onclick="ovToggle()">Show</button>
          <button class="btn btn-ghost btn-sm" onclick="copyKey()">Copy</button>
          <button class="btn btn-outline btn-sm" onclick="rollKey()">Roll Key</button>
        </div>
      </div>
      <div id="ov-credits" class="g3" style="display:none;">
        <div class="stat-card"><div class="stat-label">Allocated</div><div class="stat-value" id="ov-alloc">$25.00</div><div class="stat-sub">USD credits</div></div>
        <div class="stat-card"><div class="stat-label">Spent</div><div class="stat-value" id="ov-spent">$0.00</div><div class="stat-sub">current cycle</div></div>
        <div class="stat-card"><div class="stat-label">Remaining</div><div class="stat-value" id="ov-rem" style="color:var(--green);">$25.00</div><div class="stat-sub">available</div></div>
      </div>
      <div class="card"><div class="card-title">Quickstart &mdash; cURL</div><pre id="ov-curl" style="background:var(--bg-0);border:1px solid rgba(255,255,255,.08);padding:14px;border-radius:8px;font-family:var(--mono);font-size:12px;color:var(--cyan);overflow-x:auto;margin-top:8px;white-space:pre-wrap;"></pre></div>
      <div class="card"><div class="card-title">Quickstart &mdash; Python</div><pre id="ov-python" style="background:var(--bg-0);border:1px solid rgba(255,255,255,.08);padding:14px;border-radius:8px;font-family:var(--mono);font-size:12px;color:var(--cyan);overflow-x:auto;margin-top:8px;white-space:pre-wrap;"></pre></div>
    </section>

    <!-- API Keys -->
    <section id="panel-keys" class="panel">
      <div><div class="panel-title">API Keys</div><div class="panel-sub">Manage your sovereign inference credentials</div></div>
      <div id="keys-noauth" class="card" style="display:none;"><div class="empty-state">Sign in to manage your API keys.<p style="margin-top:10px;"><button class="btn btn-primary" onclick="openAuth('signin')">Sign In</button></p></div></div>
      <div id="keys-content" style="display:none;">
        <div class="card" style="margin-bottom:18px;">
          <div class="card-title">Primary Key</div>
          <div class="key-bar" style="margin-bottom:10px;">
            <code class="key-code" id="keys-code">sk-&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;</code>
            <button class="btn btn-ghost btn-sm" onclick="keysToggle()">Show</button>
            <button class="btn btn-ghost btn-sm" onclick="copyKey()">Copy</button>
            <button class="btn btn-outline btn-sm" onclick="rollKey()">Roll</button>
          </div>
        </div>
        <div class="card" style="margin-bottom:18px;">
          <div class="card-title" style="margin-bottom:14px;">Create Additional Key</div>
          <div id="keys-alert" class="alert"></div>
          <div class="form-group"><label class="form-label">Alias (optional)</label><input type="text" id="nk-alias" class="form-input" placeholder="e.g. production" /></div>
          <div class="g2" style="margin-bottom:14px;">
            <div class="form-group" style="margin:0;"><label class="form-label">Max Budget (USD)</label><input type="number" id="nk-budget" class="form-input" placeholder="10.00" step="0.01" min="0" /></div>
            <div class="form-group" style="margin:0;"><label class="form-label">Expiry (days)</label><input type="number" id="nk-expiry" class="form-input" placeholder="30" min="1" /></div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="createKey()">Create Key</button>
        </div>
        <div class="card"><div class="card-title">Key History</div><div id="keys-list"><div class="loading"><span class="spinner"></span> Loading...</div></div></div>
      </div>
    </section>

    <!-- Models -->
    <section id="panel-models" class="panel">
      <div><div class="panel-title">Available Models</div><div class="panel-sub">Sovereign inference models on your cluster</div></div>
      <div class="card"><div id="models-list"><div class="loading"><span class="spinner"></span> Loading models from gateway...</div></div></div>
    </section>

    <!-- Status -->
    <section id="panel-status" class="panel">
      <div><div class="panel-title">Cluster Status</div><div class="panel-sub">Real-time gateway and inference health</div></div>
      <div id="status-wrap"><div class="loading"><span class="spinner"></span> Fetching cluster telemetry...</div></div>
    </section>

    <!-- API Reference (Scalar) -->
    <section id="panel-reference" class="panel">
      <script id="api-reference"
        data-url="{openapi_url}"
        data-proxy-url=""
        data-configuration='{{"theme":"deepSpace","darkMode":true,"layout":"sidebar","showSidebar":true,"showDeveloperTools":"never","telemetry":false,"agent":{{"disabled":true}}}}'
      ></script>
    </section>

  </main>
</div>

<button id="asst-fab" onclick="toggleAsst()" title="AI Assistant">
  <img src="{favicon_url}" alt="" /> <span>AI Assistant</span>
  <span class="fab-pulse"></span>
</button>

<div id="asst-drawer">
  <div class="asst-hdr">
    <div>
      <div class="asst-title"><img src="{favicon_url}" alt="Wolinet AI" />Wolinet AI Developer Assistant</div>
      <div class="asst-subtitle"><span style="width:5px;height:5px;border-radius:50%;background:var(--green);display:inline-block;"></span> Connected to Sovereign Inference Engine</div>
    </div>
    <div style="display:flex;gap:6px;">
      <button class="asst-cls" onclick="clearAsst()" title="Clear">&#8635;</button>
      <button class="asst-cls" onclick="toggleAsst()" title="Close">&#10005;</button>
    </div>
  </div>
  <div class="asst-chips">
    <button class="asst-chip" onclick="qp('chat')">Chat Completions</button>
    <button class="asst-chip" onclick="qp('python')">Python SDK</button>
    <button class="asst-chip" onclick="qp('auth')">Auth &amp; Keys</button>
    <button class="asst-chip" onclick="qp('guardrails')">Guardrails</button>
    <button class="asst-chip" onclick="qp('status')">Cluster Status</button>
  </div>
  <div id="asst-msgs" class="asst-msgs">
    <div class="asst-msg assistant">
      <div class="asst-msg-hdr"><img src="{favicon_url}" alt="" />Wolinet AI Sovereign Assistant</div>
      <div>I'm your <b>Wolinet AI Developer Assistant</b> &mdash; sovereign OpenAPI intelligence connected directly to your cluster.<br><br>
      <b>How can I help you today?</b>
      <ul style="margin:6px 0 0 16px;padding:0;">
        <li>Find &amp; navigate endpoints, schemas, and authentication flows</li>
        <li>Generate production code in Python, TypeScript, or cURL</li>
        <li>Understand models, quotas, guardrails, and spend metering</li>
      </ul></div>
    </div>
  </div>
  <form class="asst-inp-row" onsubmit="submitAsst(event)">
    <input type="text" id="asst-inp" class="asst-inp" placeholder="Ask about endpoints, code generation, authentication..." autocomplete="off" />
    <button type="submit" id="asst-send" class="asst-send">Send</button>
  </form>
</div>

<div id="auth-modal" onclick="closeAuthBd(event)">
  <div class="modal-box" onclick="event.stopPropagation()">
    <div class="modal-hd">
      <div>
        <h3><img src="{favicon_url}" alt="" />Wolinet Developer Access</h3>
        <p>Sign in or create an account to unlock your API key and inference credits.</p>
      </div>
      <button class="asst-cls" onclick="closeAuth()">&#10005;</button>
    </div>
    <div class="modal-tabs">
      <button id="tab-signin" class="modal-tab active" onclick="switchTab('signin')">Sign In</button>
      <button id="tab-signup" class="modal-tab" onclick="switchTab('signup')">Create Account</button>
      <button id="tab-key"    class="modal-tab" onclick="switchTab('key')">API Key</button>
    </div>
    <div class="modal-body">
      <div id="auth-alert" class="alert"></div>
      <form id="form-signin" onsubmit="doSignIn(event)">
        <div class="form-group"><label class="form-label" for="si-email">Email</label><input type="email" id="si-email" class="form-input" placeholder="developer@example.com" required autocomplete="email" /></div>
        <div class="form-group"><label class="form-label" for="si-pass">Password</label><input type="password" id="si-pass" class="form-input" placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;" required autocomplete="current-password" /></div>
        <button type="submit" id="btn-signin" class="btn btn-primary btn-full">Sign In to Sovereign Portal</button>
      </form>
      <form id="form-signup" style="display:none;" onsubmit="doSignUp(event)">
        <div class="credit-note">+ Personal API key with $25 sovereign inference credits</div>
        <div class="form-group"><label class="form-label" for="su-name">Full Name</label><input type="text" id="su-name" class="form-input" placeholder="Alex Morgan" required autocomplete="name" /></div>
        <div class="form-group"><label class="form-label" for="su-email">Email</label><input type="email" id="su-email" class="form-input" placeholder="alex@example.com" required autocomplete="email" /></div>
        <div class="form-group"><label class="form-label" for="su-pass">Password</label><input type="password" id="su-pass" class="form-input" placeholder="min 8 characters" required autocomplete="new-password" /></div>
        <button type="submit" id="btn-signup" class="btn btn-primary btn-full">Create Account &amp; Get API Key</button>
      </form>
      <form id="form-key" style="display:none;" onsubmit="doKeyAuth(event)">
        <div class="form-group"><label class="form-label" for="key-inp">Existing API Key</label><input type="password" id="key-inp" class="form-input" placeholder="sk-..." required autocomplete="off" /></div>
        <button type="submit" id="btn-key" class="btn btn-primary btn-full">Authorize with Key</button>
      </form>
    </div>
  </div>
</div>

<script>
(function(){{
  var S={{authed:false,user:null,key:null,masked:true,hist:[],model:{json.dumps(default_model)}}};

  window.navTo=function(id,el){{
    document.querySelectorAll('.panel').forEach(function(p){{p.classList.remove('active');}});
    document.querySelectorAll('.nav-item').forEach(function(n){{n.classList.remove('active');}});
    var p=document.getElementById('panel-'+id);
    if(p) p.classList.add('active');
    if(el) el.classList.add('active');
    if(id==='models') loadModels();
    if(id==='status') loadStatus();
    if(id==='keys')   loadKeys();
    if(id==='reference') mountScalar();
  }};

  async function initSession(){{
    try{{
      var token=localStorage.getItem('token');
      var storedKey=localStorage.getItem('wlkey')||localStorage.getItem('wolinet_api_key');
      var h={{}};
      if(token) h['Authorization']='Bearer '+token;
      else if(storedKey) h['Authorization']='Bearer '+storedKey;
      var r=await fetch('/api/wolinet/auth/session',{{credentials:'include',headers:h}});
      if(r.ok){{
        var d=await r.json();
        if(d.authenticated&&d.user){{applyAuth(d.user,d.api_key,d.token||token,d.credits);return;}}
      }}
    }}catch(e){{}}
    applyGuest();
  }}

  function applyAuth(user,key,token,credits){{
    S.authed=true;S.user=user;S.key=key;S.token=token;
    if(token) localStorage.setItem('token',token);
    if(key)   {{localStorage.setItem('wlkey',key);localStorage.setItem('wolinet_api_key',key);}}
    document.getElementById('badge-guest').style.display='none';
    document.getElementById('badge-user').style.display='inline-flex';
    document.getElementById('hdr-uname').textContent=user.name||user.email||'Developer';
    document.getElementById('hdr-guest-btns').style.display='none';
    document.getElementById('hdr-signout').style.display='inline-flex';
    document.getElementById('ov-guest').style.display='none';
    document.getElementById('ov-key').style.display='block';
    document.getElementById('ov-credits').style.display='grid';
    document.getElementById('keys-noauth').style.display='none';
    document.getElementById('keys-content').style.display='block';
    updateKeyEls();
    if(credits) updateCredits(credits);
    renderQS();
    updateScalar(key);
  }}

  function applyGuest(){{
    S.authed=false;S.user=null;S.key=null;
    document.getElementById('badge-guest').style.display='inline-flex';
    document.getElementById('badge-user').style.display='none';
    document.getElementById('hdr-guest-btns').style.display='flex';
    document.getElementById('hdr-signout').style.display='none';
    document.getElementById('ov-guest').style.display='block';
    document.getElementById('ov-key').style.display='none';
    document.getElementById('ov-credits').style.display='none';
    document.getElementById('keys-noauth').style.display='block';
    document.getElementById('keys-content').style.display='none';
    renderQS();
    updateScalar('');
  }}

  function updateCredits(c){{
    document.getElementById('ov-alloc').textContent='$'+parseFloat(c.allocated||25).toFixed(2);
    document.getElementById('ov-spent').textContent='$'+parseFloat(c.spent||0).toFixed(2);
    document.getElementById('ov-rem').textContent='$'+parseFloat(c.remaining||25).toFixed(2);
  }}

  function updateKeyEls(){{
    var k=S.key||'';
    var masked=k.length>10?k.slice(0,5)+'\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022'+k.slice(-4):'sk-\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022';
    var val=S.masked?masked:(k||'Not available');
    ['ov-key-code','keys-code'].forEach(function(id){{var el=document.getElementById(id);if(el)el.textContent=val;}});
  }}

  window.ovToggle=function(){{S.masked=!S.masked;updateKeyEls();}};
  window.keysToggle=function(){{S.masked=!S.masked;updateKeyEls();}};

  window.copyKey=async function(){{
    if(!S.key)return;
    try{{await navigator.clipboard.writeText(S.key);}}catch(e){{return;}}
    ['ov-key-code','keys-code'].forEach(function(id){{
      var el=document.getElementById(id);if(!el)return;
      var orig=el.textContent;el.textContent='Copied!';el.style.color='var(--green)';
      setTimeout(function(){{el.textContent=orig;el.style.color='';}},1500);
    }});
  }};

  window.rollKey=async function(){{
    if(S.key && !confirm('Regenerate your API key? Existing clients using the old key will need updating.')) return;
    try{{
      var authH=S.token?('Bearer '+S.token):(S.key?('Bearer '+S.key):(localStorage.getItem('token')?('Bearer '+localStorage.getItem('token')):''));
      var r=await fetch('/api/wolinet/auth/regenerate-key',{{method:'POST',credentials:'include',headers:authH?{{'Authorization':authH}}:{{}}}});
      if(r.ok){{
        var d=await r.json();
        S.key=d.api_key;
        localStorage.setItem('wlkey',S.key);
        localStorage.setItem('wolinet_api_key',S.key);
        updateKeyEls();renderQS();updateScalar(S.key);
        alert('Key generated/regenerated successfully.');
        loadKeys();
      }}
    }}catch(e){{alert('Error: '+e.message);}}
  }};

  function renderQS(){{
    var o=window.location.origin,k=S.key||'YOUR_API_KEY',m=S.model;
    var body=JSON.stringify({{model:m,stream:true,messages:[{{role:'user',content:'Hello Wolinet AI'}}]}});
    document.getElementById('ov-curl').textContent='curl '+o+'/v1/chat/completions -H "Authorization: Bearer '+k+'" -H "Content-Type: application/json" -d '+JSON.stringify(body);
    document.getElementById('ov-python').textContent=[
      'import openai',
      'client = openai.OpenAI(',
      '    api_key="'+k+'",',
      '    base_url="'+o+'/v1"',
      ')',
      'resp = client.chat.completions.create(',
      '    model="'+m+'",',
      '    messages=[{{"role":"user","content":"Hello Wolinet AI"}}]',
      ')',
      'print(resp.choices[0].message.content)'
    ].join(String.fromCharCode(10));
  }}

  var scalarMounted=false;
  function mountScalar(){{
    if(scalarMounted)return;scalarMounted=true;
    var s=document.createElement('script');s.src='{scalar_js_url}';document.body.appendChild(s);
  }}

  function updateScalar(token){{
    var el=document.getElementById('api-reference');if(!el)return;
    el.dataset.configuration=JSON.stringify({{
      theme:'deepSpace',darkMode:true,layout:'sidebar',showSidebar:true,
      showDeveloperTools:'never',telemetry:false,agent:{{disabled:true}},
      defaultHttpClient:{{targetKey:'python',clientKey:'requests'}},
      servers:[{{url:window.location.origin,description:'Wolinet AI Sovereign Platform'}}],
      authentication:{{preferredSecurityScheme:'bearerAuth',securitySchemes:{{bearerAuth:{{token:token||''}}}}}},
    }});
  }}

  var modelsLoaded=false;
  async function loadModels(){{
    if(modelsLoaded)return;modelsLoaded=true;
    var wrap=document.getElementById('models-list');
    try{{
      var h={{}};if(S.key)h['Authorization']='Bearer '+S.key;
      var r=await fetch('/v1/models',{{credentials:'include',headers:h}});
      if(!r.ok)throw new Error('HTTP '+r.status);
      var d=await r.json();
      var models=d.data||[];
      if(!models.length){{wrap.innerHTML='<div class="empty-state">No models currently loaded on cluster.</div>';return;}}
      wrap.innerHTML=models.map(function(m){{
        return '<div class="model-item"><div><div class="model-name">'+m.id+'</div><div class="model-meta">'+(m.object||'model')+'</div></div><span class="tag tag-green">Active</span></div>';
      }}).join('');
    }}catch(e){{wrap.innerHTML='<div class="empty-state">Could not reach models endpoint.<p>'+e.message+'</p></div>';}}
  }}

  var statusLoaded=false;
  async function loadStatus(){{
    if(statusLoaded)return;statusLoaded=true;
    var wrap=document.getElementById('status-wrap');
    try{{
      var h={{}};if(S.key)h['Authorization']='Bearer '+S.key;
      var r=await fetch('/wolinet/status',{{credentials:'include',headers:h}});
      if(!r.ok)throw new Error('HTTP '+r.status);
      var d=await r.json();
      var html='<div class="g2" style="margin-bottom:16px;">';
      if(d.status)html+='<div class="stat-card"><div class="stat-label">Status</div><div class="stat-value" style="font-size:16px;color:var(--green);">'+d.status+'</div></div>';
      if(d.uptime)html+='<div class="stat-card"><div class="stat-label">Uptime</div><div class="stat-value" style="font-size:16px;">'+d.uptime+'</div></div>';
      if(d.models_loaded!=null)html+='<div class="stat-card"><div class="stat-label">Models Loaded</div><div class="stat-value" style="font-size:16px;">'+d.models_loaded+'</div></div>';
      if(d.total_requests!=null)html+='<div class="stat-card"><div class="stat-label">Total Requests</div><div class="stat-value" style="font-size:16px;">'+d.total_requests+'</div></div>';
      html+='</div><div class="card"><div class="card-title">Raw Response</div><pre style="background:var(--bg-0);padding:12px;border-radius:6px;font-family:var(--mono);font-size:11px;color:var(--cyan);overflow:auto;max-height:400px;">'+JSON.stringify(d,null,2)+'</pre></div>';
      wrap.innerHTML=html;
    }}catch(e){{wrap.innerHTML='<div class="empty-state">Cluster status unavailable.<p>'+e.message+'</p></div>';}}
  }}

  async function loadKeys(){{
    if(!S.authed)return;
    var wrap=document.getElementById('keys-list');
    wrap.innerHTML='<div class="loading"><span class="spinner"></span> Loading...</div>';
    try{{
      var authH=S.token?('Bearer '+S.token):(S.key?('Bearer '+S.key):(localStorage.getItem('token')?('Bearer '+localStorage.getItem('token')):''));
      var r=await fetch('/api/wolinet/keys',{{credentials:'include',headers:authH?{{'Authorization':authH}}:{{}}}});
      if(!r.ok)throw new Error('HTTP '+r.status);
      var d=await r.json();
      var keys=d.keys||d.data||[];
      if(!keys.length){{wrap.innerHTML='<div class="empty-state">No additional keys found.</div>';return;}}
      var rows=keys.map(function(k){{
        var disp=(k.token||k.key||'').slice(0,10)+'...';
        var budget=k.max_budget!=null?'$'+parseFloat(k.max_budget).toFixed(2):'&mdash;';
        var spent=k.spend!=null?'$'+parseFloat(k.spend).toFixed(2):'&mdash;';
        var tag=k.blocked?'<span class="tag" style="background:rgba(241,250,140,.12);border:1px solid rgba(241,250,140,.25);color:var(--yellow);">Blocked</span>':'<span class="tag tag-green">Active</span>';
        return '<tr><td>'+disp+'</td><td>'+(k.key_alias||'&mdash;')+'</td><td>'+budget+'</td><td>'+spent+'</td><td>'+tag+'</td></tr>';
      }}).join('');
      wrap.innerHTML='<table class="key-table"><thead><tr><th>Key</th><th>Alias</th><th>Budget</th><th>Spent</th><th>Status</th></tr></thead><tbody>'+rows+'</tbody></table>';
    }}catch(e){{wrap.innerHTML='<div class="empty-state">Could not load keys.<p>'+e.message+'</p></div>';}}
  }}

  window.createKey=async function(){{
    var alias=document.getElementById('nk-alias').value.trim();
    var budget=parseFloat(document.getElementById('nk-budget').value)||null;
    var expiry=parseInt(document.getElementById('nk-expiry').value)||null;
    var al=document.getElementById('keys-alert');al.className='alert';al.style.display='none';
    try{{
      var body={{}};if(alias)body.key_alias=alias;if(budget)body.max_budget=budget;if(expiry)body.duration=expiry+'d';
      var authH=S.token?('Bearer '+S.token):(S.key?('Bearer '+S.key):(localStorage.getItem('token')?('Bearer '+localStorage.getItem('token')):''));
      var r=await fetch('/api/wolinet/keys',{{method:'POST',credentials:'include',
        headers:{{'Content-Type':'application/json',...(authH?{{'Authorization':authH}}:{{}})}},
        body:JSON.stringify(body)}});
      var d=await r.json();
      if(r.ok&&d.key){{
        al.textContent='Key created: '+d.key;al.className='alert success';al.style.display='block';
        if(!S.key){{S.key=d.key;localStorage.setItem('wlkey',d.key);localStorage.setItem('wolinet_api_key',d.key);updateKeyEls();renderQS();updateScalar(d.key);}}
        loadKeys();
      }}
      else{{al.textContent=d.error||'Failed to create key.';al.className='alert error';al.style.display='block';}}
    }}catch(e){{al.textContent='Error: '+e.message;al.className='alert error';al.style.display='block';}}
  }};

  window.openAuth=function(tab){{document.getElementById('auth-modal').classList.add('open');switchTab(tab||'signin');clearAuthAlert();}};
  window.closeAuth=function(){{document.getElementById('auth-modal').classList.remove('open');}};
  window.closeAuthBd=function(e){{if(e.target&&e.target.id==='auth-modal')closeAuth();}};
  window.switchTab=function(tab){{
    ['signin','signup','key'].forEach(function(t){{
      document.getElementById('tab-'+t).classList.toggle('active',t===tab);
      document.getElementById('form-'+t).style.display=(t===tab?'block':'none');
    }});clearAuthAlert();
  }};
  function showAuthAlert(msg,err){{var el=document.getElementById('auth-alert');el.textContent=msg;el.className='alert '+(err?'error':'success');el.style.display='block';}}
  function clearAuthAlert(){{var el=document.getElementById('auth-alert');el.style.display='none';el.className='alert';}}

  window.doSignIn=async function(e){{
    e.preventDefault();var email=document.getElementById('si-email').value.trim();var pass=document.getElementById('si-pass').value;
    var btn=document.getElementById('btn-signin');btn.disabled=true;clearAuthAlert();
    try{{
      var r=await fetch('/api/wolinet/auth/login',{{method:'POST',credentials:'include',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email,password:pass}})}});
      var d=await r.json();
      if(r.ok&&d.authenticated){{showAuthAlert('Signed in!',false);setTimeout(function(){{applyAuth(d.user,d.api_key,d.token,null);closeAuth();loadKeys();}},300);}}
      else{{showAuthAlert(d.error||'Authentication failed.',true);}}
    }}catch(ex){{showAuthAlert('Network error: '+ex.message,true);}}
    finally{{btn.disabled=false;}}
  }};

  window.doSignUp=async function(e){{
    e.preventDefault();var name=document.getElementById('su-name').value.trim();var email=document.getElementById('su-email').value.trim();var pass=document.getElementById('su-pass').value;
    var btn=document.getElementById('btn-signup');btn.disabled=true;clearAuthAlert();
    try{{
      var r=await fetch('/api/wolinet/auth/register',{{method:'POST',credentials:'include',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name,email,password:pass}})}});
      var d=await r.json();
      if(r.ok&&d.authenticated){{showAuthAlert('Account created!',false);setTimeout(function(){{applyAuth(d.user,d.api_key,d.token,null);closeAuth();}},400);}}
      else{{showAuthAlert(d.error||'Registration failed.',true);}}
    }}catch(ex){{showAuthAlert('Network error: '+ex.message,true);}}
    finally{{btn.disabled=false;}}
  }};

  window.doKeyAuth=async function(e){{
    e.preventDefault();var key=document.getElementById('key-inp').value.trim();var btn=document.getElementById('btn-key');
    if(!key.startsWith('sk-')){{showAuthAlert('Key must start with sk-...',true);return;}}
    btn.disabled=true;clearAuthAlert();
    try{{
      var r=await fetch('/api/wolinet/auth/session',{{headers:{{'Authorization':'Bearer '+key}}}});
      var d=await r.json();
      if(r.ok&&d.authenticated){{localStorage.setItem('wlkey',key);applyAuth(d.user,key,null,d.credits);closeAuth();}}
      else{{showAuthAlert('Key could not be validated on sovereign cluster.',true);}}
    }}catch(ex){{showAuthAlert('Network error: '+ex.message,true);}}
    finally{{btn.disabled=false;}}
  }};

  window.doLogout=async function(){{
    try{{await fetch('/api/wolinet/auth/logout',{{method:'POST',credentials:'include'}});}}catch(e){{}}
    localStorage.removeItem('wlkey');localStorage.removeItem('token');applyGuest();
  }};

  window.toggleAsst=function(){{document.getElementById('asst-drawer').classList.toggle('open');}};
  window.clearAsst=function(){{
    S.hist=[];
    document.getElementById('asst-msgs').innerHTML='<div class="asst-msg assistant"><div class="asst-msg-hdr"><img src="{favicon_url}" alt="" />Wolinet AI Sovereign Assistant</div><div>Conversation cleared. How can I assist you today?</div></div>';
  }};

  function asstMsg(role,html){{
    var c=document.getElementById('asst-msgs');var d=document.createElement('div');d.className='asst-msg '+role;
    if(role==='assistant'){{d.innerHTML='<div class="asst-msg-hdr"><img src="{favicon_url}" alt="" />Wolinet AI Sovereign Assistant</div>'+html;}}
    else{{d.textContent=html;}}
    c.appendChild(d);c.scrollTop=c.scrollHeight;
  }}

  window.qp=function(topic){{
    var o=window.location.origin,k=S.key||'YOUR_API_KEY',m=S.model;
    var chatBody=JSON.stringify(JSON.stringify({{model:m,stream:true,messages:[{{role:'user',content:'Hello'}}]}}));
    var guardrailBody=JSON.stringify(JSON.stringify({{guardrail_name:'default',text:'Validate this'}}));
    var nl=String.fromCharCode(10);
    var prompts={{
      'chat':{{u:'Show me POST /v1/chat/completions',a:'<div><b>POST /v1/chat/completions</b> &mdash; OpenAI-compatible streaming completions.<br><br><b>cURL:</b><pre>curl '+o+'/v1/chat/completions -H "Authorization: Bearer '+k+'" -H "Content-Type: application/json" -d '+chatBody+'</pre></div>'}},
      'python':{{u:'How do I use the Python SDK?',a:'<div><b>Python SDK (OpenAI drop-in):</b><pre>'+['import openai','client = openai.OpenAI(api_key="'+k+'", base_url="'+o+'/v1")','resp = client.chat.completions.create(model="'+m+'", messages=[{{"role":"user","content":"Hello"}}])','print(resp.choices[0].message.content)'].join(nl)+'</pre></div>'}},
      'auth':{{u:'How does API authentication work?',a:S.authed?'<div><b>API Key Auth:</b><br>Send <code>Authorization: Bearer '+k+'</code> on every request. Your key is pre-filled in the API Reference test forms.</div>':'<div><b>API Key Auth:</b><br>All endpoints require <code>Authorization: Bearer &lt;key&gt;</code>.<br><br><button class="btn btn-primary btn-sm" onclick="openAuth(&quot;signin&quot;)" style="margin-top:8px;">Sign In / Register</button></div>'}},
      'guardrails':{{u:'How do I apply guardrails?',a:'<div><b>POST /guardrails/apply_guardrail</b><br>Validates text against sovereign safety policies.<br><br><pre>curl '+o+'/guardrails/apply_guardrail -H "Authorization: Bearer '+k+'" -H "Content-Type: application/json" -d '+guardrailBody+'</pre></div>'}},
      'status':{{u:'What does GET /wolinet/status return?',a:'<div><b>GET /wolinet/status</b><br>Real-time cluster health, models loaded, GPU allocations, and gateway spend.<br><br><pre>curl '+o+'/wolinet/status</pre></div>'}},
    }};
    var p=prompts[topic];if(!p)return;
    asstMsg('user',p.u);asstMsg('assistant',p.a);
  }};

  window.submitAsst=async function(e){{
    e.preventDefault();
    var inp=document.getElementById('asst-inp');var send=document.getElementById('asst-send');
    var q=(inp.value||'').trim();if(!q)return;
    inp.value='';asstMsg('user',q);send.disabled=true;

    var tid='tk-'+Date.now();var c=document.getElementById('asst-msgs');var td=document.createElement('div');
    td.id=tid;td.className='asst-msg assistant';
    td.innerHTML='<div class="asst-msg-hdr"><img src="{favicon_url}" alt="" />Wolinet AI Sovereign Assistant</div><div class="loading"><span class="spinner"></span> Reasoning across sovereign cluster...</div>';
    c.appendChild(td);c.scrollTop=c.scrollHeight;

    var o=window.location.origin;
    var sys=['You are Wolinet AI Sovereign Assistant \u2014 expert developer guide for the Wolinet AI platform.','Base URL: '+o,'User: '+(S.authed?(S.user&&S.user.name||'Developer')+' ('+((S.user&&S.user.email)||'')+')':'Guest'),'Default model: '+S.model,'Key endpoints: POST /v1/chat/completions, POST /v1/embeddings, POST /guardrails/apply_guardrail, GET /v1/models, GET /wolinet/status','Be concise, authoritative, and provide production-ready code examples. Use fenced code blocks.'].join(String.fromCharCode(10));

    S.hist.push({{role:'user',content:q}});
    if(S.hist.length>8)S.hist=S.hist.slice(-8);

    try{{
      var r=await fetch('/api/wolinet/chat',{{
        method:'POST',credentials:'include',
        headers:{{'Content-Type':'application/json','Authorization':S.key?'Bearer '+S.key:''}},
        body:JSON.stringify({{model:S.model,messages:[{{role:'system',content:sys}}].concat(S.hist),max_tokens:700,temperature:0.2}}),
      }});
      var tk=document.getElementById(tid);if(tk)tk.remove();
      if(r.ok){{
        var d=await r.json();
        var reply=(d.choices&&d.choices[0]&&d.choices[0].message&&d.choices[0].message.content)||'No response from gateway.';
        S.hist.push({{role:'assistant',content:reply}});
        var fmt=reply
          .replace(/```([a-z0-9_-]*)\\n([\\s\\S]*?)```/g,'<pre><code>$2</code></pre>')
          .replace(/`([^`]+)`/g,'<code>$1</code>')
          .replace(/\\*\\*([^*]+)\\*\\*/g,'<b>$1</b>')
          .replace(/\\n\\n/g,'<br><br>').replace(/\\n/g,'<br>');
        var eps=reply.match(/(POST|GET|DELETE|PUT)\\s+(\\/[a-zA-Z0-9_\\-\\.\\/:]+)/g);
        var btns='';
        if(eps){{var uniq=[...new Set(eps)].slice(0,3);btns='<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:5px;">'+uniq.map(function(ep){{var pts=ep.split(/\\s+/);return '<a class="ep-btn" data-method="'+pts[0]+'" data-path="'+pts[1]+'">'+ep+' &rarr;</a>';}}).join('')+'</div>';}}
        asstMsg('assistant','<div>'+fmt+btns+'</div>');
      }}else{{
        var err=await r.json().catch(function(){{return {{}};}});
        asstMsg('assistant','<div style="color:var(--red);">Gateway error: '+(err.error&&(err.error.message||err.error)||'HTTP '+r.status)+'</div>');
      }}
    }}catch(ex){{
      var tk2=document.getElementById(tid);if(tk2)tk2.remove();
      asstMsg('assistant','<div style="color:var(--red);">Connection error: '+ex.message+'</div>');
    }}
    send.disabled=false;
  }};

  document.addEventListener('click',function(e){{
    var endpoint=e.target.closest('a.ep-btn');
    if(endpoint){{e.preventDefault();navTo('reference');window.location.hash='#'+endpoint.dataset.method+endpoint.dataset.path;return;}}
    var t=e.target.closest('button,[role="button"]');if(!t)return;
    var txt=(t.textContent||'').toLowerCase();
    if((txt.includes('send request')||txt.includes('test request'))&&!S.authed){{e.preventDefault();e.stopPropagation();openAuth('signin');}}
  }},true);

  initSession();
  renderQS();
}})();
</script>
</body>
</html>"""


# ── Route Definitions ─────────────────────────────────────────────────────────

@router.get('/docs', include_in_schema=False)
@router.get('/scalar', include_in_schema=False)
async def sovereign_docs(request: Request):
    """Serve the Wolinet AI Sovereign Developer Portal."""
    return HTMLResponse(
        content=_build_portal_html(
            title='Wolinet AI — Sovereign Intelligence & Inference API',
            openapi_url='/gateway/openapi.json',
            scalar_js_url='/static/scalar.js',
            favicon_url='/static/favicon.png',
            default_model=await _default_model(),
        ),
        headers={'Cache-Control': 'no-cache'},
    )


# Exported alias for main.py integration
build_sovereign_docs_html = _build_portal_html
