# Integración con Odoo 18 — XML-RPC

## Conexión básica

Odoo expone dos endpoints XML-RPC:
- `/xmlrpc/2/common` — autenticación (no requiere uid)
- `/xmlrpc/2/object` — operaciones sobre modelos (requiere uid)

```python
import xmlrpc.client

ODOO_URL = "https://www.heinzsport.com"
ODOO_DB  = "elite"
EMAIL    = "usuario@empresa.com"
PASSWORD = "contraseña"

# 1. Autenticar
common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
uid = common.authenticate(ODOO_DB, EMAIL, PASSWORD, {})
# uid es un entero (ID del usuario) o False si falla

# 2. Obtener proxy de modelos
models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
```

En este proyecto, la autenticación la maneja `src/auth.py` y el cliente está en `src/odoo/client.py` (`OdooClient`). No instanciar `xmlrpc.client` directamente en las tools — usar siempre `odoo_from_token(token)`.

## Métodos principales de `execute_kw`

```python
models.execute_kw(db, uid, password, model, method, args, kwargs)
```

### `search_read` — buscar y leer en un paso

```python
# Siempre: dominio + fields explícitos + limit
records = models.execute_kw(
    ODOO_DB, uid, PASSWORD,
    'stock.quant',          # modelo
    'search_read',          # método
    [[                      # args: lista de condiciones (AND implícito)
        ['location_id.usage', '=', 'internal'],
        ['quantity', '>', 0]
    ]],
    {                       # kwargs
        'fields': ['product_id', 'quantity', 'location_id'],
        'limit': 50,        # SIEMPRE poner limit
        'order': 'product_id asc'
    }
)
# Retorna: [{'id': 1, 'product_id': [5, 'Tornillo'], 'quantity': 100.0, ...}, ...]
```

### `search` — solo IDs

```python
ids = models.execute_kw(
    ODOO_DB, uid, PASSWORD,
    'purchase.order', 'search',
    [[['name', '=', 'PO/2025/0087']]],
    {'limit': 1}
)
# Retorna: [42] o []
```

### `read` — leer por IDs conocidos

```python
records = models.execute_kw(
    ODOO_DB, uid, PASSWORD,
    'purchase.order', 'read',
    [[42]],
    {'fields': ['name', 'partner_id', 'state', 'amount_total']}
)
```

### `create` — crear un registro

```python
new_id = models.execute_kw(
    ODOO_DB, uid, PASSWORD,
    'purchase.order', 'create',
    [{
        'partner_id': 15,
        'order_line': [
            [0, 0, {                   # (0, 0, vals) = crear línea nueva
                'product_id': 23,
                'product_qty': 100,
                'price_unit': 45.50,
            }]
        ],
    }]
)
# Retorna: ID del nuevo registro (entero)
```

### Métodos de acción (equivalentes a botones de la UI)

```python
# Confirmar orden de compra (botón "Confirmar" en Odoo)
models.execute_kw(ODOO_DB, uid, PASSWORD,
    'purchase.order', 'button_confirm', [[42]])

# Confirmar orden de producción
models.execute_kw(ODOO_DB, uid, PASSWORD,
    'mrp.production', 'action_confirm', [[15]])
```

## Dominios (filtros) frecuentes

```python
# Solo ubicaciones internas de almacén
['location_id.usage', '=', 'internal']

# Productos con stock
['quantity', '>', 0]

# Buscar por nombre (parcial, insensible a mayúsculas)
['product_id.name', 'ilike', 'tornillo']

# Solo proveedores
['supplier_rank', '>', 0]

# OC en borrador
['state', '=', 'draft']

# OP no canceladas ni terminadas
['state', 'not in', ['done', 'cancel']]

# Combinar con OR explícito
['|', ['name', 'ilike', 'PO/2025'], ['name', 'ilike', 'PO/2024']]
```

## Campos relacionales (many2one)

Cuando un campo es `many2one`, Odoo retorna `[id, nombre]`:

```python
record['product_id']    # → [5, 'Tornillo Galvanizado 1/2"']
record['product_id'][0] # → 5   (el ID)
record['product_id'][1] # → 'Tornillo Galvanizado 1/2"' (para mostrar)
```

## Comandos one2many (listas anidadas)

```python
# (0, 0, vals) → crear y enlazar
# (1, id, vals) → modificar existente
# (2, id, 0)   → eliminar
# (4, id, 0)   → enlazar existente sin crear
# (6, 0, [ids]) → reemplazar lista completa

'order_line': [
    [0, 0, {'product_id': 23, 'product_qty': 50, 'price_unit': 10.0}],
    [0, 0, {'product_id': 24, 'product_qty': 20, 'price_unit': 5.0}],
]
```

## Modelos clave — Fase 1

### Inventario

| Modelo | Descripción |
|--------|-------------|
| `stock.quant` | Cantidad de producto en ubicación (puede haber varios por lote/serie) |
| `stock.location` | Ubicaciones físicas (`usage`: internal, supplier, customer) |
| `stock.warehouse` | Almacenes configurados |
| `stock.warehouse.orderpoint` | Reglas de reorden (stock mínimo/máximo) |

> **Nota importante:** el modelo de reglas de reorden es `stock.warehouse.orderpoint`, NO `stock.orderpoint` (este último no existe en Odoo).

**Campos útiles de `stock.quant`:**
- `product_id` (many2one → product.product)
- `location_id` (many2one → stock.location)
- `quantity` (cantidad física total)
- `reserved_quantity` (reservada para pickings/OPs)
- `available_quantity` = `quantity - reserved_quantity`

**Campos de `stock.warehouse.orderpoint`:**
- `product_id`
- `location_id`
- `product_min_qty` — mínimo configurado
- `product_max_qty` — máximo para reorden
- `qty_on_hand` — stock actual (campo computed)

### Órdenes de compra

| Modelo | Descripción |
|--------|-------------|
| `purchase.order` | Cabecera de OC |
| `purchase.order.line` | Líneas de OC |

**Estados de `purchase.order`:**
- `draft` → `sent` → `purchase` → `done` / `cancel`
- Método para confirmar: `button_confirm`

### Órdenes de producción

| Modelo | Descripción |
|--------|-------------|
| `mrp.production` | Orden de producción |
| `mrp.bom` | Lista de materiales (BOM) |

**Estados de `mrp.production`:**
- `draft` → `confirmed` → `progress` → `to_close` → `done` / `cancel`
- Método para confirmar: `action_confirm`
- `reservation_state`: `confirmed` | `assigned` (materiales disponibles) | `partially_available`

## Manejo de errores XML-RPC

```python
import xmlrpc.client

try:
    result = models.execute_kw(...)
except xmlrpc.client.Fault as e:
    # Error de Odoo (validación, acceso denegado, modelo inexistente)
    print(f"Odoo error {e.faultCode}: {e.faultString}")
except ConnectionRefusedError:
    print("Odoo no está corriendo o el puerto está bloqueado")
except Exception as e:
    print(f"Error inesperado: {e}")
```

## Verificar conexión rápida

```bash
python -c "
import xmlrpc.client
common = xmlrpc.client.ServerProxy('https://www.heinzsport.com/xmlrpc/2/common')
print(common.version())
"
# Esperado: {'server_version': '18.0-20260426', ...}
```
