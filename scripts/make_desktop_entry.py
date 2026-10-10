#!/usr/bin/env python3
"""알라딘 Ebook PC Viewer 의 Linux 앱 메뉴 / 바탕화면 바로가기를 만든다.

왜 필요한가:
  wine 설치(winetricks / wineinstaller / wine 의 menubuilder) 는 설치에 쓴 **prefix 경로**를
  그대로 박아서 ~/.local/share/applications/wine/... 에 .desktop 를 만든다.
  그 prefix 를 옮기거나 지우면 메뉴 항목은 남아 있고 Exec 이 죽은 경로를 가리켜
  **프로그램 메뉴에서 켜도 아무 일도 일어나지 않는다** (实测: 6개 항목이 삭제한 prefix 를
  가리키던 상태).

  게다가 이 앱은 두 가지 환경변수가 없으면 실행 직후 죽는다:
    · LANG/LC_ALL = C      → UTF-8 로케일에서 "Failed to create secure store file" 로 1초 만종
    · XMODIFIERS = none    → ibus XIM 이 걸린 상태에서 한글을 조합하면 WPF 가 AccessViolation
  데스크톱 세션은 UTF-8 이므로, 메뉴에서 켜면 locale 문제가 그대로 터진다.
  → Exec 에 env 로 LANG=C LC_ALL=C XMODIFIERS=none WINEPREFIX=... 를 명시해야 한다.

사용법:
  python3 make_desktop_entry.py                      # 메뉴 + 바탕화면 항목 생성 (죽은 항목 정리)
  python3 make_desktop_entry.py --desktop-dir <dir>  # 바탕화면 위치 지정
  python3 make_desktop_entry.py --clean              # 죽은 wine 항목만 삭제 (생성 안 함)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

APP_NAME = "Aladin Ebook PC Viewer"
WM_CLASS = "aladinebookviewer.exe"
ICON = "543A_AladinEbookViewer.0"
INSTALL_SUBDIR = r"drive_c/Program Files/Aladin/AladinEbookViewer"
EXE_NAME = "AladinEbookViewer.exe"

DESKTOP_TEMPLATE = """[Desktop Entry]
Type=Application
Name={name}
Name[ko_KR]=알라딘 Ebook PC Viewer
Comment=Aladin ebook viewer via Wine (LANG=C, XIM off)
Comment[ko_KR]=Wine 로 실행하는 알라딘 Ebook PC Viewer (C 로케일, XIM off)
Exec=env LANG=C LC_ALL=C XMODIFIERS=none WINEPREFIX={prefix} wine "{exe}"
Path={workdir}
Icon={icon}
StartupNotify=true
StartupWMClass={wmclass}
Terminal=false
Categories=Office;Viewer;X-Wine;
"""


def desktop_files(applications_dir: str) -> list[str]:
    out = []
    for root, _dirs, files in os.walk(applications_dir):
        for f in files:
            if f.endswith(".desktop"):
                out.append(os.path.join(root, f))
    return out


def wine_prefix_in(path: str) -> str | None:
    """ .desktop Exec 의 WINEPREFIX= 값 (죽은 prefix 검증용). """
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    m = re.search(r"WINEPREFIX=([^\s\"]+)", text)
    return os.path.expanduser(m.group(1)) if m else None


def clean_dead(applications_dir: str, live_prefix: str, apply: bool = True) -> int:
    """WINEPREFIX 가 실재하지 않는 wine .desktop 를 지운다. (살아있는 prefix 는 건드리지 않음)"""
    removed = 0
    for path in desktop_files(applications_dir):
        prefix = wine_prefix_in(path)
        if not prefix or prefix == os.path.abspath(live_prefix):
            continue
        if os.path.isdir(prefix):
            continue
        print(f"  죽은 항목: {path}  -> WINEPREFIX={prefix}")
        if apply:
            os.remove(path)
            removed += 1
    return removed


def write_entry(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(path, 0o755)
    print(f"  작성: {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="알라딘 뷰어 .desktop 바로가기 생성")
    ap.add_argument("--prefix", default=os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine-aladin")))
    ap.add_argument("--desktop-dir", default=os.path.expanduser("~/바탕화면"),
                    help="바탕화면 .desktop 을 놓을 위치 (없으면 생략, 없는 경로면 건너뜀)")
    ap.add_argument("--applications-dir", default=os.path.expanduser("~/.local/share/applications"))
    ap.add_argument("--clean", action="store_true", help="죽은 wine 항목만 정리하고 끝낸다")
    args = ap.parse_args()

    prefix = os.path.abspath(os.path.expanduser(args.prefix))
    exe = os.path.join(prefix, INSTALL_SUBDIR, EXE_NAME)
    if not os.path.exists(exe):
        print(f"!! 실행파일 없음: {exe}", file=sys.stderr)
        print("   WINEPREFIX 를 확인하세요. (예: ~/.wine-aladin)", file=sys.stderr)
        return 1

    applications = os.path.abspath(os.path.expanduser(args.applications_dir))
    print(f"== 1/3 죽은 wine 바로가기 정리 ({applications})")
    removed = clean_dead(applications, prefix)
    print(f"   삭제 {removed} 개")
    if args.clean:
        return 0

    print("== 2/3 앱 메뉴 항목")
    entry = DESKTOP_TEMPLATE.format(name=APP_NAME, prefix=prefix, exe=exe,
                                    workdir=os.path.dirname(exe), icon=ICON, wmclass=WM_CLASS)
    write_entry(os.path.join(applications, "wine", "Programs", APP_NAME, f"{APP_NAME}.desktop"), entry)

    desktop_dir = os.path.abspath(os.path.expanduser(args.desktop_dir))
    if os.path.isdir(desktop_dir):
        print("== 3/3 바탕화면 항목")
        write_entry(os.path.join(desktop_dir, f"{APP_NAME}.desktop"), entry)
    else:
        print(f"== 3/3 바탕화면 없음, 건너뜀 ({desktop_dir})")

    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", applications], capture_output=True, text=True)
    if shutil.which("desktop-file-validate"):
        for path in (os.path.join(applications, "wine", "Programs", APP_NAME, f"{APP_NAME}.desktop"),):
            done = subprocess.run(["desktop-file-validate", path], capture_output=True, text=True)
            if done.returncode:
                print("  validate 경고:\n" + (done.stdout or "")[-800:])
    print(f"\n바로가기 실행 명령:\n  env LANG=C LC_ALL=C XMODIFIERS=none WINEPREFIX={prefix} wine \"{exe}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
