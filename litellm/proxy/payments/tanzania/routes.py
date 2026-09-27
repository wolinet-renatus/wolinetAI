"""
FastAPI Router for Tanzania Payment Gateway
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List
from .models import TanzaniaCheckoutRequest, TanzaniaCheckoutResponse, TanzaniaWebhookPayload, CreditPackage
from .manager import TanzaniaPaymentManager, AVAILABLE_PACKAGES

router = APIRouter(prefix="/v1/payments/tanzania", tags=["Tanzania Payments"])

@router.get("/packages", response_model=List[CreditPackage])
async def list_packages():
    """List available credit packages denominated in Tanzanian Shillings (TZS)."""
    return AVAILABLE_PACKAGES

@router.post("/checkout", response_model=TanzaniaCheckoutResponse)
async def checkout(request: TanzaniaCheckoutRequest):
    """
    Initiate a Mobile Money payment via M-Pesa, Tigo Pesa, or Airtel Money.
    Triggers an instant USSD PIN push to the customer's mobile phone.
    """
    try:
        return await TanzaniaPaymentManager.create_checkout(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status/{order_id}")
async def check_status(order_id: str):
    """Check payment status for a given order ID."""
    order = TanzaniaPaymentManager.get_order_status(order_id)
    if order.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.post("/webhook")
async def webhook(payload: TanzaniaWebhookPayload):
    """Webhook listener for Selcom / AzamPay / Telco payment confirmations."""
    if payload.status == "SUCCESS":
        result = await TanzaniaPaymentManager.handle_payment_success(payload.order_id, payload.reference)
        return {"status": "ok", "result": result}
    return {"status": "ignored", "order_status": payload.status}

@router.post("/simulate-success/{order_id}")
async def simulate_success(order_id: str):
    """
    Developer sandbox testing endpoint: Simulates immediate M-Pesa customer PIN confirmation.
    Credits the user's budget and issues an active API key immediately.
    """
    result = await TanzaniaPaymentManager.handle_payment_success(order_id, trans_id=f"MPESA-{order_id[-6:]}")
    return {"message": "Simulated successful mobile money transaction", "data": result, **result}
