#!/bin/bash

################################################################################
# Coherence Network - Next Steps Automation
# Tracks deployment progress and suggests next actions
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROGRESS_FILE=".deployment_progress"

################################################################################
# Progress Tracking
################################################################################

init_progress() {
    if [ ! -f "$PROGRESS_FILE" ]; then
        cat > "$PROGRESS_FILE" << EOF
# Coherence Network Deployment Progress
# Auto-generated: $(date)

PHASE_0_PREREQ=false
PHASE_1_SERVICES=false
PHASE_2_DEPLOYMENT=false
PHASE_3_CODE=false
PHASE_4_VM_DEPLOY=false
PHASE_5_VERIFY=false
PHASE_6_POST=false
EOF
    fi
}

mark_complete() {
    local phase=$1
    sed -i '' "s/${phase}=false/${phase}=true/" "$PROGRESS_FILE" 2>/dev/null || \
    sed -i "s/${phase}=false/${phase}=true/" "$PROGRESS_FILE"
}

is_complete() {
    local phase=$1
    source "$PROGRESS_FILE"
    eval echo \$$phase
}

################################################################################
# Status Display
################################################################################

show_status() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  Coherence Network - Deployment Status                        ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    source "$PROGRESS_FILE"
    
    local phases=(
        "PHASE_0_PREREQ:Prerequisites Check"
        "PHASE_1_SERVICES:Service Signups"
        "PHASE_2_DEPLOYMENT:Automated Deployment"
        "PHASE_3_CODE:Code Generation (Cursor)"
        "PHASE_4_VM_DEPLOY:Deploy to Oracle VM"
        "PHASE_5_VERIFY:Verification"
        "PHASE_6_POST:Post-Deployment Setup"
    )
    
    local total=0
    local completed=0
    
    for phase_info in "${phases[@]}"; do
        IFS=':' read -r phase_var phase_name <<< "$phase_info"
        total=$((total + 1))
        
        eval status=\$$phase_var
        if [ "$status" = "true" ]; then
            echo -e "${GREEN}✓${NC} $phase_name"
            completed=$((completed + 1))
        else
            echo -e "  $phase_name"
        fi
    done
    
    echo ""
    echo "Progress: $completed/$total phases complete"
    
    if [ $completed -eq $total ]; then
        echo ""
        echo -e "${GREEN}🎉 DEPLOYMENT COMPLETE!${NC}"
        echo ""
        echo "Your Coherence Network is live at:"
        echo "  API: https://api.coherencycoin.com"
        echo "  Web: https://coherencycoin.com"
        echo ""
        return 0
    else
        echo ""
        echo "Next: Run './next_steps.sh suggest' to see what to do next"
        return 1
    fi
}

################################################################################
# Suggest Next Action
################################################################################

suggest_next() {
    source "$PROGRESS_FILE"
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "NEXT RECOMMENDED ACTION"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    if [ "$PHASE_0_PREREQ" != "true" ]; then
        cat << EOF
📋 PHASE 0: Prerequisites Check

ACTION: Install required tools

COMMAND:
  brew install git docker curl jq
  open -a Docker

VERIFY:
  git --version
  docker --version

WHEN DONE:
  ./next_steps.sh complete PHASE_0_PREREQ
EOF
        return
    fi
    
    if [ "$PHASE_1_SERVICES" != "true" ]; then
        cat << EOF
🔑 PHASE 1: Service Signups

ACTION: Sign up for free tier services

SERVICES TO CONFIGURE:
  1. Supabase (https://supabase.com) - PostgreSQL
  2. Neo4j Aura (https://console.neo4j.io) - Graph DB
  3. Redis Cloud (https://redis.com/try-free) - Cache
  4. Cloudflare (https://dash.cloudflare.com) - DNS
  5. Railway (https://railway.app) - API hosting
  6. GitHub Token (https://github.com/settings/tokens) - CI/CD

GUIDE: See DEPLOYMENT_GUIDE.md Phase 1

SAVE CREDENTIALS TO:
  ~/ccn_credentials.txt

WHEN DONE:
  ./next_steps.sh complete PHASE_1_SERVICES
EOF
        return
    fi
    
    if [ "$PHASE_2_DEPLOYMENT" != "true" ]; then
        cat << EOF
🚀 PHASE 2: Automated Deployment

ACTION: Run the deployment automation

COMMANDS:
  ./deploy_master.sh all

This will:
  - Configure DNS records
  - Set up Railway API service
  - Deploy application skeleton
  - Verify basic connectivity

ESTIMATED TIME: 15 minutes

WHEN DONE:
  ./next_steps.sh complete PHASE_2_DEPLOYMENT
EOF
        return
    fi
    
    if [ "$PHASE_3_CODE" != "true" ]; then
        cat << EOF
💻 PHASE 3: Code Generation with Cursor

ACTION: Generate application code using Cursor

SETUP:
  1. Open Cursor: open -a Cursor
  2. Select Model: Cmd+Shift+P → "google/gemini-flash-1.5"
  3. Open Chat: Cmd+L

PROMPTS: Use cursor_prompts_openrouter.md
  1. FastAPI Structure (5 min)
  2. Database Integration (10 min)
  3. Distribution Engine (7 min)
  4. GitHub Webhooks (5 min)
  5. Node Operators (8 min)
  6. Landing Page (5 min)

ESTIMATED TIME: 40 minutes

WHEN DONE:
  ./next_steps.sh complete PHASE_3_CODE
EOF
        return
    fi
    
    if [ "$PHASE_4_VM_DEPLOY" != "true" ]; then
        cat << EOF
📤 PHASE 4: Deploy Code to VM

ACTION: Push code to GitHub and deploy to Railway

COMMANDS:
  # Commit code
  git add .
  git commit -m "Generated Coherence Network application"
  git push origin main
  
  # Deploy to VM
  ./deploy_application.sh

ESTIMATED TIME: 10 minutes

WHEN DONE:
  ./next_steps.sh complete PHASE_4_VM_DEPLOY
EOF
        return
    fi
    
    if [ "$PHASE_5_VERIFY" != "true" ]; then
        cat << EOF
✅ PHASE 5: Verification

ACTION: Verify deployment is working

COMMAND:
  ./verify_deployment.sh

This checks:
  - DNS resolution
  - API endpoints
  - Database connectivity
  - SSL certificates
  - Application health

EXPECTED: 90%+ pass rate

WHEN DONE:
  ./next_steps.sh complete PHASE_5_VERIFY
EOF
        return
    fi
    
    if [ "$PHASE_6_POST" != "true" ]; then
        cat << EOF
🎯 PHASE 6: Post-Deployment Setup

ACTIONS:
  1. Record your initial contribution
  2. Set up GitHub webhook
  3. Update Claude Project knowledge

COMMANDS:
  # Record contribution
  curl -X POST https://api.coherencycoin.com/v1/contributions \\
    -H "Content-Type: application/json" \\
    -d '{"cost_amount": 450.06, ...}'
  
  # Generate Claude knowledge
  ./generate_claude_knowledge.sh
  git add .claude/
  git commit -m "Add Claude knowledge base"
  git push

  # Configure GitHub webhook
  # Go to: https://github.com/seeker71/Coherence-Network/settings/hooks

WHEN DONE:
  ./next_steps.sh complete PHASE_6_POST
EOF
        return
    fi
    
    # All phases complete
    cat << EOF
🎉 ALL PHASES COMPLETE!

Your Coherence Network is fully deployed and configured.

NEXT STEPS:
  1. Invite contributors
  2. Set up monitoring (Uptime Robot)
  3. Create first distribution
  4. Marketing & growth

USEFUL COMMANDS:
  ./next_steps.sh status     - Show deployment status
  ./verify_deployment.sh     - Re-run verification
  docker-compose logs        - View application logs (on VM)

Visit your deployment:
  https://coherencycoin.com
  https://api.coherencycoin.com
EOF
}

################################################################################
# Helper Functions
################################################################################

run_quick_test() {
    echo "Running quick connectivity test..."
    echo ""
    
    # Test API
    echo -n "Testing API... "
    if curl -s -o /dev/null -w "%{http_code}" https://api.coherencycoin.com/health | grep -q "200"; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${YELLOW}✗ FAIL${NC}"
    fi
    
    # Test DNS
    echo -n "Testing DNS... "
    if dig +short api.coherencycoin.com | grep -q "."; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${YELLOW}✗ FAIL${NC}"
    fi
    
    # Test database config
    echo -n "Testing config... "
    if [ -f ".deployment_config" ]; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${YELLOW}✗ MISSING${NC}"
    fi
}

show_help() {
    cat << EOF
Coherence Network - Next Steps Helper

USAGE:
  ./next_steps.sh [command]

COMMANDS:
  status              Show deployment progress
  suggest             Show next recommended action
  complete PHASE      Mark a phase as complete
  test                Run quick connectivity test
  help                Show this help message

PHASES:
  PHASE_0_PREREQ      Prerequisites installed
  PHASE_1_SERVICES    Services signed up
  PHASE_2_DEPLOYMENT  Automated deployment run
  PHASE_3_CODE        Code generated with Cursor
  PHASE_4_VM_DEPLOY   Code deployed to VM
  PHASE_5_VERIFY      Verification passed
  PHASE_6_POST        Post-deployment complete

EXAMPLES:
  ./next_steps.sh status
  ./next_steps.sh suggest
  ./next_steps.sh complete PHASE_0_PREREQ
  ./next_steps.sh test
EOF
}

################################################################################
# Main
################################################################################

main() {
    init_progress
    
    case "${1:-status}" in
        status)
            show_status
            ;;
        suggest)
            suggest_next
            ;;
        complete)
            if [ -z "$2" ]; then
                echo "Error: Please specify phase to complete"
                echo "Usage: $0 complete PHASE_0_PREREQ"
                exit 1
            fi
            mark_complete "$2"
            echo -e "${GREEN}✓${NC} Marked $2 as complete"
            echo ""
            suggest_next
            ;;
        test)
            run_quick_test
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "Unknown command: $1"
            echo "Run '$0 help' for usage information"
            exit 1
            ;;
    esac
}

main "$@"
