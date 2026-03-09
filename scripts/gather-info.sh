#!/usr/bin/env bash
# Gather kaiju server state for docs/kaiju-os-state.md.
# Run on the server (as root or with sudo). Optional: pass output path as first argument.
# Example: ./gather-info.sh
#          ./gather-info.sh /path/to/kaiju-configs/docs/kaiju-os-state.md

set -e

OUT="${1:-}"

emit() {
  if [[ -n "$OUT" ]]; then
    printf '%s\n' "$*" >> "$OUT"
  else
    printf '%s\n' "$*"
  fi
}

if [[ -n "$OUT" ]]; then
  : > "$OUT"
fi

emit "# Kaiju OS state"
emit ""
emit "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
emit ""

emit "## OS and kernel"
emit '```'
emit "Hostname: $(hostname)"
if [[ -r /etc/os-release ]]; then
  (. /etc/os-release && echo "ID=$ID" && echo "VERSION=$VERSION" && echo "VERSION_CODENAME=$VERSION_CODENAME") | while read -r line; do emit "$line"; done
fi
emit "Kernel: $(uname -r)"
emit "Uptime: $(uptime -p 2>/dev/null || uptime)"
emit '```'
emit ""

emit "## CPU and memory"
emit '```'
if command -v nproc &>/dev/null; then
  emit "CPUs: $(nproc)"
fi
if [[ -r /proc/meminfo ]]; then
  awk '/^MemTotal:/{printf "MemTotal: %s kB\n", $2} /^MemAvailable:/{printf "MemAvailable: %s kB\n", $2}' /proc/meminfo | while read -r line; do emit "$line"; done
fi
emit '```'
emit ""

emit "## Disks and mounts"
emit '```'
if command -v lsblk &>/dev/null; then
  lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE 2>/dev/null | while read -r line; do emit "$line"; done
fi
emit "---"
if command -v df &>/dev/null; then
  df -h 2>/dev/null | head -30 | while read -r line; do emit "$line"; done
fi
emit '```'
emit ""

emit "## Network (active interfaces, no MACs)"
emit '```'
if command -v ip &>/dev/null; then
  ip -br addr show 2>/dev/null | while read -r iface state rest; do
    if [[ "$state" == "UP" ]]; then
      emit "$iface $state $rest"
    fi
  done
else
  ifconfig 2>/dev/null | while read -r line; do emit "$line"; done
fi
emit '```'
emit ""

emit "## btrfs subvolumes"
emit '```'
for m in / /vault; do
  if mountpoint -q "$m" 2>/dev/null && command -v btrfs &>/dev/null; then
    emit "--- $m ---"
    btrfs subvolume list -p "$m" 2>/dev/null | while read -r line; do emit "$line"; done
  fi
done
emit '```'
emit ""

emit "## LUKS devices"
emit '```'
if command -v lsblk &>/dev/null; then
  lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT -e 7 2>/dev/null | while read -r line; do emit "$line"; done
fi
if command -v dmsetup &>/dev/null; then
  dmsetup ls --target crypt 2>/dev/null | while read -r line; do emit "$line"; done
fi
emit '```'
emit ""

emit "## systemd services (running, relevant)"
emit '```'
systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null | head -60 | while read -r line; do emit "$line"; done
emit '```'
emit ""

emit "## Docker"
emit '```'
if command -v docker &>/dev/null; then
  v=$(docker info --format '{{.ServerVersion}}' 2>/dev/null) && emit "Docker version: $v" || emit "Docker not running or not installed"
  emit "--- Containers ---"
  docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | while read -r line; do emit "$line"; done
else
  emit "Docker not installed"
fi
emit '```'
emit ""

emit "## Relevant packages"
emit '```'
for pkg in docker-ce containerd.io docker-compose-plugin nftables fail2ban unattended-upgrades systemd-zram-generator btrfs-progs; do
  if dpkg -l "$pkg" 2>/dev/null | grep -q '^ii'; then
    dpkg -l "$pkg" 2>/dev/null | grep '^ii' | while read -r line; do emit "$line"; done
  fi
done
emit '```'
emit ""

if [[ -n "$OUT" ]]; then
  echo "Written to $OUT" >&2
fi
