"""Transaction type enum for portfolio movements."""

from enum import Enum


class TransactionType(Enum):
    """Represents supported portfolio transaction categories."""

    BUY = "buy"
    SELL = "sell"
    COUPON = "coupon"
    MATURITY = "maturity"
    ADJUSTMENT = "adjustment"
