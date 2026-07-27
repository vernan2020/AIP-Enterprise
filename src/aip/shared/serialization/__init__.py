"""JSON serialization support for AIP Enterprise.

This module provides custom JSON encoders and decoders for financial
types including Decimal, Date, and other domain-specific types.

Classes:
    DecimalEncoder: JSON encoder for Decimal values.
    DateEncoder: JSON encoder for date values.
    JsonSerializer: Main JSON serialization utility.
"""

import json
from decimal import Decimal
from datetime import date, datetime
from typing import Any


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder supporting Decimal types.
    
    Handles Decimal serialization by converting to string to maintain precision.
    
    References:
    - JSON RFC 7159
    - Python decimal documentation
    """
    
    def default(self, obj: Any) -> Any:
        """Encode object to JSON-serializable form.
        
        Args:
            obj: The object to encode.
            
        Returns:
            JSON-serializable representation.
        """
        if isinstance(obj, Decimal):
            # Convert Decimal to string to maintain precision
            return str(obj)
        
        return super().default(obj)


class DateEncoder(json.JSONEncoder):
    """JSON encoder supporting date and datetime types.
    
    Handles date serialization using ISO 8601 format.
    
    References:
    - ISO 8601 Date and Time Standard
    """
    
    def default(self, obj: Any) -> Any:
        """Encode object to JSON-serializable form.
        
        Args:
            obj: The object to encode.
            
        Returns:
            JSON-serializable representation.
        """
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        
        return super().default(obj)


class JsonSerializer:
    """JSON serialization utility for domain objects.
    
    Provides methods for serializing and deserializing financial types
    with proper handling of Decimal and date values.
    """
    
    @staticmethod
    def serialize(obj: Any, include_decimals: bool = True, include_dates: bool = True) -> str:
        """Serialize object to JSON string.
        
        Args:
            obj: The object to serialize.
            include_decimals: Whether to handle Decimal types (default: True).
            include_dates: Whether to handle date types (default: True).
            
        Returns:
            JSON string representation.
            
        Raises:
            TypeError: If object contains non-serializable types.
            
        Example:
            >>> from decimal import Decimal
            >>> from datetime import date
            >>> obj = {
            ...     "amount": Decimal("123.45"),
            ...     "date": date(2024, 7, 27),
            ... }
            >>> json_str = JsonSerializer.serialize(obj)
        """
        # Choose appropriate encoder
        if include_decimals and include_dates:
            encoder = _CombinedEncoder
        elif include_decimals:
            encoder = DecimalEncoder
        elif include_dates:
            encoder = DateEncoder
        else:
            encoder = json.JSONEncoder
        
        return json.dumps(obj, cls=encoder, indent=2)
    
    @staticmethod
    def serialize_compact(obj: Any) -> str:
        """Serialize object to compact JSON (no whitespace).
        
        Args:
            obj: The object to serialize.
            
        Returns:
            Compact JSON string representation.
        """
        return json.dumps(obj, cls=_CombinedEncoder, separators=(",", ":"))
    
    @staticmethod
    def deserialize(json_str: str) -> Any:
        """Deserialize JSON string to Python object.
        
        Args:
            json_str: JSON string to deserialize.
            
        Returns:
            Python object representation.
            
        Raises:
            json.JSONDecodeError: If JSON is invalid.
            
        Example:
            >>> json_str = '{"amount": "123.45", "date": "2024-07-27"}'
            >>> obj = JsonSerializer.deserialize(json_str)
        """
        return json.loads(json_str)
    
    @staticmethod
    def deserialize_decimal(json_str: str) -> Any:
        """Deserialize JSON string, converting decimal strings to Decimal.
        
        Args:
            json_str: JSON string to deserialize.
            
        Returns:
            Python object with Decimal values converted.
        """
        obj = json.loads(json_str)
        return JsonSerializer._convert_decimals(obj)
    
    @staticmethod
    def deserialize_dates(json_str: str) -> Any:
        """Deserialize JSON string, converting ISO dates to date objects.
        
        Args:
            json_str: JSON string to deserialize.
            
        Returns:
            Python object with date values converted.
        """
        obj = json.loads(json_str)
        return JsonSerializer._convert_dates(obj)
    
    @staticmethod
    def _convert_decimals(obj: Any) -> Any:
        """Recursively convert numeric strings to Decimal.
        
        Args:
            obj: Object to convert.
            
        Returns:
            Object with decimals converted.
        """
        if isinstance(obj, dict):
            return {k: JsonSerializer._convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [JsonSerializer._convert_decimals(item) for item in obj]
        elif isinstance(obj, str):
            try:
                return Decimal(obj)
            except:
                return obj
        else:
            return obj
    
    @staticmethod
    def _convert_dates(obj: Any) -> Any:
        """Recursively convert ISO date strings to date objects.
        
        Args:
            obj: Object to convert.
            
        Returns:
            Object with dates converted.
        """
        if isinstance(obj, dict):
            return {k: JsonSerializer._convert_dates(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [JsonSerializer._convert_dates(item) for item in obj]
        elif isinstance(obj, str):
            try:
                # Try to parse as ISO date
                return datetime.fromisoformat(obj).date()
            except (ValueError, TypeError):
                return obj
        else:
            return obj


class _CombinedEncoder(json.JSONEncoder):
    """Combined encoder for both Decimal and date types.
    
    Internal use only. Handles both Decimal and date encoding.
    """
    
    def default(self, obj: Any) -> Any:
        """Encode object to JSON-serializable form.
        
        Args:
            obj: The object to encode.
            
        Returns:
            JSON-serializable representation.
        """
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()
        
        return super().default(obj)
