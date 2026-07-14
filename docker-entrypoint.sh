#!/bin/sh
set -eu

config_dir="${OPENCODE_CONFIG_DIR:-${HOME}/.config/opencode}"
skill_source="/opt/opencode-skills/huawei-cloud-terraform"
skill_target="${config_dir}/skills/huawei-cloud-terraform"

mkdir -p "$(dirname "${skill_target}")"

# Preserve a user-managed Skill; otherwise expose the immutable image copy.
if [ ! -e "${skill_target}" ] && [ ! -L "${skill_target}" ]; then
    ln -s "${skill_source}" "${skill_target}"
fi

exec "$@"
