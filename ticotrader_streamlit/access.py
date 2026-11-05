"""Authorization of claims already verified by Streamlit's OIDC implementation."""

import math
import time


def authorize(claims, settings, client_id, now=None):
    allowed = {str(x).strip().lower() for x in settings.get("allowed_emails", [])}
    admins = {str(x).strip().lower() for x in settings.get("admin_emails", [])}
    if not allowed or len(allowed) > 20 or not admins or not admins <= allowed:
        raise ValueError("Configure entre 1 y 20 correos y al menos un administrador autorizado.")
    email = str(claims.get("email", "")).strip().lower()
    try:
        expiry = float(claims.get("exp", 0))
    except (ValueError, TypeError):
        expiry = 0
    audience = claims.get("aud", [])
    if isinstance(audience, str):
        audience = [audience]
    if (
        not claims.get("is_logged_in")
        or claims.get("email_verified") is not True
        or claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com")
        or not client_id
        or client_id not in audience
        or not math.isfinite(expiry)
        or expiry <= (time.time() if now is None else now)
        or email not in allowed
    ):
        raise PermissionError("Acceso no autorizado o sesión vencida. Iniciá sesión nuevamente.")
    return email, email in admins
