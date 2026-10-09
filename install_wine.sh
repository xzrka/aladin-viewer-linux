#!/usr/bin/env bash
# WineHQ wine-stable (9.x/10.x) + winetricks 설치. root 로 실행:  sudo bash install_wine.sh
# Ubuntu/Pop!_OS 22.04 (jammy) 기준. 약 700MB ~ 1GB 설치.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

[ "$(id -u)" -eq 0 ] || { echo "root 로 실행하세요:  sudo bash $0"; exit 1; }

echo "[1/4] i386 아키텍처 활성화 (32bit 전용 앱이므로 필수)"
dpkg --add-architecture i386

echo "[2/4] WineHQ 저장소 등록"
install -d -m 0755 /etc/apt/keyrings
[ -f /etc/apt/keyrings/winehq-archive.key ] || \
  curl -fsSL -o /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
[ -f /etc/apt/sources.list.d/winehq-jammy.sources ] || \
  curl -fsSL -o /etc/apt/sources.list.d/winehq-jammy.sources \
  https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources

echo "[3/4] wine-stable + winetricks + 보조 도구 설치"
apt-get update
apt-get install -y --no-install-recommends \
  winehq-stable wine-stable wine32:i386 \
  winetricks cabextract p7zip-full aria2 winbind

echo "[4/4] 확인"
wine --version
echo
echo "Wine 버전 확인 위에서 9.x/10.x 나오면 정상 (Ubuntu 기본 6.0.3 은 .NET Framework 4.8 미지원)."
echo "이어서:  cd $(pwd) && ./wine_aladin.sh prefix"
