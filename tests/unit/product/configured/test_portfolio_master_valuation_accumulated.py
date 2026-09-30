from __future__ import annotations

from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReader,
)


def test_reader_maps_valuacion_acumulada_as_source_field() -> None:
    reader = InstitutionalPortfolioMasterReader()

    position = reader._build_position(
        {
            "isin": "CRTEST",
            "emisor": "Emisor",
            "moneda": "CRC",
            "valuacion acumulada": 123.45,
        },
        row_number=8,
        file_name="Maestro.xlsx",
    )

    assert position is not None
    assert position["valuation_accumulated"] == 123.45
    assert position["source_row"] == 8
    assert position["source_file"] == "Maestro.xlsx"
