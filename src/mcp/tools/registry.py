from .inventory import get_stock_by_product, get_low_stock_products, get_stock_by_warehouse
from .manufacturing import (
    create_purchase_order, confirm_purchase_order,
    create_manufacturing_order, confirm_manufacturing_order,
    register_production_output, get_open_manufacturing_orders,
)
from .attendance import check_in_attendance, check_out_attendance, get_attendance_status

TOOL_DEFINITIONS = [
    # ── Inventario ────────────────────────────────────────────────────────────
    {
        "name": "get_stock_by_product",
        "description": "Consulta el stock disponible de un producto en todos los almacenes internos de Odoo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Nombre o parte del nombre del producto (búsqueda parcial)."},
                "product_id": {"type": "integer", "description": "ID interno del producto en Odoo (más preciso que el nombre)."},
            },
        },
    },
    {
        "name": "get_low_stock_products",
        "description": "Lista los productos cuyo stock actual está por debajo del mínimo configurado en Odoo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "warehouse_name": {"type": "string", "description": "Filtrar por nombre del almacén (opcional)."},
                "limit": {"type": "integer", "description": "Máximo de resultados (default 20, máximo 50)."},
            },
        },
    },
    {
        "name": "get_stock_by_warehouse",
        "description": "Retorna el inventario completo de un almacén específico.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "warehouse_name": {"type": "string", "description": "Nombre del almacén a consultar."},
                "limit": {"type": "integer", "description": "Máximo de productos (default 30, máximo 50)."},
            },
            "required": ["warehouse_name"],
        },
    },
    # ── Órdenes de compra ─────────────────────────────────────────────────────
    {
        "name": "create_purchase_order",
        "description": "Crea una orden de compra en estado borrador en Odoo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "supplier_name": {"type": "string", "description": "Nombre del proveedor (debe existir en Odoo)."},
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_name": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit_price": {"type": "number"},
                        },
                        "required": ["product_name", "quantity"],
                    },
                    "description": "Lista de productos a comprar.",
                },
                "notes": {"type": "string", "description": "Notas internas para la OC."},
            },
            "required": ["supplier_name", "lines"],
        },
    },
    {
        "name": "confirm_purchase_order",
        "description": "Confirma una orden de compra existente en Odoo (cambia de borrador a confirmada).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "po_number": {"type": "string", "description": "Número de la OC, ej: PO/2025/0087"},
                "po_id": {"type": "integer", "description": "ID interno de la OC en Odoo."},
            },
        },
    },
    # ── Órdenes de producción ─────────────────────────────────────────────────
    {
        "name": "create_manufacturing_order",
        "description": "Crea una orden de producción (MO) en estado borrador en Odoo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Nombre del producto a fabricar."},
                "quantity": {"type": "number", "description": "Cantidad a producir."},
                "scheduled_date": {"type": "string", "description": "Fecha programada ISO 8601 (ej: 2025-07-20). Default: hoy."},
                "notes": {"type": "string"},
            },
            "required": ["product_name", "quantity"],
        },
    },
    {
        "name": "confirm_manufacturing_order",
        "description": "Confirma una orden de producción existente en Odoo (reserva materiales).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mo_number": {"type": "string", "description": "Número de la OP, ej: MO/2025/0043"},
                "mo_id": {"type": "integer", "description": "ID interno de la OP en Odoo."},
            },
        },
    },
    # ── Órdenes de manufactura ────────────────────────────────────────────────
    {
        "name": "get_open_manufacturing_orders",
        "description": "Lista las órdenes de producción abiertas en Odoo (confirmadas, en proceso o por cerrar). Muestra producto, cantidad planificada, producida y pendiente.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Filtrar por nombre parcial del producto (opcional). Sin filtro lista todas.",
                },
            },
        },
    },
    # ── Ingreso de producción ─────────────────────────────────────────────────
    {
        "name": "register_production_output",
        "description": (
            "Registra el ingreso parcial o total de producto terminado al almacén desde una Orden de Producción abierta en Odoo. "
            "Busca la OP confirmada del producto indicado y mueve la cantidad al stock de Carabayllo. "
            "La OP queda abierta con el restante pendiente si la cantidad es parcial."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Nombre parcial o código del producto fabricado (ej: 'camiseta roja' o código QR escaneado).",
                },
                "quantity": {
                    "type": "number",
                    "description": "Cantidad a ingresar al almacén en esta operación.",
                },
            },
            "required": ["product_name", "quantity"],
        },
    },
    # ── Asistencias ───────────────────────────────────────────────────────────
    {
        "name": "check_in_attendance",
        "description": (
            "Registra la entrada (check-in) del empleado en Odoo. "
            "Valida que el empleado esté dentro de los 20 metros de una sede autorizada. "
            "Requiere la ubicación GPS actual del dispositivo."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "description": "Latitud GPS actual del dispositivo (ej: -11.924449)."},
                "longitude": {"type": "number", "description": "Longitud GPS actual del dispositivo (ej: -77.018218)."},
            },
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "check_out_attendance",
        "description": (
            "Registra la salida (check-out) del empleado en Odoo. "
            "Valida que el empleado esté dentro de los 20 metros de una sede autorizada. "
            "Requiere la ubicación GPS actual del dispositivo."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "description": "Latitud GPS actual del dispositivo (ej: -11.924449)."},
                "longitude": {"type": "number", "description": "Longitud GPS actual del dispositivo (ej: -77.018218)."},
            },
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "get_attendance_status",
        "description": "Consulta el estado de asistencia del empleado hoy: si está trabajando, hora de entrada, horas acumuladas.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

TOOL_HANDLERS: dict[str, callable] = {
    "get_stock_by_product": get_stock_by_product,
    "get_low_stock_products": get_low_stock_products,
    "get_stock_by_warehouse": get_stock_by_warehouse,
    "create_purchase_order": create_purchase_order,
    "confirm_purchase_order": confirm_purchase_order,
    "create_manufacturing_order": create_manufacturing_order,
    "confirm_manufacturing_order": confirm_manufacturing_order,
    "get_open_manufacturing_orders": get_open_manufacturing_orders,
    "register_production_output": register_production_output,
    "check_in_attendance": check_in_attendance,
    "check_out_attendance": check_out_attendance,
    "get_attendance_status": get_attendance_status,
}
