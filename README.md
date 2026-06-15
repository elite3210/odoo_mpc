# odoo-mcp — Servidor MCP para Odoo 18

Servidor MCP (Model Context Protocol) que conecta **Heinzbot** (asistente conversacional Android) con **Odoo 18 Community** en un entorno de manufactura.

## Inicio rápido

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con los datos de tu instancia Odoo

# 3. Verificar conexión a Odoo
python -c "from src.odoo.client import odoo; print(odoo.test_connection())"

# 4. Arrancar servidor
uvicorn src.main:app --reload --port 8001

# 5. Health check
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

En el menú **Conectores** de Heinzbot:
- **URL**: `https://tu-dominio.com/mcp`
- **API Key**: el valor de `MCP_API_KEY` en tu `.env`
