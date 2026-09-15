# pricing 2.3.0: formats a price line.


def price_line(item: str, cents: int) -> str:
    return f"{item} costs {cents} cents"
