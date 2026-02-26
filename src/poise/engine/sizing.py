from decimal import Decimal, ROUND_DOWN

_FRACTION = Decimal("0.05")


def unit_bet(balance: Decimal) -> Decimal:
    """5% of available balance, rounded down to 2 decimal places."""
    return (balance * _FRACTION).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
