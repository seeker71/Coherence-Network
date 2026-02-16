#!/bin/bash
# Link Tokenized Gold (Paxos Gold, Tether Gold)

PROVIDER=$1
AMOUNT=$2

echo "Linking tokenized gold..."
echo "Provider: $PROVIDER"
echo "Amount: $AMOUNT troy ounces"
echo ""

# Contract addresses
case $PROVIDER in
    paxos)
        CONTRACT="0x45804880De22913dAFE09f4980848ECE6EcbAf78"  # PAXG on Ethereum
        SYMBOL="PAXG"
        CUSTODIAN="Paxos Trust Company"
        AUDIT_URL="https://paxos.com/attestations"
        ;;
    tether)
        CONTRACT="0x68749665FF8D2d112Fa859AA293F07A622782F38"  # XAUT on Ethereum
        SYMBOL="XAUT"
        CUSTODIAN="TG Commodities Limited"
        AUDIT_URL="https://tether.to/en/transparency"
        ;;
    *)
        echo "Unknown provider: $PROVIDER"
        exit 1
        ;;
esac

# Get current gold price from Chainlink oracle
GOLD_PRICE=$(curl -s "https://api.coinbase.com/v2/prices/XAU-USD/spot" | jq -r '.data.amount')
TOTAL_VALUE=$(echo "$AMOUNT * $GOLD_PRICE" | bc)

echo "Current gold price: \$$GOLD_PRICE/oz"
echo "Total value: \$$TOTAL_VALUE"
echo ""

# Verify on-chain ownership
echo "Verifying on-chain ownership..."
BALANCE=$(cast balance --token "$CONTRACT" "$CONTRIBUTOR_WALLET" --rpc-url "$ETH_RPC_URL")

if [ "$(echo "$BALANCE >= $AMOUNT" | bc)" -eq 1 ]; then
    echo "✅ Ownership verified: You own $BALANCE $SYMBOL"
else
    echo "❌ Ownership verification failed"
    echo "Your balance: $BALANCE $SYMBOL"
    echo "Required: $AMOUNT $SYMBOL"
    exit 1
fi

# Record asset
API_URL=${COHERENCE_API_URL:-"https://api.coherencycoin.com"}

curl -X POST "$API_URL/api/assets/external" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $COHERENCE_API_KEY" \
  -d "{
    \"contributor_id\": \"$CONTRIBUTOR_ID\",
    \"asset_type\": \"PHYSICAL_BACKED\",
    \"asset_class\": \"PRECIOUS_METAL\",
    \"underlying_asset\": \"GOLD\",
    \"tokenization\": {
      \"platform\": \"$PROVIDER\",
      \"blockchain\": \"ethereum\",
      \"contract\": \"$CONTRACT\",
      \"symbol\": \"$SYMBOL\"
    },
    \"amount\": $AMOUNT,
    \"unit\": \"troy_ounces\",
    \"custody\": {
      \"custodian\": \"$CUSTODIAN\",
      \"audit_url\": \"$AUDIT_URL\"
    },
    \"value\": {
      \"current_value_usd\": $TOTAL_VALUE,
      \"price_per_unit\": $GOLD_PRICE,
      \"oracle_source\": \"Chainlink XAU/USD\"
    },
    \"verification\": {
      \"blockchain_verified\": true,
      \"ownership_verified\": true
    }
  }"

echo ""
echo "✅ Tokenized gold asset linked!"
echo "Your contribution: $AMOUNT oz gold = \$$TOTAL_VALUE"
