#!/usr/bin/env bash
set -euo pipefail

APP_NAME="nannyfy"
APP_DIR="/opt/${APP_NAME}"
PY_ENV="${APP_DIR}/venv"
APP_FILE="${APP_DIR}/app.py"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"

# --- Comprobaciones ---
if [[ $EUID -ne 0 ]]; then
  echo "Por favor, ejecútalo con sudo o como root."
  exit 1
fi

# --- Input token ---
read -rp "Ingresa tu BUTTER_API_TOKEN: " BUTTER_API_TOKEN
if [[ -z "${BUTTER_API_TOKEN}" ]]; then
  echo "BUTTER_API_TOKEN es obligatorio."
  exit 1
fi

# --- Paquetes base ---
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-venv python3-pip ca-certificates curl jq libcap2-bin

# --- Crear usuario de sistema (sin login) ---
if ! id -u "${APP_NAME}" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_NAME}"
fi

# --- Crear estructura ---
mkdir -p "${APP_DIR}"
chown -R "${APP_NAME}:${APP_NAME}" "${APP_DIR}"

# --- Colocar app.py si no existe ---
if [[ ! -f "${APP_FILE}" ]]; then
  cat > "${APP_FILE}" <<'PYCODE'
REPLACE_APP_PY
PYCODE
  # Reemplazo posterior del marcador
fi

# --- Crear venv e instalar dependencias (últimas estables) ---
python3 -m venv "${PY_ENV}"
source "${PY_ENV}/bin/activate"
pip install --upgrade pip
pip install "fastapi" "uvicorn[standard]" "httpx"

# --- Permitir bind a puerto 80 sin root ---
# Damos capacidad al binario de Python del venv para puertos <1024
setcap 'cap_net_bind_service=+ep' "${PY_ENV}/bin/python3" || true

# --- Variables de entorno del servicio ---
ENV_FILE="${APP_DIR}/.env"
cat > "${ENV_FILE}" <<EOF
BUTTER_API_TOKEN=${BUTTER_API_TOKEN}
EOF
chown "${APP_NAME}:${APP_NAME}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

# --- Systemd service ---
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Nannyfy FastAPI (ButterCMS bridge)
After=network.target

[Service]
User=${APP_NAME}
Group=${APP_NAME}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${PY_ENV}/bin/uvicorn app:app --host 0.0.0.0 --port 80 --workers 2
Restart=on-failure
RestartSec=3

# Seguridad básica
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

if grep -q "REPLACE_APP_PY" "${APP_FILE}"; then
  echo "Actualizando app.py..."
  cat > "${APP_FILE}" <<'PYFALLBACK'
import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def hi():
    return {"msg": "Sube tu app.py. Falta contenido."}
PYFALLBACK
fi

# --- Abrir firewall (si usa UFW) ---
if command -v ufw >/dev/null 2>&1; then
  ufw allow 80/tcp || true
fi

# --- Recargar y arrancar ---
systemctl daemon-reload
systemctl enable "${APP_NAME}"
systemctl restart "${APP_NAME}"

# --- Mostrar estado y URL ---
PUB_IP=$(curl -s http://checkip.amazonaws.com || echo "TU_IP_PUBLICA")
echo
echo "========================================"
echo "🧸 Nannyfy desplegado correctamente!"
echo "Servicio: ${APP_NAME}"
echo "Estado: "
systemctl --no-pager --full status "${APP_NAME}" | sed -n '1,12p' || true
echo
echo "🌐 Prueba en:  http://${PUB_IP}/blog"
echo "❤️ Healthcheck: http://${PUB_IP}/health"
echo "🏠 Inicio: http://${PUB_IP}/"
echo "========================================"
