# External Asset Tracking Guide

Coherence Network supports tracking and attributing value to external assets:

## Supported Asset Types

### 1. NFTs (Non-Fungible Tokens)
- **Platforms**: OpenSea, Rarible, Blur
- **Blockchains**: Ethereum, Polygon, Solana
- **Verification**: On-chain ownership via smart contract
- **Valuation**: Real-time floor price + last sale price

### 2. Tokenized Precious Metals
- **Paxos Gold (PAXG)**: 1 PAXG = 1 troy oz gold
- **Tether Gold (XAUT)**: 1 XAUT = 1 troy oz gold
- **Verification**: Blockchain + custody audits
- **Valuation**: Chainlink XAU/USD oracle

### 3. Tokenized Real Estate
- **RealT**: Fractional property ownership
- **Lofty**: Automated rent distribution
- **Verification**: Property deed + LLC ownership
- **Valuation**: Property appraisal + market comps

### 4. Carbon Credits
- **Toucan Protocol**: Tokenized carbon credits
- **Verification**: Verra registry + blockchain
- **Valuation**: Market price on DEXs

### 5. DeFi Positions
- **Uniswap**: LP tokens
- **Aave**: Lending deposits
- **Curve**: LP positions
- **Verification**: On-chain position tracking
- **Valuation**: Real-time protocol value

## Quick Start

```bash
# Link an NFT
./scripts/asset_tracking/link_external_asset.sh

# Choose NFT → Enter details → Auto-verified!

# Check your assets
./scripts/asset_tracking/asset_dashboard.sh
```

## Why Physically-Backed Assets?

**Stability**: Real-world assets have intrinsic value  
**Verifiability**: Custody audits + blockchain proof  
**Liquidity**: Can be sold/traded for value distribution  
**Transparency**: Public ledger of ownership  

## Example: Contributing 10 oz Gold

```bash
# You own 10 PAXG tokens (10 oz gold)
./scripts/asset_tracking/physically_backed/link_tokenized_gold.sh \
  --provider paxos \
  --amount 10

# System verifies:
✅ Blockchain: You own 10 PAXG
✅ Custody: Paxos holds 10 oz physical gold
✅ Audit: Latest audit confirms reserves
✅ Value: $21,000 (10 × $2,100/oz)

# Your contribution is recorded:
# - Asset ID: uuid
# - Value: $21,000
# - Verification: Blockchain + custody proof
# - Public ledger: Viewable by anyone
```

See `docs/guides/physically_backed_assets.md` for complete guide.
