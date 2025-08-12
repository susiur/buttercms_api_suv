# 🧸 Guía de Nannyfy API - ButterCMS Integration

Esta guía explica cómo funciona la API moderna de **Nannyfy** construida con FastAPI, que actúa como puente (proxy) y renderer HTML para nuestro blog de cuidado infantil.

## 1) 🎯 ButterCMS: Conceptos y API

ButterCMS es nuestro CMS headless con una API REST robusta.

- **Base URL**: `https://api.buttercms.com`
- **Versión**: `v2`
- **Autenticación**: querystring `auth_token=<TU_TOKEN>` en cada petición
- **Respuestas**: JSON estructurado
- **Paginación**: parámetros `page` (1..n) y `page_size` (ej: 10, 20)

### Endpoints principales para blog:

#### Lista de posts
```
GET /v2/posts/
```
- **Parámetros**: `page`, `page_size`, `exclude_body=1`, filtros por categorías
- **Respuesta**: `{ data: [...posts], meta: { next_page, previous_page } }`

#### Detalle de post
```
GET /v2/posts/{slug}/
```
- **Respuesta**: `{ data: { title, slug, body, published, ... } }`

#### Páginas por tipo
```
GET /v2/pages/{page_type}/?slug=...
```

### 🔧 Observaciones técnicas:

- ButterCMS redirige (HTTP 301) cuando falta `/` final; usamos `follow_redirects`
- Respetamos cabeceras de caché: `Cache-Control`, `ETag`, `Last-Modified`, `Expires`
- Documentación oficial: https://buttercms.com/docs/api/

## 2) 🚀 API Nannyfy (FastAPI)

Esta API hace dos cosas:

1. Proxy 1:1 a la API de ButterCMS bajo `/v2/*`, inyectando tu `auth_token` automáticamente desde la variable de entorno `BUTTER_API_TOKEN`.
2. Render HTML sencillo para `/blog` y `/blog/{slug}` para tener una vista básica del blog sin frontend aparte.

### Configuración

- `BUTTER_API_TOKEN` debe estar presente en el entorno (o via systemd EnvironmentFile).
- CORS está abierto (`*`) por simplicidad.

### Cliente HTTP

- Se usa `httpx.AsyncClient` con `base_url=https://api.buttercms.com` y `follow_redirects=true`.
- Tiempo de espera: 20s connect/ 30s read.
- Los parámetros de consulta entrantes se copian, excepto `auth_token` (se omite para evitar sobreescrituras maliciosas), y se añade el token del entorno.

### Rutas expuestas

- `GET /health`

  - Respuesta: `{ "status": "ok" }` para chequeos de vida.

- `GET /v2/posts`

  - Proxy directo a `GET https://api.buttercms.com/v2/posts/` (con slash final) + query params entrantes + `auth_token` del entorno.
  - Responde JSON de ButterCMS tal cual.
  - Copia cabeceras de caché relevantes del upstream.

- `GET /v2/posts/{slug}`

  - Proxy a `GET .../v2/posts/{slug}/`.

- `GET /v2/pages/{page_type}`

  - Proxy a `GET .../v2/pages/{page_type}/`.

- `GET /v2/pages/{page_type}/{slug}`

  - Convierte el patrón a `GET .../v2/pages/{page_type}/?slug={slug}` (ButterCMS espera `slug` como query en pages).

- `GET /` -> HTML mínimo con enlace a `/blog`.

- `GET /blog`

  - Llama a `GET .../v2/posts/` con paginación (`page`, `page_size`).
  - Renderiza una grilla de tarjetas con título, fecha y resumen.
  - Incluye paginador con `previous_page` y `next_page`.

- `GET /blog/{slug}`
  - Llama a `GET .../v2/posts/{slug}/` y renderiza el contenido (campo `body`) como HTML.

### Cabeceras de caché

La app copia desde Butter las cabeceras `Cache-Control`, `ETag`, `Last-Modified`, `Expires` cuando están presentes, de modo que un CDN o navegador pueda aprovecharlas.

### Errores comunes y soluciones

- 301 Moved Permanently: añade barra final al endpoint o confía en `follow_redirects` (ya activado).
- 401/403: revisa `BUTTER_API_TOKEN`.
- 5xx: problemas temporales de upstream; reintenta y/o añade un backoff en el cliente que consuma esta API.

## 3) Ejemplos de consumo

- Listar posts (JSON):

```
GET http://<tu-host>/v2/posts?page=1&page_size=10
```

- Ver post (JSON):

```
GET http://<tu-host>/v2/posts/mi-slug
```

- Índice HTML:

```
GET http://<tu-host>/blog
```

- Post HTML:

```
GET http://<tu-host>/blog/mi-slug
```

## 4) Seguridad y despliegue

- Token sólo en el servidor (variable de entorno). El cliente nunca debería enviar `auth_token`.
- Para producción, considera Nginx delante y HTTPS con Let’s Encrypt.
- Si usas puerto 80 directamente, aplica `setcap` al binario de Python del venv o usa systemd como en el script de despliegue.
