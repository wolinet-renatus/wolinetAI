"""
Data models for Tanzania Payment Gateway API
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field

PaymentProvider = Literal["selcom", "azampay", "mpesa", "tigopesa", "airtel"]

class TanzaniaCheckoutRequest(BaseModel):
    user_id: Optional[str] = Field(default="wolinet-user", description="ID or email of the Wolinet AI user")
    phone_number: str = Field(..., description="Tanzania phone number in format 2557XXXXXXXX or 07XXXXXXXX")
    amount_tzs: Optional[float] = Field(default=None, description="Amount in Tanzanian Shillings")
    package_id: Optional[str] = Field(default=None, description="Optional package identifier e.g. tz-starter")
    customer_name: Optional[str] = Field(default=None, description="Optional customer display name")
    provider: PaymentProvider = Field(default="selcom", description="Target provider (selcom, azampay, mpesa, etc.)")
    plan_name: Optional[str] = Field(default="credits_topup", description="Selected package or plan")
    metadata: Optional[dict] = Field(default=None, description="Optional caller metadata")

class TanzaniaCheckoutResponse(BaseModel):
    success: bool
    order_id: str
    message: str
    checkout_url: Optional[str] = None
    provider: str
    carrier: Optional[str] = None
    amount_tzs: float
    amount_usd: Optional[float] = None
    ussd_instructions: Optional[str] = None
    status: Literal["pending", "completed", "failed"]

class TanzaniaWebhookPayload(BaseModel):
    order_id: str
    reference: str
    amount_tzs: float
    status: Literal["SUCCESS", "FAILED", "PENDING"]
    phone_number: Optional[str] = None
    trans_id: Optional[str] = None
    signature: Optional[str] = None

class CreditPackage(BaseModel):
    package_id: str
    name: str
    price_tzs: float
    price_usd_equiv: float
    local_tokens: str
    cloud_credit_usd: float
    features: list[str]

class TanzaniaOrderRecord(BaseModel):
    order_id: str
    user_id: str
    customer_name: Optional[str] = None
    phone: str
    carrier: str
    amount_tzs: float
    amount_usd: float
    package_id: Optional[str] = None
    status: str = "pending"
    provider: str = "selcom"
    trans_id: Optional[str] = None
    metadata: Optional[dict[str, object]] = None

