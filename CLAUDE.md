# CLAUDE.md — Guía para Asistentes de IA

## Qué es este proyecto

Servidor MCP (Model Context Protocol) para exponer datos y operaciones de **Odoo 18 Community** a **Heinzbot**, una app Android de chat conversacional que conecta modelos LLM (DeepSeek, Claude, Gemini, ChatGPT, etc.) con sistemas empresariales.

El servidor actúa como puente: el LLM dentro de Heinzbot envía tool-calls autenticadas → el servidor las traduce a llamadas XML-RPC → Odoo ejecuta la operación → el resultado vuelve al LLM como contexto.

**URL del servidor Odoo:** `https://www.heinzsport.com`  
**Base de datos Odoo:** `elite`

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI (Python 3.10+) |
| Protocolo | MCP Streamable HTTP (spec 2025-03-26) |
| Autenticación | JWT por usuario (login con credenciales Odoo) |
| Conexión Odoo | XML-RPC nativo (`xmlrpc.client`) |
| Infraestructura | Hostinger VPS (Ubuntu), mismo servidor que Odoo |
| Testing | pytest + pytest-asyncio |

## Estructura del proyecto

```
odoo_mpc/
├── CLAUDE.md                   # Esta guía
├── README.md
├── docs/
│   ├── PRD.md                  # Requerimientos del producto
│   ├── ARCHITECTURE.md         # Diseño del sistema
│   ├── API_SPEC.md             # Especificación de herramientas MCP y endpoints
│   └── ODOO_INTEGRATION.md     # Patrones XML-RPC con Odoo 18
├── src/
│   ├── main.py                 # Entry point FastAPI
│   ├── config.py               # Settings desde variables de entorno
│   ├── auth.py                 # JWT: login contra Odoo + validación de tokens
│   ├── auth_router.py          # Endpoint POST /auth/login
│   ├── audit.py                # Log JSON Lines de operaciones de escritura
│   ├── mcp/
│   │   ├── protocol.py         # Handler MCP JSON-RPC (initialize, tools/list, tools/call)
│   │   └── tools/
│   │       ├── inventory.py    # Herramientas de inventario (lectura)
│   │       ├── manufacturing.py # Herramientas MRP + compras (lectura + escritura)
│   │       └── registry.py     # Registro central de todas las tools
│   └── odoo/
│       ├── client.py           # OdooClient por usuario + factory odoo_from_token()
│       └── __init__.py
├── tests/
│   └── (pendiente)
├── .env.example
├── .env                        # NO commitear — ignorado en .gitignore
├── requirements.txt
└── systemd/
    └── odoo-mcp.service        # Unit file para VPS Hostinger
```

## Variables de entorno requeridas

```bash
# Odoo (solo URL y BD — las credenciales llegan por usuario en cada request)
ODOO_URL=https://www.heinzsport.com
ODOO_DB=elite

# Seguridad JWT
JWT_SECRET=<genera con: python -c "import secrets; print(secrets.token_hex(32))">
JWT_EXPIRE_HOURS=8        # tiempo de vida del token por usuario

# Servidor
MCP_HOST=0.0.0.0
MCP_PORT=8001

# Audit log
AUDIT_LOG_PATH=audit.jsonl
```

## Flujo de autenticación (por usuario)

Cada usuario de Heinzbot usa sus propias credenciales de Odoo:

```
1. Usuario abre Heinzbot → configura el conector con la URL del servidor
2. Heinzbot llama POST /auth/login con {"email": "...", "password": "..."}
3. El servidor verifica las credenciales contra Odoo XML-RPC (authenticate)
4. Si son válidas, retorna un JWT firmado (8h de vida) con uid + credenciales cifradas
5. Heinzbot guarda ese token como "API Key" del conector (Bearer)
6. Todas las tool-calls MCP usan ese token → servidor extrae uid y credenciales
7. Las llamadas a Odoo XML-RPC se hacen como el usuario real (sus permisos aplican)
```

## Protocolo MCP que implementamos

| Método | Path | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/auth/login` | Ninguna | Obtener token JWT con credenciales Odoo |
| POST | `/mcp` | Bearer JWT | Endpoint MCP principal |
| GET | `/health` | Ninguna | Estado del servidor y conexión Odoo |
| GET | `/docs` | Ninguna | Documentación OpenAPI auto-generada |

### Métodos MCP soportados

- `initialize` — handshake del protocolo
- `tools/list` — lista todas las herramientas disponibles
- `tools/call` — ejecutar una herramienta

## Cómo agregar una nueva herramienta MCP

1. Implementar en `src/mcp/tools/<dominio>.py` con firma `(odoo: OdooClient, user_email: str, **params) -> str`
2. Registrarla en `src/mcp/tools/registry.py` — añadir a `TOOL_DEFINITIONS` y `TOOL_HANDLERS`
3. Documentar en `docs/API_SPEC.md`
4. Escribir test en `tests/`

Reglas para toda tool:
- Nombre en `snake_case` descriptivo
- Retorna siempre `str` (texto legible para el LLM)
- Nunca expone passwords, tokens ni datos internos de config
- Las escrituras DEBEN registrarse en audit log antes de retornar
- Limit en todas las consultas (máximo 50)
- Fields explícitos en `search_read` — nunca `fields=[]`

## Patrón XML-RPC con Odoo

```python
# El cliente se instancia por request con las credenciales del usuario del token
from src.odoo.client import OdooClient, odoo_from_token

# En protocol.py — se crea por cada tool-call
odoo = odoo_from_token(token)   # token = payload JWT decodificado

# Lectura — siempre fields explícitos + limit
quants = odoo.search_read(
    'stock.quant',
    [['location_id.usage', '=', 'internal'], ['quantity', '>', 0]],
    fields=['product_id', 'quantity', 'location_id'],
    limit=50
)

# Escritura — registrar en audit ANTES de retornar
po_id = odoo.create('purchase.order', vals)
log_write('create_purchase_order', {'user': user_email, ...}, {'po_id': po_id})
```

## Módulos Odoo en uso

| Módulo | Modelos clave |
|--------|--------------|
| `stock` | `stock.quant`, `stock.warehouse`, `stock.warehouse.orderpoint` |
| `mrp` | `mrp.production`, `mrp.bom` |
| `purchase` | `purchase.order`, `purchase.order.line` |
| `product` | `product.product`, `product.template` |
| `base` | `res.partner`, `res.users` |

> **Importante:** el modelo de reglas de reorden es `stock.warehouse.orderpoint` (no `stock.orderpoint`).

## Fase 1 — Herramientas implementadas

| Tool | Tipo | Módulo |
|------|------|--------|
| `get_stock_by_product` | Lectura | stock |
| `get_low_stock_products` | Lectura | stock |
| `get_stock_by_warehouse` | Lectura | stock |
| `create_purchase_order` | Escritura | purchase |
| `confirm_purchase_order` | Escritura | purchase |
| `create_manufacturing_order` | Escritura | mrp |
| `confirm_manufacturing_order` | Escritura | mrp |

## Comandos útiles de desarrollo

```bash
# Instalar dependencias
pip install -r requirements.txt

# Generar JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"

# Arrancar servidor en desarrollo
python -m uvicorn src.main:app --reload --port 8001

# Verificar conexión a Odoo (sin credenciales de usuario)
curl http://localhost:8001/health

# Obtener token (reemplaza con credenciales reales)
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "tu@email.com", "password": "tu_password"}'

# Llamar una tool con el token
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_low_stock_products","arguments":{}},"id":1}'
```

## Reglas de desarrollo

- **Sin usuario técnico compartido** — cada request usa las credenciales reales del usuario Odoo
- **No mockear Odoo en tests de integración** — usar instancia de Odoo de prueba o fixtures reales
- **Audit log obligatorio** para cualquier operación que modifique datos
- **Limit en todas las consultas** — nunca `search_read` sin `limit`
- **Fields explícitos** — nunca `fields=[]`
