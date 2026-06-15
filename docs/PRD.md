# PRD — Servidor MCP para Odoo 18

## Visión del producto

Permitir que Heinzbot (asistente conversacional Android con LLM) consulte y opere el ERP Odoo 18 Community mediante conversación natural, habilitando a la gerencia de la empresa de manufactura para tomar decisiones rápidas sin navegar la interfaz web de Odoo.

## Contexto

| Elemento | Detalle |
|---------|---------|
| ERP | Odoo 18 Community — `https://www.heinzsport.com` (BD: `elite`) |
| Servidor | Hostinger VPS (Ubuntu), mismo donde corre Odoo |
| Cliente | Heinzbot — app Android con soporte multi-LLM (DeepSeek, Claude, Gemini, ChatGPT) |
| Conexión Heinzbot | Menú "Conectores" → URL del servidor + JWT personal como API Key |
| Usuario principal | Gerencia / Directivos de la empresa |
| Giro | Manufactura y producción |
| Módulos activos | MRP, Inventario, Ventas, Contabilidad |

## Problema que resuelve

La gerencia necesita consultar estado de inventario, producción y órdenes en tiempo real sin depender de reportes programados ni de abrir Odoo manualmente. Además, quieren poder iniciar documentos (órdenes de compra, órdenes de producción) desde el chat sin perder contexto de la conversación.

## Modelo de autenticación

Cada usuario de Heinzbot usa sus propias credenciales de Odoo:

1. El usuario llama `POST /auth/login` con su email y contraseña de Odoo
2. El servidor verifica contra Odoo y emite un JWT personal (válido 8 horas)
3. El usuario configura ese JWT como "API Key" en el conector de Heinzbot
4. Todas las operaciones en Odoo se ejecutan con los permisos reales de ese usuario

Esto garantiza trazabilidad y que el sistema de permisos nativo de Odoo se respete.

## Usuarios y roles

### Gerente General / Director
- Consulta inventario y estado de producción
- Toma decisiones de reabastecimiento
- Confirma órdenes urgentes desde el chat

### Jefe de Producción (fase futura)
- Crea y gestiona órdenes de producción
- Consulta disponibilidad de materias primas

## Historias de usuario — Fase 1

### US-01: Consulta de stock por producto
**Como** gerente, **quiero** preguntarle a Heinzbot "¿cuánto stock tenemos de [producto]?" **para** saber si puedo aceptar un pedido.

**Criterios de aceptación:**
- Retorna cantidad disponible por ubicación y total
- Si el producto no existe, indica claramente
- Respuesta en menos de 3 segundos

### US-02: Alerta de productos bajo mínimo
**Como** gerente, **quiero** preguntar "¿qué productos están por agotarse?" **para** planificar compras.

**Criterios de aceptación:**
- Lista productos donde `qty_on_hand < product_min_qty` (en `stock.warehouse.orderpoint`)
- Incluye: producto, stock actual, stock mínimo, estado (AGOTADO o déficit)
- Si no hay productos críticos, lo indica

### US-03: Stock por almacén
**Como** gerente, **quiero** ver el stock de un almacén específico **para** evaluar capacidad de producción.

**Criterios de aceptación:**
- Lista de productos con cantidad disponible
- Filtrable por nombre del almacén
- Máximo 50 resultados

### US-04: Crear orden de compra
**Como** gerente, **quiero** crear una OC desde el chat **para** iniciar el proceso de compra sin abrir Odoo.

**Criterios de aceptación:**
- OC creada en estado borrador
- Retorna número de OC (ej: PO/2025/0087)
- Registrado en audit log con email del usuario
- Valida que proveedor y producto existan en Odoo

### US-05: Confirmar orden de compra
**Como** gerente, **quiero** confirmar una OC desde el chat.

**Criterios de aceptación:**
- Solo confirma OCs en estado borrador
- Retorna estado resultante
- Registrado en audit log

### US-06: Crear orden de producción
**Como** jefe de producción, **quiero** crear una OP desde Heinzbot.

**Criterios de aceptación:**
- Requiere: producto, cantidad, fecha programada (opcional)
- OP creada en borrador
- Lista de materiales asignada automáticamente si existe una BOM
- Registrado en audit log

### US-07: Confirmar orden de producción
**Como** jefe de producción, **quiero** confirmar una OP para reservar materiales.

**Criterios de aceptación:**
- Solo confirma OPs en borrador
- Indica disponibilidad de materiales (assigned / insufficient)
- Registrado en audit log

## Herramientas MCP — Fase 1

| Tool name | Tipo | US |
|-----------|------|----|
| `get_stock_by_product` | Lectura | US-01 |
| `get_low_stock_products` | Lectura | US-02 |
| `get_stock_by_warehouse` | Lectura | US-03 |
| `create_purchase_order` | Escritura | US-04 |
| `confirm_purchase_order` | Escritura | US-05 |
| `create_manufacturing_order` | Escritura | US-06 |
| `confirm_manufacturing_order` | Escritura | US-07 |

## Requerimientos no funcionales

| Atributo | Requerimiento |
|---------|--------------|
| Latencia | < 3 segundos para lectura |
| Seguridad | JWT por usuario + HTTPS obligatorio en producción |
| Audit | Toda escritura registrada en `audit.jsonl` con timestamp, tool, args, user_email y resultado |
| Disponibilidad | Error claro si Odoo no responde (no caída del servidor MCP) |
| Límites | Máximo 50 registros por consulta de listado |
| Auth | Token JWT caduca en 8 horas; requiere nuevo login para renovar |

## Fuera de alcance — Fase 1

- Interfaz web de administración
- Notificaciones push / SSE streaming
- Integración contabilidad (facturas, pagos)
- Multi-tenant (múltiples BDs Odoo)
- Gestión de usuarios desde el chat

## Fase 2 (backlog)

- KPIs gerenciales: ventas del mes, eficiencia de producción, cuentas por cobrar
- Consulta y creación de facturas
- Estado de entregas / guías de remisión
- Panel web de auditoría
- SSE streaming para respuestas largas

## Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Credenciales Odoo en el JWT | JWT firmado con `JWT_SECRET` + HTTPS obligatorio + tokens de 8h |
| Odoo caído bloquea respuestas | Timeout en XML-RPC + mensajes de error descriptivos |
| LLM envía parámetros incorrectos | Validación en cada tool antes de llamar a Odoo |
| Token comprometido | Rotación del `JWT_SECRET` invalida todos los tokens activos |
