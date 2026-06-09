#!/usr/bin/env bash
# ============================================================================
# Mood-IoT — cloud-init pour VM Oracle Cloud Always Free (Ampere ARM A1)
#
# À coller dans "User data" lors de la création de la VM Oracle Cloud, ou à
# exécuter manuellement après SSH la 1re fois :
#     curl -fsSL https://raw.githubusercontent.com/<owner>/mood-iot/main/infrastructure/oracle/cloud-init.sh | sudo bash
#
# Idempotent : peut être rejoué sans casser l'install existante.
#
# Pré-requis VM :
#   - Ubuntu 22.04 ARM (Canonical-Ubuntu-22.04-aarch64)
#   - 4 OCPU + 24 GB RAM (Always Free tier)
#   - Volume boot 100 GB (Always Free tier)
#   - Security List ouverte : 22 (SSH), 80 (HTTP/ACME), 443 (HTTPS)
#
# Variables à customiser AVANT de lancer :
#   REPO_URL       = https://github.com/<owner>/mood-iot.git
#   APP_USER       = utilisateur Linux qui possède l'app (par défaut : ubuntu)
#   APP_DIR        = chemin de l'install (par défaut : /opt/mood-iot)
# ============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/CHANGE-ME/mood-iot.git}"
APP_USER="${APP_USER:-ubuntu}"
APP_DIR="${APP_DIR:-/opt/mood-iot}"

log() { printf "\033[1;34m[mood-iot]\033[0m %s\n" "$*"; }

# ── 1. Pré-requis système ───────────────────────────────────────────────────
log "Mise à jour APT + installation de Docker, git, ufw, fail2ban"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    ca-certificates curl gnupg lsb-release \
    git ufw fail2ban htop tmux jq

# ── 2. Docker Engine (officiel, pas le docker.io d'Ubuntu) ──────────────────
if ! command -v docker >/dev/null 2>&1; then
    log "Installation de Docker Engine"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor --batch --yes -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        | tee /etc/apt/sources.list.d/docker.list >/dev/null
    apt-get update -qq
    apt-get install -y -qq \
        docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
fi

# ── 3. User dans le groupe docker (pour utiliser docker sans sudo) ──────────
usermod -aG docker "$APP_USER" || true

# ── 4. Firewall UFW (en complément du Security List Oracle) ─────────────────
log "Configuration UFW : 22, 80, 443"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ── 5. Fail2ban pour SSH ────────────────────────────────────────────────────
log "Activation de fail2ban"
systemctl enable --now fail2ban

# ── 6. Swap 4 GB (Ubuntu cloud images n'en ont pas par défaut) ──────────────
if [ ! -f /swapfile ]; then
    log "Création swap 4 GB"
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab >/dev/null
fi

# ── 7. Clonage du repo ──────────────────────────────────────────────────────
if [ ! -d "$APP_DIR" ]; then
    log "Clonage du repo dans $APP_DIR"
    install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR"
    sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
else
    log "Repo déjà présent, git pull"
    sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only || true
fi

# ── 8. .env.prod template (l'utilisateur le complète avant le 1er up) ──────
if [ ! -f "$APP_DIR/.env.prod" ]; then
    log "Création de $APP_DIR/.env.prod depuis le template"
    cp "$APP_DIR/.env.example" "$APP_DIR/.env.prod"
    chown "$APP_USER":"$APP_USER" "$APP_DIR/.env.prod"
    chmod 600 "$APP_DIR/.env.prod"
    cat <<'WARN'

    ████████████████████████████████████████████████████████████████████
    ⚠  .env.prod créé avec valeurs par défaut.
        ÉDITEZ-LE AVANT le premier `docker compose up` :
            nano /opt/mood-iot/.env.prod
        Champs CRITIQUES à remplacer :
            POSTGRES_PASSWORD           → générer 32 chars random
            JWT_SECRET_KEY              → générer 32 chars random
            ENCRYPTION_KEY              → Fernet.generate_key()
            KC_BOOTSTRAP_ADMIN_PASSWORD → mot de passe admin Keycloak
            ANTHROPIC_API_KEY           → votre clé Claude
            RESEND_API_KEY              → votre clé Resend
            KEYCLOAK_HOSTNAME           → auth.mood-iot.fr
    ████████████████████████████████████████████████████████████████████

WARN
fi

# ── 9. Pull/build des images (ne pas démarrer tant que .env.prod pas prêt) ─
log "Pré-build des images Docker (peut prendre 5-10 min sur ARM)"
sudo -u "$APP_USER" docker compose \
    -f "$APP_DIR/docker-compose.prod.yml" \
    --env-file "$APP_DIR/.env.prod" \
    build || log "Build en erreur — vérifiez .env.prod puis : docker compose -f docker-compose.prod.yml build"

# ── 10. Unattended upgrades (security only) ─────────────────────────────────
log "Activation des mises à jour de sécurité automatiques"
apt-get install -y -qq unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# ── 11. Service systemd pour relancer docker compose au reboot ──────────────
cat > /etc/systemd/system/mood-iot.service <<UNIT
[Unit]
Description=Mood-IoT (docker compose prod stack)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml --env-file .env.prod down
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable mood-iot.service

log "═══════════════════════════════════════════════════════════════════"
log "Bootstrap terminé."
log ""
log "  1) Éditez : nano $APP_DIR/.env.prod"
log "  2) Démarrez : sudo systemctl start mood-iot"
log "  3) Suivez les logs : docker compose -f $APP_DIR/docker-compose.prod.yml logs -f"
log ""
log "Surveillance santé : curl -fsS http://localhost/health (ou api.mood-iot.fr)"
log "═══════════════════════════════════════════════════════════════════"
