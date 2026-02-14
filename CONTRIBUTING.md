# Contributing to Coherence Network

Welcome! Coherence Network rewards **all** contributions proportionally to the value they create. This guide shows you how to:

1. **Set up your own node** and earn from hosting
2. **Contribute code/content** and get paid when it generates value
3. **Track external assets** (NFTs, tokenized assets, physical assets)
4. **Verify your contributions** are properly recorded

---

## 🚀 Quick Start for Contributors

### Option 1: Code Contribution (No Infrastructure Needed)

```bash
# 1. Fork the repo
gh repo fork seeker71/Coherence-Network

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/Coherence-Network
cd Coherence-Network

# 3. Create contributor account
./scripts/create_contributor.sh

# 4. Make changes
git checkout -b feature/my-contribution

# 5. Commit (auto-tracked via webhook!)
git add .
git commit -m "Add feature X"
git push origin feature/my-contribution

# 6. Create PR
gh pr create

# Your contribution is automatically tracked when merged! ✅
```

### Option 2: Run Your Own Node (Earn Hosting Revenue)

```bash
# 1. Clone repo
git clone https://github.com/seeker71/Coherence-Network
cd Coherence-Network

# 2. Run node setup
./scripts/setup_node_operator.sh

# 3. Register with network
./scripts/register_node.sh

# Done! You're now earning from hosting. 💰
```

### Option 3: Track External Assets (Digital Assets, NFTs, Tokenized Assets)

```bash
# 1. Configure asset tracking API
./scripts/configure_asset_tracker.sh

# 2. Link your assets
./scripts/link_external_asset.sh --type NFT --contract 0x...

# 3. Verify on public ledger
./scripts/verify_asset_link.sh

# Your asset contributions are now tracked! 📊
```

---

## 📋 Contribution Types & How They're Tracked

### 1. Code Contributions

**What counts**:
- Bug fixes
- New features
- Documentation
- Tests
- Infrastructure improvements

**How it's tracked**:
- Automatic via GitHub webhook when PR merged
- Cost = Hours worked × your rate (self-reported)
- Coherence = Automated code quality analysis
- Verification = Public commit hash on ledger

**Example**:
```bash
# After your PR is merged
curl https://api.coherencycoin.com/v1/contributors/YOUR_ID/contributions
# Shows your contribution with cost and coherence score
```

### 2. Node Operator Contributions

**What counts**:
- Running API servers
- Providing storage
- Compute resources
- Network bandwidth

**How it's tracked**:
- Real-time usage metering
- Cost = Your pricing × usage
- Revenue share = Market competitive rate
- Verification = Uptime monitoring + health checks

**Example**:
```bash
# Check your node earnings
./scripts/node_earnings.sh
# Shows: $45.23 earned this month from 1.2M requests
```

### 3. Digital Asset Contributions

**What counts**:
- NFTs created/owned
- Tokenized assets (real estate, art, commodities)
- Digital content (licensed)
- Intellectual property

**How it's tracked**:
- Blockchain verification (Ethereum, Polygon, Solana)
- External API integration (OpenSea, Rarible, etc.)
- Public ledger of ownership
- Value = Appraised or market value

**Supported APIs**:
- OpenSea API (NFTs)
- Chainlink Oracles (Price feeds)
- Paxos (Tokenized gold)
- RealT (Tokenized real estate)
- Custom APIs (via adapter)

**Example**:
```bash
# Link your NFT
./scripts/link_external_asset.sh \
  --type NFT \
  --blockchain ethereum \
  --contract 0x1234... \
  --token-id 5678 \
  --value-api opensea

# Verify
curl https://api.coherencycoin.com/v1/assets/external/YOUR_ASSET_ID
# Shows: NFT #5678, value $5,000, verified on Ethereum
```

### 4. Physically-Backed Asset Contributions

**What counts**:
- Tokenized gold (Paxos, Tether Gold)
- Tokenized real estate (RealT, Lofty)
- Carbon credits (Toucan Protocol)
- Commodities (tokenized oil, metals)

**How it's tracked**:
- Blockchain proof of ownership
- Oracle price feeds (Chainlink, Band Protocol)
- Physical verification (audit reports)
- Public ledger of custody

**Example - Tokenized Gold**:
```bash
# Link Paxos Gold tokens
./scripts/link_external_asset.sh \
  --type PHYSICAL_BACKED \
  --asset-class GOLD \
  --blockchain ethereum \
  --contract 0x45804880De22913dAFE09f4980848ECE6EcbAf78 \  # PAXG
  --amount 10.5 \
  --value-api chainlink \
  --oracle-feed 0x214eD9Da11D2fbe465a6fc601a91E62EbEc1a0D6  # XAU/USD

# Result: 10.5 oz gold = $21,000 tracked as your contribution
```

---

## 🏗️ Setting Up Your Infrastructure Node

### Prerequisites

- VPS or dedicated server (min 1GB RAM, 10GB storage)
- Public IP address
- Domain name (optional but recommended)

### Free Hosting Options

1. **Railway/Render free tier** (recommended)
   - Forever free
   - 1 CPU, 1GB RAM
   - Perfect for small nodes

2. **AWS Free Tier** (12 months)
   - t2.micro instance
   - 1 year free

3. **Google Cloud Free Tier**
   - e2-micro instance
   - $300 credit

4. **Your Own Hardware**
   - Raspberry Pi 4 (4GB+)
   - Old laptop
   - Home server

### Setup Steps

```bash
# 1. Clone repo on your server
git clone https://github.com/seeker71/Coherence-Network
cd Coherence-Network

# 2. Run automated setup
./scripts/setup_node_operator.sh

# This will:
# - Install Docker & dependencies
# - Configure firewall
# - Set up automatic HTTPS (Caddy)
# - Deploy application
# - Register with network

# 3. Set your pricing
./scripts/configure_node_pricing.sh \
  --api-request 0.00002 \
  --storage-gb-month 0.005 \
  --compute-hour 0.008

# 4. Start earning!
./scripts/start_node.sh

# Monitor earnings
watch -n 60 ./scripts/node_earnings.sh
```

### Verification

```bash
# Check node is registered
curl https://api.coherencycoin.com/v1/nodes/YOUR_NODE_ID

# Health check
curl https://your-node-domain.com/health

# Earnings dashboard
./scripts/node_dashboard.sh
```

---

## 💎 External Asset Integration

### Supported Asset Types

| Type | Examples | Verification Method | Value Source |
|------|----------|---------------------|--------------|
| **Digital Assets** | NFTs, domains, in-game items | Blockchain | Market price APIs |
| **Tokenized Securities** | Stocks, bonds, funds | Blockchain + KYC | Exchange prices |
| **Commodities** | Gold, silver, oil | Blockchain + Custody | Oracle feeds |
| **Real Estate** | Properties, land | Blockchain + Deed | Appraisal APIs |
| **Carbon Credits** | CO2 offsets | Registry + Blockchain | Market prices |
| **Intellectual Property** | Patents, copyrights | Registry + NFT | Licensing revenue |

### Integration Architecture

```
┌─────────────────────┐
│ Your External Asset │
│ (NFT, Gold, etc.)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Asset Tracking API  │
│ (OpenSea, Chainlink)│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ CCN Asset Adapter   │
│ (Verification)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ CCN Ledger          │
│ (Public Record)     │
└─────────────────────┘
```

### Adding a Custom Asset Tracker

```bash
# 1. Create adapter
cp .github/templates/asset_adapter_template.py \
   adapters/my_custom_asset.py

# 2. Implement required methods
class MyCustomAssetAdapter(AssetAdapter):
    def verify_ownership(self, asset_id, owner_id):
        # Verify owner controls this asset
        pass
    
    def get_current_value(self, asset_id):
        # Get current market value
        pass
    
    def get_proof_of_authenticity(self, asset_id):
        # Get verification proof
        pass

# 3. Register adapter
./scripts/register_asset_adapter.sh \
  --name my_custom_asset \
  --type PHYSICAL_BACKED \
  --verification-method ORACLE

# 4. Link your assets
./scripts/link_external_asset.sh \
  --adapter my_custom_asset \
  --asset-id ABC123
```

### Physically-Backed Asset Examples

#### Example 1: Tokenized Gold (Paxos Gold)

```javascript
{
  "asset_type": "PHYSICAL_BACKED",
  "asset_class": "PRECIOUS_METAL",
  "underlying_asset": "GOLD",
  "tokenization": {
    "platform": "Paxos",
    "blockchain": "Ethereum",
    "contract": "0x45804880De22913dAFE09f4980848ECE6EcbAf78",
    "token_symbol": "PAXG"
  },
  "amount": 10.5,
  "unit": "troy_ounces",
  "custody": {
    "custodian": "Paxos Trust Company",
    "audit_firm": "Withum",
    "latest_audit": "2026-01-15",
    "certificate_url": "https://paxos.com/attestations"
  },
  "value_tracking": {
    "primary_source": "Chainlink Oracle",
    "oracle_address": "0x214eD9Da11D2fbe465a6fc601a91E62EbEc1a0D6",
    "fallback_source": "Kitco API",
    "current_value_usd": 21000.00
  },
  "verification": {
    "blockchain_proof": "0x789abc...",
    "ownership_verified": true,
    "custody_verified": true,
    "value_verified": true
  }
}
```

#### Example 2: Tokenized Real Estate (RealT)

```javascript
{
  "asset_type": "PHYSICAL_BACKED",
  "asset_class": "REAL_ESTATE",
  "underlying_asset": "RESIDENTIAL_PROPERTY",
  "property": {
    "address": "15095 Hartwell St, Detroit, MI 48227",
    "property_type": "Single Family",
    "year_built": 1926,
    "sqft": 1400,
    "legal_description": "Lot 315, J E Blossoms Subdivision"
  },
  "tokenization": {
    "platform": "RealT",
    "blockchain": "Gnosis Chain",
    "contract": "0x...",
    "token_symbol": "REALTOKEN-15095-HARTWELL",
    "total_tokens": 1000,
    "tokens_owned": 100
  },
  "value": {
    "property_value": 75000.00,
    "token_value": 75.00,
    "your_value": 7500.00,
    "ownership_percentage": 10.0
  },
  "verification": {
    "title_company": "Chicago Title",
    "deed_recorded": true,
    "llc_ownership": "15095 Hartwell LLC",
    "blockchain_proof": "0x...",
    "rent_distribution": "Weekly via smart contract"
  },
  "income": {
    "annual_rent": 6750.00,
    "your_share": 675.00,
    "distribution_frequency": "Weekly"
  }
}
```

---

## 🔍 Contribution Verification

### Automatic Verification (Git Commits)

When you commit code:

1. **GitHub webhook** triggers on push
2. **Commit metadata** extracted (author, files, lines)
3. **Cost estimated** (files × complexity factor)
4. **Coherence calculated** (linting + tests + docs)
5. **Event recorded** in public ledger
6. **Verification link** sent to you

```bash
# Check your latest contribution
curl https://api.coherencycoin.com/v1/contributions/latest?contributor_id=YOUR_ID

# Response:
{
  "event_id": "uuid",
  "commit_hash": "abc123",
  "cost_amount": 150.00,
  "coherence_score": 0.87,
  "verification_url": "https://github.com/seeker71/Coherence-Network/commit/abc123",
  "ledger_entry": "0x789def...",
  "status": "verified"
}
```

### Manual Verification (Other Contributions)

For non-code contributions:

```bash
# Record manual contribution
./scripts/record_contribution.sh \
  --type DOCUMENTATION \
  --hours 3 \
  --rate 100 \
  --description "Wrote contributor onboarding guide" \
  --proof-url "https://github.com/.../CONTRIBUTING.md"

# Verify it was recorded
./scripts/verify_contribution.sh --contribution-id abc123
```

### External Asset Verification

```bash
# Verify asset ownership & value
./scripts/verify_external_asset.sh --asset-id YOUR_ASSET_ID

# Response:
{
  "asset_id": "uuid",
  "type": "PHYSICAL_BACKED",
  "blockchain_verified": true,
  "ownership_verified": true,
  "value_verified": true,
  "last_verification": "2026-02-13T10:00:00Z",
  "next_verification": "2026-02-14T10:00:00Z",
  "proofs": [
    "Blockchain: 0x...",
    "Oracle: Price=$2000/oz",
    "Custody: Audit dated 2026-01-15"
  ]
}
```

---

## 📊 Public Ledger Access

All contributions are publicly verifiable:

```bash
# View complete ledger
curl https://api.coherencycoin.com/v1/ledger

# View specific contributor's record
curl https://api.coherencycoin.com/v1/ledger/contributor/YOUR_ID

# View specific asset's contributions
curl https://api.coherencycoin.com/v1/ledger/asset/ASSET_ID

# Verify specific event
curl https://api.coherencycoin.com/v1/ledger/event/EVENT_ID/verify
```

### Blockchain Settlement (Optional)

For maximum transparency, major distributions can be settled on-chain:

```bash
# Enable blockchain settlement
./scripts/enable_blockchain_settlement.sh --chain arbitrum

# View on-chain record
./scripts/blockchain_proof.sh --distribution-id DIST_ID
# Returns Arbiscan link to transaction
```

---

## 💰 Getting Paid

### When Value is Generated

When an asset generates revenue (e.g., API usage fees, licenses, sales):

1. **Distribution triggered** (manually or automatically)
2. **Your share calculated** (weighted by coherence)
3. **Payout record created**
4. **Payment sent** (crypto or fiat)

### Payout Methods

**Cryptocurrency** (preferred):
- Ethereum / Arbitrum / Optimism
- Stablecoins (USDC, DAI)
- Instant, low-fee

**Traditional Banking**:
- Bank transfer (ACH, Wire)
- PayPal
- Stripe
- 1-3 day delay

### Setting Up Payouts

```bash
# Add wallet address (crypto)
./scripts/set_payout_wallet.sh --address 0x...

# Or add bank account (fiat)
./scripts/set_payout_bank.sh \
  --account-number XXX \
  --routing-number XXX \
  --account-type checking
```

### Checking Earnings

```bash
# Total earned to date
./scripts/my_earnings.sh

# Pending payouts
./scripts/pending_payouts.sh

# Payout history
./scripts/payout_history.sh
```

---

## 🧪 Testing Your Setup

### Local Development

```bash
# Run local instance
docker-compose up -d

# Create test contributor
./scripts/create_contributor.sh --test

# Record test contribution
./scripts/record_contribution.sh \
  --test \
  --cost 100 \
  --coherence 0.8

# Test distribution
./scripts/test_distribution.sh --value 1000

# Verify
./scripts/verify_test_setup.sh
```

### Node Operator Testing

```bash
# Test node health
./scripts/test_node_health.sh

# Simulate requests
./scripts/simulate_traffic.sh --requests 100

# Check earnings calculation
./scripts/test_earnings.sh
```

### External Asset Testing

```bash
# Test asset verification
./scripts/test_asset_verification.sh \
  --type NFT \
  --blockchain ethereum \
  --test-mode

# Test value tracking
./scripts/test_value_tracking.sh --asset-id TEST_ASSET
```

---

## 🤝 Community & Support

**Need help?**
- GitHub Discussions: https://github.com/seeker71/Coherence-Network/discussions
- Discord: (coming soon)
- Email: support@coherencycoin.com

**Report issues**:
- GitHub Issues: https://github.com/seeker71/Coherence-Network/issues

**Propose features**:
- Create an issue with label `enhancement`
- Or submit a PR!

---

## 📜 Contributor Agreement

By contributing, you agree:

1. ✅ Your contributions are tracked in the public ledger
2. ✅ You earn proportionally when value is generated
3. ✅ Coherence scoring may adjust your share (quality matters!)
4. ✅ External assets must be verifiable and backed
5. ✅ You own your contributions (no copyright transfer)

See [LICENSE](LICENSE) for legal details.

---

## 🎓 Examples from Real Contributors

### seeker71 (Founder)
- Contribution: Initial architecture + deployment ($2,413.19)
- Coherence: 0.92 (1.20x multiplier)
- Earnings: 96.5% of distributions
- Node: Running on Railway/Render free tier

### Future You?
- Contribution: Feature X
- Coherence: TBD (aim for >0.8!)
- Earnings: Proportional to value created
- Node: Optional but encouraged

---

## ✅ Checklist for New Contributors

**Before your first contribution**:
- [ ] Fork the repository
- [ ] Run `./scripts/create_contributor.sh`
- [ ] Set up payout method
- [ ] Read this guide fully

**For code contributions**:
- [ ] Create feature branch
- [ ] Write tests (boosts coherence!)
- [ ] Add documentation (boosts coherence!)
- [ ] Submit PR
- [ ] Wait for merge (auto-tracked!)

**For node operators**:
- [ ] Get server/VPS
- [ ] Run `./scripts/setup_node_operator.sh`
- [ ] Set competitive pricing
- [ ] Monitor earnings

**For asset contributors**:
- [ ] Configure asset tracker
- [ ] Link your assets
- [ ] Verify ownership
- [ ] Monitor value

---

**Welcome to Coherence!**

Every contribution matters. Every contributor earns. Quality is rewarded.

🌐 **Let's build together.**
