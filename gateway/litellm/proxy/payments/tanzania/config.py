"""
Wolinet AI - Tanzania Payment Gateway Configuration
Supports Selcom Pay, AzamPay, Vodacom M-Pesa, and Airtel Money.
"""
import os
from dataclasses import dataclass

@dataclass
class TanzaniaPaymentConfig:
    # Default Currency
    currency: str = "TZS"
    
    # Selcom Gateway Credentials
    selcom_vendor_id: str = os.getenv("SELCOM_VENDOR_ID", "")
    selcom_api_key: str = os.getenv("SELCOM_API_KEY", "")
    selcom_api_secret: str = os.getenv("SELCOM_API_SECRET", "")
    selcom_base_url: str = os.getenv("SELCOM_BASE_URL", "https://apigw.selcommobile.com/v1")
    
    # AzamPay Gateway Credentials
    azampay_app_name: str = os.getenv("AZAMPAY_APP_NAME", "Wolinet AI")
    azampay_client_id: str = os.getenv("AZAMPAY_CLIENT_ID", "")
    azampay_client_secret: str = os.getenv("AZAMPAY_CLIENT_SECRET", "")
    azampay_base_url: str = os.getenv("AZAMPAY_BASE_URL", "https://authenticator.azampay.co.tz")
    
    # Webhook secret for signature validation
    webhook_secret: str = os.getenv("TANZANIA_PAYMENT_WEBHOOK_SECRET", "wolinet-secret-tz-2026")
    
    # Exchange rate estimate: 1 USD = 2,600 TZS
    usd_to_tzs_rate: float = float(os.getenv("USD_TO_TZS_RATE", "2600.0"))

config = TanzaniaPaymentConfig()
