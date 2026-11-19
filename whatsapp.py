"""
WhatsApp Cloud API integration with demo mode fallback.
"""
import logging
from datetime import date
from typing import Optional
import httpx
from models import Customer, NotificationLog, AppSettings

logger = logging.getLogger(__name__)


class WhatsAppClient:
    BASE_URL = "https://graph.facebook.com"

    def __init__(self, settings: dict):
        self.access_token = settings.get("access_token", "")
        self.phone_number_id = settings.get("phone_number_id", "")
        self.api_version = settings.get("api_version", "v21.0")
        self.demo_mode = settings.get("demo_mode", True)
        self.customer_template = settings.get("customer_template_name", "license_expiry_reminder")
        self.client_template = settings.get("client_template_name", "license_expiry_client_notification")
        self.language_code = settings.get("template_language_code", "hi")
        self.client_number = settings.get("client_whatsapp_number", "")

    def _is_configured(self) -> bool:
        return bool(self.access_token and self.phone_number_id and not self.demo_mode)

    def _format_number(self, mobile: str) -> str:
        """Normalize mobile number to E.164 without +."""
        mobile = str(mobile).strip().replace(" ", "").replace("-", "").replace("+", "")
        if mobile.startswith("0"):
            mobile = "91" + mobile[1:]
        if len(mobile) == 10:
            mobile = "91" + mobile
        return mobile

    async def send_customer_reminder(
        self, customer: Customer, app_db_settings: AppSettings
    ) -> dict:
        """Send expiry reminder to the customer."""
        mobile = self._format_number(customer.mobile)
        expiry_str = customer.expiry_date.strftime("%d %B %Y")
        license_display = (customer.license_number or "").strip() or "N/A"

        template_params = [
            {"type": "text", "text": customer.name},
            {"type": "text", "text": license_display},
            {"type": "text", "text": expiry_str},
        ]

        message_preview = (
            f"Namaste {customer.name},\n\n"
            f"Aapka license number {license_display}, "
            f"{expiry_str} ko expire hone wala hai.\n\n"
            f"Kripya samay par apna license renew karwa lein.\n\nDhanyavaad."
        )

        return await self._send_template(
            to=mobile,
            template_name=self.customer_template,
            params=template_params,
            preview=message_preview,
            notification_type="customer",
        )

    async def send_client_notification(
        self, customer: Customer, app_db_settings: AppSettings
    ) -> dict:
        """Send expiry notification to the business client/owner."""
        if not self.client_number:
            return {"success": False, "error": "Client WhatsApp number not configured"}

        client_mobile = self._format_number(self.client_number)
        expiry_str = customer.expiry_date.strftime("%d %B %Y")
        license_display = (customer.license_number or "").strip() or "N/A"

        template_params = [
            {"type": "text", "text": customer.name},
            {"type": "text", "text": customer.mobile},
            {"type": "text", "text": license_display},
            {"type": "text", "text": expiry_str},
        ]

        message_preview = (
            f"License Expiry Reminder!\n\n"
            f"Customer: {customer.name}\n"
            f"Mobile: {customer.mobile}\n"
            f"License Number: {license_display}\n"
            f"Expiry Date: {expiry_str}\n\n"
            f"Customer ko WhatsApp reminder bhejne ki process initiate kar di gayi hai."
        )

        return await self._send_template(
            to=client_mobile,
            template_name=self.client_template,
            params=template_params,
            preview=message_preview,
            notification_type="client",
        )

    async def _send_template(
        self,
        to: str,
        template_name: str,
        params: list,
        preview: str,
        notification_type: str,
    ) -> dict:
        if not self._is_configured():
            # Demo mode: log instead of sending
            logger.info(
                f"[DEMO MODE] Would send '{notification_type}' WhatsApp to {to}:\n{preview}"
            )
            return {
                "success": True,
                "demo": True,
                "message_id": f"demo_{notification_type}_{to}_{date.today()}",
                "preview": preview,
            }

        url = f"{self.BASE_URL}/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": self.language_code},
                "components": [
                    {
                        "type": "body",
                        "parameters": params,
                    }
                ],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                msg_id = data.get("messages", [{}])[0].get("id", "")
                logger.info(f"WhatsApp sent to {to}, msg_id={msg_id}")
                return {"success": True, "demo": False, "message_id": msg_id}
        except httpx.HTTPStatusError as e:
            error_body = e.response.text if e.response else str(e)
            logger.error(f"WhatsApp API error for {to}: {error_body}")
            return {"success": False, "error": error_body}
        except Exception as e:
            logger.error(f"WhatsApp send failed for {to}: {e}")
            return {"success": False, "error": str(e)}
