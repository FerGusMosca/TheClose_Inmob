class WhatsAppUtils:
    @staticmethod
    def extract_number(wa_str: str) -> str:
        """
        Extracts the numeric part of a WhatsApp string like 'whatsapp:+14155238886'.
        Returns only the digits as a string, or '' if nothing valid is found.
        """
        if not wa_str:
            return ""
        # Keep only digits
        return "".join(ch for ch in wa_str if ch.isdigit())
