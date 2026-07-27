"""Tests for serialization module.

Comprehensive tests for JSON serialization support.
"""

import pytest
import json
from decimal import Decimal
from datetime import date, datetime

from src.aip.shared.serialization import (
    JsonSerializer,
    DecimalEncoder,
    DateEncoder,
)


class TestDecimalEncoder:
    """Tests for DecimalEncoder."""
    
    def test_encode_decimal(self) -> None:
        """Test encoding Decimal."""
        data = {"amount": Decimal("123.45")}
        result = json.dumps(data, cls=DecimalEncoder)
        
        assert "123.45" in result
    
    def test_encode_nested_decimal(self) -> None:
        """Test encoding nested Decimal."""
        data = {
            "portfolio": {
                "value": Decimal("1000.50")
            }
        }
        result = json.dumps(data, cls=DecimalEncoder)
        
        assert "1000.50" in result
    
    def test_encode_list_of_decimals(self) -> None:
        """Test encoding list of Decimals."""
        data = [Decimal("100"), Decimal("200.50")]
        result = json.dumps(data, cls=DecimalEncoder)
        
        assert "100" in result
        assert "200.50" in result

    def test_decimal_encoder_unsupported_type_raises_type_error(self) -> None:
        """Test DecimalEncoder delegates unsupported types to JSON default."""
        class Unsupported:
            pass

        with pytest.raises(TypeError):
            json.dumps({"value": Unsupported()}, cls=DecimalEncoder)


class TestDateEncoder:
    """Tests for DateEncoder."""
    
    def test_encode_date(self) -> None:
        """Test encoding date."""
        data = {"date": date(2024, 7, 27)}
        result = json.dumps(data, cls=DateEncoder)
        
        assert "2024-07-27" in result
    
    def test_encode_datetime(self) -> None:
        """Test encoding datetime."""
        dt = datetime(2024, 7, 27, 10, 30, 45)
        data = {"timestamp": dt}
        result = json.dumps(data, cls=DateEncoder)
        
        assert "2024-07-27" in result

    def test_date_encoder_unsupported_type_raises_type_error(self) -> None:
        """Test DateEncoder delegates unsupported types to JSON default."""
        class Unsupported:
            pass

        with pytest.raises(TypeError):
            json.dumps({"value": Unsupported()}, cls=DateEncoder)


class TestJsonSerializer:
    """Tests for JsonSerializer utility."""
    
    def test_serialize_with_decimal(self) -> None:
        """Test serializing data with Decimal."""
        data = {
            "amount": Decimal("100.50"),
            "quantity": 5,
            "currency": "USD"
        }
        
        result = JsonSerializer.serialize(data)
        
        assert "100.50" in result
        assert "USD" in result
    
    def test_serialize_with_date(self) -> None:
        """Test serializing data with date."""
        data = {
            "date": date(2024, 7, 27),
            "name": "Test"
        }
        
        result = JsonSerializer.serialize(data)
        
        assert "2024-07-27" in result
    
    def test_serialize_with_both_decimal_and_date(self) -> None:
        """Test serializing data with both Decimal and date."""
        data = {
            "amount": Decimal("100.50"),
            "date": date(2024, 7, 27)
        }
        
        result = JsonSerializer.serialize(data)
        
        assert "100.50" in result
        assert "2024-07-27" in result
    
    def test_serialize_compact(self) -> None:
        """Test compact serialization."""
        data = {"amount": Decimal("100.50")}
        
        result = JsonSerializer.serialize_compact(data)
        
        # Compact should have no extra whitespace
        assert "\n" not in result
        assert "100.50" in result
    
    def test_deserialize_simple(self) -> None:
        """Test simple deserialization."""
        json_str = '{"amount": 100, "currency": "USD"}'
        
        result = JsonSerializer.deserialize(json_str)
        
        assert result["amount"] == 100
        assert result["currency"] == "USD"
    
    def test_deserialize_invalid_json_raises_error(self) -> None:
        """Test invalid JSON raises error."""
        with pytest.raises(json.JSONDecodeError):
            JsonSerializer.deserialize("invalid json")
    
    def test_deserialize_decimal_strings(self) -> None:
        """Test deserializing decimal strings to Decimal."""
        json_str = '{"amount": "100.50", "price": "50.25"}'
        
        result = JsonSerializer.deserialize_decimal(json_str)
        
        assert isinstance(result["amount"], Decimal)
        assert result["amount"] == Decimal("100.50")
    
    def test_deserialize_dates(self) -> None:
        """Test deserializing ISO date strings."""
        json_str = '{"date": "2024-07-27", "end_date": "2024-12-31"}'
        
        result = JsonSerializer.deserialize_dates(json_str)
        
        assert isinstance(result["date"], date)
        assert result["date"] == date(2024, 7, 27)
    
    def test_serialize_then_deserialize_roundtrip(self) -> None:
        """Test serialize/deserialize roundtrip."""
        original_data = {
            "amount": Decimal("123.45"),
            "date": date(2024, 7, 27),
            "name": "Test Portfolio"
        }
        
        # Serialize
        json_str = JsonSerializer.serialize(original_data)
        
        # Deserialize
        deserialized = JsonSerializer.deserialize(json_str)
        
        # Check structure is preserved
        assert deserialized["name"] == original_data["name"]
        assert deserialized["amount"] == "123.45"  # Comes back as string
        assert deserialized["date"] == "2024-07-27"  # Comes back as string
    
    def test_complex_nested_structure(self) -> None:
        """Test serializing complex nested structures."""
        data = {
            "portfolio": {
                "positions": [
                    {
                        "ticker": "AAPL",
                        "quantity": Decimal("100"),
                        "value": Decimal("15000.00"),
                        "purchase_date": date(2024, 1, 15)
                    },
                    {
                        "ticker": "MSFT",
                        "quantity": Decimal("50"),
                        "value": Decimal("20000.00"),
                        "purchase_date": date(2024, 2, 20)
                    }
                ],
                "total_value": Decimal("35000.00")
            }
        }
        
        result = JsonSerializer.serialize(data)
        
        # Verify structure is preserved
        assert "AAPL" in result
        assert "15000.00" in result
        assert "2024-01-15" in result

    def test_deserialize_preserves_structure(self) -> None:
        """Test deserialize preserves data structure."""
        json_str = '{"portfolio": {"total": 50000, "currency": "USD"}}'
        
        result = JsonSerializer.deserialize(json_str)
        
        assert result["portfolio"]["total"] == 50000
        assert result["portfolio"]["currency"] == "USD"
    
    def test_large_decimal_precision(self) -> None:
        """Test serialization preserves large decimal precision."""
        large_amount = Decimal("999999999.999999")
        data = {"amount": large_amount}
        
        json_str = JsonSerializer.serialize(data)
        result = JsonSerializer.deserialize(json_str)
        
        assert "999999999.999999" in json_str
    
    def test_multiple_decimals_in_array(self) -> None:
        """Test array of decimals."""
        amounts = [Decimal("100.25"), Decimal("200.50"), Decimal("300.75")]
        data = {"amounts": amounts}
        
        json_str = JsonSerializer.serialize(data)
        
        assert "100.25" in json_str
        assert "200.50" in json_str
        assert "300.75" in json_str
    
    def test_null_values_preserved(self) -> None:
        """Test null values are preserved."""
        data = {"value": None, "name": "test"}
        
        json_str = JsonSerializer.serialize(data)
        result = JsonSerializer.deserialize(json_str)
        
        assert result["value"] is None
        assert result["name"] == "test"

    def test_serialize_without_decimal_encoder_raises_type_error(self) -> None:
        """Test serialize with decimal handling disabled."""
        with pytest.raises(TypeError):
            JsonSerializer.serialize({"amount": Decimal("1.23")}, include_decimals=False)

    def test_serialize_without_date_encoder_raises_type_error(self) -> None:
        """Test serialize with date handling disabled."""
        with pytest.raises(TypeError):
            JsonSerializer.serialize({"trade_date": date(2024, 7, 27)}, include_dates=False)

    def test_serialize_without_any_special_encoder_raises_type_error(self) -> None:
        """Test serialize with all special handlers disabled."""
        with pytest.raises(TypeError):
            JsonSerializer.serialize(
                {"amount": Decimal("1.23"), "trade_date": date(2024, 7, 27)},
                include_decimals=False,
                include_dates=False,
            )

    def test_deserialize_decimal_keeps_non_numeric_strings(self) -> None:
        """Test decimal conversion ignores non-numeric strings."""
        result = JsonSerializer.deserialize_decimal('{"name":"alpha","value":"10.5"}')
        assert result["name"] == "alpha"
        assert result["value"] == Decimal("10.5")

    def test_deserialize_decimal_nested_list(self) -> None:
        """Test decimal conversion in nested list values."""
        result = JsonSerializer.deserialize_decimal('{"values":["1.1","2","x"]}')
        assert result["values"][0] == Decimal("1.1")
        assert result["values"][1] == Decimal("2")
        assert result["values"][2] == "x"

    def test_deserialize_dates_keeps_invalid_date_strings(self) -> None:
        """Test date conversion ignores invalid date strings."""
        result = JsonSerializer.deserialize_dates('{"good":"2024-07-27","bad":"2024-13-99"}')
        assert result["good"] == date(2024, 7, 27)
        assert result["bad"] == "2024-13-99"

    def test_deserialize_dates_nested_list(self) -> None:
        """Test date conversion in nested list values."""
        result = JsonSerializer.deserialize_dates('{"dates":["2024-01-01","text"]}')
        assert result["dates"][0] == date(2024, 1, 1)
        assert result["dates"][1] == "text"
