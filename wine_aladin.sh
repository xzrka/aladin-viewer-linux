#!/usr/bin/env bash
# 알라딘 Ebook PC Viewer (AladinEbookViewer) 를 wine 32bit prefix 에 설치/실행
# 디스크 실사용 약 3~5 GB (trim 시 ~2.5 GB)
#
# 사용법 (순서대로):
#   1) sudo bash install_wine.sh          # WineHQ wine 9+ / 10+ / 11 + winetricks (root)
#   2) ./wine_aladin.sh prefix            # prefix 생성 + corefonts/vcrun/dotnet48 (30~60분)
#   3) ./wine_aladin.sh fonts             # WPF 크롬 + ebook 폰트 등록 (한글 □□□ / 도서 로딩)
#   4) SETUP=./AladinEbookViewerSetup_1.9.0.5.exe ./wine_aladin.sh install
#   5) ./wine_aladin.sh run               # 실행
#   6) ./wine_aladin.sh trim              # pdb / TTS 음성 / 미사용 로케일 정리 (~600MB 회수)
#   7) ./wine_aladin.sh size              # 디스크 사용량
#
# ※ 앱 설치 파일(setup.exe) 은 저작권이 있는 알라딘 배포물이므로 이 저장소에 포함하지 않습니다.
#    aladinviewer.aladin.co.kr/library 에서 받아 SETUP= 경로로 지정하세요.

set -uo pipefail

PREFIX="${WINEPREFIX:-$HOME/.wine-aladin}"
SETUP="${SETUP:-$(dirname "$0")/setup.exe}"
INSTALL_DIR="$PREFIX/drive_c/Program Files/Aladin/AladinEbookViewer"
EXE="$INSTALL_DIR/AladinEbookViewer.exe"
HERE="$(cd "$(dirname "$0")" && pwd)"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

need_wine() {
  command -v wine >/dev/null || { echo "wine 이 설치되어 있지 않습니다.  sudo bash install_wine.sh"; exit 1; }
  local v; v=$(wine --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
  if [ "${v%%.*}" -lt 9 ] 2>/dev/null; then
    echo "경고: wine $v — .NET Framework 4.8(이 앱 필수) 은 Wine 9+ 에서 안정적입니다."
    echo "WineHQ 저장소 설치: https://wiki.winehq.org/Ubuntu"
  fi
}

cmd_prefix() {
  need_wine
  [ -d "$PREFIX" ] && echo "prefix 이미 존재: $PREFIX"
  log "32bit wine prefix 생성 ($PREFIX)"
  WINEARCH=win32 WINEPREFIX="$PREFIX" wineboot -u

  log "winetricks: corefonts (원본 Arial 필요 — 한글 폰트 생성의 골격) + VC++ 런타임"
  WINEPREFIX="$PREFIX" winetricks -q corefonts vcrun2012 vcrun2013 vcrun2022 \
    || echo "일부 vcrun 실패: 설치기가 레지스트리 검사에서 막히면 무시하고 진행"

  log "winetricks: .NET Framework 4.8  (가장 취약한 단계, 2~3회 재시도가 정상)"
  WINEPREFIX="$PREFIX" winetricks -q dotnet48 \
    || { echo "dotnet48 실패 → dotnet472 로 시도"; WINEPREFIX="$PREFIX" winetricks -q dotnet472; }

  log "완료. 다음: $0 fonts  →  $0 install"
}

cmd_fonts() {
  command -v python3 >/dev/null || { echo "python3 필요"; exit 1; }
  log "[1/2] WPF 크롬 (툴바·로그인·입력장) 용 폰트 → fontconfig 사용자 디렉터리"
  python3 "$HERE/scripts/install_kr_fonts.py" --prefix "$PREFIX" --no-restart
  log "[2/2] 앱이 ebook 본문에 쓰는 폰트 이름 → wine prefix + 레지스트리 (미등록 시 도서 로딩 실패)"
  python3 "$HERE/scripts/register_prefix_fonts.py" --prefix "$PREFIX" --no-restart
  echo
  echo "적용하려면 wineserver 재시작:  WINEPREFIX=$PREFIX wineserver -k  후 $0 run"
}

cmd_install() {
  need_wine
  [ -f "$SETUP" ] || { echo "설치 파일 없음: $SETUP  (SETUP=경로 로 지정하세요)"; exit 1; }
  log "AladinEbookViewer 무인 설치"
  WINEPREFIX="$PREFIX" wine start //exec //verysilent //norestart //suppressmsgboxes \
    "$(realpath "$SETUP")" 2>/dev/null \
    || WINEPREFIX="$PREFIX" wine "$SETUP" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES
  [ -f "$EXE" ] && echo "설치 확인: $EXE" || echo "실행파일 미검출: $EXE (설치 경로 확인)"
}

cmd_run() {
  need_wine
  [ -f "$EXE" ] || { echo "실행파일 없음: $EXE (먼저 $0 install)"; exit 1; }
  # 앱은 UTF-8 로케일에서 즉시 종료한다 (实测: en_US.UTF-8 에서 1초 만종). C 로 고정.
  export LANG=C LC_ALL=C
  export WINEPREFIX="$PREFIX"
  # NO_IME=1: XIM(ibus/fcitx) 연결을 꺼서 한글 입력 조합 시 나는 WPF 크래시를 피한다.
  # (ID/비밀번호는 영문·숫자이므로 실사용 지장 없음)
  if [ "${NO_IME:-1}" = 1 ]; then
    export XMODIFIERS=none
    echo "XIM 비활성 (NO_IME=1): 한글 IME 입력 조합으로 인한 WPF 크래시 회피"
  fi
  wine "$EXE"
}

cmd_trim() {
  [ -d "$INSTALL_DIR" ] || { echo "설치 디렉터리 없음: $INSTALL_DIR"; exit 1; }
  log "pdb / TTS 음성 / 미사용 로케일 정리 (실행에 불필요)"
  find "$INSTALL_DIR" -name '*.pdb' -delete
  find "$INSTALL_DIR/locales" -type f ! -name 'ko.pak' ! -name 'en-US.pak' -delete 2>/dev/null
  rm -rf "$INSTALL_DIR/voices" "$INSTALL_DIR/GPUCache"
  echo "정리 완료 (TTS '읽어주기' 기능은 사용 불가)"
}

cmd_size() { du -sh "$PREFIX" 2>/dev/null; du -sh "$INSTALL_DIR" 2>/dev/null; }

case "${1:-}" in
  prefix)  cmd_prefix ;;
  fonts)   cmd_fonts ;;
  install) cmd_install ;;
  run)     cmd_run ;;
  trim)    cmd_trim ;;
  size)    cmd_size ;;
  *) grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed -n '3,20p' ;;
esac
