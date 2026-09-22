#!/usr/bin/env bash
# Assign a static IP on the wired interface so the PC can reach the Gen3 at 192.168.1.10.
# Usage: ./setup_network.sh [interface]   (default: enp131s0)
# The address is not persistent; it is lost on reboot / cable replug.
set -euo pipefail

IFACE="${1:-enp131s0}"
PC_IP="192.168.1.11/24"
ROBOT_IP="192.168.1.10"

sudo ip link set "$IFACE" up
if ! ip -br addr show "$IFACE" | grep -q "${PC_IP%/*}"; then
    sudo ip addr add "$PC_IP" dev "$IFACE"
fi
ip -br addr show "$IFACE"

echo "Pinging robot at $ROBOT_IP ..."
ping -c 3 -W 2 "$ROBOT_IP" && echo "Robot reachable. Web app: http://$ROBOT_IP (admin/admin)"
