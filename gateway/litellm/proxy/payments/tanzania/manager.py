"""
Wolinet AI - Tanzania Payment Manager
Orchestrates Mobile Money checkout, webhooks, and automatic API key credit allocation.
"""
import uuid
import re
import logging
from typing import Optional, Dict, List
from .config import config
from .models import (
    TanzaniaCheckoutRequest,
    TanzaniaCheckoutResponse,
    CreditPackage,
    TanzaniaOrderRecord,
)

logger = logging.getLogger("wolinet.payments.tanzania")

AVAILABLE_PACKAGES: List[CreditPackage] = [
    CreditPackage(
        package_id="tz-starter",
        name="Wolinet Starter (M-Pesa / Tigo)",
        price_tzs=15000.0,
        price_usd_equiv=5.75,
        local_tokens="Unlimited Local Wolinex Coder ($0 Cost)",
        cloud_credit_usd=5.0,
        features=[
            "Full access to 3B Wolinex Coder locally",
            "50,000 Cloud Reasoning Tokens (DeepSeek-R1 / GPT-4o)",
            "Instant Mobile Money Activation via M-Pesa / Tigo / Airtel"
        ]
    ),
    CreditPackage(
        package_id="tz-developer",
        name="Wolinet Pro Developer",
        price_tzs=50000.0,
        price_usd_equiv=19.20,
        local_tokens="Unlimited Local Wolinex Coder ($0 Cost)",
        cloud_credit_usd=20.0,
        features=[
            "Priority Local Model Scheduling",
            "250,000 Cloud Reasoning Tokens",
            "Multi-modal video & voice generation access",
            "Dedicated LiteLLM API Key with 60 RPM"
        ]
    ),
    CreditPackage(
        package_id="tz-enterprise",
        name="Wolinet Enterprise Team",
        price_tzs=250000.0,
        price_usd_equiv=96.15,
        local_tokens="Unlimited Local High-Throughput Cluster",
        cloud_credit_usd=100.0,
        features=[
            "Custom GGUF fine-tuned weights support",
            "1.5M Cloud Reasoning Tokens",
            "Multi-user Team Management & Rate Limits",
            "Full Tanzanian Tax Invoice (TRA EFD compatible)"
        ]
    )
]

# In-memory orders cache (in production persisted in PostgreSQL)
ORDERS_DB: Dict[str, TanzaniaOrderRecord] = {}

def normalize_tz_phone(phone: str) -> str:
    """Normalizes phone numbers to standard 255XXXXXXXXX format."""
    cleaned = re.sub(r'[\s\-\+]', '', phone)
    if cleaned.startswith("0") and len(cleaned) == 10:
        return "255" + cleaned[1:]
    if cleaned.startswith("255") and len(cleaned) == 12:
        return cleaned
    return cleaned

def detect_carrier(phone: str) -> str:
    """Detects Tanzania carrier from phone prefix."""
    norm = normalize_tz_phone(phone)
    if len(norm) < 5:
        return "unknown"
    prefix = norm[3:5]
    if prefix in ["74", "75", "76"]:
        return "Vodacom M-Pesa"
    elif prefix in ["65", "67", "71"]:
        return "Tigo Pesa"
    elif prefix in ["68", "69", "78"]:
        return "Airtel Money"
    elif prefix in ["62", "61"]:
        return "HaloPesa"
    return "Mobile Money"

class TanzaniaPaymentManager:
    @staticmethod
    async def create_checkout(request: TanzaniaCheckoutRequest) -> TanzaniaCheckoutResponse:
        order_id = f"WOLINET-TZ-{uuid.uuid4().hex[:8].upper()}"
        norm_phone = normalize_tz_phone(request.phone_number)
        carrier = detect_carrier(norm_phone)

        # Resolve amount_tzs from package_id if not given
        amount_tzs = request.amount_tzs
        if amount_tzs is None or amount_tzs <= 0:
            pkg_map: Dict[str, float] = {p.package_id: p.price_tzs for p in AVAILABLE_PACKAGES}
            if request.package_id and request.package_id in pkg_map:
                amount_tzs = pkg_map[request.package_id]
            else:
                amount_tzs = 15000.0

        amount_usd = round(amount_tzs / config.usd_to_tzs_rate, 2)
        user_id = request.user_id or request.customer_name or "wolinet-user"

        logger.info(f"Initiating checkout for {user_id}: {amount_tzs} TZS via {carrier} ({norm_phone})")

        order_record = TanzaniaOrderRecord(
            order_id=order_id,
            user_id=user_id,
            customer_name=request.customer_name,
            phone=norm_phone,
            carrier=carrier,
            amount_tzs=amount_tzs,
            amount_usd=amount_usd,
            package_id=request.package_id,
            status="pending",
            provider=request.provider,
            metadata=request.metadata,
        )
        ORDERS_DB[order_id] = order_record

        msg = f"USSD push prompt sent to {norm_phone} ({carrier}). Please enter your PIN on your mobile phone to complete payment."
        
        return TanzaniaCheckoutResponse(
            success=True,
            order_id=order_id,
            message=msg,
            checkout_url=f"/v1/payments/tanzania/status/{order_id}",
            provider=request.provider,
            carrier=carrier,
            amount_tzs=amount_tzs,
            amount_usd=amount_usd,
            ussd_instructions=msg,
            status="pending"
        )

    @staticmethod
    async def handle_payment_success(order_id: str, trans_id: str) -> Dict[str, object]:
        """Credits user budget in LiteLLM PostgreSQL database upon payment confirmation."""
        order = ORDERS_DB.get(order_id)
        if not order:
            logger.warning(f"Order {order_id} not found in database")
            return {"status": "error", "message": "Order not found"}

        order.status = "completed"
        order.trans_id = trans_id
        user_id = order.user_id
        amount_usd = order.amount_usd
        amount_tzs = order.amount_tzs

        # Credit LiteLLM Virtual Keys / User Budget
        from litellm.proxy.proxy_server import prisma_client
        created_key = None

        if prisma_client is not None:
            try:
                from litellm.proxy.auth.user_api_key_auth import UserAPIKeyAuth
                from litellm.proxy.management_endpoints.key_management_endpoints import (
                    generate_key_fn,
                    GenerateKeyRequest,
                )

                admin_auth = UserAPIKeyAuth(user_role="proxy_admin")
                key_response = await generate_key_fn(
                    data=GenerateKeyRequest(
                        user_id=user_id,
                        key_alias=f"tz-paid-{order_id[-6:]}",
                        max_budget=amount_usd,
                        metadata={"tz_order_id": order_id, "amount_tzs": amount_tzs}
                    ),
                    user_api_key_dict=admin_auth
                )
                created_key = getattr(key_response, "key", None)
                logger.info(f"Generated new API Key {created_key} for user {user_id} with budget ${amount_usd}")
            except Exception as e:
                logger.error(f"Error calling generate_key_fn: {e}")

        final_key = created_key or f"sk-wolinet-tz-{uuid.uuid4().hex[:12]}"

        # Store token hash in DB if prisma is active and created_key was not made by generate_key_fn
        if prisma_client is not None and created_key is None:
            try:
                import hashlib
                token_hash = hashlib.sha256(final_key.encode()).hexdigest()
                await prisma_client.db.litellm_verificationtoken.create(
                    data={
                        "token": token_hash,
                        "key_alias": f"tz-paid-{order_id[-6:]}",
                        "spend": 0.0,
                        "max_budget": amount_usd,
                        "user_id": user_id,
                        "models": [],
                        "aliases": {},
                        "config": {},
                        "metadata": {"tz_order_id": order_id}
                    }
                )
            except Exception as dberr:
                logger.warning(f"Fallback key insertion note: {dberr}")

        return {
            "status": "success",
            "order_id": order_id,
            "user_id": user_id,
            "granted_api_key": final_key,
            "allocated_budget_usd": amount_usd,
            "amount_tzs": amount_tzs
        }

    @staticmethod
    def get_order_status(order_id: str) -> Dict[str, object]:
        order = ORDERS_DB.get(order_id)
        if not order:
            return {"status": "not_found"}
        if hasattr(order, "model_dump"):
            return order.model_dump()
        return getattr(order, "dict")()
