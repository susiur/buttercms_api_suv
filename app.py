import logging
from typing import Iterable, Tuple, Dict, List

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from config import settings

# ========= Config =========
BUTTER_API_TOKEN = settings.get_butter_token() or ""
BUTTER_BASE_URL = settings.BUTTER_BASE_URL
BUTTER_V2 = settings.BUTTER_V2
TIMEOUT = httpx.Timeout(settings.REQUEST_TIMEOUT, read=settings.READ_TIMEOUT)

if not BUTTER_API_TOKEN:
    logging.warning("BUTTER_API_TOKEN no está definido. Configúralo en el entorno.")

# ========= App =========
app = FastAPI(
    title=settings.APP_TITLE, 
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION
)

# CORS abierto a todos (como pediste)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_headers=settings.ALLOWED_HEADERS,
    allow_methods=settings.ALLOWED_METHODS,
)

# Seguir redirecciones (evita 301 por slash final)
client = httpx.AsyncClient(
    timeout=TIMEOUT, base_url=BUTTER_BASE_URL, follow_redirects=True
)
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
    # Normaliza con slash final para evitar 301
    norm = path.lstrip("/").rstrip("/") + "/"
    url = f"{BUTTER_V2}/{norm}"
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
  :root { 
    --bg: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --card-bg: rgba(255, 255, 255, 0.95);
    --text: #2d3748;
    --text-muted: #718096;
    --accent: #4299e1;
    --accent-hover: #3182ce;
    --border: rgba(160, 174, 192, 0.2);
    --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  }
  * { box-sizing: border-box; }
  body { 
    background: var(--bg);
    color: var(--text);
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.6;
    min-height: 100vh;
  }
  a { 
    color: var(--accent); 
    text-decoration: none; 
    transition: color 0.2s ease;
  }
  a:hover { color: var(--accent-hover); }
  
  header { 
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border);
    position: sticky; 
    top: 0; 
    z-index: 100;
    box-shadow: var(--shadow);
  }
  
  .header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  
  .logo {
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  
  .nav-links {
    display: flex;
    gap: 24px;
    align-items: center;
  }
  
  .nav-links a {
    font-weight: 500;
    padding: 8px 16px;
    border-radius: 8px;
    transition: all 0.2s ease;
  }
  
  .nav-links a:hover {
    background: var(--accent);
    color: white;
  }
  
  .wrap { 
    max-width: 1200px; 
    margin: 0 auto; 
    padding: 32px 24px; 
  }
  
  .hero {
    text-align: center;
    padding: 60px 0;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    margin-bottom: 40px;
    backdrop-filter: blur(10px);
  }
  
  .hero h1 {
    font-size: 48px;
    font-weight: 800;
    margin: 0 0 16px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  
  .hero p {
    font-size: 20px;
    color: var(--text-muted);
    margin: 0;
  }
  
  .grid { 
    display: grid; 
    gap: 24px; 
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); 
  }
  
  .card { 
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    box-shadow: var(--shadow);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }
  
  .card:hover {
    transform: translateY(-2px);
    box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
  }
  
  .title { 
    font-size: 22px; 
    font-weight: 700;
    margin: 0 0 12px;
    line-height: 1.3;
  }
  
  .meta { 
    color: var(--text-muted); 
    font-size: 14px; 
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .meta::before {
    content: "📅";
  }
  
  .desc { 
    color: var(--text); 
    font-size: 16px; 
    line-height: 1.6;
    margin-bottom: 20px;
  }
  
  nav.pager { 
    display: flex; 
    justify-content: space-between; 
    align-items: center;
    gap: 16px; 
    margin-top: 40px;
    padding: 20px 0;
  }
  
  .btn { 
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 24px; 
    border-radius: 12px; 
    background: var(--accent);
    color: white;
    border: none;
    font-weight: 600;
    font-size: 14px;
    transition: all 0.2s ease;
    cursor: pointer;
  }
  
  .btn:hover {
    background: var(--accent-hover);
    transform: translateY(-1px);
    color: white;
  }
  
  .btn[disabled] { 
    opacity: 0.5; 
    pointer-events: none;
    transform: none;
  }
  
  .btn.secondary {
    background: rgba(255, 255, 255, 0.9);
    color: var(--accent);
    border: 1px solid var(--border);
  }
  
  .btn.secondary:hover {
    background: white;
    color: var(--accent-hover);
  }
  
  article { 
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 40px;
    box-shadow: var(--shadow);
    margin-bottom: 24px;
  }
  
  article h1 { 
    font-size: 36px; 
    font-weight: 800;
    margin: 0 0 20px;
    line-height: 1.2;
  }
  
  .content { 
    color: var(--text); 
    line-height: 1.8;
    font-size: 16px;
  }
  
  .content img { 
    max-width: 100%; 
    height: auto; 
    border-radius: 12px;
    margin: 20px 0;
    box-shadow: var(--shadow);
  }
  
  .content h2 {
    font-size: 24px;
    font-weight: 700;
    margin: 32px 0 16px;
    color: var(--text);
  }
  
  .content h3 {
    font-size: 20px;
    font-weight: 600;
    margin: 24px 0 12px;
    color: var(--text);
  }
  
  .content p {
    margin: 16px 0;
  }
  
  .content blockquote {
    border-left: 4px solid var(--accent);
    padding-left: 20px;
    margin: 24px 0;
    font-style: italic;
    color: var(--text-muted);
  }
  
  footer { 
    background: rgba(255, 255, 255, 0.9);
    color: var(--text-muted); 
    font-size: 14px; 
    text-align: center; 
    padding: 40px 24px;
    margin-top: 60px;
    border-top: 1px solid var(--border);
  }
  
  .page-indicator {
    background: rgba(255, 255, 255, 0.9);
    padding: 8px 16px;
    border-radius: 20px;
    font-weight: 600;
    border: 1px solid var(--border);
  }
  
  @media (max-width: 768px) {
    .hero h1 { font-size: 32px; }
    .hero p { font-size: 18px; }
    .grid { grid-template-columns: 1fr; }
    .nav-links { display: none; }
    article { padding: 24px; }
    .wrap { padding: 20px 16px; }
  }
</style>
"""


def _html_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang=\"es\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
{HTML_BASE_CSS}
</head>
<body>
<header>
  <div class=\"header-content\">
    <div class=\"logo\">🧸 Nannyfy</div>
    <nav class=\"nav-links\">
      <a href=\"/\">Inicio</a>
      <a href=\"/blog\">Blog</a>
    </nav>
  </div>
</header>
<main class=\"wrap\">{body}</main>
<footer>© 2025 Nannyfy • Tu plataforma de cuidado infantil de confianza • Powered by FastAPI</footer>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, tags=["html"])
async def root():
    body = '''
    <div class="hero">
      <h1>🧸 Bienvenido a Nannyfy</h1>
      <p>Tu plataforma de confianza para encontrar el cuidado infantil perfecto</p>
    </div>
    <div class="grid">
      <div class="card">
        <h2 class="title">🏠 Cuidado en Casa</h2>
        <p class="desc">Niñeras profesionales y verificadas que cuidan a tus hijos en la comodidad de tu hogar.</p>
        <a class="btn" href="/blog">Conoce más</a>
      </div>
      <div class="card">
        <h2 class="title">📚 Blog de Consejos</h2>
        <p class="desc">Artículos especializados sobre crianza, desarrollo infantil y consejos para padres.</p>
        <a class="btn" href="/blog">Leer artículos</a>
      </div>
      <div class="card">
        <h2 class="title">✅ Servicios Verificados</h2>
        <p class="desc">Todos nuestros cuidadores pasan por un riguroso proceso de verificación y capacitación.</p>
        <a class="btn secondary" href="/blog">Descubre cómo</a>
      </div>
    </div>
    '''
    return HTMLResponse(_html_shell("Nannyfy - Cuidado Infantil de Confianza", body))


@app.get("/blog", response_class=HTMLResponse, tags=["html"])
async def blog_index(request: Request):
    page = request.query_params.get("page", "1")
    page_size = request.query_params.get("page_size", "9")
    params = [("page", page), ("page_size", page_size)]
    qp = _merge_query_params(params)
    # Asegura slash final para evitar 301
    r = await client.get(f"{BUTTER_V2}/posts/", params=qp)
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
        <div class=\"card\">
          <h2 class=\"title\"><a href=\"/blog/{slug}\">{title}</a></h2>
          <div class=\"meta\">Publicado el {published}</div>
          <p class=\"desc\">{summary}</p>
          <a class=\"btn\" href=\"/blog/{slug}\">📖 Leer artículo</a>
        </div>
        """)
    grid = f'<div class="grid">{"".join(cards) or "<div class=\"card\"><h2 class=\"title\">📝 No hay artículos disponibles</h2><p class=\"desc\">Pronto tendremos contenido interesante sobre cuidado infantil.</p></div>"}</div>'
    try:
        curr = int(page)
    except Exception:
        curr = 1
    prev_q = f"?page={curr - 1}&page_size={page_size}" if previous_page else ""
    next_q = f"?page={curr + 1}&page_size={page_size}" if next_page else ""
    pager = f"""
    <nav class=\"pager\">
      <a class=\"btn\" {"disabled" if not previous_page else ""} href=\"/blog{prev_q}\">← Anterior</a>
      <span class=\"page-indicator\">Página {curr}</span>
      <a class=\"btn\" {"disabled" if not next_page else ""} href=\"/blog{next_q}\">Siguiente →</a>
    </nav>
    """
    body = grid + pager
    return HTMLResponse(_html_shell("Nannyfy • Blog de Crianza y Cuidado Infantil", body))


@app.get("/blog/{slug}", response_class=HTMLResponse, tags=["html"])
async def blog_post(slug: str, request: Request):
    qp = _merge_query_params([])
    # Asegura slash final para evitar 301
    r = await client.get(f"{BUTTER_V2}/posts/{slug}/", params=qp)
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
      <div class=\"meta\">📅 Publicado el {published}</div>
      <div class=\"content\">{body_html}</div>
      <p><a class=\"btn secondary\" href=\"/blog\">← Volver al blog</a></p>
    </article>
    """
    return HTMLResponse(_html_shell(f"Nannyfy • {title}", html))


@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()
