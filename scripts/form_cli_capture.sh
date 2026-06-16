#!/usr/bin/env bash
# form_cli_capture.sh — capture agent turns as training samples for the form-cli.
#
# Turns the reasoning + tool use of an agent turn into samples the native models
# can be tried on and measured against (champion-challenger). Two sources:
#   --from-transcript <jsonl> [N]  : extract the last N real turns from a Claude
#                                    Code session transcript (the agent's own
#                                    reasoning + tool calls).
#   --gap <task> <reasoning> <answer> <outcome> <oracle> : emit one sample (used
#                                    by form_cli_close_gap.sh to capture each close).
#
# The reshaping of the transcript jsonl into turn records is pure I/O gathering (a
# thin carrier). The SAMPLE is a Form cell: form-cli-sample.fk validates every
# captured sample's shape on the kernel before it lands in the corpus. The corpus
# (form/form-samples/agent-turns/corpus.jsonl) accumulates locally; a curated
# seed.jsonl is committed so form-cli has samples to replay offline.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
CORPUS_DIR="$ROOT/form/form-samples/agent-turns"; mkdir -p "$CORPUS_DIR"
CORPUS="$CORPUS_DIR/corpus.jsonl"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null

MODE="${1:-}"; shift || true

emit_jsonl=""   # the JSONL we will validate + append

if [[ "$MODE" == "--from-transcript" ]]; then
    JS="${1:?transcript jsonl}"; N="${2:-10}"
    [[ -f "$JS" ]] || { echo "no transcript at $JS"; exit 1; }
    # thin carrier: reshape jsonl -> turn records (task, reasoning, steps, answer).
    emit_jsonl="$(python3 - "$JS" "$N" <<'PY'
import json, sys, hashlib, re
path, n = sys.argv[1], int(sys.argv[2])
def sig(s): return hashlib.sha256((s or "").encode("utf-8","replace")).hexdigest()[:16]
def clip(s, k=2000): return (s or "")[:k]
# Cell sovereignty: a turn touching tender/personal context never enters the
# corpus. Structural redaction, not manual — specific personal markers only, so
# the technical "flight-ready" metaphor stays. A matched turn is dropped whole.
GATED=re.compile(r"irina|\bpartner\b|psoriatic|dispenza|\bcancer\b|longmont|"
                 r"switzerland|intimacy|\babuse\b|insomnia|maija|louisa|\bmerly\b|"
                 r"chrysanthemum|\bbali\b|\bcolorado\b|household|infusion|"
                 r"loneliness|\blonely\b|\bval\b(?!id)", re.I)
def gated(t):
    blob=" ".join([t["task"], t["reasoning"] if isinstance(t["reasoning"],str) else " ".join(t["reasoning"]),
                   t["answer"]] + [s.get("args","")+" "+s.get("result","") for s in t["steps"]])
    return bool(GATED.search(blob))
KERNEL={"Bash","Read","Write","Edit","Grep","Glob","ToolSearch","NotebookEdit",
        "TaskCreate","TaskUpdate","TaskGet","TaskList"}
def surface(tool):
    if tool=="Agent": return "local-oracle"   # spawns a reasoning agent
    return "os-kernel"                          # file/shell/host tools
turns=[]; cur=None
def flush():
    global cur
    if cur and cur["steps"] and cur["task"].strip():
        cur["reasoning"]=" ".join(cur["reasoning"])[:4000]
        turns.append(cur)
    cur=None
for line in open(path, encoding="utf-8", errors="replace"):
    try: o=json.loads(line)
    except: continue
    typ=o.get("type"); msg=o.get("message",{}) or {}; content=msg.get("content")
    if typ=="user":
        # a human task starts a new turn; tool_result user-messages attach results
        if isinstance(content,str):
            flush(); cur={"task":content,"reasoning":[],"steps":[],"answer":"","pending":{}}
        elif isinstance(content,list):
            tr=[b for b in content if isinstance(b,dict) and b.get("type")=="tool_result"]
            if tr and cur is not None:
                for b in tr:
                    sid=b.get("tool_use_id")
                    res=b.get("content")
                    if isinstance(res,list):
                        res=" ".join(x.get("text","") for x in res if isinstance(x,dict))
                    st=cur["pending"].get(sid)
                    if st is not None: st["result"]=clip(str(res))
            else:
                txt=" ".join(b.get("text","") for b in content if isinstance(b,dict) and b.get("type")=="text")
                if txt.strip():
                    flush(); cur={"task":txt,"reasoning":[],"steps":[],"answer":"","pending":{}}
    elif typ=="assistant" and cur is not None:
        for b in content or []:
            if not isinstance(b,dict): continue
            if b.get("type")=="text" and b.get("text","").strip():
                cur["reasoning"].append(b["text"]); cur["answer"]=b["text"][:2000]
            elif b.get("type")=="tool_use":
                st={"tool":b.get("name","?"),"surface":surface(b.get("name","?")),
                    "args":clip(json.dumps(b.get("input",{}),ensure_ascii=False)),"result":""}
                cur["steps"].append(st); cur["pending"][b.get("id")]=st
flush()
# keep the last n turns that actually have a final answer + results
turns=[t for t in turns if t["answer"].strip() and any(s["result"] for s in t["steps"])
       and not gated(t) and not t["task"].lstrip().startswith("<")][-n:]
for t in turns:
    rec={"task":t["task"][:1200],"oracle":"claude","reasoning":t["reasoning"],
         "steps":[{"tool":s["tool"],"surface":s["surface"],
                   "args_sig":sig(s["args"]),"result_sig":sig(s["result"]),
                   "args":s["args"][:400],"result":s["result"][:400]} for s in t["steps"]],
         "answer":t["answer"],"outcome":"success","task_sig":sig(t["task"])}
    rec["reasoning_sig"]=sig(rec["reasoning"]); rec["answer_sig"]=sig(rec["answer"])
    print(json.dumps(rec,ensure_ascii=False))
PY
)"
elif [[ "$MODE" == "--gap" ]]; then
    TASK="${1:?task}"; REASON="${2:?reasoning}"; ANSWER="${3:?answer}"; OUTCOME="${4:-success}"; ORACLE="${5:-qwen-coder}"
    emit_jsonl="$(python3 - "$TASK" "$REASON" "$ANSWER" "$OUTCOME" "$ORACLE" <<'PY'
import json,sys,hashlib
task,reason,answer,outcome,oracle=sys.argv[1:6]
def sig(s): return hashlib.sha256(s.encode("utf-8","replace")).hexdigest()[:16]
rec={"task":task,"oracle":oracle,"reasoning":reason,
     "steps":[{"tool":"oracle","surface":"local-oracle","args_sig":sig(task),"result_sig":sig(answer),"args":task[:400],"result":answer[:400]},
              {"tool":"Bash","surface":"os-kernel","args_sig":sig("kernel validate"),"result_sig":sig(outcome),"args":"kernel validate draft","result":outcome}],
     "answer":answer,"outcome":outcome,"task_sig":sig(task),"reasoning_sig":sig(reason),"answer_sig":sig(answer)}
print(json.dumps(rec,ensure_ascii=False))
PY
)"
else
    echo "usage: $0 --from-transcript <jsonl> [N] | --gap <task> <reasoning> <answer> <outcome> <oracle>"; exit 2
fi

[[ -n "$emit_jsonl" ]] || { echo "no turns captured"; exit 1; }

# ── validate every captured sample's SHAPE on the kernel (Form is the judge) ──
nvalid=0; ntotal=0
while IFS= read -r rec; do
    [[ -z "$rec" ]] && continue
    ntotal=$((ntotal+1))
    # build a Form program that constructs the sample from its sigs and validates it
    vprog="$(mktemp)"
    { cat "$STD/form-cli-sample.fk"
      printf '(let steps (list'
      echo "$rec" | python3 -c "
import json,sys
r=json.load(sys.stdin)
for s in r['steps']:
    print(' (fcs-step \"%s\" \"%s\" \"%s\" \"%s\")' % (s['tool'],s['surface'],s['args_sig'],s['result_sig']), end='')
"
      printf '))\n'
      echo "$rec" | python3 -c "
import json,sys
r=json.load(sys.stdin)
print('(let smp (fcs-sample \"%s\" \"%s\" \"%s\" steps \"%s\" \"%s\"))' % (r['task_sig'],r['oracle'],r['reasoning_sig'],r['answer_sig'],r['outcome']))
"
      echo '(print (fcs-sample-valid? smp))'
      echo '(print (fcs-offline-reproducible? smp))'
    } > "$vprog"
    res="$("$GO" "$vprog" 2>/dev/null | head -1 | tr -d '[:space:]')"
    rm -f "$vprog"
    if [[ "$res" == "1" || "$res" == "true" ]]; then nvalid=$((nvalid+1)); echo "$rec" >> "$CORPUS"; fi
done <<< "$emit_jsonl"

echo "captured $ntotal turn(s), $nvalid valid by the Form schema → $CORPUS"
echo "corpus now holds $(grep -c . "$CORPUS" 2>/dev/null | tr -d ' ') sample(s)"
