"""Create a private local .env without putting passwords into shell history."""

import hashlib
import secrets
from getpass import getpass
from pathlib import Path


def main():
    target = Path(__file__).parent / ".env"
    if target.exists():
        raise SystemExit(
            "Ya existe ticotrader_web/.env; edítelo sin sobrescribir sus credenciales."
        )
    username = input("Usuario administrador: ").strip()
    if not username or any(x in username for x in "\r\n'\"#= "):
        raise SystemExit("Use un usuario sin espacios ni caracteres especiales.")
    password = getpass("Contraseña (mínimo 14 caracteres): ")
    if len(password) < 14 or password != getpass("Repetir contraseña: "):
        raise SystemExit("Contraseña corta o confirmación distinta.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000).hex()
    value = f"pbkdf2_sha256$600000${salt.hex()}${digest}"
    content = (
        f"TICOTRADER_USERNAME={username}\nTICOTRADER_PASSWORD_HASH='{value}'\n"
        "TICOTRADER_ALLOWED_HOSTS=localhost,127.0.0.1\nTICOTRADER_COOKIE_SECURE=false\n"
        "AIP_EXECUTION_MODE=CONFIGURED\nAIP_DEMO_MODE_ENABLED=false\n"
        "AIP_SUGEF_FINANCIAL_ENABLED=true\nAIP_SUGEF_FINANCIAL_API_ENABLED=true\n"
        "AIP_SUGEF_FINANCIAL_ENTITY_CODES=3004045138\nAIP_BCCR_ENABLED=true\n"
        "AIP_BCCR_TOKEN=\nAIP_BCCR_EMAIL=\nAIP_BCCR_NAME=TicoTrader\n"
    )
    target.write_text(content, encoding="utf-8")
    target.chmod(0o600)
    print(
        "Acceso configurado. Para publicar con HTTPS, active TICOTRADER_COOKIE_SECURE=true y defina el dominio autorizado."
    )


if __name__ == "__main__":
    main()
