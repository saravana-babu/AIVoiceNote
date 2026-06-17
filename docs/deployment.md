# VoiceMind AI Production Deployment Guide

This guide describes how to configure, deploy, and maintain the VoiceMind AI application on a single DigitalOcean Droplet with PostgreSQL + pgvector, Cloudflare R2, and Google Gemini.

---

## Droplet Specifications & Budget
* **Hosting Provider**: DigitalOcean
* **Operating System**: Ubuntu 24.04 LTS
* **Plan**: Basic Droplet
* **Resources**: 2 vCPU, 2 GB RAM, 60 GB SSD
* **Target Budget**: $18-$20/month

---

## 1. DigitalOcean Droplet Initial Setup

1. **Create the Droplet**:
   - Select **Ubuntu 24.04 LTS**.
   - Choose the Shared CPU, regular SSD option ($18/month regular 2GB Droplet).
   - Choose a region closest to your target users.
   - Add your SSH Key for access.

2. **Configure SSH Access**:
   Access the server via terminal:
   ```bash
   ssh root@your_droplet_ip
   ```

3. **System Update & Firewall Setup**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow ssh
   sudo ufw allow http
   sudo ufw allow https
   sudo ufw enable
   ```

---

## 2. Docker & Docker Compose Installation

Install Docker Engine and Docker Compose:

```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Ensure docker runs automatically:
```bash
sudo systemctl enable docker
sudo systemctl start docker
```

---

## 3. Cloudflare R2 Setup

1. Log in to your Cloudflare Dashboard and navigate to **R2**.
2. Click **Create Bucket**, name it `voicemind-audio`, and choose your region/location.
3. Generate R2 Credentials:
   - Navigate to **Manage R2 API Tokens**.
   - Click **Create API Token**.
   - Select **Edit** permissions. Set scope to your bucket.
   - Keep the generated **Access Key ID**, **Secret Access Key**, and the Cloudflare **Account ID** (visible in R2 dashboard).

---

## 4. Deploying the Application

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/AIVoiceNote.git /app/voicemind
   cd /app/voicemind
   ```

2. **Create Environment Configuration**:
   Copy the example environment template and populate it with production keys:
   ```bash
   cp .env.example .env
   nano .env
   ```
   Provide your:
   - `SECRET_KEY` (Generate with `openssl rand -hex 32`)
   - `POSTGRES_PASSWORD`
   - `GOOGLE_API_KEY` (Gemini API token)
   - `R2_*` (Cloudflare R2 details)
   - `SMTP_*` (SMTP notifications provider details)

3. **Deploy the Containers**:
   Execute the deployment automation script:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

---

## 5. SSL / HTTPS Configuration (Nginx + Let's Encrypt)

We terminate SSL using Let's Encrypt and Certbot on the host machine.

1. **Install Certbot**:
   ```bash
   sudo apt install -y certbot
   ```

2. **Temporary stop Nginx container** (if it's running) to free port 80:
   ```bash
   docker compose stop nginx
   ```

3. **Request Certificate**:
   Replace `yourdomain.com` with your actual domain name:
   ```bash
   sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com --agree-tos --email webmaster@yourdomain.com
   ```

4. **Mount Certificates**:
   Ensure the certificates path `/etc/letsencrypt/live/yourdomain.com/` matches the certificate parameters inside your `nginx/nginx.conf` file. (By default Nginx is configured to look in `/etc/letsencrypt/live/voicemind.ai/` - edit your `nginx/nginx.conf` path to match your domain).

5. **Restart Nginx**:
   ```bash
   docker compose start nginx
   ```

6. **Automatic SSL Certificate Renewal Setup**:
   Add a crontab entry to automatically renew SSL certificates:
   ```bash
   crontab -e
   # Add the following line to run renewal daily and reload nginx:
   0 3 * * * certbot renew --post-hook "docker compose exec -T nginx nginx -s reload"
   ```

---

## 6. Backup Strategy

Since SQLite is removed in favor of PostgreSQL, backups are performed using `pg_dump`.

### Daily Automated Backups script
Create a script `/app/voicemind/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/app/voicemind/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/voicemind_db_$TIMESTAMP.sql.gz"

echo "Creating database backup..."
docker compose exec -T db pg_dump -U postgres voicemind | gzip > "$BACKUP_FILE"

# Keep only the last 7 days of backups
find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +7 -delete

echo "Backup created: $BACKUP_FILE"
```

Configure cron to run the backup script daily:
```bash
chmod +x /app/voicemind/backup.sh
crontab -e
# Add the following line (runs at 2:00 AM daily):
0 2 * * * /app/voicemind/backup.sh
```

---

## 7. Restore Procedure

In the event of a server failure or data loss:

1. Identify the backup file you want to restore under `/app/voicemind/backups/`.
2. Stop the API container to avoid writes:
   ```bash
   docker compose stop api
   ```
3. Restore the database:
   ```bash
   gunzip -c /app/voicemind/backups/voicemind_db_YYYYMMDD_HHMMSS.sql.gz | docker compose exec -T db psql -U postgres -d voicemind
   ```
4. Start the API container:
   ```bash
   docker compose start api
   ```

---

## Troubleshooting

### Inspect Container Health:
```bash
docker compose ps
```

### View Live Backend Logs:
```bash
docker compose logs -f api
```

### Check Database Connectivity:
```bash
docker compose exec db pg_isready -U postgres -d voicemind
```
