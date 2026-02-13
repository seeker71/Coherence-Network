#!/bin/bash
# ONE-COMMAND Node Operator Setup

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Coherence Network - Node Operator Setup                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected: macOS"
    PKG_MANAGER="brew"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected: Linux"
    PKG_MANAGER="apt"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

# Install Docker if needed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    if [ "$PKG_MANAGER" == "brew" ]; then
        brew install docker
    else
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker $USER
    fi
fi

# Create node directory
mkdir -p ~/coherence-node
cd ~/coherence-node

# Copy application files
cp -r ../docker/* .
cp ../.env.example .env

echo ""
read -p "Your contributor ID: " CONTRIBUTOR_ID
read -p "Node endpoint (e.g., https://node.example.com): " ENDPOINT
read -p "API request price (USD, e.g., 0.00002): " API_PRICE
read -p "Storage price per GB/month (USD, e.g., 0.005): " STORAGE_PRICE

# Configure
cat > .env << ENVEOF
CONTRIBUTOR_ID=$CONTRIBUTOR_ID
NODE_ENDPOINT=$ENDPOINT
API_REQUEST_PRICE=$API_PRICE
STORAGE_GB_MONTH_PRICE=$STORAGE_PRICE
COHERENCE_API_URL=https://api.coherencycoin.com
ENVEOF

# Start node
docker-compose up -d

echo ""
echo "✅ Node setup complete!"
echo ""
echo "Next steps:"
echo "1. Register node: ./scripts/node_operator/register_node.sh"
echo "2. Monitor earnings: ./scripts/node_operator/node_earnings.sh"
