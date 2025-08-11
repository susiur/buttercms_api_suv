import os
import logging
from typing import Iterable, Tuple, Dict, List

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

# ========= Config =========
BUTTER_API_TOKEN = os.getenv("BUTTER_API_TOKEN", "").strip()
BUTTER_BASE_URL = "https://api.buttercms.com"
BUTTER_V2 = "/v2"
TIMEOUT = httpx.Timeout(20.0, read=30.0)

if not BUTTER_API_TOKEN:
    logging.warning("BUTTER_API_TOKEN no está definido. Configúralo en el entorno.")

# ========= App =========
app = FastAPI(title="Bookly ButterCMS Bridge", version="1.0.0")

# CORS abierto a todos (como pediste)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

client = httpx.AsyncClient(timeout=TIMEOUT, base_url=BUTTER_BASE_URL)
UPSTREAM_CACHE_HEADERS = {"cache-control", "etag", "last-modified", "expires"}


def _merge_query_params(original: Iterable[Tuple[str, str]]) -> Dict[str, List[str]]:
    merged: Dict[str, List[str]] = {}
    for k, v in original:
        if k.lower() == "auth_token":
            continue
        merged.setdefault(k, []).append(v)
    merged["auth_token"] = [BUTTER_API_TOKEN]
    return merged


def _copy_cache_headers(upstream_headers: httpx.Headers, response: Response):
    for h in UPSTREAM_CACHE_HEADERS:
        if h in upstream_headers:
            response.headers[h] = upstream_headers[h]


async def _proxy_get(
    path: str, params: Iterable[Tuple[str, str]], response: Response
) -> Response:
    qp = _merge_query_params(params)
    url = f"{BUTTER_V2}/{path.lstrip('/')}"
    upstream = await client.get(url, params=qp)
    _copy_cache_headers(upstream.headers, response)
    ctype = upstream.headers.get("content-type", "")
    response.status_code = upstream.status_code
    if "application/json" in ctype.lower():
        return Response(
            content=upstream.content,
            media_type="application/json",
            status_code=upstream.status_code,
        )
    return Response(
        content=upstream.text,
        media_type=ctype or "text/plain",
        status_code=upstream.status_code,
    )


# ========= Meta =========
@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# ========= Proxy ButterCMS (JSON 1:1) =========
@app.get("/v2/posts", tags=["posts"])
async def list_posts(request: Request, response: Response):
    return await _proxy_get("posts", request.query_params.multi_items(), response)


@app.get("/v2/posts/{slug}", tags=["posts"])
async def get_post(slug: str, request: Request, response: Response):
    return await _proxy_get(
        f"posts/{slug}", request.query_params.multi_items(), response
    )


@app.get("/v2/pages/{page_type}", tags=["pages"])
async def get_pages_by_type(page_type: str, request: Request, response: Response):
    return await _proxy_get(
        f"pages/{page_type}", request.query_params.multi_items(), response
    )


@app.get("/v2/pages/{page_type}/{slug}", tags=["pages"])
async def get_page_by_type_and_slug(
    page_type: str, slug: str, request: Request, response: Response
):
    items = list(request.query_params.multi_items())
    items.append(("slug", slug))
    return await _proxy_get(f"pages/{page_type}", items, response)


# ========= HTML sencillo para blogs =========
HTML_BASE_CSS = """
<style>
  :root { --bg:#0b0b10; --fg:#e9eef2; --muted:#9fb3c8; --card:#131722; --acc:#7aa2f7; }
  * { box-sizing: border-box; }
  body { background:var(--bg); color:var(--fg); margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, sans-serif; }
  a { color: var(--acc); text-decoration: none; }
  header { padding: 24px; border-bottom: 1px solid #1c2333; position: sticky; top: 0; background: rgba(11,11,16,0.8); backdrop-filter: blur(8px); }
  .wrap { max-width: 960px; margin: 0 auto; padding: 16px; }
  .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
  .card { background: var(--card); border: 1px solid #1c2333; border-radius: 14px; padding: 16px; }
  .title { font-size: 20px; margin: 0 0 6px; }
  .meta { color: var(--muted); font-size: 13px; margin-bottom: 8px; }
  .desc { color: #cdd6e3; font-size: 14px; line-height: 1.5; }
  nav.pager { display:flex; justify-content: space-between; gap: 12px; margin-top: 16px; }
  .btn { display:inline-block; padding: 10px 14px; border-radius: 10px; background:#1a2232; border:1px solid #273149; }
  .btn[disabled] { opacity:.4; pointer-events:none; }
  article { background: var(--card); border:1px solid #1c2333; border-radius: 14px; padding: 20px; }
  article h1 { font-size: 28px; margin: 0 0 12px; }
  .content { color: #cdd6e3; line-height: 1.7; }
  .content img { max-width: 100%; height: auto; border-radius:12px; }
  footer { color: var(--muted); font-size: 13px; text-align:center; padding: 24px; }
</style>
"""


def _html_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
{HTML_BASE_CSS}
</head>
<body>
<header><div class="wrap"><strong>Bookly Blog</strong></div></header>
<main class="wrap">{body}</main>
<footer>© Bookly • servido por FastAPI en EC2</footer>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, tags=["html"])
async def root():
    body = '<div class="card"><p>Hola 👋 Visita <a href="/blog">/blog</a> para ver las entradas.</p></div>'
    return HTMLResponse(_html_shell("Bookly", body))


@app.get("/blog", response_class=HTMLResponse, tags=["html"])
async def blog_index(request: Request):
    page = request.query_params.get("page", "1")
    page_size = request.query_params.get("page_size", "9")
    params = [("page", page), ("page_size", page_size)]
    qp = _merge_query_params(params)
    r = await client.get(f"{BUTTER_V2}/posts", params=qp)
    if r.status_code != 200:
        return PlainTextResponse(
            f"Error al cargar posts ({r.status_code})", status_code=r.status_code
        )
    data = r.json()
    posts = data.get("data", [])
    meta = data.get("meta", {}) or {}
    next_page = meta.get("next_page")
    previous_page = meta.get("previous_page")
    cards = []
    for p in posts:
        slug = p.get("slug", "")
        title = p.get("title", "Sin título")
        summary = p.get("summary") or ""
        published = (p.get("published") or "")[:10]
        cards.append(f"""
        <div class="card">
          <h2 class="title"><a href="/blog/{slug}">{title}</a></h2>
          <div class="meta">Publicado: {published}</div>
          <p class="desc">{summary}</p>
          <a class="btn" href="/blog/{slug}">Leer más</a>
        </div>
        """)
    grid = f'<div class="grid">{"".join(cards) or "<p>No hay posts.</p>"}</div>'
    try:
        curr = int(page)
    except Exception:
        curr = 1
    prev_q = f"?page={curr - 1}&page_size={page_size}" if previous_page else ""
    next_q = f"?page={curr + 1}&page_size={page_size}" if next_page else ""
    pager = f"""
    <nav class="pager">
      <a class="btn" {"disabled" if not previous_page else ""} href="/blog{prev_q}">← Anterior</a>
      <span style="align-self:center;color:#9fb3c8">Página {curr}</span>
      <a class="btn" {"disabled" if not next_page else ""} href="/blog{next_q}">Siguiente →</a>
    </nav>
    """
    body = grid + pager
    return HTMLResponse(_html_shell("Bookly • Blog", body))


@app.get("/blog/{slug}", response_class=HTMLResponse, tags=["html"])
async def blog_post(slug: str, request: Request):
    qp = _merge_query_params([])
    r = await client.get(f"{BUTTER_V2}/posts/{slug}", params=qp)
    if r.status_code != 200:
        return PlainTextResponse(
            f"Post no encontrado ({r.status_code})", status_code=r.status_code
        )
    post = r.json().get("data", {})
    title = post.get("title", "Sin título")
    published = (post.get("published") or "")[:10]
    body_html = post.get("body") or "<p>Sin contenido.</p>"
    html = f"""
    <article>
      <h1>{title}</h1>
      <div class="meta">Publicado: {published}</div>
      <div class="content">{body_html}</div>
      <p><a class="btn" href="/blog">← Volver</a></p>
    </article>
    """
    return HTMLResponse(_html_shell(f"Bookly • {title}", html))


@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()
