#!/bin/bash
# VoiceMind AI Production Deployment Automation Script
set -e

echo "========================================================"
echo "Starting VoiceMind AI Production Deployment..."
echo "========================================================"

# 1. Pull latest code from Git
echo ">>> Pulling latest code from main branch..."
git pull origin main

# 2. Build and restart containers in detached mode
echo ">>> Building and starting services..."
docker-compose down
docker-compose up --build -d

# 3. Wait for Database to become healthy
echo ">>> Waiting for PostgreSQL database container to boot..."
until docker-compose exec -T db pg_isready -U postgres -d voicemind; do
  echo "Postgres is unavailable - sleeping for 2 seconds..."
  sleep 2
done
echo "PostgreSQL is healthy!"

# 4. Execute database migrations
echo ">>> Running database migrations..."
docker-compose exec -T api alembic upgrade head

# 5. Verify system health
echo ">>> Verifying health endpoints..."
sleep 3
# Call health check through local API port
HEALTH_RESP=$(docker-compose exec -T api curl -s http://localhost:8000/health)

if echo "$HEALTH_RESP" | grep -q '"status":"ok"'; then
  echo "========================================================"
  echo "SUCCESS: VoiceMind AI has been deployed successfully!"
  echo "========================================================"
else
  echo "========================================================"
  echo "WARNING: Health check failed or returned degraded."
  echo "Response: $HEALTH_RESP"
  echo "Check container logs using 'docker-compose logs'"
  echo "========================================================"
  exit 1
fi
