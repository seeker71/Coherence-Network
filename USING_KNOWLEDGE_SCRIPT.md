# How to Generate Claude Project Knowledge Base

This script automatically creates all the documentation files for Claude Projects to work efficiently with your Coherence Network codebase.

## Quick Start (3 Steps)

### Step 1: Download & Run Script

```bash
# Navigate to your Coherence Network repo
cd ~/path/to/Coherence-Network

# Download the script (if not already in repo)
# Or copy generate_claude_knowledge.sh to your repo

# Make executable
chmod +x generate_claude_knowledge.sh

# Run it!
./generate_claude_knowledge.sh
```

**Done!** The script creates `.claude/` folder with all files.

### Step 2: Commit to GitHub

```bash
git add .claude/
git commit -m "Add Claude Project knowledge base

Generated 11 markdown files + 3 JSON references for Claude Projects:
- PROJECT_CONTEXT.md: Quick project overview
- ARCHITECTURE.md: Technical architecture
- CONTRIBUTION_GUIDE.md: How to contribute
- API_REFERENCE.md: Complete API docs
- ECONOMIC_MODEL.md: Economic system explained
- DATABASE_SCHEMAS.md: PostgreSQL + Neo4j schemas
- EXAMPLES.md: Real-world examples
- TROUBLESHOOTING.md: Common issues
- GLOSSARY.md: Term definitions
- CURSOR_WORKFLOWS.md: Cursor prompts

Total size: ~80KB for comprehensive project knowledge."

git push origin main
```

### Step 3: Add to Claude Project

**Option A: Upload Files**
1. Go to claude.ai → Your project
2. Click "Project knowledge"
3. Upload key files:
   - `.claude/PROJECT_CONTEXT.md`
   - `.claude/ARCHITECTURE.md`
   - `.claude/API_REFERENCE.md`
   - `.claude/ECONOMIC_MODEL.md`
   - `.claude/EXAMPLES.md`

**Option B: Connect GitHub**
1. Go to claude.ai → Your project
2. Click "Add content" → "GitHub"
3. Connect repository
4. Claude auto-indexes all `.claude/*.md` files

## What Gets Generated

### 11 Markdown Files (~80KB total)

```
.claude/
├── README.md                    (2KB) - Index of all files
├── PROJECT_CONTEXT.md          (4KB) - Quick overview
├── ARCHITECTURE.md             (10KB) - Technical details
├── CONTRIBUTION_GUIDE.md       (6KB) - How to contribute
├── API_REFERENCE.md            (7KB) - Complete API
├── ECONOMIC_MODEL.md           (7KB) - Economic system
├── DATABASE_SCHEMAS.md         (4KB) - DB structure
├── EXAMPLES.md                 (3KB) - Real examples
├── TROUBLESHOOTING.md          (2KB) - Common issues
├── GLOSSARY.md                 (2KB) - Terms
├── CURSOR_WORKFLOWS.md         (2KB) - Cursor prompts
└── reference/
    ├── initial_contribution.json    - Your $2,413 contribution
    ├── distribution_example.json    - $10k distribution
    └── node_pricing_examples.json   - Pricing examples
```

## What This Fixes

**Before** (without knowledge base):
```
User: How do I record my contribution?
Claude: You can track contributions by documenting in a spreadsheet...
```

**After** (with knowledge base):
```
User: How do I record my contribution?
Claude: To record your contribution to Coherence Network, use this API:

curl -X POST https://api.your-domain.com/v1/contributions \
  -H "Content-Type: application/json" \
  -d '{
    "contributor_id": "your-id",
    "cost_amount": 150.00,
    "resonance": {"coherence_score": 0.85}
  }'

According to CONTRIBUTION_GUIDE.md, your coherence score of 0.85
gives you a 1.35x multiplier on value distributions.
```

**Much better!** 🎯

## Benefits

✅ **Claude knows your project** - No need to re-explain concepts  
✅ **Accurate examples** - Uses your real $2,413 contribution  
✅ **Correct terminology** - Coherence, resonance, weighted cost  
✅ **API reference** - Copy-paste ready curl commands  
✅ **Troubleshooting** - Common issues pre-solved  

## Script Features

✅ **Works anywhere** - Detects git repo automatically  
✅ **Safe** - Doesn't modify existing files  
✅ **Fast** - Generates all files in 5 seconds  
✅ **Complete** - 80KB of documentation  
✅ **Tested** - Verified to work correctly  

## File Structure After Running

```
Coherence-Network/
├── .claude/              ← NEW FOLDER
│   ├── README.md
│   ├── PROJECT_CONTEXT.md
│   ├── ARCHITECTURE.md
│   ├── CONTRIBUTION_GUIDE.md
│   ├── API_REFERENCE.md
│   ├── ECONOMIC_MODEL.md
│   ├── DATABASE_SCHEMAS.md
│   ├── EXAMPLES.md
│   ├── TROUBLESHOOTING.md
│   ├── GLOSSARY.md
│   ├── CURSOR_WORKFLOWS.md
│   └── reference/
│       ├── initial_contribution.json
│       ├── distribution_example.json
│       └── node_pricing_examples.json
├── api/
├── models/
└── ...
```

## Troubleshooting

### "Not in a git repository"

**Solution**: Run from inside your Coherence-Network folder
```bash
cd Coherence-Network
./generate_claude_knowledge.sh
```

### Permission denied

**Solution**: Make script executable
```bash
chmod +x generate_claude_knowledge.sh
```

### Files already exist

**Safe**: Script won't overwrite existing files. Delete `.claude/` first if you want fresh copies:
```bash
rm -rf .claude/
./generate_claude_knowledge.sh
```

## Updating Documentation

When your project changes, just re-run:

```bash
# Delete old version
rm -rf .claude/

# Generate fresh docs
./generate_claude_knowledge.sh

# Commit changes
git add .claude/
git commit -m "Update Claude knowledge base"
git push
```

**Pro tip**: This documentation update is also a contribution! Record it:
```bash
curl -X POST https://api.your-domain.com/v1/contributions \
  -d '{
    "event_type": "DOCUMENTATION",
    "cost_amount": 25.00,
    "resonance": {"documentation_score": 0.95}
  }'
```

## Next Steps

1. ✅ Run `./generate_claude_knowledge.sh`
2. ✅ Review generated files in `.claude/`
3. ✅ Commit to GitHub
4. ✅ Add to your Claude Project
5. ✅ Test by asking Claude: "What is my coherence score and why?"

**Expected answer**:
```
Your coherence score is 0.92, which gives you a 1.42x multiplier.

This high score is due to:
- Perfect architecture alignment (1.0) - you designed the system
- Novel contribution (1.0) - new project inception
- Good code quality (0.85)
- Strong documentation (0.7)

According to ECONOMIC_MODEL.md, this means when $10,000 is distributed,
you receive $9,622 instead of $9,600 - a $22 quality bonus!
```

If Claude answers this correctly citing the docs, **it's working!** 🎉

## Why `.claude/` Folder?

**Benefits**:
- ✅ Version controlled with code
- ✅ Available to all contributors
- ✅ Single source of truth
- ✅ Updates via pull requests
- ✅ Documentation IS a contribution
- ✅ Portable across tools

**Alternative locations**:
- `docs/claude/` - If you want separation
- `.github/claude/` - If GitHub-specific
- `knowledge/` - Generic name

Choose what works for your team!

## Questions?

- Script not working? Open an issue
- Want to modify generated content? Edit the script
- Need custom documentation? Fork and customize

**The network is self-documenting. The network is coherent. The network knows itself.**

🌐 **Happy documenting!**
