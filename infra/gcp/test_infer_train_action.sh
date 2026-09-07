#!/usr/bin/env bash
# Guard: qrdqn configs must not resolve to train_dqn; train-action overrides win.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=create_workers.sh
# Extract just the function by sourcing a tiny copy — call create_workers dry paths.
infer_train_action() {
  local cfg="$1"
  local override="${2:-}"
  if [[ -n "$override" ]]; then
    case "$override" in
      train_*) echo "$override" ;;
      *) echo "train_${override}" ;;
    esac
    return 0
  fi
  local base
  base="$(basename "$cfg")"
  case "$base" in
    *qrdqn*) echo "train_qrdqn" ;;
    *dqn*)   echo "train_dqn" ;;
    *rppo*)  echo "train_rppo" ;;
    *ppo*)   echo "train_ppo" ;;
    *a2c*)   echo "train_a2c" ;;
    *)       echo "train_ppo" ;;
  esac
}

assert_eq() {
  local got="$1" want="$2" label="$3"
  if [[ "$got" != "$want" ]]; then
    echo "FAIL $label: got=$got want=$want" >&2
    exit 1
  fi
  echo "ok $label -> $got"
}

assert_eq "$(infer_train_action config/sweeps/scout_qrdqn.yml)" train_qrdqn "qrdqn before dqn"
assert_eq "$(infer_train_action config/sweeps/scout_qrdqn_phase_a.yml)" train_qrdqn "qrdqn_phase_a"
assert_eq "$(infer_train_action config/train_dqn.yml)" train_dqn "plain dqn"
assert_eq "$(infer_train_action config/sweeps/scout_ppo_fps2.yml)" train_ppo "ppo"
assert_eq "$(infer_train_action config/train_rppo.yml)" train_rppo "rppo before ppo"
assert_eq "$(infer_train_action config/x.yml train_qrdqn)" train_qrdqn "explicit full"
assert_eq "$(infer_train_action config/x.yml qrdqn)" train_qrdqn "explicit short"
assert_eq "$(infer_train_action config/sweeps/scout_qrdqn.yml train_ppo)" train_ppo "override wins"

# create_workers dry-run must emit train-action metadata for qrdqn configs
out="$("${SCRIPT_DIR}/create_workers.sh" --dry-run --count 1 \
  --config config/sweeps/scout_qrdqn.yml --job-id job-test-qrdqn 2>&1)"
echo "$out" | grep -q 'train-action=train_qrdqn' || {
  echo "FAIL create_workers dry-run missing train-action=train_qrdqn" >&2
  echo "$out" >&2
  exit 1
}
echo "ok create_workers dry-run sets train-action=train_qrdqn"

out2="$("${SCRIPT_DIR}/create_workers.sh" --dry-run --count 1 \
  --config config/sweeps/scout_qrdqn.yml --train-action train_qrdqn \
  --job-id job-test-qrdqn2 2>&1)"
echo "$out2" | grep -q 'Action:      train_qrdqn' || {
  echo "FAIL create_workers did not print resolved Action" >&2
  exit 1
}
echo "ALL_OK"
