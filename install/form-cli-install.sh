#!/usr/bin/env bash
# Install the fkwu-built form-cli from a local Coherence Network checkout.
set -euo pipefail

repo_url="https://github.com/seeker71/Coherence-Network.git"
destination="${FORM_CLI_HOME:-$HOME/coherence-network}"
bin_dir="${FORM_CLI_BIN_DIR:-$HOME/.local/bin}"

if [ ! -d "$destination/.git" ]; then
  git clone --recurse-submodules "$repo_url" "$destination"
else
  git -C "$destination" pull --ff-only origin main
  git -C "$destination" submodule sync --recursive
  git -C "$destination" submodule update --init --recursive
fi

bash "$destination/scripts/ensure_form_cli_native.sh" >/dev/null
mkdir -p "$bin_dir"
ln -sfn "$destination/bin/form-cli" "$bin_dir/form-cli"
printf 'form-cli installed at %s/form-cli\n' "$bin_dir"
