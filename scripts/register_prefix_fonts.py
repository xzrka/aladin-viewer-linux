#!/usr/bin/env python3
"""앱이 ebook 렌더링에 쓰는 폰트 이름(SeoulNamsan / UnDinaru / CREMA_MYUNGJO2B / Nanum* …)을
wine prefix 의 C:\\windows\\Fonts + 레지스트리에 등록한다.

왜 필요한가 (实测):
  AladinEbookViewer 는 ebook本文을 CEF/GDI 로 그리면서 자기 폰트 이름
  (SEOULNAMSAN, UnDinaru, CREMA_MYUNGJO2B, NanumGothic, Batang, Gungsuh, hunminjungum,
  kopubbatangmedium …) 을 하드코딩으로 요구한다. 앱 설치 디렉터리에는 폰트 파일이 없고,
  Wine 의 GDI 는 `HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Fonts` 의
  "가족 이름 (TrueType)" -> 파일 매핑으로 그 이름을 푼다.
  → 이 매핑이 빠지면 **도서 로딩이 안 된다**(实测).

왜 WPF 이름(Segoe UI 등)은 등록하지 않는가 (实测):
  같은 이름을 레지스트리에 등록하면 WPF 는 fontconfig 사본 대신 그 레지스트리 파일을 쓰고,
  MS OpenType 파서가 우리 생성 파일을 거부해서 크롬 글자가 다시 □ 가 된다.
  → WPF 용은 install_kr_fonts.py (fontconfig), 앱 ebook 용은 이 스크립트 (prefix+registry).
    두 층을 분리하는 것이 이 저장소의 결론이다.

사용법:
  python3 register_prefix_fonts.py                      # 생성+설치+등록+검증
  python3 register_prefix_fonts.py --source <dir>       # 기존 폰트 파일 사용 (파일명 매핑은 APP_FONTS)
  python3 register_prefix_fonts.py --uninstall          # 파일 원복 + 레지스트리 값 삭제
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_kr_fonts import FAMILIES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# 앱 바이너리/XAML·CEF 가 ebook 렌더링에 쓰는 이름과, wine prefix 에 쓸 파일명.
# (이름 목록은 이전 세션의 fonts_ttf.reg 과 AladinEbookViewer.exe 문자열 实测 기준.
#  파일명은 이 저장의 생성작이 만드는 이름과 일치시킨다 — Wine 은 파일명을 그대로 연다.)
APP_FONTS = {
    "Malgun Gothic": "malgun.ttf",
    "Malgun Gothic Bold": "malgunbd.ttf",
    "Gulim": "gulim.ttf",
    "Gulim Bold": "gulimbd.ttf",
    "GulimChe": "gulimche.ttf",
    "GulimChe Bold": "gulimchebd.ttf",
    "Dotum": "dotum.ttf",
    "Dotum Bold": "dotumbd.ttf",
    "DotumChe": "dotumche.ttf",
    "DotumChe Bold": "dotumchebd.ttf",
    "Batang": "batang.ttf",
    "Batang Bold": "batangbd.ttf",
    "BatangChe": "batangche.ttf",
    "Gungsuh": "gungsuh.ttf",
    "Gungsuh Bold": "gungsuhbd.ttf",
    "Microsoft Sans Serif": "micross.ttf",
    "Tahoma": "tahoma.ttf",
    "Tahoma Bold": "tahomabd.ttf",
    "Meiryo": "meiryo.ttf",
    "Yu Gothic UI": "yugothic.ttf",
    "NanumGothic": "nanumgothic.ttf",
    "NanumMyeongjo": "nanummyeongjo.ttf",
    "NanumPen": "nanumpen.ttf",
    "UnDinaru": "undinaru.ttf",
    "UnGraphic": "ungraphic.ttf",
    "UnPilgi": "unpilgi.ttf",
    "hunminjungum": "hunminjungum.ttf",
    "kopubbatangmedium": "kopubbatangmedium.ttf",
    "SeoulNamsan": "seoulnamsan.ttf",
    "SeoulNamsanB": "seoulnamsanb.ttf",
    "SeoulHangangB": "seoulhangangb.ttf",
    "CREMA_MYUNGJO2B": "crema_myungjo2b.ttf",
}
# WPF 가 쓰는 이름은 등록 대상에서 뺀다 (위 문서 상단 참조).
WPF_NAMES = {row[1] for row in FAMILIES if row[1].startswith(("Segoe UI", "Arial"))}


def run(cmd: list[str], capture: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, env=env)


def reg(prefix: str, op: str, family: str, file_name: str | None = None) -> None:
    key = r"HKLM\Software\Microsoft\Windows\CurrentVersion\Fonts"
    env = dict(os.environ, WINEPREFIX=prefix, WINEDEBUG="-all", LC_ALL="C", LANG="C")
    args = ["wine", "reg", op, key, "/v", f"{family} (TrueType)"]
    if op == "add":
        args += ["/t", "REG_SZ", "/d", file_name, "/f"]
    else:
        args += ["/f"]
    run(args, env=env)


def build(source: str, skeleton_dir: str, noto_dir: str) -> str:
    """APP_FONTS 에 필요한 face 를 만들어 담을 디렉터리를 돌려준다."""
    if source:
        missing = [f for f in set(APP_FONTS.values()) if not os.path.exists(os.path.join(source, f))]
        if missing:
            print(f"!! --source {source} 에 파일 없음: {', '.join(sorted(missing))}", file=sys.stderr)
            raise SystemExit(1)
        return source
    tmp = tempfile.mkdtemp(prefix="aladin-appfonts-")
    cmd = [sys.executable, os.path.join(HERE, "make_kr_fonts.py"), tmp,
           "--skeleton-dir", skeleton_dir, "--noto-dir", noto_dir]
    if subprocess.run(cmd).returncode:
        raise SystemExit("폰트 생성 실패")
    return tmp


def install(prefix: str, source: str) -> None:
    fonts = os.path.join(prefix, "drive_c", "windows", "Fonts")
    os.makedirs(fonts, exist_ok=True)
    for family, file_name in sorted(APP_FONTS.items()):
        src = os.path.join(source, file_name)
        if not os.path.exists(src):
            print(f"  건너뜀 {family:<22} ({file_name} 없음 — make_kr_fonts FAMILIES 에 추가 필요)")
            continue
        dst = os.path.join(fonts, file_name)
        backup = dst + ".orig-aladin"
        if os.path.exists(dst) and not os.path.exists(backup):
            shutil.copy2(dst, backup)
        shutil.copy2(src, dst)
        reg(prefix, "add", family, file_name)
        print(f"  등록 {family:<22} -> {file_name}")
    print(f"fc-cache -f {fonts}")
    run(["fc-cache", "-f", fonts])


def uninstall(prefix: str) -> None:
    fonts = os.path.join(prefix, "drive_c", "windows", "Fonts")
    for family, file_name in sorted(APP_FONTS.items()):
        reg(prefix, "delete", family)
        target = os.path.join(fonts, file_name)
        backup = target + ".orig-aladin"
        if os.path.exists(backup):
            shutil.move(backup, target)
            print(f"  복원 {file_name}")
        elif os.path.exists(target):
            os.remove(target)
            print(f"  삭제 {file_name}")
    run(["fc-cache", "-f", fonts])
    print("원복 완료. wineserver -k 후 앱을 켜면 이전 상태로 돌아갑니다.")


def verify(prefix: str) -> int:
    env = dict(os.environ, WINEPREFIX=prefix, WINEDEBUG="-all", LC_ALL="C", LANG="C")
    missing = []
    for family in sorted(APP_FONTS):
        out = run(["wine", "reg", "query", r"HKLM\Software\Microsoft\Windows\CurrentVersion\Fonts",
                   "/v", f"{family} (TrueType)"], env=env)
        if "REG_SZ" not in (out.stdout or ""):
            missing.append(family)
    print(f"레지스트리 등록 확인: {len(APP_FONTS) - len(missing)}/{len(APP_FONTS)}"
          + (f"  미등록: {', '.join(missing)}" if missing else ""))
    return 1 if missing else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="알라딘 뷰어 ebook 폰트를 wine prefix 에 등록")
    ap.add_argument("--prefix", default=os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine-aladin")))
    ap.add_argument("--source", default="", help="폰트 .ttf 가 있는 디렉터리 (생성 대신 사용)")
    ap.add_argument("--skeleton-dir", default="/usr/share/fonts/truetype/msttcorefonts")
    ap.add_argument("--noto-dir", default="/usr/share/fonts/opentype/noto")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--no-restart", action="store_true")
    args = ap.parse_args()

    prefix = os.path.abspath(os.path.expanduser(args.prefix))
    if not os.path.isdir(os.path.join(prefix, "drive_c")):
        raise SystemExit(f"wine prefix 없음: {prefix}")

    if args.uninstall:
        uninstall(prefix)
        return 0

    print(f"== ebook 폰트 {len(APP_FONTS)} 개을 {prefix} 에 등록합니다")
    print(f"   (WPF 가 쓰는 이름은 제외: {', '.join(sorted(WPF_NAMES))})")
    source = build(args.source, args.skeleton_dir, args.noto_dir)
    install(prefix, source)

    if not args.no_restart:
        print("== wineserver 재시작 (실행 중인 알라딘 뷰어가 종료됩니다)")
        run(["wineserver", "-k"], capture=False)
        subprocess.run(["sleep", "3"])
    return verify(prefix)


if __name__ == "__main__":
    sys.exit(main())
