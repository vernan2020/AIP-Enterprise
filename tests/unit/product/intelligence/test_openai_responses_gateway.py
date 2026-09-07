from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

import pytest

from aip.domain.intelligence.models import (
    FinancialIntelligenceContext,
    FinancialIntelligenceReport,
    IntelligenceEvidence,
    IntelligenceFinding,
    IntelligenceKind,
    IntelligenceSeverity,
)
from aip.product.intelligence.llm_gateway_factory import build_llm_gateway
from aip.product.intelligence.openai_responses_gateway import OpenAIResponsesGateway


def _context() -> FinancialIntelligenceContext:
    return FinancialIntelligenceContext(
        cutoff_date=date(2026, 8, 31),
        execution_mode="CONFIGURED",
        data_quality_status="DEGRADED",
        source_states=("portfolio=HEALTHY", "liquidity=DEGRADED"),
        warnings=("local-sensitive-warning-not-for-llm",),
        market_value_crc=Decimal("306330000000"),
        weighted_yield_percent=Decimal("5.20"),
        modified_duration=Decimal("1.46"),
        hqla_percent=Decimal("67.3"),
        dv01_crc=Decimal("35450000"),
        issuer_hhi=Decimal("3799"),
        government_bccr_share_percent=Decimal("84"),
        duration_under_1_share_percent=Decimal("70.13"),
        duration_1_5_share_percent=Decimal("20"),
        duration_over_5_share_percent=Decimal("9.87"),
        icl_total=Decimal("11.82"),
        hqla_capacity_crc=Decimal("206248280000"),
        hqla_restricted_count=2,
        liquidity_policy_status="Cumple",
        liquidity_stress_result="No configurado",
        opportunities=(),
    )


def _report() -> FinancialIntelligenceReport:
    finding = IntelligenceFinding(
        finding_id="data-quality",
        kind=IntelligenceKind.ALERT,
        severity=IntelligenceSeverity.HIGH,
        domain="Datos",
        title="Calidad de datos no está en estado saludable",
        summary="El estado de calidad reportado es DEGRADED.",
        recommendation="Validar fuentes antes de ejecutar una estrategia.",
        evidence=(
            IntelligenceEvidence(
                metric="Calidad de datos",
                value="DEGRADED",
                source="AIP Runtime",
            ),
        ),
        confidence=Decimal("1"),
    )
    return FinancialIntelligenceReport(
        generated_at=datetime(2026, 8, 31, 12, 0, 0),
        cutoff_date=date(2026, 8, 31),
        mode="DETERMINISTIC",
        coverage=("Portafolio", "Mercado", "Liquidez"),
        executive_summary="AIP identificó señales que requieren atención.",
        findings=(finding,),
        warnings=("warning",),
    )


def test_openai_payload_is_grounded_minimal_and_not_stored() -> None:
    gateway = OpenAIResponsesGateway(api_key="secret-key", model="test-model")

    payload = gateway._build_payload(_context(), _report(), "¿Qué debo priorizar?")
    serialized = json.dumps(payload, ensure_ascii=False)
    input_text = payload["input"][0]["content"][0]["text"]
    evidence_payload = json.loads(input_text)

    assert payload["store"] is False
    assert payload["model"] == "test-model"
    assert evidence_payload["data_quality_status"] == "DEGRADED"
    assert evidence_payload["warning_count"] == 1
    assert evidence_payload["user_question"] == "¿Qué debo priorizar?"
    assert evidence_payload["deterministic_report"]["findings"][0]["severity"] == "HIGH"
    assert "secret-key" not in serialized
    assert "local-sensitive-warning-not-for-llm" not in serialized


def test_openai_answer_extracts_rest_output_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = OpenAIResponsesGateway(api_key="secret-key", model="test-model")
    monkeypatch.setattr(
        gateway,
        "_post_with_retry",
        lambda payload: {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Priorice validar la calidad de datos.",
                        }
                    ],
                }
            ]
        },
    )

    answer = gateway.answer(_context(), _report(), "¿Qué debo priorizar?")

    assert answer == "Priorice validar la calidad de datos."


def test_openai_gateway_rejects_empty_question() -> None:
    gateway = OpenAIResponsesGateway(api_key="secret-key", model="test-model")

    with pytest.raises(ValueError, match="vacía"):
        gateway.answer(_context(), _report(), "   ")


def test_llm_factory_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIP_LLM_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    gateway = build_llm_gateway()

    assert gateway.available is False
    assert gateway.provider_name == "NO CONFIGURADO"


def test_llm_factory_enables_openai_from_local_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIP_LLM_ENABLED", "true")
    monkeypatch.setenv("AIP_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "project-secret")
    monkeypatch.setenv("AIP_LLM_MODEL", "test-model")

    gateway = build_llm_gateway()

    assert gateway.available is True
    assert gateway.provider_name == "OpenAI · test-model"
