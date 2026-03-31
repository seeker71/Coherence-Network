#!/bin/bash
# Create Contributor Account

echo "Creating Coherence Network contributor account..."
echo ""

read -p "Your name: " NAME
read -p "Email address: " EMAIL
read -p "Wallet address (for crypto payouts): " WALLET
read -p "Hourly rate (USD): " RATE

API_URL=${COHERENCE_API_URL:-"https://api.coherencycoin.com"}

RESPONSE=$(curl -s -X POST "$API_URL/v1/contributors" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"HUMAN\",
    \"name\": \"$NAME\",
    \"email\": \"$EMAIL\",
    \"wallet_address\": \"$WALLET\",
    \"hourly_rate\": $RATE
  }")

CONTRIBUTOR_ID=$(echo "$RESPONSE" | jq -r '.id')

if [ "$CONTRIBUTOR_ID" != "null" ]; then
    echo ""
    echo "✅ Account created!"
    echo "Your Contributor ID: $CONTRIBUTOR_ID"
    echo ""
    echo "Save this to your .env file:"
    echo "CONTRIBUTOR_ID=$CONTRIBUTOR_ID"
    echo ""
    echo "Next steps:"
    echo "1. Set up payout method: ./scripts/contributor/setup_payout.sh"
    echo "2. Start contributing!"
else
    echo "❌ Error creating account"
    echo "$RESPONSE"
fi
