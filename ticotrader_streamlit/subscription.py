"""Validate the BCCR subscription on demand, returning only safe status messages."""

import http.client
import json
from urllib.parse import urlencode


def check_subscription(token, email):
    token = (token or "").strip()
    email = (email or "").strip()
    if not email or not token:
        return False, "Completá el correo registrado y el token del BCCR en Secrets."
    if not token.isascii() or any(char.isspace() or not char.isprintable() for char in token):
        return (
            False,
            "Revisá el formato del token en Secrets. Pegá solo el valor emitido por el BCCR.",
        )

    # The official validation method requires query parameters. Keep the URL
    # out of application logs and never relay response bodies or exceptions.
    path = "/SDDE/api/Bccr.GE.SDDE.Publico.Indicadores.API/Usuario/ValideSuscripcion"
    params = urlencode({"correo": email, "token": token})
    connection = http.client.HTTPSConnection("apim.bccr.fi.cr", timeout=8)
    try:
        connection.request(
            "POST",
            f"{path}?{params}",
            body=b"",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        response = connection.getresponse()
        if response.status in (401, 403):
            return (
                False,
                f"El BCCR rechazó el acceso (HTTP {response.status}). Revisá la suscripción.",
            )
        if response.status != 200:
            return False, f"Validación inconclusa (HTTP {response.status})."
        body = json.loads(response.read(16385))
        if (
            isinstance(body, dict)
            and body.get("estado") is True
            and str(body.get("mensaje", "")).strip().rstrip(".").casefold() == "suscripción válida"
        ):
            return True, "El BCCR confirmó la suscripción para el correo y el token configurados."
        if isinstance(body, dict) and body.get("estado") is False:
            return (
                False,
                "El BCCR no confirmó la suscripción. Revisá la asociación entre el correo y el token.",
            )
        return False, "Validación inconclusa. El BCCR devolvió una respuesta inesperada."
    except (OSError, http.client.HTTPException, ValueError):
        return False, "Validación inconclusa. No se pudo leer una respuesta válida del BCCR."
    finally:
        connection.close()
