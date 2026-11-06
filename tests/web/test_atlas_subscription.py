import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest

from ticotrader_streamlit.subscription import check_subscription


@pytest.mark.parametrize(
    "status,body,valid,detail",
    [
        (200, {"estado": True, "mensaje": "Suscripción válida"}, True, "confirmó la suscripción"),
        (200, {"estado": False}, False, "no confirmó"),
        (200, {}, False, "inconclusa"),
        (200, {"estado": True}, False, "inconclusa"),
        (403, {}, False, "rechazó"),
        (500, {}, False, "inconclusa"),
    ],
)
def test_bccr_validates_only_at_official_host(status, body, valid, detail):
    with patch("ticotrader_streamlit.subscription.http.client.HTTPSConnection") as factory:
        conn = factory.return_value
        resp = conn.getresponse.return_value
        resp.status = status
        resp.read.return_value = json.dumps({"mensaje": "private.example", **body}).encode()
        ok, message = check_subscription("private.example", "me@example.invalid")
        factory.assert_called_once_with("apim.bccr.fi.cr", timeout=8)
        method, path = conn.request.call_args.args
        assert method == "POST"
        assert urlsplit(path).path.endswith("/Usuario/ValideSuscripcion")
        assert parse_qs(urlsplit(path).query)["correo"] == ["me@example.invalid"]
        assert parse_qs(urlsplit(path).query)["token"] == ["private.example"]
        assert conn.request.call_args.kwargs["headers"]["Authorization"] == "Bearer private.example"
        assert ok is valid and detail in message
        assert "private.example" not in message
        conn.close.assert_called_once()
