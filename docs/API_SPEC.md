# Especificación de la API

## Endpoints del servidor

| Método | Path | Auth | Descripción |
|--------|------|------|-------------|
| `POST` | `/auth/login` | Ninguna | Obtener token JWT personal |
| `POST` | `/mcp` | Bearer JWT | Endpoint MCP principal |
| `GET` | `/health` | Ninguna | Estado del servidor y Odoo |
| `GET` | `/docs` | Ninguna | Documentación OpenAPI interactiva |

---

## POST /auth/login

Autentica al usuario con sus credenciales de Odoo y retorna un JWT personal.  
**No requiere Authorization header.**

### Request

```json
{
  "email": "usuario@empresa.com",
  "password": "contraseña_odoo"
}
```

### Respuesta exitosa (200)

```json
{
  "token": "eyJhbGci...",
  "token_type": "Bearer",
  "user_name": "Eli Mandujano",
  "user_email": "elite3210@gmail.com",
  "expires_in_hours": 8,
  "usage": "Configura en Heinzbot — API Key: Bearer eyJhbGci..."
}
```

### Respuesta con error (401)

```json
{
  "detail": "Credenciales incorrectas"
}
```

### Notas

- El token expira en 8 horas (`JWT_EXPIRE_HOURS` en `.env`)
- Para renovar, llamar `/auth/login` de nuevo
- En Heinzbot: copiar el valor de `token` como "API Key" del conector

---

## POST /mcp — Protocolo MCP

**Auth:** `Authorization: Bearer <token>`  
**Content-Type:** `application/json`

### Estructura base JSON-RPC

```json
{
  "jsonrpc": "2.0",
  "method": "<método>",
  "params": { ... },
  "id": 1
}
```

### initialize — Handshake del protocolo

```json
{ "jsonrpc": "2.0", "method": "initialize", "params": { "protocolVersion": "2025-03-26" }, "id": 1 }
```

**Respuesta:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "protocolVersion": "2025-03-26",
    "serverInfo": { "name": "odoo-mcp", "version": "1.0.0" },
    "capabilities": { "tools": {} }
  },
  "id": 1
}
```

### tools/list — Listar herramientas

```json
{ "jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1 }
```

### tools/call — Ejecutar herramienta

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "<nombre_tool>",
    "arguments": { ... }
  },
  "id": 1
}
```

**Respuesta exitosa:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [{ "type": "text", "text": "Texto de respuesta para el LLM" }],
    "isError": false
  },
  "id": 1
}
```

**Respuesta con error:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [{ "type": "text", "text": "Error: descripción del problema" }],
    "isError": true
  },
  "id": 1
}
```

---

## Herramientas MCP — Fase 1

### `get_stock_by_product`

Retorna el stock disponible de un producto en todos los almacenes internos.

**Parámetros:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `product_name` | string | Sí (o `product_id`) | Nombre parcial del producto (búsqueda insensible a mayúsculas). |
| `product_id` | integer | No | ID interno de Odoo (más preciso). |

**Ejemplo:**
```json
{ "name": "get_stock_by_product", "arguments": { "product_name": "bolsa pebd" } }
```

**Respuesta:**
```
Stock de "[EB0011] Bolsa PEBD Plancha 15*22*1.5":
  • WH/Existencias: 654
  • WH/Existencias: 165
  ...
Total disponible: 1,221
```

---

### `get_low_stock_products`

Lista productos cuyo stock actual está por debajo del mínimo configurado en Odoo (reglas de reorden `stock.warehouse.orderpoint`).

**Parámetros:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `warehouse_name` | string | No | Filtrar por almacén. Si se omite, revisa todos. |
| `limit` | integer | No | Máximo de resultados (default 20, máximo 50). |

**Ejemplo:**
```json
{ "name": "get_low_stock_products", "arguments": { "limit": 10 } }
```

**Respuesta:**
```
Productos con stock crítico (2 encontrados):

1. [PC0051] Palito de chupetin 12cm — Stock: 0, Mínimo: 5 (AGOTADO)
2. [FURN_7777] Office Chair — Stock: 0, Mínimo: 3 (AGOTADO)
```

**Nota:** Solo lista productos que tienen regla de reorden configurada en Odoo.

---

### `get_stock_by_warehouse`

Retorna el inventario completo de un almacén específico.

**Parámetros:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `warehouse_name` | string | Sí | Nombre del almacén (búsqueda parcial). |
| `limit` | integer | No | Máximo de productos (default 30, máximo 50). |

**Ejemplo:**
```json
{ "name": "get_stock_by_warehouse", "arguments": { "warehouse_name": "WH" } }
```

---

### `create_purchase_order`

Crea una orden de compra en estado borrador. **Registra en audit log.**

**Parámetros:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `supplier_name` | string | Sí | Nombre del proveedor (debe existir en Odoo). |
| `lines` | array | Sí | Productos a comprar. |
| `lines[].product_name` | string | Sí | Nombre del producto. |
| `lines[].quantity` | number | Sí | Cantidad. |
| `lines[].unit_price` | number | No | Precio unitario. |
| `notes` | string | No | Notas internas. |

**Ejemplo:**
```json
{
  "name": "create_purchase_order",
  "arguments": {
    "supplier_name": "Proveedor ABC",
    "lines": [{ "product_name": "Tornillo M8", "quantity": 500, "unit_price": 0.15 }]
  }
}
```

---

### `confirm_purchase_order`

Confirma una OC en estado borrador. **Registra en audit log.**

**Parámetros:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `po_number` | string | Sí (o `po_id`) | Número de la OC, ej: `PO/2025/0087`. |
| `po_id` | integer | No | ID interno de Odoo. |

---

### `create_manufacturing_order`

Crea una orden de producción en estado borrador. **Registra en audit log.**

**Parámetros:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `product_name` | string | Sí | Producto a fabricar. |
| `quantity` | number | Sí | Cantidad a producir. |
| `scheduled_date` | string | No | Fecha ISO 8601 (ej: `2025-07-20`). Default: hoy. |
| `notes` | string | No | Notas de producción. |

---

### `confirm_manufacturing_order`

Confirma una OP en borrador (reserva materiales). **Registra en audit log.**

**Parámetros:**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `mo_number` | string | Sí (o `mo_id`) | Número de la OP, ej: `MO/2025/0043`. |
| `mo_id` | integer | No | ID interno de Odoo. |

---

## GET /health

Health check sin autenticación.

**Respuesta:**
```json
{
  "status": "ok",
  "odoo_connected": true,
  "odoo_version": "18.0-20260426",
  "server_version": "1.0.0"
}
```

`status` puede ser `"ok"` o `"degraded"` (si Odoo no responde).

---

## Configurar en Heinzbot

1. Abrir Heinzbot → menú **Conectores**
2. Agregar nuevo conector:
   - **URL**: `https://<dominio-o-ip>/mcp`
   - **API Key**: (dejar vacío por ahora)
3. Llamar `/auth/login` desde Postman o terminal:
   ```bash
   curl -X POST https://<dominio>/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "tu@email.com", "password": "tu_password"}'
   ```
4. Copiar el valor de `token` de la respuesta
5. En Heinzbot, pegar `Bearer <token>` en el campo **API Key** del conector
