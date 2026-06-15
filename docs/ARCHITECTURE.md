# Arquitectura del Sistema

## Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────┐
│                    Hostinger VPS (Ubuntu)                    │
│                                                             │
│  ┌──────────────────────┐    ┌─────────────────────────┐   │
│  │   odoo-mcp server    │    │      Odoo 18 Community  │   │
│  │   (FastAPI :8001)    │    │   heinzsport.com (:443) │   │
│  │                      │    │    BD: elite            │   │
│  │  ┌────────────────┐  │    │                         │   │
│  │  │  POST          │  │    │  ┌───────────────────┐  │   │
│  │  │  /auth/login   │──┼────┼─▶│ XML-RPC /common   │  │   │
│  │  │  (sin Bearer)  │  │    │  │  authenticate()   │  │   │
│  │  └───────┬────────┘  │    │  └───────────────────┘  │   │
│  │          │ JWT        │    │                         │   │
│  │  ┌───────▼────────┐  │    │  ┌───────────────────┐  │   │
│  │  │  POST /mcp     │  │    │  │ XML-RPC /object   │  │   │
│  │  │  Bearer JWT    │  │    │  │  execute_kw()     │  │   │
│  │  │                │  │    │  │                   │  │   │
│  │  │  MCP Protocol  │  │XML-RPC  Módulos:          │  │   │
│  │  │  Tool Registry │──┼────┼──▶ stock, mrp,       │  │   │
│  │  │                │  │    │  │ purchase, product  │  │   │
│  │  └───────┬────────┘  │    │  └───────────────────┘  │   │
│  │          │            │    └─────────────────────────┘   │
│  │  ┌───────▼────────┐  │                                   │
│  │  │   Audit Log    │  │                                   │
│  │  │  (JSON Lines)  │  │                                   │
│  │  └────────────────┘  │                                   │
│  └──────────┬───────────┘                                   │
│             │ HTTPS :443 (Nginx reverse proxy)              │
└─────────────┼───────────────────────────────────────────────┘
              │
              │  POST /auth/login  (sin auth)
              │  POST /mcp         Authorization: Bearer <JWT>
              │  GET  /health      (sin auth)
              │
┌─────────────▼──────────────┐
│       Heinzbot (Android)    │
│                             │
│  ┌─────────────────────┐   │
│  │  Conector MCP:      │   │
│  │  URL: https://...   │   │
│  │  API Key: Bearer... │   │  ← Token personal por usuario (JWT 8h)
│  └──────────┬──────────┘   │
│             │               │
│  ┌──────────▼──────────┐   │
│  │  LLM (DeepSeek /    │   │
│  │  Claude / Gemini /  │   │
│  │  ChatGPT)           │   │
│  │  → tool-calls MCP   │   │
│  └─────────────────────┘   │
└────────────────────────────┘
```

## Flujo completo de una solicitud

### Paso 0 — Login (una vez, al configurar Heinzbot)

```
Usuario → POST /auth/login {"email": "...", "password": "..."}
        → Servidor verifica contra Odoo XML-RPC authenticate()
        → Si OK: genera JWT {uid, email, pwd_cifrada, exp=+8h}
        → Heinzbot guarda el JWT como "API Key" del conector
```

### Paso 1 — Tool-call desde Heinzbot

```
Usuario habla con Heinzbot
        │
        ▼
LLM analiza intención → genera tool-call
        │
        ▼ POST /mcp  Authorization: Bearer <JWT>
        │  {"method": "tools/call", "params": {"name": "get_stock_by_product", ...}}
        │
        ▼
[Auth] Decodifica y valida JWT → extrae {uid, email, pwd}
        │
        ▼
[MCP Protocol] Parsea JSON-RPC, identifica tool
        │
        ▼
[Tool] Valida parámetros de la tool
        │
        ▼
[OdooClient(email, pwd)] XML-RPC → Odoo execute_kw(...)
        │
        ▼  (si es escritura)
[Audit] Registra {ts, tool, args, user_email, result}
        │
        ▼
MCP Response: {"result": {"content": [{"type": "text", "text": "..."}]}}
        │
        ▼
LLM construye respuesta en lenguaje natural
        │
        ▼
Usuario ve la respuesta en Heinzbot
```

## Decisiones de diseño

### Por qué autenticación por usuario (JWT) y no API key estática

Con un API key compartido, todas las operaciones en Odoo se harían como el mismo usuario técnico, perdiendo:
- La trazabilidad real (quién hizo qué)
- El control de permisos nativo de Odoo (un vendedor no debería confirmar OPs)
- La capacidad de auditoría por persona

Con JWT por usuario, cada request lleva las credenciales reales del usuario → Odoo aplica sus propios permisos → el audit log tiene el email real → un token comprometido solo afecta a un usuario.

### Por qué el token incluye la contraseña (cifrada en el JWT)

La API XML-RPC de Odoo requiere la contraseña en cada llamada `execute_kw`. Las alternativas son:
1. Guardar contraseñas en base de datos del servidor (más complejo, estado compartido)
2. Pedir las credenciales en cada request (mala UX)
3. Incluir la contraseña en el JWT firmado con el `JWT_SECRET` del servidor

La opción 3 es la más simple y stateless. La contraseña solo es legible si se conoce el `JWT_SECRET`, y el JWT viaja siempre por HTTPS. La mitigación de riesgo es: HTTPS obligatorio + tokens de vida corta (8h) + rotación del JWT_SECRET si hay compromiso.

### Por qué XML-RPC y no REST

Odoo 18 Community no incluye una API REST nativa completa. La API XML-RPC es el estándar oficial, estable, y no requiere módulos adicionales.

### Por qué FastAPI

- Validación de parámetros con Pydantic integrada
- Documentación automática en `/docs` (útil para depuración)
- Async nativo para no bloquear mientras espera respuesta de Odoo
- Fácil de desplegar con uvicorn + systemd en el VPS

### Por qué MCP Streamable HTTP y no stdio

El transporte `stdio` solo funciona para procesos locales. Heinzbot es una app Android remota que necesita conectarse via HTTP. El transporte Streamable HTTP (spec MCP 2025-03-26) usa un único endpoint POST con respuestas síncronas o SSE según el cliente.

### Por qué el servidor MCP usa puerto 8001 (no 8069 de Odoo)

Evitar interferencias. Nginx rutea en el VPS:
- `https://heinzsport.com/...` → Odoo :443 (ya configurado)
- `https://mcp.heinzsport.com/...` (o subdomain) → MCP server :8001

### Audit log: JSON Lines en archivo

Para fase 1, un archivo JSON Lines es suficiente:
- Sin dependencia de base de datos extra
- Fácil inspección con `jq` o importar a Excel
- `tail -f audit.jsonl` para monitoreo en tiempo real
- Rotación con `logrotate` del sistema operativo

## Configuración de Nginx (referencia para VPS)

```nginx
server {
    listen 443 ssl;
    server_name mcp.heinzsport.com;   # o un path en el mismo dominio

    ssl_certificate /etc/letsencrypt/live/heinzsport.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/heinzsport.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;   # necesario para SSE (fase 2)
        proxy_cache off;
    }
}
```

## Modelo de datos relevante en Odoo

```
product.product          ─── producto con variante (SKU / código interno)
    └── product.template ─── plantilla del producto

stock.quant              ─── cantidad de stock (por producto + ubicación + lote)
    ├── product_id       → product.product
    ├── location_id      → stock.location
    ├── quantity         ─── cantidad física
    └── reserved_quantity

stock.location           ─── ubicación física
    └── usage            ─── 'internal' | 'supplier' | 'customer' | 'inventory'

stock.warehouse          ─── almacén
    └── lot_stock_id     → stock.location (ubicación raíz del stock)

stock.warehouse.orderpoint  ─── regla de reorden (mínimos de stock)
    ├── product_id       → product.product
    ├── product_min_qty  ─── mínimo configurado
    └── qty_on_hand      ─── stock actual (campo computed)

mrp.production           ─── orden de producción
    ├── name             ─── número (MO/2025/0001)
    ├── state            ─── 'draft' | 'confirmed' | 'progress' | 'done' | 'cancel'
    ├── reservation_state ── 'confirmed' | 'assigned' | 'partially_available'
    └── date_planned_start

purchase.order           ─── orden de compra
    ├── name             ─── número (PO/2025/0001)
    ├── partner_id       → res.partner (proveedor — supplier_rank > 0)
    ├── state            ─── 'draft' | 'purchase' | 'done' | 'cancel'
    └── order_line       → purchase.order.line[]
```
