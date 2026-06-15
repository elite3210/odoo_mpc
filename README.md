# odoo-mcp — Servidor MCP para Odoo 18

Servidor MCP (Model Context Protocol) que conecta **Heinzbot** (asistente conversacional Android) con **Odoo 18 Community** en un entorno de manufactura.

## Inicio rápido

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con los datos de tu instancia Odoo

# 3. Arrancar servidor
python -m uvicorn src.main:app --reload --port 8001

# 4. Health check
curl http://localhost:8001/health
```

## Documentación

- [`CLAUDE.md`](CLAUDE.md) — Guía para asistentes de IA (arquitectura, patrones, reglas)
- [`docs/PRD.md`](docs/PRD.md) — Requerimientos del producto e historias de usuario
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Diseño del sistema y decisiones técnicas
- [`docs/API_SPEC.md`](docs/API_SPEC.md) — Especificación de todas las herramientas MCP
- [`docs/ODOO_INTEGRATION.md`](docs/ODOO_INTEGRATION.md) — Patrones XML-RPC con Odoo 18

## Herramientas disponibles (Fase 1)

| Tool | Descripción |
|------|-------------|
| `get_stock_by_product` | Stock disponible de un producto |
| `get_low_stock_products` | Productos con stock bajo mínimo |
| `get_stock_by_warehouse` | Inventario completo de un almacén |
| `create_purchase_order` | Crear OC en borrador |
| `confirm_purchase_order` | Confirmar OC existente |
| `create_manufacturing_order` | Crear OP en borrador |
| `confirm_manufacturing_order` | Confirmar OP existente |

## Configurar en Heinzbot

### Primera vez

**1.** Obtener token personal (reemplaza con tus credenciales de Odoo):

```bash
curl -X POST https://www.heinzsport.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "tu@email.com", "password": "tu_password"}'
```

**2.** En Heinzbot → menú **Conectores** → agregar nuevo conector:
- **URL**: `https://www.heinzsport.com/mcp`
- **API Key**: `Bearer <token del paso anterior>`

### Renovar token (caduca cada 8 horas)

Cuando Heinzbot deje de responder sobre Odoo, el token expiró. Para renovarlo:

**1.** Ejecutar en Putty (SSH al VPS) o en cualquier terminal:

```bash
curl -X POST https://www.heinzsport.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "tu@email.com", "password": "tu_password"}'
```

**2.** Copiar el valor de `token` de la respuesta.

**3.** En Heinzbot → **Conectores** → **MCP Odoo** → editar → pegar `Bearer <nuevo_token>` en el campo **API Key**.

## Producción (VPS Hostinger)

El servidor corre como servicio systemd en `/opt/odoo-mcp`:

```bash
# Ver estado
systemctl status odoo-mcp

# Reiniciar
systemctl restart odoo-mcp

# Ver logs en tiempo real
journalctl -u odoo-mcp -f

# Actualizar código desde GitHub
cd /opt/odoo-mcp && git pull && systemctl restart odoo-mcp
```
