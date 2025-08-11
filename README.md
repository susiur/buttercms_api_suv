# Bookly ButterCMS Bridge (FastAPI)

Pequeño proxy/renderer para ButterCMS con FastAPI. Expone endpoints `/v2/*` compatibles y rutas HTML `/blog` y `/blog/{slug}`.

## Requisitos locales

- Python 3.10+
- pip

## Desarrollo local

1. Crear venv e instalar dependencias

```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
```

2. Exportar variable y arrancar

```bash
$env:BUTTER_API_TOKEN="tu_token"
uvicorn app:app --reload --port 8000
```

3. Probar

- http://localhost:8000/health
- http://localhost:8000/blog

## Despliegue en EC2 (puerto 80 con systemd)

1. Copia `setup_bookly.sh` y `app.py` al servidor (Ubuntu/Debian).
2. Ejecuta como root:

```bash
chmod +x setup_bookly.sh
sudo ./setup_bookly.sh
```

El script:

- Crea usuario de sistema `bookly`.
- Crea venv en `/opt/bookly/venv`.
- Instala FastAPI, Uvicorn, httpx.
- Configura systemd para arrancar en el puerto 80 sin root (setcap).
- Arranca y muestra estado.

Nota: para HTTPS y mejor flexibilidad, usa Nginx + Let’s Encrypt y deja Uvicorn en 8000.

## Variables de entorno

- `BUTTER_API_TOKEN`: token de ButterCMS. Puedes usar `.env` en el server vía systemd `EnvironmentFile`.

## Licencia

MIT
