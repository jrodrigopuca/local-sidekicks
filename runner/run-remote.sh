#!/bin/sh
# Run the two measured tasks against an ollama served on another machine.
#
#   runner/run-remote.sh <ip-or-host> [model] [n]
#   runner/run-remote.sh 192.168.1.20 qwen3.5:8b 3
#
# Inference happens there; grep/read/edit/vitest run HERE on the fixtures, so
# the code never leaves this machine. Results land in runs/<date>-<model>/,
# one JSON per run plus the console log — that folder is the evidence that
# MODELOS.md cites, commit it.
set -eu
HOST=${1:?usage: $0 <ip-or-host> [model] [n]}
MODEL=${2:-qwen3.5:8b}
N=${3:-3}
cd "$(dirname "$0")/.."
export OLLAMA_URL="http://$HOST:11434"
OUT="runs/$(date +%Y%m%d-%H%M)-$(printf '%s' "$MODEL" | tr ':/' '--')"

curl -sf -m 5 "$OLLAMA_URL/api/version" >/dev/null || { echo "ollama no responde en $OLLAMA_URL (¿OLLAMA_HOST=0.0.0.0 en esa máquina? ¿misma red?)"; exit 1; }
curl -s -m 10 "$OLLAMA_URL/api/show" -d "{\"model\":\"$MODEL\"}" | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
if "error" in d: print("el modelo no está en esa máquina:", d["error"]); sys.exit(1)
det = d.get("details", {})
print("modelo:", sys.argv[1], "|", det.get("parameter_size"), det.get("quantization_level"), "| modified:", d.get("modified_at"))
' "$MODEL" || exit 1
mkdir -p "$OUT"
{ echo "host: $OLLAMA_URL"; echo "model: $MODEL"; echo "date: $(date -Iseconds)"; echo "ollama: $(curl -s -m 5 "$OLLAMA_URL/api/version")";
  curl -s -m 10 "$OLLAMA_URL/api/tags" | python3 -I -c 'import json,sys; m=sys.argv[1]; print("digest:", next((x.get("digest","")[:12] for x in json.load(sys.stdin).get("models",[]) if x.get("name")==m or x.get("model")==m), "?"))' "$MODEL"; } > "$OUT/meta.txt"
cat "$OUT/meta.txt"

echo "== find-usages (nivel 1)"
python3 -I runner/control.py --agent runner/examples/find-usages/agent.md --cwd runner/fixtures/find-usages \
  --prompt "Where is formatPrice used in this repo?" --n "$N" --out "$OUT/find-usages" --model "$MODEL" \
  --expect runner/fixtures/find-usages.expect.json | tee "$OUT/find-usages.log"

echo "== update-vitest-test (nivel 2)"
[ -d runner/fixtures/vitest/node_modules ] || (cd runner/fixtures/vitest && npm install --prefer-offline --no-audit --no-fund --silent)
python3 -I runner/control.py --agent runner/examples/update-vitest-test/agent.md --cwd runner/fixtures/vitest \
  --prompt "formatPercent(ratio) was added to src/lib/format.ts. Add a test in src/lib/format.test.ts checking that formatPercent(0.125) returns '12,5 %'. Run the tests." \
  --n "$N" --out "$OUT/update-vitest-test" --model "$MODEL" --reset --verify "npx vitest run" \
  --expect-tests 2 --expect-diff 'formatPercent\(0\.125\)' | tee "$OUT/update-vitest-test.log"
git checkout -- runner/fixtures/vitest && git clean -fdq runner/fixtures/vitest

echo "== change-react-component (nivel 3)"
[ -d runner/fixtures/react/node_modules ] || (cd runner/fixtures/react && npm install --prefer-offline --no-audit --no-fund --silent)
python3 -I runner/control.py --agent runner/examples/change-react-component/agent.md --cwd runner/fixtures/react \
  --prompt "Add an optional discount prop to the Cart component (a percentage from 0 to 100). When discount is given and greater than 0, render a line 'Descuento: -<amount>' before the total, where <amount> is the discounted amount formatted with formatPrice, and make the total line show the total after the discount. Without the prop, or with 0, nothing changes. Run the tests." \
  --n "$N" --out "$OUT/change-react-component" --model "$MODEL" --reset --verify "sh ../react.oracle/verify.sh" \
  --expect-diff 'discount' | tee "$OUT/change-react-component.log"
# leave the fixtures as committed; each run's diff is inside its JSON
git checkout -- runner/fixtures/react && git clean -fdq runner/fixtures/react
echo "resultados en $OUT"
