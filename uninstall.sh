#!/usr/bin/env bash
set -uo pipefail

INSTALL_DIR="/opt/aimilivpn"
ASSUME_YES=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;36m'
PLAIN='\033[0m'

usage() {
    cat <<'EOF'
AimiliVPN clean uninstaller

Usage:
  bash uninstall.sh          Ask for confirmation
  bash uninstall.sh --yes    Uninstall without an interactive prompt
  bash uninstall.sh --help   Show this help

This permanently removes the AimiliVPN service, runtime data, logs, generated
OpenVPN profiles, Web credentials, API relay service, and the `ml` command.
It does not uninstall shared system packages such as Python, OpenVPN, Git, or curl.
EOF
}

for arg in "$@"; do
    case "$arg" in
        -y|--yes)
            ASSUME_YES=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: ${arg}${PLAIN}" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}错误: 必须以 root 权限运行卸载脚本。${PLAIN}" >&2
    exit 1
fi

if [ "$INSTALL_DIR" != "/opt/aimilivpn" ]; then
    echo -e "${RED}安全检查失败: 安装目录不是预期路径。${PLAIN}" >&2
    exit 1
fi

echo -e "${BLUE}==========================================================${PLAIN}"
echo -e "${BLUE}              AimiliVPN 彻底清理卸载${PLAIN}"
echo -e "${BLUE}==========================================================${PLAIN}"
echo -e "将永久删除："
echo -e "  - ${INSTALL_DIR}（包括配置、日志和节点缓存）"
echo -e "  - aimilivpn 与 aimilivpn-api-relay 服务"
echo -e "  - /usr/bin/ml 和 /etc/default 下的 AimiliVPN 配置"
echo -e "  - AimiliVPN 创建的策略路由与 sysctl 配置"

if [ "$ASSUME_YES" -ne 1 ]; then
    read -r -p "确定继续吗？请输入 YES: " answer
    if [ "$answer" != "YES" ]; then
        echo "已取消卸载。"
        exit 0
    fi
fi

echo -e "${YELLOW}[1/6] 停止并禁用服务...${PLAIN}"
if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now aimilivpn.service >/dev/null 2>&1 || true
    systemctl disable --now aimilivpn-api-relay.service >/dev/null 2>&1 || true
fi
if command -v rc-service >/dev/null 2>&1; then
    rc-service aimilivpn stop >/dev/null 2>&1 || true
    rc-update del aimilivpn default >/dev/null 2>&1 || rc-update del aimilivpn >/dev/null 2>&1 || true
fi

echo -e "${YELLOW}[2/6] 终止仅属于 AimiliVPN 的残留进程...${PLAIN}"
if command -v pkill >/dev/null 2>&1; then
    pkill -TERM -f '/opt/aimilivpn/vpngate_manager.py' >/dev/null 2>&1 || true
    pkill -TERM -f 'openvpn.*/opt/aimilivpn/vpngate_data' >/dev/null 2>&1 || true
    pkill -TERM -f '^/opt/aimilivpn/aimilivpn([[:space:]]|$)' >/dev/null 2>&1 || true
    sleep 1
    pkill -KILL -f '/opt/aimilivpn/vpngate_manager.py' >/dev/null 2>&1 || true
    pkill -KILL -f 'openvpn.*/opt/aimilivpn/vpngate_data' >/dev/null 2>&1 || true
fi

echo -e "${YELLOW}[3/6] 清理 AimiliVPN 策略路由...${PLAIN}"
if command -v ip >/dev/null 2>&1; then
    TUN_INTERFACE="aimili0"
    if [ -f "${INSTALL_DIR}/vpngate_data/ui_auth.json" ] && command -v python3 >/dev/null 2>&1; then
        TUN_INTERFACE=$(python3 - "${INSTALL_DIR}/vpngate_data/ui_auth.json" <<'PY' 2>/dev/null || echo "aimili0"
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        print(json.load(f).get("tun_interface") or "aimili0")
except Exception:
    print("aimili0")
PY
)
    fi
    flush_table=0
    for dev in "$TUN_INTERFACE" aimili0 tun0; do
        [ -n "$dev" ] || continue
        while ip rule del oif "$dev" table 100 >/dev/null 2>&1; do :; done
        if ip route show table 100 2>/dev/null | grep -qF "dev $dev"; then
            flush_table=1
        fi
    done
    if [ "$flush_table" -eq 1 ]; then
        ip route flush table 100 >/dev/null 2>&1 || true
    fi
fi

echo -e "${YELLOW}[4/6] 删除服务与系统配置...${PLAIN}"
rm -f -- \
    /lib/systemd/system/aimilivpn.service \
    /etc/systemd/system/aimilivpn.service \
    /lib/systemd/system/aimilivpn-api-relay.service \
    /etc/systemd/system/aimilivpn-api-relay.service \
    /etc/init.d/aimilivpn \
    /etc/default/aimilivpn \
    /etc/default/aimilivpn-api-relay \
    /etc/sysctl.d/99-aimilivpn.conf \
    /etc/systemd/system/multi-user.target.wants/aimilivpn.service \
    /etc/systemd/system/multi-user.target.wants/aimilivpn-api-relay.service \
    /run/aimilivpn.pid \
    /usr/bin/ml

# Remove only the marked block created by current installers. Unmarked matching
# lines from old installations are left intact because they may be user-owned.
if [ -f /etc/sysctl.conf ]; then
    sed -i '/^# BEGIN AimiliVPN$/,/^# END AimiliVPN$/d' /etc/sysctl.conf || true
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl reset-failed aimilivpn.service aimilivpn-api-relay.service >/dev/null 2>&1 || true
fi

echo -e "${YELLOW}[5/6] 删除安装目录和全部运行数据...${PLAIN}"
cd /
rm -rf -- "$INSTALL_DIR"

echo -e "${YELLOW}[6/6] 验证卸载结果...${PLAIN}"
remaining=0
for path in \
    "$INSTALL_DIR" \
    /usr/bin/ml \
    /lib/systemd/system/aimilivpn.service \
    /etc/systemd/system/aimilivpn.service \
    /etc/init.d/aimilivpn \
    /etc/default/aimilivpn; do
    if [ -e "$path" ] || [ -L "$path" ]; then
        echo -e "${RED}仍有残留: ${path}${PLAIN}" >&2
        remaining=1
    fi
done

if [ "$remaining" -ne 0 ]; then
    echo -e "${RED}卸载未完全完成，请根据上面的残留路径手动检查。${PLAIN}" >&2
    exit 1
fi

echo -e "${GREEN}AimiliVPN 已彻底卸载。共享系统软件包未被删除。${PLAIN}"
