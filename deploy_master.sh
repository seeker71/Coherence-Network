#!/bin/bash

################################################################################
# Coherence Network - Automated Deployment Master Script
# For Mac M4 Ultra with coherencycoin.com domain
# Cost: $0/month using free tiers
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration file
CONFIG_FILE=".deployment_config"

################################################################################
# PHASE 0: Prerequisites Check
################################################################################

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing=()
    
    # Check for required tools
    command -v git >/dev/null 2>&1 || missing+=("git")
    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v curl >/dev/null 2>&1 || missing+=("curl")
    command -v jq >/dev/null 2>&1 || missing+=("jq")
    
    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing[*]}"
        log_info "Install with: brew install ${missing[*]}"
        exit 1
    fi
    
    # Check if in git repo
    if [ ! -d ".git" ]; then
        log_error "Not in a git repository. Please run from Coherence-Network repo root."
        exit 1
    fi
    
    # Check for Cursor
    if [ ! -d "$HOME/.cursor" ] && [ ! -d "/Applications/Cursor.app" ]; then
        log_warning "Cursor not detected. Install from cursor.sh"
    fi
    
    log_success "Prerequisites check passed"
}

################################################################################
# PHASE 1: Service Registration & API Keys
################################################################################

collect_service_credentials() {
    log_info "Collecting service credentials..."
    
    # Load existing config if present
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
        log_info "Loaded existing configuration"
    fi
    
    echo ""
    echo "=================================================="
    echo "SERVICE CREDENTIALS COLLECTION"
    echo "=================================================="
    echo ""
    echo "We'll collect API keys for free tier services."
    echo "Sign up links will be provided. Press ENTER after signup."
    echo ""
    
    # Supabase
    if [ -z "$SUPABASE_URL" ]; then
        echo "1. SUPABASE (PostgreSQL Database)"
        echo "   → Open: https://supabase.com/dashboard"
        echo "   → Create project: coherence-network"
        echo "   → Copy Connection String"
        read -p "Press ENTER when ready..."
        read -p "Supabase URL (postgres://...): " SUPABASE_URL
        read -p "Supabase Anon Key: " SUPABASE_ANON_KEY
    else
        log_success "Supabase credentials already configured"
    fi
    
    # Neo4j Aura
    if [ -z "$NEO4J_URI" ]; then
        echo ""
        echo "2. NEO4J AURA (Graph Database)"
        echo "   → Open: https://console.neo4j.io"
        echo "   → Create free instance: coherence-network"
        echo "   → Download credentials"
        read -p "Press ENTER when ready..."
        read -p "Neo4j URI (neo4j+s://...): " NEO4J_URI
        read -p "Neo4j Password: " NEO4J_PASSWORD
    else
        log_success "Neo4j credentials already configured"
    fi
    
    # Redis Cloud
    if [ -z "$REDIS_URL" ]; then
        echo ""
        echo "3. REDIS CLOUD (Cache)"
        echo "   → Open: https://redis.com/try-free"
        echo "   → Create free database: coherence-cache"
        echo "   → Copy endpoint"
        read -p "Press ENTER when ready..."
        read -p "Redis URL (redis://...): " REDIS_URL
    else
        log_success "Redis credentials already configured"
    fi
    
    # Cloudflare
    if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
        echo ""
        echo "4. CLOUDFLARE (DNS + CDN)"
        echo "   → Open: https://dash.cloudflare.com/profile/api-tokens"
        echo "   → Create Token → Edit Zone DNS"
        echo "   → Add coherencycoin.com zone first if not done"
        read -p "Press ENTER when ready..."
        read -p "Cloudflare API Token: " CLOUDFLARE_API_TOKEN
        read -p "Cloudflare Zone ID (from domain overview): " CLOUDFLARE_ZONE_ID
    else
        log_success "Cloudflare credentials already configured"
    fi
    
    # Oracle Cloud (requires manual signup)
    if [ -z "$ORACLE_VM_IP" ]; then
        echo ""
        echo "5. ORACLE CLOUD (Forever Free VM)"
        echo "   → Open: https://cloud.oracle.com/compute/instances"
        echo "   → Create VM.Standard.E2.1.Micro instance"
        echo "   → Ubuntu 22.04, assign public IP"
        echo "   → Download SSH key"
        read -p "Press ENTER when ready..."
        read -p "Oracle VM Public IP: " ORACLE_VM_IP
        read -p "SSH Private Key Path: " ORACLE_SSH_KEY
    else
        log_success "Oracle VM already configured"
    fi
    
    # GitHub (for Actions)
    if [ -z "$GITHUB_TOKEN" ]; then
        echo ""
        echo "6. GITHUB (CI/CD)"
        echo "   → Open: https://github.com/settings/tokens"
        echo "   → Generate new token (classic)"
        echo "   → Scopes: repo, workflow"
        read -p "Press ENTER when ready..."
        read -p "GitHub Personal Access Token: " GITHUB_TOKEN
    else
        log_success "GitHub token already configured"
    fi
    
    # Save configuration
    cat > "$CONFIG_FILE" << EOF
# Coherence Network Deployment Configuration
# Generated: $(date)

# Database
SUPABASE_URL="$SUPABASE_URL"
SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY"
NEO4J_URI="$NEO4J_URI"
NEO4J_PASSWORD="$NEO4J_PASSWORD"
REDIS_URL="$REDIS_URL"

# DNS/CDN
CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN"
CLOUDFLARE_ZONE_ID="$CLOUDFLARE_ZONE_ID"

# Hosting
ORACLE_VM_IP="$ORACLE_VM_IP"
ORACLE_SSH_KEY="$ORACLE_SSH_KEY"

# CI/CD
GITHUB_TOKEN="$GITHUB_TOKEN"

# Generated
SECRET_KEY=$(openssl rand -hex 32)
API_KEY_ADMIN=$(openssl rand -hex 16)
GITHUB_WEBHOOK_SECRET=$(openssl rand -hex 32)
EOF

    chmod 600 "$CONFIG_FILE"
    log_success "Configuration saved to $CONFIG_FILE"
}

################################################################################
# PHASE 2: DNS Configuration
################################################################################

configure_dns() {
    log_info "Configuring DNS for coherencycoin.com..."
    
    source "$CONFIG_FILE"
    
    # Create A record for api.coherencycoin.com
    log_info "Creating DNS record: api.coherencycoin.com → $ORACLE_VM_IP"
    
    curl -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records" \
      -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
      -H "Content-Type: application/json" \
      --data "{
        \"type\": \"A\",
        \"name\": \"api\",
        \"content\": \"$ORACLE_VM_IP\",
        \"ttl\": 1,
        \"proxied\": true
      }" | jq '.'
    
    # Create CNAME for www
    log_info "Creating DNS record: www.coherencycoin.com → coherencycoin.com"
    
    curl -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records" \
      -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
      -H "Content-Type: application/json" \
      --data "{
        \"type\": \"CNAME\",
        \"name\": \"www\",
        \"content\": \"coherencycoin.com\",
        \"ttl\": 1,
        \"proxied\": true
      }" | jq '.'
    
    log_success "DNS configured. Wait 1-2 minutes for propagation."
}

################################################################################
# PHASE 3: Oracle VM Setup
################################################################################

setup_oracle_vm() {
    log_info "Setting up Oracle Cloud VM..."
    
    source "$CONFIG_FILE"
    
    # Test SSH connection
    log_info "Testing SSH connection to $ORACLE_VM_IP..."
    if ! ssh -i "$ORACLE_SSH_KEY" -o StrictHostKeyChecking=no ubuntu@"$ORACLE_VM_IP" "echo 'Connected'"; then
        log_error "Cannot connect to Oracle VM. Check IP and SSH key."
        exit 1
    fi
    
    log_success "SSH connection successful"
    
    # Create setup script
    cat > /tmp/vm_setup.sh << 'VMEOF'
#!/bin/bash
set -e

echo "Updating system..."
sudo apt update && sudo apt upgrade -y

echo "Installing Docker..."
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu

echo "Installing Docker Compose..."
ARCH="$(uname -m)"
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
  BIN="docker-compose-linux-aarch64"
else
  BIN="docker-compose-linux-x86_64"
fi

sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/${BIN}" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "Installing Caddy (automatic HTTPS)..."
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor --batch --yes --no-tty \
    -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy

echo "Creating application directory..."
mkdir -p ~/coherence-network
cd ~/coherence-network

echo "Setup complete!"
VMEOF
    
    # Copy and execute setup script
    log_info "Copying setup script to VM..."
    scp -i "$ORACLE_SSH_KEY" /tmp/vm_setup.sh ubuntu@"$ORACLE_VM_IP":/tmp/
    
    log_info "Executing setup script on VM (this may take 5-10 minutes)..."
    ssh -i "$ORACLE_SSH_KEY" ubuntu@"$ORACLE_VM_IP" "bash /tmp/vm_setup.sh"
    
    log_success "Oracle VM setup complete"
}

################################################################################
# PHASE 4: Deploy Application
################################################################################

deploy_application() {
    log_info "Deploying application to Oracle VM..."
    
    source "$CONFIG_FILE"
    
    # Create .env file
    cat > /tmp/.env << EOF
# Database
DATABASE_URL=$SUPABASE_URL
NEO4J_URI=$NEO4J_URI
NEO4J_USER=neo4j
NEO4J_PASSWORD=$NEO4J_PASSWORD
REDIS_URL=$REDIS_URL

# Security
SECRET_KEY=$SECRET_KEY
API_KEY_ADMIN=$API_KEY_ADMIN
GITHUB_WEBHOOK_SECRET=$GITHUB_WEBHOOK_SECRET

# Network
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=production
DOMAIN=api.coherencycoin.com
EOF
    
    # Create docker-compose.yml
    cat > /tmp/docker-compose.yml << 'DCEOF'
version: '3.8'

services:
  api:
    build: .
    image: coherence-network:latest
    container_name: coherence-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - coherence

networks:
  coherence:
    driver: bridge
DCEOF
    
    # Create Caddyfile
    cat > /tmp/Caddyfile << 'CADEOF'
api.coherencycoin.com {
    reverse_proxy localhost:8000
}

coherencycoin.com, www.coherencycoin.com {
    respond "Coherence Network - Coming Soon" 200
}
CADEOF
    
    # Copy files to VM
    log_info "Copying configuration files..."
    scp -i "$ORACLE_SSH_KEY" /tmp/.env ubuntu@"$ORACLE_VM_IP":~/coherence-network/
    scp -i "$ORACLE_SSH_KEY" /tmp/docker-compose.yml ubuntu@"$ORACLE_VM_IP":~/coherence-network/
    scp -i "$ORACLE_SSH_KEY" /tmp/Caddyfile ubuntu@"$ORACLE_VM_IP":/tmp/
    
    # Copy application code
    log_info "Copying application code..."
    ssh -i "$ORACLE_SSH_KEY" ubuntu@"$ORACLE_VM_IP" "mkdir -p ~/coherence-network/app"
    
    # Create minimal Dockerfile
    cat > /tmp/Dockerfile << 'DKEOF'
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
DKEOF
    
    scp -i "$ORACLE_SSH_KEY" /tmp/Dockerfile ubuntu@"$ORACLE_VM_IP":~/coherence-network/
    
    # Install Caddy config
    log_info "Installing Caddy configuration..."
    ssh -i "$ORACLE_SSH_KEY" ubuntu@"$ORACLE_VM_IP" "sudo mv /tmp/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy"
    
    # Build and start application
    log_info "Building and starting application..."
    ssh -i "$ORACLE_SSH_KEY" ubuntu@"$ORACLE_VM_IP" << 'SSHEOF'
cd ~/coherence-network
docker-compose build
docker-compose up -d
docker-compose logs -f --tail=50
SSHEOF
    
    log_success "Application deployed!"
}

################################################################################
# PHASE 5: Verification
################################################################################

verify_deployment() {
    log_info "Verifying deployment..."
    
    local checks=0
    local passed=0
    
    # Check DNS
    checks=$((checks + 1))
    log_info "Checking DNS resolution..."
    if dig +short api.coherencycoin.com | grep -q "."; then
        log_success "DNS resolving correctly"
        passed=$((passed + 1))
    else
        log_warning "DNS not resolving yet (may need time to propagate)"
    fi
    
    # Check HTTPS
    checks=$((checks + 1))
    log_info "Checking HTTPS..."
    if curl -s -o /dev/null -w "%{http_code}" https://api.coherencycoin.com/health | grep -q "200"; then
        log_success "HTTPS working"
        passed=$((passed + 1))
    else
        log_warning "HTTPS not ready yet (Caddy may still be getting certificate)"
    fi
    
    # Check API
    checks=$((checks + 1))
    log_info "Checking API health..."
    response=$(curl -s https://api.coherencycoin.com/health || echo "failed")
    if echo "$response" | grep -q "healthy"; then
        log_success "API is healthy"
        passed=$((passed + 1))
    else
        log_warning "API not responding correctly"
    fi
    
    echo ""
    log_info "Verification: $passed/$checks checks passed"
    
    if [ $passed -eq $checks ]; then
        log_success "All checks passed! Deployment successful!"
        return 0
    else
        log_warning "Some checks failed. Wait a few minutes and run verification again."
        return 1
    fi
}

################################################################################
# MAIN EXECUTION
################################################################################

main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  Coherence Network - Automated Deployment                     ║"
    echo "║  Domain: coherencycoin.com                                     ║"
    echo "║  Target: Oracle Cloud Free Tier                                ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Parse command line arguments
    case "${1:-all}" in
        prereq)
            check_prerequisites
            ;;
        credentials)
            collect_service_credentials
            ;;
        dns)
            configure_dns
            ;;
        vm)
            setup_oracle_vm
            ;;
        deploy)
            deploy_application
            ;;
        verify)
            verify_deployment
            ;;
        all)
            check_prerequisites
            collect_service_credentials
            configure_dns
            setup_oracle_vm
            deploy_application
            verify_deployment
            ;;
        *)
            echo "Usage: $0 {all|prereq|credentials|dns|vm|deploy|verify}"
            echo ""
            echo "Commands:"
            echo "  all         - Run complete deployment (default)"
            echo "  prereq      - Check prerequisites only"
            echo "  credentials - Collect service credentials only"
            echo "  dns         - Configure DNS only"
            echo "  vm          - Setup Oracle VM only"
            echo "  deploy      - Deploy application only"
            echo "  verify      - Verify deployment only"
            exit 1
            ;;
    esac
}

# Run main with arguments
main "$@"
