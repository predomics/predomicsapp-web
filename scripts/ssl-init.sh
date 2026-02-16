#!/usr/bin/env bash
# PredomicsApp — First-Time SSL Certificate Setup
#
# Solves the chicken-and-egg problem: NGINX needs certificates to start,
# but certbot needs NGINX running to complete the ACME challenge.
#
# Usage:
#   1. Set DOMAIN and CERTBOT_EMAIL in your .env file
#   2. Run: ./scripts/ssl-init.sh
#   3. Start the full stack: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
#
# For testing, pass --staging to use Let's Encrypt staging servers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# --------------------------------------------------------------------------
# Load .env
# --------------------------------------------------------------------------
if [ -f .env ]; then
    # shellcheck source=/dev/null
    set -a; source .env; set +a
fi

DOMAIN="${DOMAIN:?ERROR: Set DOMAIN in .env (e.g. predomics.example.com)}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:?ERROR: Set CERTBOT_EMAIL in .env}"
STAGING_FLAG=""

if [ "${1:-}" = "--staging" ]; then
    STAGING_FLAG="--staging"
    echo "Using Let's Encrypt STAGING servers (certificates will not be trusted)."
fi

CERTBOT_DIR="./certbot"
NGINX_CONF="./nginx/nginx.conf"

echo "=== SSL Certificate Setup ==="
echo "Domain: $DOMAIN"
echo "Email:  $CERTBOT_EMAIL"
echo ""

# --------------------------------------------------------------------------
# Step 1: Create dummy certificate so NGINX can start
# --------------------------------------------------------------------------
echo "[1/4] Creating temporary self-signed certificate..."
LIVE_DIR="${CERTBOT_DIR}/conf/live/${DOMAIN}"
mkdir -p "$LIVE_DIR"

openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "${LIVE_DIR}/privkey.pem" \
    -out "${LIVE_DIR}/fullchain.pem" \
    -subj "/CN=${DOMAIN}" 2>/dev/null

echo "      Temporary certificate created."

# --------------------------------------------------------------------------
# Step 2: Update NGINX config with actual domain
# --------------------------------------------------------------------------
echo "[2/4] Configuring NGINX for ${DOMAIN}..."
if grep -q '\${DOMAIN:-localhost}' "$NGINX_CONF" 2>/dev/null; then
    sed -i.bak "s/\${DOMAIN:-localhost}/${DOMAIN}/g" "$NGINX_CONF"
    rm -f "${NGINX_CONF}.bak"
    echo "      NGINX config updated."
else
    echo "      NGINX config already configured (or using custom config)."
fi

# --------------------------------------------------------------------------
# Step 3: Start NGINX with the dummy certificate
# --------------------------------------------------------------------------
echo "[3/4] Starting NGINX..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx
echo "      Waiting for NGINX to be ready..."
sleep 3

# --------------------------------------------------------------------------
# Step 4: Request real certificate from Let's Encrypt
# --------------------------------------------------------------------------
echo "[4/4] Requesting Let's Encrypt certificate..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm certbot \
    certbot certonly --webroot \
    -w /var/www/certbot \
    --email "$CERTBOT_EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN" \
    $STAGING_FLAG

# --------------------------------------------------------------------------
# Reload NGINX with the real certificate
# --------------------------------------------------------------------------
echo ""
echo "Reloading NGINX with the real certificate..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload

echo ""
echo "=== SSL setup complete ==="
echo ""
echo "Your certificate is ready. Start the full stack with:"
echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
