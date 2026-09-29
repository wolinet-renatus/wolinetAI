import os
import logging
import aiohttp
from typing import Optional, Dict, Any

log = logging.getLogger(__name__)


def _litellm_base_url() -> str:
    """Resolve gateway base URL at call time so env overrides applied after import are honoured."""
    return (
        os.getenv("LITELLM_BASE_URL")
        or os.getenv("OPENAI_API_BASE_URL", "").replace("/v1", "")
        or "http://127.0.0.1:4000"
    ).rstrip("/")


def _litellm_master_key() -> str:
    """Resolve master key at call time."""
    return os.getenv(
        "LITELLM_MASTER_KEY",
        os.getenv("OPENAI_API_KEY", "sk-wolinet-admin-2026"),
    )


def _default_user_budget() -> float:
    return float(os.getenv("DEFAULT_USER_BUDGET", "25.0"))


DEFAULT_ALLOWED_MODELS = [
    "wolinex-coder",
    "wolinex-coder-pro",
    "wolinex-coder-lite",
    "wolinex-omni",
    "wolinex-embed",
]


async def provision_litellm_user(
    user_id: str,
    email: str,
    name: str,
    role: str = "user",
    max_budget: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Provisions a user into LiteLLM Gateway (/user/new), assigning them an initial budget
    and generating their virtual API key for sovereign usage and spend tracking.
    """
    if max_budget is None:
        max_budget = 10000.0 if role == "admin" else _default_user_budget()

    litellm_role = "proxy_admin" if role == "admin" else "internal_user"
    default_model = os.getenv("DEFAULT_MODELS", "wolinex-coder")

    payload = {
        "user_id": user_id,
        "user_email": email,
        "user_alias": name,
        "user_role": litellm_role,
        "max_budget": max_budget,
        "auto_create_key": True,
        "models": DEFAULT_ALLOWED_MODELS if role != "admin" else [],
        "metadata": {
            "default_model": default_model,
            "credits_allocated": max_budget,
            "tier": "Sovereign Administrator" if role == "admin" else "Sovereign Free Tier",
            "provider": "Wolinet AI",
        },
    }

    base_url = _litellm_base_url()
    master_key = _litellm_master_key()
    headers = {
        "Authorization": f"Bearer {master_key}",
        "Content-Type": "application/json",
    }

    url = f"{base_url}/user/new"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    log.info(
                        f"Successfully provisioned LiteLLM user {user_id} ({email}) with budget ${max_budget}"
                    )
                    return data
                elif resp.status in (400, 409):
                    # User might already exist, fetch their info
                    log.info(
                        f"LiteLLM user {user_id} already exists or returned {resp.status}. Fetching user info..."
                    )
                    return await get_litellm_user_info(user_id)
                else:
                    text = await resp.text()
                    log.warning(
                        f"Failed to provision LiteLLM user {user_id} (HTTP {resp.status}): {text}"
                    )
                    return None
    except Exception as e:
        log.error(f"Error communicating with LiteLLM gateway at {url}: {e}")
        return None


async def get_litellm_user_info(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches user info and spend from LiteLLM Gateway (/user/info).
    """
    base_url = _litellm_base_url()
    url = f"{base_url}/user/info?user_id={user_id}"
    headers = {
        "Authorization": f"Bearer {_litellm_master_key()}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    except Exception as e:
        log.error(f"Error fetching LiteLLM user info for {user_id}: {e}")
        return None


async def ensure_litellm_user_exists(user) -> Optional[Dict[str, Any]]:
    """
    Ensures that a user is registered in LiteLLM, provisioning them if not present.
    """
    try:
        info = await get_litellm_user_info(user.id)
        if not info:
            return await provision_litellm_user(
                user_id=user.id,
                email=user.email,
                name=user.name,
                role=user.role,
            )
        return info
    except Exception as e:
        log.error(f"Error ensuring LiteLLM user exists for {user.id}: {e}")
        return None
