IVA_RATE = 19


def price(value):
    return "$ " + f"{value:,}".replace(",", ".")


def summarize_cart(product_map, cart):
    lines = [
        {"product": product_map[sku], "qty": quantity, "total": product_map[sku]["price_cop"] * quantity}
        for sku, quantity in cart.items()
        if sku in product_map
    ]
    total = sum(line["total"] for line in lines)
    # Catalog prices include tax. Round the implied base to the nearest peso.
    divisor = 100 + IVA_RATE
    base = (total * 100 + divisor // 2) // divisor
    return {
        "lines": lines, "subtotal": base, "iva": total - base, "iva_rate": IVA_RATE,
        "total": total, "has_shortage": any(line["qty"] > line["product"]["stock"] for line in lines),
    }
