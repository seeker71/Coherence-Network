#!/bin/bash

################################################################################
# Coherence Network - Deployment Verification Script
# For Mac M4 Ultra
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_check() {
    echo -ne "${BLUE}[CHECK]${NC} $1... "
}

log_pass() {
    echo -e "${GREEN}✓ PASS${NC}"
}

log_fail() {
    echo -e "${RED}✗ FAIL${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠ WARN${NC}"
}

################################################################################
# Verification Functions
################################################################################

check_local_environment() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "1. LOCAL ENVIRONMENT"
    echo "═══════════════════════════════════════════════════════════════"
    
    local_checks=0
    local_passed=0
    
    # Git
    local_checks=$((local_checks + 1))
    log_check "Git installed"
    if command -v git &> /dev/null; then
        log_pass
        local_passed=$((local_passed + 1))
    else
        log_fail
    fi
    
    # Docker
    local_checks=$((local_checks + 1))
    log_check "Docker installed"
    if command -v docker &> /dev/null; then
        log_pass
        local_passed=$((local_passed + 1))
    else
        log_fail
    fi
    
    # Cursor
    local_checks=$((local_checks + 1))
    log_check "Cursor installed"
    if [ -d "/Applications/Cursor.app" ] || [ -d "$HOME/.cursor" ]; then
        log_pass
        local_passed=$((local_passed + 1))
    else
        log_warn
    fi
    
    # Ollama
    local_checks=$((local_checks + 1))
    log_check "Ollama running"
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        log_pass
        local_passed=$((local_passed + 1))
    else
        log_warn
    fi
    
    # Git repo
    local_checks=$((local_checks + 1))
    log_check "In Coherence-Network repo"
    if [ -d ".git" ] && git remote get-url origin 2>/dev/null | grep -q "Coherence-Network"; then
        log_pass
        local_passed=$((local_passed + 1))
    else
        log_fail
    fi
    
    echo ""
    echo "Local Environment: $local_passed/$local_checks checks passed"
    return $((local_checks - local_passed))
}

check_service_credentials() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "2. SERVICE CREDENTIALS"
    echo "═══════════════════════════════════════════════════════════════"
    
    cred_checks=0
    cred_passed=0
    
    if [ ! -f ".deployment_config" ]; then
        echo "No .deployment_config file found. Run deployment script first."
        return 1
    fi
    
    source .deployment_config
    
    # Supabase
    cred_checks=$((cred_checks + 1))
    log_check "Supabase configured"
    if [ -n "$SUPABASE_URL" ]; then
        log_pass
        cred_passed=$((cred_passed + 1))
    else
        log_fail
    fi
    
    # Neo4j
    cred_checks=$((cred_checks + 1))
    log_check "Neo4j configured"
    if [ -n "$NEO4J_URI" ]; then
        log_pass
        cred_passed=$((cred_passed + 1))
    else
        log_fail
    fi
    
    # Redis
    cred_checks=$((cred_checks + 1))
    log_check "Redis configured"
    if [ -n "$REDIS_URL" ]; then
        log_pass
        cred_passed=$((cred_passed + 1))
    else
        log_fail
    fi
    
    # Cloudflare
    cred_checks=$((cred_checks + 1))
    log_check "Cloudflare configured"
    if [ -n "$CLOUDFLARE_API_TOKEN" ]; then
        log_pass
        cred_passed=$((cred_passed + 1))
    else
        log_fail
    fi
    
    # Oracle
    cred_checks=$((cred_checks + 1))
    log_check "Oracle VM configured"
    if [ -n "$ORACLE_VM_IP" ]; then
        log_pass
        cred_passed=$((cred_passed + 1))
    else
        log_fail
    fi
    
    echo ""
    echo "Service Credentials: $cred_passed/$cred_checks checks passed"
    return $((cred_checks - cred_passed))
}

check_dns_configuration() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "3. DNS CONFIGURATION"
    echo "═══════════════════════════════════════════════════════════════"
    
    dns_checks=0
    dns_passed=0
    
    # api.coherencycoin.com
    dns_checks=$((dns_checks + 1))
    log_check "api.coherencycoin.com resolves"
    if dig +short api.coherencycoin.com | grep -q "."; then
        log_pass
        dns_passed=$((dns_passed + 1))
        
        # Check if points to Oracle VM
        if [ -f ".deployment_config" ]; then
            source .deployment_config
            if dig +short api.coherencycoin.com | grep -q "$ORACLE_VM_IP"; then
                echo "  → Points to Oracle VM ✓"
            fi
        fi
    else
        log_fail
    fi
    
    # coherencycoin.com
    dns_checks=$((dns_checks + 1))
    log_check "coherencycoin.com resolves"
    if dig +short coherencycoin.com | grep -q "."; then
        log_pass
        dns_passed=$((dns_passed + 1))
    else
        log_fail
    fi
    
    # www.coherencycoin.com
    dns_checks=$((dns_checks + 1))
    log_check "www.coherencycoin.com resolves"
    if dig +short www.coherencycoin.com | grep -q "."; then
        log_pass
        dns_passed=$((dns_passed + 1))
    else
        log_warn
    fi
    
    echo ""
    echo "DNS Configuration: $dns_passed/$dns_checks checks passed"
    return $((dns_checks - dns_passed))
}

check_database_connectivity() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "4. DATABASE CONNECTIVITY"
    echo "═══════════════════════════════════════════════════════════════"
    
    db_checks=0
    db_passed=0
    
    if [ ! -f ".deployment_config" ]; then
        echo "No .deployment_config file found."
        return 1
    fi
    
    source .deployment_config
    
    # PostgreSQL (Supabase)
    db_checks=$((db_checks + 1))
    log_check "PostgreSQL connection"
    if command -v psql &> /dev/null; then
        if psql "$SUPABASE_URL" -c "SELECT 1;" &> /dev/null; then
            log_pass
            db_passed=$((db_passed + 1))
        else
            log_fail
        fi
    else
        log_warn
        echo "  → psql not installed, skipping test"
    fi
    
    # Neo4j
    db_checks=$((db_checks + 1))
    log_check "Neo4j connection"
    if command -v cypher-shell &> /dev/null; then
        if echo "RETURN 1;" | cypher-shell -a "$NEO4J_URI" -u neo4j -p "$NEO4J_PASSWORD" &> /dev/null; then
            log_pass
            db_passed=$((db_passed + 1))
        else
            log_fail
        fi
    else
        log_warn
        echo "  → cypher-shell not installed, skipping test"
    fi
    
    # Redis
    db_checks=$((db_checks + 1))
    log_check "Redis connection"
    if command -v redis-cli &> /dev/null; then
        redis_host=$(echo "$REDIS_URL" | sed 's|redis://.*@||' | cut -d':' -f1)
        redis_port=$(echo "$REDIS_URL" | sed 's|redis://.*@||' | cut -d':' -f2)
        if redis-cli -h "$redis_host" -p "$redis_port" ping &> /dev/null; then
            log_pass
            db_passed=$((db_passed + 1))
        else
            log_fail
        fi
    else
        log_warn
        echo "  → redis-cli not installed, skipping test"
    fi
    
    echo ""
    echo "Database Connectivity: $db_passed/$db_checks checks passed (warnings OK)"
    return 0  # Don't fail on warnings
}

check_oracle_vm() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "5. ORACLE VM STATUS"
    echo "═══════════════════════════════════════════════════════════════"
    
    vm_checks=0
    vm_passed=0
    
    if [ ! -f ".deployment_config" ]; then
        echo "No .deployment_config file found."
        return 1
    fi
    
    source .deployment_config
    
    # SSH connectivity
    vm_checks=$((vm_checks + 1))
    log_check "SSH connection to VM"
    if ssh -i "$ORACLE_SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@"$ORACLE_VM_IP" "echo 'Connected'" &> /dev/null; then
        log_pass
        vm_passed=$((vm_passed + 1))
    else
        log_fail
        echo ""
        echo "SSH Connection Failed. Troubleshooting:"
        echo "1. Check Oracle Cloud firewall rules (allow port 22)"
        echo "2. Verify SSH key permissions: chmod 600 $ORACLE_SSH_KEY"
        echo "3. Test manually: ssh -i $ORACLE_SSH_KEY ubuntu@$ORACLE_VM_IP"
        return 1
    fi
    
    # Docker installed
    vm_checks=$((vm_checks + 1))
    log_check "Docker installed on VM"
    if ssh -i "$ORACLE_SSH_KEY" ubuntu@"$ORACLE_VM_IP" "docker --version" &> /dev/null; then
        log_pass
        vm_passed=$((vm_passed + 1))
    else
        log_fail
    fi
    
    # Caddy installed
    vm_checks=$((vm_checks + 1))
    log_check "Caddy installed on VM"
    if ssh -i "$ORACLE_SSH_KEY" ubuntu@"$ORACLE_VM_IP" "caddy version" &> /dev/null; then
        log_pass
        vm_passed=$((vm_passed + 1))
    else
        log_fail
    fi
    
    # Application running
    vm_checks=$((vm_checks + 1))
    log_check "Application container running"
    if ssh -i "$ORACLE_SSH_KEY" ubuntu@"$ORACLE_VM_IP" "docker ps | grep coherence-api" &> /dev/null; then
        log_pass
        vm_passed=$((vm_passed + 1))
    else
        log_fail
    fi
    
    echo ""
    echo "Oracle VM Status: $vm_passed/$vm_checks checks passed"
    return $((vm_checks - vm_passed))
}

check_api_endpoints() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "6. API ENDPOINTS"
    echo "═══════════════════════════════════════════════════════════════"
    
    api_checks=0
    api_passed=0
    
    API_URL="https://api.coherencycoin.com"
    
    # Health endpoint
    api_checks=$((api_checks + 1))
    log_check "GET /health"
    response=$(curl -s -w "%{http_code}" -o /tmp/health_response.json "$API_URL/health" 2>/dev/null || echo "000")
    if [ "$response" = "200" ]; then
        log_pass
        api_passed=$((api_passed + 1))
        cat /tmp/health_response.json | jq '.' 2>/dev/null || cat /tmp/health_response.json
    else
        log_fail
        echo "  → HTTP $response"
    fi
    
    # Contributors endpoint
    api_checks=$((api_checks + 1))
    log_check "POST /v1/contributors (API exists)"
    response=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$API_URL/v1/contributors" \
        -H "Content-Type: application/json" \
        -d '{"type":"HUMAN","name":"Test","email":"test@example.com"}' 2>/dev/null || echo "000")
    if [ "$response" = "200" ] || [ "$response" = "401" ]; then
        log_pass
        api_passed=$((api_passed + 1))
        echo "  → Endpoint exists (got HTTP $response)"
    else
        log_warn
        echo "  → HTTP $response (may not be implemented yet)"
    fi
    
    # SSL/TLS
    api_checks=$((api_checks + 1))
    log_check "HTTPS/SSL certificate valid"
    if curl -s --head "$API_URL/health" | grep -q "HTTP/2 200"; then
        log_pass
        api_passed=$((api_passed + 1))
    else
        log_warn
    fi
    
    echo ""
    echo "API Endpoints: $api_passed/$api_checks checks passed"
    return $((api_checks - api_passed))
}

check_codebase() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "7. CODEBASE STRUCTURE"
    echo "═══════════════════════════════════════════════════════════════"
    
    code_checks=0
    code_passed=0
    
    # Required directories
    for dir in "api" "models" ".claude"; do
        code_checks=$((code_checks + 1))
        log_check "Directory: $dir/"
        if [ -d "$dir" ]; then
            log_pass
            code_passed=$((code_passed + 1))
        else
            log_fail
        fi
    done
    
    # Required files
    for file in "api/main.py" "requirements.txt" "Dockerfile"; do
        code_checks=$((code_checks + 1))
        log_check "File: $file"
        if [ -f "$file" ]; then
            log_pass
            code_passed=$((code_passed + 1))
        else
            log_fail
        fi
    done
    
    echo ""
    echo "Codebase Structure: $code_passed/$code_checks checks passed"
    return $((code_checks - code_passed))
}

################################################################################
# Summary Report
################################################################################

generate_summary() {
    local total_checks=$1
    local total_passed=$2
    local total_failed=$((total_checks - total_passed))
    local pass_rate=$((total_passed * 100 / total_checks))
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "VERIFICATION SUMMARY"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "Total Checks:  $total_checks"
    echo "Passed:        $total_passed"
    echo "Failed:        $total_failed"
    echo "Pass Rate:     $pass_rate%"
    echo ""
    
    if [ $pass_rate -ge 90 ]; then
        echo -e "${GREEN}✓ DEPLOYMENT SUCCESSFUL${NC}"
        echo ""
        echo "Your Coherence Network is live at:"
        echo "  API: https://api.coherencycoin.com"
        echo "  Web: https://coherencycoin.com"
        echo ""
        echo "Next steps:"
        echo "  1. Record your contribution: ./record_contribution.sh"
        echo "  2. Set up GitHub webhook"
        echo "  3. Invite contributors"
        echo ""
        return 0
    elif [ $pass_rate -ge 70 ]; then
        echo -e "${YELLOW}⚠ DEPLOYMENT PARTIALLY COMPLETE${NC}"
        echo ""
        echo "Most checks passed but some issues remain."
        echo "Review failed checks above and fix them."
        echo ""
        return 1
    else
        echo -e "${RED}✗ DEPLOYMENT INCOMPLETE${NC}"
        echo ""
        echo "Critical issues detected. Review failed checks above."
        echo ""
        return 2
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  Coherence Network - Deployment Verification                  ║"
    echo "║  Domain: coherencycoin.com                                     ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    
    total_checks=0
    total_passed=0
    
    # Run all checks
    check_local_environment || true
    check_service_credentials || true
    check_dns_configuration || true
    check_database_connectivity || true
    check_oracle_vm || true
    check_api_endpoints || true
    check_codebase || true
    
    # Count results
    total_checks=$(grep -c "log_check" "$0" || echo "0")
    total_passed=$(grep -c "log_pass" /tmp/verify.log 2>/dev/null || echo "0")
    
    # Generate summary
    generate_summary 30 $total_passed  # Approximate count
}

# Redirect all output to log file as well
exec > >(tee /tmp/verify.log)
exec 2>&1

main "$@"
