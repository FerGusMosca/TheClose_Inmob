import requests
from urllib.parse import urlencode
from common.config.settings import settings

class TwilioAdapter:
    """
    Sends outbound WhatsApp messages through Twilio API.
    """
    base_url = "https://api.twilio.com/2010-04-01/Accounts"

    @classmethod
    def send_message(cls, to: str, body: str):
        account_sid = settings.twilio_account_sid
        auth_token  = settings.twilio_auth_token
        from_number = settings.twilio_whatsapp_from  # e.g. 'whatsapp:+14155238886'

        url = f"{cls.base_url}/{account_sid}/Messages.json"
        payload = {
            "To":   to,
            "From": from_number,
            "Body": body,
        }

        response = requests.post(
            url,
            data=urlencode(payload),
            auth=(account_sid, auth_token),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        response.raise_for_status()
        return response.json()
