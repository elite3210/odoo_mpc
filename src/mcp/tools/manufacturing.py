import datetime
import xmlrpc.client
from src.odoo.client import OdooClient
from src.audit import log_write


def _find_product(odoo: OdooClient, name: str) -> dict | None:
    results = odoo.search_read(
        "product.product", [["name", "ilike", name], ["active", "=", True]],
        fields=["id", "name", "uom_id"], limit=3,
    )
    return results[0] if results else None


def _find_supplier(odoo: OdooClient, name: str) -> dict | None:
    results = odoo.search_read(
        "res.partner",
        [["name", "ilike", name], ["supplier_rank", ">", 0]],
        fields=["id", "name"], limit=3,
    )
    return results[0] if results else None


def _find_order(odoo: OdooClient, model: str, number: str | None, record_id: int | None) -> dict | None:
    if record_id:
        domain = [["id", "=", record_id]]
    elif number:
        domain = [["name", "=", number]]
    else:
        return None
    results = odoo.search_read(model, domain, fields=["id", "name", "state"], limit=1)
    return results[0] if results else None


def create_purchase_order(odoo: OdooClient, user_email: str, supplier_name: str, lines: list, notes: str = "") -> str:
    supplier = _find_supplier(odoo, supplier_name)
    if not supplier:
        return f'Error: no se encontró el proveedor "{supplier_name}" en Odoo.'

    order_lines = []
    total_desc = []
    for line in lines:
        product = _find_product(odoo, line.get("product_name", ""))
        if not product:
            return f'Error: no se encontró el producto "{line.get("product_name")}".'
        qty = float(line.get("quantity", 0))
        price = float(line.get("unit_price", 0))
        order_lines.append([0, 0, {
            "product_id": product["id"],
            "product_qty": qty,
            "price_unit": price,
        }])
        total_desc.append(f"  • {product['name']} — {qty:,.0f} × {price:,.2f} = {qty * price:,.2f}")

    vals = {"partner_id": supplier["id"], "order_line": order_lines}
    if notes:
        vals["notes"] = notes

    try:
        po_id = odoo.create("purchase.order", vals)
        po = odoo.read("purchase.order", [po_id], ["name", "amount_total"])[0]
        result = {"po_id": po_id, "po_name": po["name"]}
        log_write("create_purchase_order", {"user": user_email, "supplier": supplier_name, "lines": lines}, result)
        return (
            f"Orden de Compra creada:\n\n"
            f"Número: {po['name']}\n"
            f"Proveedor: {supplier['name']}\n"
            f"Estado: Borrador\n\n"
            f"Líneas:\n" + "\n".join(total_desc) +
            f"\n\nTotal: {po['amount_total']:,.2f}\n\n"
            f'Para confirmarla: confirm_purchase_order con "{po["name"]}"'
        )
    except xmlrpc.client.Fault as e:
        log_write("create_purchase_order", {"user": user_email, "supplier": supplier_name}, str(e), is_error=True)
        return f"Error de Odoo: {e.faultString}"


def confirm_purchase_order(odoo: OdooClient, user_email: str, po_number: str | None = None, po_id: int | None = None) -> str:
    order = _find_order(odoo, "purchase.order", po_number, po_id)
    ref = po_number or f"ID {po_id}"

    if not order:
        return f'No se encontró la OC "{ref}".'
    if order["state"] != "draft":
        labels = {"purchase": "Confirmada", "done": "Bloqueada", "cancel": "Cancelada", "sent": "Enviada"}
        return f'La OC {order["name"]} ya está en estado "{labels.get(order["state"], order["state"])}".'

    try:
        odoo.call("purchase.order", "button_confirm", [order["id"]])
        updated = odoo.read("purchase.order", [order["id"]], ["name", "state", "amount_total"])[0]
        log_write("confirm_purchase_order", {"user": user_email, "po": ref}, {"new_state": updated["state"]})
        return (
            f'OC {updated["name"]} confirmada.\n'
            f'Estado: Borrador → Orden de Compra\n'
            f'Total: {updated["amount_total"]:,.2f}'
        )
    except xmlrpc.client.Fault as e:
        log_write("confirm_purchase_order", {"user": user_email, "po": ref}, str(e), is_error=True)
        return f"Error de Odoo: {e.faultString}"


def create_manufacturing_order(odoo: OdooClient, user_email: str, product_name: str, quantity: float, scheduled_date: str | None = None, notes: str = "") -> str:
    product = _find_product(odoo, product_name)
    if not product:
        return f'Error: no se encontró el producto "{product_name}".'

    date_str = scheduled_date or datetime.date.today().isoformat()
    vals = {"product_id": product["id"], "product_qty": quantity, "date_planned_start": date_str}

    boms = odoo.search("mrp.bom", [["product_id", "=", product["id"]]], limit=1)
    if boms:
        vals["bom_id"] = boms[0]

    try:
        mo_id = odoo.create("mrp.production", vals)
        mo = odoo.read("mrp.production", [mo_id], ["name", "state"])[0]
        log_write("create_manufacturing_order", {"user": user_email, "product": product_name, "qty": quantity}, {"mo_id": mo_id, "mo_name": mo["name"]})
        bom_info = "Lista de materiales asignada automáticamente." if boms else "Sin lista de materiales — asígnala en Odoo."
        return (
            f"Orden de Producción creada:\n\n"
            f"Número: {mo['name']}\n"
            f"Producto: {product['name']}\n"
            f"Cantidad: {quantity:,.0f} {product['uom_id'][1]}\n"
            f"Fecha: {date_str}\n"
            f"Estado: Borrador\n\n{bom_info}\n"
            f'Para confirmarla: confirm_manufacturing_order con "{mo["name"]}"'
        )
    except xmlrpc.client.Fault as e:
        log_write("create_manufacturing_order", {"user": user_email, "product": product_name}, str(e), is_error=True)
        return f"Error de Odoo: {e.faultString}"


def confirm_manufacturing_order(odoo: OdooClient, user_email: str, mo_number: str | None = None, mo_id: int | None = None) -> str:
    order = _find_order(odoo, "mrp.production", mo_number, mo_id)
    ref = mo_number or f"ID {mo_id}"

    if not order:
        return f'No se encontró la OP "{ref}".'
    if order["state"] != "draft":
        return f'La OP {order["name"]} ya está en estado "{order["state"]}".'

    try:
        odoo.call("mrp.production", "action_confirm", [order["id"]])
        updated = odoo.read("mrp.production", [order["id"]], ["name", "state", "reservation_state"])[0]
        availability = "Materiales disponibles" if updated.get("reservation_state") == "assigned" else "Materiales insuficientes — revisa en Odoo"
        log_write("confirm_manufacturing_order", {"user": user_email, "mo": ref}, {"new_state": updated["state"]})
        return (
            f'OP {updated["name"]} confirmada.\n'
            f"Estado: Borrador → Confirmada\n"
            f"Materiales: {availability}"
        )
    except xmlrpc.client.Fault as e:
        log_write("confirm_manufacturing_order", {"user": user_email, "mo": ref}, str(e), is_error=True)
        return f"Error de Odoo: {e.faultString}"
