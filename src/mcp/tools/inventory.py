from src.odoo.client import OdooClient


def get_stock_by_product(odoo: OdooClient, user_email: str = "", product_name: str | None = None, product_id: int | None = None) -> str:
    if not product_name and not product_id:
        return "Error: debes proporcionar product_name o product_id."

    if product_id:
        domain = [["product_id", "=", product_id], ["location_id.usage", "=", "internal"]]
    else:
        domain = [
            ["product_id.name", "ilike", product_name],
            ["location_id.usage", "=", "internal"],
            ["quantity", ">", 0],
        ]

    quants = odoo.search_read(
        "stock.quant", domain,
        fields=["product_id", "location_id", "quantity", "reserved_quantity"],
        limit=50,
        order="product_id asc",
    )

    if not quants:
        term = product_name or f"ID {product_id}"
        return f'No se encontró stock para "{term}" en almacenes internos.'

    lines = []
    total = 0.0
    product_display = quants[0]["product_id"][1]

    for q in quants:
        available = q["quantity"] - q["reserved_quantity"]
        loc = q["location_id"][1]
        lines.append(f"  • {loc}: {available:,.0f}")
        total += available

    header = f'Stock de "{product_display}":\n'
    return header + "\n".join(lines) + f"\n\nTotal disponible: {total:,.0f}"


def get_low_stock_products(odoo: OdooClient, user_email: str = "", warehouse_name: str | None = None, limit: int = 20) -> str:
    limit = min(limit, 50)
    domain: list = []
    if warehouse_name:
        domain.append(["location_id.warehouse_id.name", "ilike", warehouse_name])

    orderpoints = odoo.search_read(
        "stock.warehouse.orderpoint", domain,
        fields=["product_id", "location_id", "product_min_qty", "qty_on_hand"],
        limit=limit,
    )

    critical = [op for op in orderpoints if op["qty_on_hand"] < op["product_min_qty"]]

    if not critical:
        return "No hay productos con stock crítico en este momento."

    lines = [f"Productos con stock crítico ({len(critical)} encontrados):\n"]
    for i, op in enumerate(critical, 1):
        name = op["product_id"][1]
        current = op["qty_on_hand"]
        minimum = op["product_min_qty"]
        deficit = minimum - current
        status = "AGOTADO" if current == 0 else f"déficit: {deficit:,.0f}"
        lines.append(f"{i}. {name} — Stock: {current:,.0f}, Mínimo: {minimum:,.0f} ({status})")

    return "\n".join(lines)


def get_stock_by_warehouse(odoo: OdooClient, user_email: str = "", warehouse_name: str = "", limit: int = 30) -> str:
    limit = min(limit, 50)

    warehouses = odoo.search_read(
        "stock.warehouse", [["name", "ilike", warehouse_name]],
        fields=["id", "name", "lot_stock_id"],
        limit=5,
    )

    if not warehouses:
        return f'No se encontró el almacén "{warehouse_name}".'

    wh = warehouses[0]
    stock_location_id = wh["lot_stock_id"][0]

    quants = odoo.search_read(
        "stock.quant",
        [["location_id", "child_of", stock_location_id], ["quantity", ">", 0]],
        fields=["product_id", "quantity", "reserved_quantity"],
        limit=limit,
        order="product_id asc",
    )

    if not quants:
        return f'El almacén "{wh["name"]}" no tiene stock registrado.'

    lines = [f'Inventario — {wh["name"]} (mostrando {len(quants)} productos):\n']
    lines.append(f'{"Producto":<40} {"Disponible":>12}')
    lines.append("-" * 54)

    for q in quants:
        name = q["product_id"][1][:39]
        available = q["quantity"] - q["reserved_quantity"]
        lines.append(f"{name:<40} {available:>12,.0f}")

    if len(quants) == limit:
        lines.append(f"\nSe mostraron los primeros {limit} productos.")

    return "\n".join(lines)
