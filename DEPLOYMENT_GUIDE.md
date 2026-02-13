# COMPLETE DEPLOYMENT GUIDE
## Coherence Network on coherencycoin.com
### Mac M4 Ultra with Ollama & Cursor

**Total Time**: 2-3 hours  
**Total Cost**: $0/month (free tier everything)  
**Difficulty**: Medium (mostly automated)

---

## 📋 WHAT YOU'LL BUILD

- ✅ API at `https://api.coherencycoin.com`
- ✅ Website at `https://coherencycoin.com`
- ✅ PostgreSQL database (Supabase)
- ✅ Neo4j graph database
- ✅ Redis cache
- ✅ Oracle Cloud VM (forever free)
- ✅ Automatic HTTPS via Cloudflare
- ✅ GitHub webhook integration
- ✅ All for $0/month!

---

## 🎯 QUICK START (TL;DR)

```bash
# 1. Download scripts
cd ~/Coherence-Network
curl -O https://raw.githubusercontent.com/.../deploy_master.sh
curl -O https://raw.githubusercontent.com/.../verify_deployment.sh
chmod +x *.sh

# 2. Run deployment
./deploy_master.sh all

# 3. Verify
./verify_deployment.sh

# 4. Done!
open https://coherencycoin.com
```

---

## 📖 DETAILED STEP-BY-STEP GUIDE

### PHASE 0: Prerequisites (10 minutes)

#### Step 0.1: Install Required Tools

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install git docker curl jq

# Start Docker Desktop
open -a Docker

# Verify installations
git --version
docker --version
curl --version
jq --version
```

**Expected Output**: All commands show version numbers

#### Step 0.2: Verify Cursor & OpenRouter

```bash
# Check Cursor is installed
ls -la /Applications/Cursor.app
# Should show Cursor.app directory

# Open Cursor
open -a Cursor

# In Cursor:
# 1. Cmd+Shift+P
# 2. Type "Select Model"
# 3. Choose "google/gemini-flash-1.5" or similar OpenRouter free model
# 4. Close Cursor
```

**Expected**: Cursor opens and model is selectable

#### Step 0.3: Clone/Setup Repository

```bash
# If starting fresh
cd ~
git clone https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network

# Or if already have repo
cd ~/path/to/Coherence-Network
git pull origin main
```

**Verify**: You're in the repo root with `.git/` directory

---

### PHASE 1: Service Signups (45 minutes)

This is the only manual part. Follow each service in order.

#### Step 1.1: Supabase (PostgreSQL) - 10 minutes

1. **Go to**: https://supabase.com/dashboard
2. **Click**: "New Project"
3. **Settings**:
   - Name: `coherence-network`
   - Database Password: (generate strong password, save it!)
   - Region: Closest to you
4. **Wait**: 2 minutes for provisioning
5. **Get Connection String**:
   - Settings → Database → Connection String
   - Copy the `postgres://` URL
6. **Save**:
   ```bash
   echo 'SUPABASE_URL="postgres://..."' >> ~/ccn_credentials.txt
   ```

**Verify**: Can connect
```bash
# Install PostgreSQL client
brew install postgresql

# Test connection
psql "YOUR_SUPABASE_URL" -c "SELECT 1;"
# Should print: 1
```

#### Step 1.2: Neo4j Aura (Graph DB) - 10 minutes

1. **Go to**: https://neo4j.com/cloud/aura-free
2. **Sign up**: Use GitHub or email
3. **Create Free Instance**:
   - Name: `coherence-network`
   - Region: Same as Supabase
4. **Download Credentials**: Click "Download" button
5. **Save**:
   ```bash
   echo 'NEO4J_URI="neo4j+s://..."' >> ~/ccn_credentials.txt
   echo 'NEO4J_PASSWORD="..."' >> ~/ccn_credentials.txt
   ```

**Verify**: Can connect
```bash
# Install Neo4j shell
brew install cypher-shell

# Test connection (use password from download)
cypher-shell -a YOUR_NEO4J_URI -u neo4j -p YOUR_PASSWORD
# Type: RETURN 1;
# Should print: 1
```

#### Step 1.3: Redis Cloud (Cache) - 5 minutes

1. **Go to**: https://redis.com/try-free
2. **Sign up**: Use Google or email
3. **Create Free Database**:
   - Name: `coherence-cache`
   - Region: Same as others
4. **Get Endpoint**:
   - Database → Configuration → Public Endpoint
   - Copy the `redis://` URL with password
5. **Save**:
   ```bash
   echo 'REDIS_URL="redis://..."' >> ~/ccn_credentials.txt
   ```

**Verify**: Can connect
```bash
# Install Redis client
brew install redis

# Extract host and port from URL
# Format: redis://default:PASSWORD@HOST:PORT
redis-cli -h YOUR_HOST -p YOUR_PORT -a YOUR_PASSWORD ping
# Should print: PONG
```

#### Step 1.4: Cloudflare (DNS + CDN) - 10 minutes

1. **Go to**: https://dash.cloudflare.com
2. **Add Site**: coherencycoin.com
3. **Follow Instructions**:
   - Copy the 2 nameservers shown
   - Go to your domain registrar
   - Update nameservers (this can take 24 hours, but usually 5 minutes)
4. **Wait**: Check "Recheck Nameservers" until active
5. **Create API Token**:
   - My Profile → API Tokens → Create Token
   - Use "Edit Zone DNS" template
   - Zone Resources: Include → Specific Zone → coherencycoin.com
   - Create Token and copy it
6. **Get Zone ID**:
   - Overview page of coherencycoin.com
   - Right column → API → Zone ID
7. **Save**:
   ```bash
   echo 'CLOUDFLARE_API_TOKEN="..."' >> ~/ccn_credentials.txt
   echo 'CLOUDFLARE_ZONE_ID="..."' >> ~/ccn_credentials.txt
   ```

**Verify**: Nameservers updated
```bash
dig coherencycoin.com NS +short
# Should show Cloudflare nameservers (*.ns.cloudflare.com)
```

#### Step 1.5: Oracle Cloud (VM) - 15 minutes

1. **Go to**: https://cloud.oracle.com
2. **Sign Up**: Requires credit card (won't be charged, free tier forever)
3. **Create Compute Instance**:
   - Compute → Instances → Create Instance
   - Name: `coherence-network`
   - Image: Ubuntu 22.04
   - Shape: VM.Standard.E2.1.Micro (Always Free)
   - Add SSH Key: Generate new pair, download private key
   - Assign Public IP: Yes
4. **Wait**: 2-3 minutes for provisioning
5. **Configure Firewall**:
   - Instance Details → Attached VNICs → Subnet → Security Lists
   - Ingress Rules → Add:
     - Source: 0.0.0.0/0
     - IP Protocol: TCP
     - Destination Port: 80,443,22,8000
6. **Save**:
   ```bash
   # Move SSH key to safe location
   mv ~/Downloads/ssh-key-*.key ~/.ssh/oracle_vm_key
   chmod 600 ~/.ssh/oracle_vm_key
   
   # Save credentials
   echo 'ORACLE_VM_IP="YOUR_VM_IP"' >> ~/ccn_credentials.txt
   echo 'ORACLE_SSH_KEY="/Users/$(whoami)/.ssh/oracle_vm_key"' >> ~/ccn_credentials.txt
   ```

**Verify**: Can SSH
```bash
ssh -i ~/.ssh/oracle_vm_key ubuntu@YOUR_VM_IP
# Should connect and show Ubuntu prompt
# Type: exit
```

#### Step 1.6: GitHub (CI/CD) - 5 minutes

1. **Go to**: https://github.com/settings/tokens
2. **Generate Token**:
   - Classic token
   - Name: `coherence-network-deploy`
   - Scopes: `repo`, `workflow`
   - Generate
3. **Save**:
   ```bash
   echo 'GITHUB_TOKEN="ghp_..."' >> ~/ccn_credentials.txt
   ```

**Verify**: Token works
```bash
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
# Should show your GitHub user info
```

---

### PHASE 2: Automated Deployment (15 minutes)

Now the fun part - everything is automated!

#### Step 2.1: Download Deployment Scripts

```bash
cd ~/Coherence-Network

# Download scripts (from the files you created)
# Alternatively, if files are in /mnt/user-data/outputs:
cp /path/to/deploy_master.sh .
cp /path/to/verify_deployment.sh .

# Make executable
chmod +x deploy_master.sh verify_deployment.sh
```

#### Step 2.2: Consolidate Credentials

```bash
# Create deployment config from your saved credentials
cat ~/ccn_credentials.txt > .deployment_config

# Add generated secrets
cat >> .deployment_config << EOF
SECRET_KEY=$(openssl rand -hex 32)
API_KEY_ADMIN=$(openssl rand -hex 16)
GITHUB_WEBHOOK_SECRET=$(openssl rand -hex 32)
EOF

# Secure the file
chmod 600 .deployment_config

# Verify
cat .deployment_config
# Should show all your credentials
```

#### Step 2.3: Run Deployment (Fully Automated)

```bash
# Full deployment - sit back and watch!
./deploy_master.sh all

# This will:
# 1. Configure DNS (2 minutes)
# 2. Setup Oracle VM (5 minutes)
# 3. Deploy application (5 minutes)
# 4. Verify deployment (1 minute)
```

**Watch the output**. It will show progress for each step.

**If any step fails**, you can run individually:
```bash
./deploy_master.sh dns      # Just DNS
./deploy_master.sh vm       # Just VM setup
./deploy_master.sh deploy   # Just app deployment
./deploy_master.sh verify   # Just verification
```

---

### PHASE 3: Generate Code with Cursor (40 minutes)

Now use Cursor to generate the actual application code.

#### Step 3.1: Open Cursor and Configure

```bash
# Open project in Cursor
open -a Cursor ~/Coherence-Network
```

**In Cursor**:
1. Press `Cmd+Shift+P`
2. Type "Select Model"
3. Choose: `google/gemini-flash-1.5` (or similar free model)
4. Press `Cmd+L` to open Chat

#### Step 3.2: Run Cursor Prompts (6 prompts)

Open the file `cursor_prompts_openrouter.md` and follow each prompt:

**PROMPT 1** (5 minutes): FastAPI Structure
```
Copy entire PROMPT 1 from cursor_prompts_openrouter.md
Paste into Cursor Chat
Send
Wait for generation
Review code
Accept changes (checkmark or Cmd+Enter)
```

**Test**:
```bash
pip install -r requirements.txt
uvicorn api.main:app --reload &
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
kill %1  # Stop uvicorn
```

**PROMPT 2** (10 minutes): Database Integration
```
Copy PROMPT 2
Paste into Cursor
Send and accept
```

**Test**:
```bash
# Load environment
source .deployment_config
export DATABASE_URL=$SUPABASE_URL

uvicorn api.main:app --reload &
curl -X POST http://localhost:8000/v1/contributors \
  -H "Content-Type: application/json" \
  -d '{"type":"HUMAN","name":"Test","email":"test@example.com"}'
kill %1
```

**PROMPT 3** (7 minutes): Distribution Engine
```
Copy PROMPT 3
Paste into Cursor
Send and accept
```

**PROMPT 4** (5 minutes): GitHub Webhooks
```
Copy PROMPT 4
Paste into Cursor
Send and accept
```

**PROMPT 5** (8 minutes): Node Operators
```
Copy PROMPT 5
Paste into Cursor
Send and accept
```

**PROMPT 6** (5 minutes): Landing Page
```
Copy PROMPT 6
Paste into Cursor
Send and accept
```

**Total**: 40 minutes of Cursor work

---

### PHASE 4: Deploy Code to Oracle VM (10 minutes)

#### Step 4.1: Push to GitHub

```bash
# Commit all generated code
git add .
git commit -m "Generated complete Coherence Network application via Cursor

- FastAPI backend with health endpoint
- PostgreSQL and Neo4j integration
- Value distribution engine
- GitHub webhook handler
- Node operator marketplace
- Landing page frontend

Generated using Cursor with google/gemini-flash-1.5"

git push origin main
```

#### Step 4.2: Deploy to VM

```bash
# SSH into VM
ssh -i ~/.ssh/oracle_vm_key ubuntu@$ORACLE_VM_IP

# Clone/update repo
cd ~/coherence-network
git clone https://github.com/seeker71/Coherence-Network.git .
# Or: git pull origin main

# Copy environment file from local
exit
scp -i ~/.ssh/oracle_vm_key .deployment_config ubuntu@$ORACLE_VM_IP:~/coherence-network/.env

# SSH back in
ssh -i ~/.ssh/oracle_vm_key ubuntu@$ORACLE_VM_IP
cd ~/coherence-network

# Build and start
docker-compose build
docker-compose up -d

# Check logs
docker-compose logs -f
# Press Ctrl+C when you see "Application startup complete"

exit
```

---

### PHASE 5: Verification (5 minutes)

#### Step 5.1: Run Verification Script

```bash
cd ~/Coherence-Network
./verify_deployment.sh
```

**Expected Output**:
```
═══════════════════════════════════════
VERIFICATION SUMMARY
═══════════════════════════════════════

Total Checks:  30
Passed:        28
Failed:        2
Pass Rate:     93%

✓ DEPLOYMENT SUCCESSFUL

Your Coherence Network is live at:
  API: https://api.coherencycoin.com
  Web: https://coherencycoin.com
```

#### Step 5.2: Manual Verification

```bash
# Test API
curl https://api.coherencycoin.com/health
# Should return: {"status":"healthy"}

# Test HTTPS
curl -I https://api.coherencycoin.com
# Should show: HTTP/2 200

# Open website
open https://coherencycoin.com
# Should show landing page
```

**If everything works: SUCCESS!** 🎉

---

### PHASE 6: Post-Deployment Setup (15 minutes)

#### Step 6.1: Record Your Initial Contribution

```bash
# Calculate your total cost
# - Deployment time: 3 hours × $150/hr = $450
# - Mac M4 compute: 3 hours × $0.02/hr = $0.06
# - Total: $450.06

# Record it
curl -X POST https://api.coherencycoin.com/v1/contributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY_ADMIN" \
  -d '{
    "contributor_id": "YOUR_CONTRIBUTOR_ID",
    "asset_id": "coherence-network-asset-id",
    "event_type": "PROJECT_DEPLOYMENT",
    "cost_amount": 450.06,
    "resonance": {
      "code_quality_score": 0.8,
      "architecture_alignment": 1.0,
      "value_add_score": 1.0,
      "documentation_score": 0.9
    },
    "metadata": {
      "hours_worked": 3,
      "description": "Complete deployment: infrastructure + code generation"
    }
  }'
```

#### Step 6.2: Configure GitHub Webhook

1. **Go to**: https://github.com/seeker71/Coherence-Network/settings/hooks
2. **Add Webhook**:
   - Payload URL: `https://api.coherencycoin.com/webhooks/github`
   - Content type: `application/json`
   - Secret: (from `$GITHUB_WEBHOOK_SECRET` in .deployment_config)
   - Events: "Just the push event"
3. **Test**: Make a commit and verify webhook received

#### Step 6.3: Update Claude Project

```bash
# Run knowledge base generator
./generate_claude_knowledge.sh

# Commit to GitHub
git add .claude/
git commit -m "Add Claude Project knowledge base"
git push origin main

# Upload to Claude Project:
# 1. Go to claude.ai → Your project
# 2. "Add content" → Upload .claude/*.md files
```

---

## 🎯 NEXT STEPS

### Immediate (Today)

1. ✅ **Test the API**
   ```bash
   curl https://api.coherencycoin.com/health
   ```

2. ✅ **Invite First Contributor**
   - Share API docs
   - Have them create account
   - Record their first contribution

3. ✅ **Customize Landing Page**
   - Edit `frontend/index.html`
   - Add your branding
   - Deploy update

### This Week

4. ✅ **Set Up Monitoring**
   - Add Uptime Robot: https://uptimerobot.com (free)
   - Monitor API health endpoint
   - Get alerts if down

5. ✅ **First Distribution**
   - When you get first revenue
   - Run distribution to test payout system

6. ✅ **Invite Node Operators**
   - Post on Reddit r/selfhosted
   - Offer bonus for first 5 operators

### This Month

7. ✅ **Add Features**
   - Use remaining Cursor prompts
   - Add analytics dashboard
   - Add contributor profiles

8. ✅ **Marketing**
   - Post on Hacker News
   - Write blog post
   - Create demo video

9. ✅ **Scale**
   - Monitor usage
   - Upgrade if needed (still free tier for now!)

---

## 🐛 TROUBLESHOOTING

### Problem: DNS not resolving

**Symptoms**: `dig api.coherencycoin.com` returns nothing

**Solution**:
```bash
# Check nameservers
dig coherencycoin.com NS +short

# If not Cloudflare nameservers, wait longer or check registrar

# Force DNS record creation
./deploy_master.sh dns

# Wait 5 minutes and check again
```

### Problem: SSH to Oracle VM fails

**Symptoms**: `ssh: connect to host X port 22: Connection refused`

**Solution**:
```bash
# 1. Check firewall in Oracle Cloud Console
# 2. Verify SSH key permissions
chmod 600 ~/.ssh/oracle_vm_key

# 3. Try with verbose output
ssh -v -i ~/.ssh/oracle_vm_key ubuntu@YOUR_VM_IP

# 4. Check if VM is running in Oracle console
```

### Problem: Docker build fails

**Symptoms**: `ERROR: failed to solve`

**Solution**:
```bash
# SSH into VM
ssh -i ~/.ssh/oracle_vm_key ubuntu@$ORACLE_VM_IP

# Check Docker
docker info

# Rebuild with no cache
cd ~/coherence-network
docker-compose build --no-cache

# Check logs
docker-compose logs
```

### Problem: API returns 502 Bad Gateway

**Symptoms**: `curl https://api.coherencycoin.com` returns 502

**Solution**:
```bash
# Check if container is running
ssh -i ~/.ssh/oracle_vm_key ubuntu@$ORACLE_VM_IP
docker ps | grep coherence

# If not running, check logs
docker-compose logs api

# Restart
docker-compose restart api
```

### Problem: Cursor not generating code

**Symptoms**: Cursor returns "I can't help with that"

**Solution**:
```bash
# 1. Check model selected
# Cmd+Shift+P → Select Model → Choose free model

# 2. Try different prompt phrasing
# Instead of "create", use "generate code for"

# 3. Use Ollama locally
ollama pull llama3.1
# Then use local model in Cursor
```

---

## 💰 COST BREAKDOWN

**Monthly Recurring**: $0.00
- Supabase Free: 500MB database ✅
- Neo4j Aura Free: 50MB graph ✅
- Redis Cloud Free: 30MB cache ✅
- Oracle Cloud Free: Forever! ✅
- Cloudflare Free: Unlimited ✅

**One-Time Setup**: $0.00
- Domain: Already owned ✅
- All services: Free tier ✅

**When You'll Need to Upgrade** (still cheap):
- >500MB data in PostgreSQL → $25/month
- >1M requests/month → Scale horizontally, add nodes
- **Even at scale: <$100/month** vs $1000+ on AWS

---

## ✅ SUCCESS CRITERIA

You're done when:
- ✅ https://coherencycoin.com loads
- ✅ https://api.coherencycoin.com/health returns 200
- ✅ Can create contributor via API
- ✅ GitHub webhook triggers on push
- ✅ Verification script shows 90%+ pass rate

**Congratulations!** You have a production Coherence Network! 🎉

---

## 📞 GETTING HELP

**Scripts not working?**
- Check the troubleshooting section above
- Review error messages carefully
- Run verification script: `./verify_deployment.sh`

**Cursor not cooperating?**
- Try different free model
- Use Ollama locally
- Break prompt into smaller pieces

**Database issues?**
- Check service status pages
- Verify connection strings
- Test with CLI tools

**Need more help?**
- GitHub Issues: https://github.com/seeker71/Coherence-Network/issues
- Read logs: `docker-compose logs` on VM

---

## 🎓 WHAT YOU LEARNED

Through this deployment, you now know how to:
- ✅ Set up free tier cloud infrastructure
- ✅ Configure DNS with Cloudflare
- ✅ Deploy Docker apps to Oracle Cloud
- ✅ Use Cursor for code generation
- ✅ Integrate multiple databases
- ✅ Set up automated deployments
- ✅ Run a production web service for $0/month

**These skills are valuable!** You can now deploy any project for free.

---

**The network is live. The network is coherent. The network is yours.**

🌐 **Welcome to Coherence.**
