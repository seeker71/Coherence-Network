#!/usr/bin/env bash
# Land the current Codex worktree branch through the Form-owned landing plan.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPO=""
BASE="main"
TITLE=""
BODY_FILE=""
TIMEOUT_SECONDS=1800
POLL_SECONDS=20
CHECK_REFRESH_GRACE_SECONDS=60
MAX_REBASES=2
SKIP_LOCAL_GATES=0
SKIP_FOLLOWTHROUGH=0
ALLOW_EMPTY_CHECKS=0
MERGE=0
MERGE_METHOD="rebase"
DELETE_BRANCH=1
SETTLE_DEPLOY=0
API_URL="https://api.coherencycoin.com"
WEB_URL="https://coherencycoin.com"
DRY_RUN=0
FORM_NATIVE_CLI=""
LAST_PUSH_EPOCH=0

usage() {
  cat <<'EOF'
usage: form-cli land [options]

Land the current named worktree branch through the Form-owned current-branch
landing plan. The plan is proven in current-branch-landing.fk; git, gh, and
network calls are explicit host-effect passthrough carriers.

Options:
  --repo OWNER/REPO
  --base BRANCH
  --title TITLE
  --body-file FILE
  --timeout-seconds N
  --poll-seconds N
  --check-refresh-grace-seconds N
  --max-rebases N
  --skip-local-gates
  --skip-followthrough
  --allow-empty-checks
  --merge
  --merge-method merge|squash|rebase
  --delete-branch / --no-delete-branch
  --settle-deploy
  --api-url URL
  --web-url URL
  --dry-run
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

qcmd() {
  printf '$'
  printf ' %q' "$@"
  printf '\n'
}

run() {
  qcmd "$@"
  "$@"
}

capture() {
  "$@"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --base) BASE="${2:-}"; shift 2 ;;
    --title) TITLE="${2:-}"; shift 2 ;;
    --body-file) BODY_FILE="${2:-}"; shift 2 ;;
    --timeout-seconds) TIMEOUT_SECONDS="${2:-}"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="${2:-}"; shift 2 ;;
    --check-refresh-grace-seconds) CHECK_REFRESH_GRACE_SECONDS="${2:-}"; shift 2 ;;
    --max-rebases) MAX_REBASES="${2:-}"; shift 2 ;;
    --skip-local-gates) SKIP_LOCAL_GATES=1; shift ;;
    --skip-followthrough) SKIP_FOLLOWTHROUGH=1; shift ;;
    --allow-empty-checks) ALLOW_EMPTY_CHECKS=1; shift ;;
    --merge) MERGE=1; shift ;;
    --merge-method) MERGE_METHOD="${2:-}"; shift 2 ;;
    --delete-branch) DELETE_BRANCH=1; shift ;;
    --no-delete-branch) DELETE_BRANCH=0; shift ;;
    --settle-deploy) SETTLE_DEPLOY=1; shift ;;
    --api-url) API_URL="${2:-}"; shift 2 ;;
    --web-url) WEB_URL="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

case "$MERGE_METHOD" in
  merge|squash|rebase) ;;
  *) die "--merge-method must be merge, squash, or rebase" ;;
esac

numeric_or_die() {
  case "$2" in
    ''|*[!0-9]*) die "$1 must be a positive integer" ;;
  esac
  [ "$2" -gt 0 ] || die "$1 must be a positive integer"
}

numeric_or_die "--timeout-seconds" "$TIMEOUT_SECONDS"
numeric_or_die "--poll-seconds" "$POLL_SECONDS"
case "$CHECK_REFRESH_GRACE_SECONDS" in
  ''|*[!0-9]*) die "--check-refresh-grace-seconds must be a non-negative integer" ;;
esac
case "$MAX_REBASES" in
  ''|*[!0-9]*) die "--max-rebases must be a non-negative integer" ;;
esac

need git
need gh
need bash
need python3

ensure_native_land_cli() {
  if [ -n "$FORM_NATIVE_CLI" ] && [ -x "$FORM_NATIVE_CLI" ]; then
    printf '%s\n' "$FORM_NATIVE_CLI"
    return
  fi
  bash "$ROOT/scripts/ensure_form_cli_native.sh" >/dev/null 2>&1 || true
  if [ ! -x "$ROOT/form/form-cli" ]; then
    die "native form-cli unavailable; cannot compute non-host landing readiness in Form"
  fi
  FORM_NATIVE_CLI="$ROOT/form/form-cli"
  printf '%s\n' "$FORM_NATIVE_CLI"
}

native_land_readiness() {
  local cmd="$1"
  local cli
  cli="$(ensure_native_land_cli)"
  printf '%s\nquit\n' "$cmd" | "$cli" | sed '/^null$/d' | head -1
}

form_plan_probe() {
  printf 'form-native-plan: form/form-stdlib/current-branch-landing.fk\n'
  printf 'trust path:native grounded:yes freq:yes suffic:yes -> form-plan-band\n'
  run bash form/validate.sh form-stdlib/core.fk form-stdlib/current-branch-landing.fk form-stdlib/tests/current-branch-landing-band.fk
}

current_branch() {
  local branch
  branch="$(capture git rev-parse --abbrev-ref HEAD)"
  [ -n "$branch" ] || die "failed to detect current branch"
  [ "$branch" != "HEAD" ] || die "current worktree is detached; attach a codex/<topic> branch first"
  case "$branch" in
    main|master) die "refusing to land directly from $branch" ;;
  esac
  printf '%s\n' "$branch"
}

require_clean_worktree() {
  local status
  status="$(capture git status --porcelain)"
  [ -z "$status" ] || die "worktree must be clean before landing:
$status"
}

repo_from_remote() {
  local remote path
  remote="$(capture git config --get remote.origin.url)"
  case "$remote" in
    git@github.com:*) path="${remote#git@github.com:}" ;;
    *github.com/*) path="${remote#*github.com/}" ;;
    *) die "unsupported GitHub remote URL: $remote" ;;
  esac
  path="${path%.git}"
  path="${path#/}"
  path="${path%/}"
  [ "$(printf '%s\n' "$path" | awk -F/ '{print NF}')" -ge 2 ] || die "unable to resolve owner/repo from remote URL: $remote"
  printf '%s/%s\n' "$(printf '%s\n' "$path" | cut -d/ -f1)" "$(printf '%s\n' "$path" | cut -d/ -f2)"
}

resolve_repo() {
  if [ -n "$REPO" ]; then
    printf '%s\n' "$REPO"
    return
  fi
  if gh repo view --json nameWithOwner --jq '.nameWithOwner' >/tmp/form-cli-land-repo.$$ 2>/dev/null; then
    cat /tmp/form-cli-land-repo.$$
    rm -f /tmp/form-cli-land-repo.$$
    return
  fi
  rm -f /tmp/form-cli-land-repo.$$
  repo_from_remote
}

latest_commit_subject() {
  capture git log -1 --pretty=%s
}

read_body_arg() {
  if [ -n "$BODY_FILE" ]; then
    printf '%s\n' "--body-file"
    printf '%s\n' "$BODY_FILE"
    return
  fi
  printf '%s\n' "--body"
  printf '%s\n' "Automated current-branch landing.

Proof path: Form-owned landing plan, rebase, changed commit evidence validation, local PR guard, follow-through guard, check wait, GitHub API merge."
}

run_local_gates() {
  local base_ref="$1"
  run python3 scripts/validate_commit_evidence.py --base "$base_ref" --head HEAD --require-changed-evidence
  run python3 scripts/worktree_pr_guard.py --mode local --base-ref "$base_ref"
  if [ "$SKIP_FOLLOWTHROUGH" -eq 0 ]; then
    run python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict
  fi
}

sync_with_base() {
  local base_ref="origin/$BASE"
  run git fetch origin "$BASE"
  run git rebase "$base_ref"
  require_clean_worktree
  if [ "$SKIP_LOCAL_GATES" -eq 0 ]; then
    run_local_gates "$base_ref"
  fi
}

upstream_branch() {
  git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true
}

push_current_branch() {
  local branch="$1"
  local upstream
  upstream="$(upstream_branch)"
  if [ "$upstream" = "origin/$branch" ]; then
    run git push --force-with-lease origin "HEAD:$branch"
  else
    run git push -u origin "HEAD:$branch"
  fi
  LAST_PUSH_EPOCH="$(date +%s)"
}

find_pr() {
  local repo="$1"
  local branch="$2"
  gh pr view "$branch" --repo "$repo" --json number,url,state,title --jq '[.number,.url] | @tsv' 2>/dev/null || true
}

create_or_find_pr() {
  local repo="$1"
  local branch="$2"
  local title="$3"
  local existing body_flag body_value
  existing="$(find_pr "$repo" "$branch")"
  if [ -n "$existing" ]; then
    printf 'pr: existing #%s %s\n' "$(printf '%s\n' "$existing" | cut -f1)" "$(printf '%s\n' "$existing" | cut -f2)"
    printf '%s\n' "$existing"
    return
  fi
  body_flag="$(read_body_arg | sed -n '1p')"
  body_value="$(read_body_arg | sed -n '2,$p')"
  run gh pr create --repo "$repo" --base "$BASE" --head "$branch" --title "$title" "$body_flag" "$body_value"
  existing="$(find_pr "$repo" "$branch")"
  [ -n "$existing" ] || die "PR create returned successfully, but PR could not be read back"
  printf 'pr: created #%s %s\n' "$(printf '%s\n' "$existing" | cut -f1)" "$(printf '%s\n' "$existing" | cut -f2)"
  printf '%s\n' "$existing"
}

pr_readiness() {
  local repo="$1"
  local number="$2"
  gh pr view "$number" --repo "$repo" --json state,isDraft,mergeStateStatus,reviewDecision,statusCheckRollup --jq '
    def check_name: (.name // .context // "unknown");
    def check_failed:
      if .__typename == "CheckRun" then
        ((.status // "" | ascii_upcase) == "COMPLETED")
        and (((.conclusion // "" | ascii_upcase) != "SUCCESS")
        and ((.conclusion // "" | ascii_upcase) != "NEUTRAL")
        and ((.conclusion // "" | ascii_upcase) != "SKIPPED"))
      elif .__typename == "StatusContext" then
        ((.state // "" | ascii_upcase) != "SUCCESS")
        and ((.state // "" | ascii_upcase) != "PENDING")
        and ((.state // "" | ascii_upcase) != "EXPECTED")
      else false end;
    def check_pending:
      if .__typename == "CheckRun" then
        ((.status // "" | ascii_upcase) != "COMPLETED")
      elif .__typename == "StatusContext" then
        ((.state // "" | ascii_upcase) == "PENDING")
        or ((.state // "" | ascii_upcase) == "EXPECTED")
      else true end;
    def failed_list: [.statusCheckRollup[]? | select(check_failed) | check_name];
    def pending_list: [.statusCheckRollup[]? | select(check_pending) | check_name];
    [
      (.state // "UNKNOWN"),
      (.isDraft | tostring),
      (.reviewDecision // ""),
      (.mergeStateStatus // "UNKNOWN"),
      (.statusCheckRollup // [] | length),
      (failed_list | length),
      (pending_list | length),
      (failed_list | join(",")),
      (pending_list | join(","))
    ] | join("\u001f")'
}

wait_until_ready() {
  local repo="$1"
  local number="$2"
  local branch="$3"
  local deadline rebase_count last_message
  deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
  rebase_count=0
  last_message=""

  while true; do
    local line state is_draft review merge_state check_count failed_count pending_count failed_names pending_names status reason message now refresh_int now_epoch
    line="$(pr_readiness "$repo" "$number")"
    IFS=$'\037' read -r state is_draft review merge_state check_count failed_count pending_count failed_names pending_names <<EOF
$line
EOF
    state="$(printf '%s' "$state" | tr '[:lower:]' '[:upper:]')"
    review="$(printf '%s' "$review" | tr '[:lower:]' '[:upper:]')"
    merge_state="$(printf '%s' "$merge_state" | tr '[:lower:]' '[:upper:]')"
    failed_count="${failed_count:-0}"
    pending_count="${pending_count:-0}"

    refresh_int=0
    now_epoch="$(date +%s)"
    if [ "$LAST_PUSH_EPOCH" -gt 0 ] && [ "$failed_count" -gt 0 ] && [ "$CHECK_REFRESH_GRACE_SECONDS" -gt 0 ] && [ $((now_epoch - LAST_PUSH_EPOCH)) -lt "$CHECK_REFRESH_GRACE_SECONDS" ]; then
      refresh_int=1
    fi

    local draft_int review_arg
    draft_int=0
    [ "$is_draft" = "true" ] && draft_int=1
    review_arg="${review:-none}"
    status="$(native_land_readiness "land-readiness ${state:-UNKNOWN} $draft_int $review_arg ${merge_state:-UNKNOWN} ${check_count:-0} $failed_count $pending_count $ALLOW_EMPTY_CHECKS $refresh_int")"
    reason="merge_state=${merge_state:-UNKNOWN} checks=pending:${pending_names:-not_reported}"
    case "$status" in
      ready) reason="merge_state=CLEAN checks=green" ;;
      needs_rebase) reason="merge_state=$merge_state" ;;
      blocked)
        if [ "$state" != "OPEN" ]; then
          reason="state=${state:-UNKNOWN}"
        elif [ "$is_draft" = "true" ]; then
          reason="draft=true"
        elif [ "$review" = "CHANGES_REQUESTED" ]; then
          reason="review_decision=CHANGES_REQUESTED"
        elif [ "$failed_count" -gt 0 ]; then
          reason="checks_failed:$failed_names"
        else
          reason="blocked"
        fi
        ;;
      waiting)
        if [ "$refresh_int" -eq 1 ]; then
          reason="checks_refreshing_after_push:${failed_names:-not_reported}"
        elif [ "${check_count:-0}" -eq 0 ] && [ "$ALLOW_EMPTY_CHECKS" -eq 0 ]; then
          reason="merge_state=${merge_state:-UNKNOWN} checks=pending:checks_not_reported"
        fi
        ;;
      *) die "native land-readiness returned unexpected status: $status" ;;
    esac

    message="pr #$number: $status ($reason)"
    if [ "$message" != "$last_message" ]; then
      printf '%s\n' "$message"
      last_message="$message"
    fi

    case "$status" in
      ready) return 0 ;;
      blocked) die "PR #$number is blocked: $reason" ;;
      needs_rebase)
        [ "$rebase_count" -lt "$MAX_REBASES" ] || die "PR #$number still needs rebase after $MAX_REBASES attempt(s)"
        rebase_count=$((rebase_count + 1))
        printf 'pr #%s: rebasing current branch because %s\n' "$number" "$reason"
        sync_with_base
        push_current_branch "$branch"
        last_message=""
        ;;
      waiting)
        now="$(date +%s)"
        [ "$now" -lt "$deadline" ] || die "timed out waiting for PR #$number: $reason"
        sleep "$POLL_SECONDS"
        ;;
    esac
  done
}

api_merge() {
  local repo="$1"
  local number="$2"
  run gh api -X PUT "repos/$repo/pulls/$number/merge" -f "merge_method=$MERGE_METHOD"
}

delete_remote_branch() {
  local repo="$1"
  local branch="$2"
  run gh api -X DELETE "repos/$repo/git/refs/heads/$branch" || {
    printf 'warning: remote branch delete failed; branch=%s\n' "$branch" >&2
  }
}

post_merge_verify() {
  local repo="$1"
  local number="$2"
  local state merged_at
  state="$(gh pr view "$number" --repo "$repo" --json state --jq '.state')"
  merged_at="$(gh pr view "$number" --repo "$repo" --json mergedAt --jq '.mergedAt')"
  printf 'post-merge-pr: state=%s mergedAt=%s\n' "$state" "$merged_at"
  run git fetch origin "$BASE"
  qcmd git diff --quiet HEAD "origin/$BASE"
  if git diff --quiet HEAD "origin/$BASE"; then
    printf 'post-merge-tree-matches-origin-%s=true\n' "$BASE"
  else
    printf 'post-merge-tree-matches-origin-%s=false\n' "$BASE"
  fi
}

print_plan() {
  local branch="$1"
  local repo="$2"
  printf 'land-current-branch dry run\n'
  printf 'branch=%s\n' "$branch"
  printf 'repo=%s\n' "$repo"
  printf 'base=origin/%s\n' "$BASE"
  printf 'plan=form/form-stdlib/current-branch-landing.fk\n'
  printf 'boundary=host-effects-explicit-git-gh-network-passthrough\n'
  printf 'would: require clean worktree\n'
  if [ "$SKIP_LOCAL_GATES" -eq 0 ]; then
    printf 'would: fetch, rebase, validate changed commit evidence, run local PR guard\n'
  fi
  if [ "$SKIP_FOLLOWTHROUGH" -eq 0 ]; then
    printf 'would: run stale PR follow-through guard\n'
  fi
  printf 'would: push current branch, create/read PR, wait for clean merge state and green checks\n'
  printf 'would: treat stale failed checks during the %ss post-push refresh window as native waiting\n' "$CHECK_REFRESH_GRACE_SECONDS"
  if [ "$MERGE" -eq 1 ]; then
    printf 'would: merge PR through GitHub API using method=%s\n' "$MERGE_METHOD"
    if [ "$DELETE_BRANCH" -eq 1 ]; then
      printf 'would: delete remote branch through GitHub API\n'
    fi
  fi
  if [ "$SETTLE_DEPLOY" -eq 1 ]; then
    printf 'would: run scripts/settle_public_deploy.sh after merge\n'
  fi
}

main() {
  local branch repo title pr_line pr_number pr_url
  branch="$(current_branch)"
  repo="$(resolve_repo)"
  if [ "$DRY_RUN" -eq 1 ]; then
    form_plan_probe
    print_plan "$branch" "$repo"
    return 0
  fi

  form_plan_probe
  require_clean_worktree
  sync_with_base
  push_current_branch "$branch"

  title="$TITLE"
  if [ -z "$title" ]; then
    title="$(latest_commit_subject)"
  fi
  pr_line="$(create_or_find_pr "$repo" "$branch" "$title" | tail -n 1)"
  pr_number="$(printf '%s\n' "$pr_line" | cut -f1)"
  pr_url="$(printf '%s\n' "$pr_line" | cut -f2)"
  [ -n "$pr_number" ] && [ "$pr_number" != "0" ] || die "PR number was not available after create/read"

  wait_until_ready "$repo" "$pr_number" "$branch"

  if [ "$MERGE" -eq 1 ]; then
    api_merge "$repo" "$pr_number"
    if [ "$DELETE_BRANCH" -eq 1 ]; then
      delete_remote_branch "$repo" "$branch"
    fi
    post_merge_verify "$repo" "$pr_number"
    if [ "$SETTLE_DEPLOY" -eq 1 ]; then
      run bash scripts/settle_public_deploy.sh "$API_URL" "$WEB_URL"
    fi
  else
    printf 'ready-pr: #%s %s\n' "$pr_number" "$pr_url"
    printf 'merge skipped; rerun with --merge to land through the GitHub API\n'
  fi
}

main
