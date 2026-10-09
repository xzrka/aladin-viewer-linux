#!/usr/bin/env python3
"""알라딘 Ebook PC Viewer 의 WPF 크롬 한글 □□□ 패치: 폰트 생성 → 설치 → 검증.

实测로 확정한 방식 (이게 이 스크립트의 존재 이유다)
--------------------------------------------------------------
· WPF(PresentationNative_cor32.dll) 의 폰트 목록은 **fontconfig 가 스캔하는 디렉터리**에서
  만들어진다. XAML 기본 폰트 이름 "Segoe UI" 가 그 목록에 물리 face 로 없으면 WPF 는
  자기 안의 last-resort face(라틴 전용) 를 쓰고 → 한글만 □ 가 된다.
· 그래서 폰트는 **fontconfig 사용자 폰트 디렉터리**에 넣는다. root 필요 없다.
· `wine prefix` 의 `drive_c/windows/Fonts` 에 복사하고 `HKLM\\Software\\Microsoft\\Windows\\
  CurrentVersion\\Fonts` 에 레지스트리까지 등록하면 **도리어 실패한다**:
  WPF 가 그 family 를 레지스트리 파일로 해석하려고 하기 때문이다 (实测: 43개 family 전부
  TryGetGlyphTypeface=False → 레지스트리 값 삭제 + prefix 파일 원복 후同一 파일 True).
  → 이 스크립트는 prefix 와 레지스트리에 **손대지 않는다**.
· 앱 바이너리(setup.exe, AladinEbookViewer.exe, DLL) 는 절대 수정하지 않는다.

사용법:
  python3 install_kr_fonts.py                # 생성 + 설치 + wineserver 재시작 + WPF 해석 검증
  python3 install_kr_fonts.py --uninstall    # 설치 전으로 원복
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_kr_fonts import FAMILIES, KEEP_RANGES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "ProbeKr.cs")
# 앱 바이너리/XAML 이 실제로 요청하는 이름들 (实测: AladinEbookViewer.exe 문자열 = Arial*,
# XAML 기본값 = Segoe UI*). 패치 성공 기준은 이 이름들이다.
# 나머지는 앱이 ebook 렌더링(CEF/GDI) 에서 쓰는 이름으로 WPF 크롬과 무관하다.
WPF_CRITICAL = {
    "Segoe UI", "Segoe UI Bold", "Segoe UI Light", "Segoe UI Semibold", "Segoe UI Symbol",
    "Segoe UI Emoji", "Arial", "Arial Black", "Microsoft Sans Serif", "Tahoma",
}
CSC = "C:/windows/Microsoft.NET/Framework/v4.0.30319/csc.exe"
WPF_REFS = [
    "C:/windows/Microsoft.NET/Framework/v4.0.30319/WPF/PresentationCore.dll",
    "C:/windows/Microsoft.NET/Framework/v4.0.30319/WPF/PresentationFramework.dll",
    "C:/windows/Microsoft.NET/Framework/v4.0.30319/WPF/WindowsBase.dll",
    "C:/windows/Microsoft.NET/Framework/v4.0.30319/System.Xaml.dll",
]
DIR_NAME = "aladin-wine-kr"


def user_font_dir() -> str:
    """fontconfig 가 스캔하는 사용자 폰트 디렉터리 (WPF 가 보는 곳)."""
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(xdg, "fonts", DIR_NAME)


def run(cmd: list[str], capture: bool = False, env: dict | None = None,
         cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, env=env, cwd=cwd)


def wine_env(prefix: str) -> dict:
    return dict(os.environ, WINEPREFIX=prefix, WINEDEBUG="-all", LC_ALL="C", LANG="C")


def zpath(path: str) -> str:
    """POSIX 절대경로를 wine 용 Z: 경로로. csc.exe 는 '/tmp/x.cs' 를 스위치로 오인한다."""
    return "z:" + os.path.abspath(os.path.expanduser(path)).replace(os.sep, "/")


def build_fonts(outdir: str, skeleton_dir: str, noto_dir: str) -> None:
    cmd = [sys.executable, os.path.join(HERE, "make_kr_fonts.py"), outdir,
           "--skeleton-dir", skeleton_dir, "--noto-dir", noto_dir]
    print(f"$ {' '.join(cmd)}")
    if subprocess.run(cmd).returncode:
        raise SystemExit("폰트 생성 실패")


def install(target: str, build_dir: str) -> None:
    os.makedirs(target, exist_ok=True)
    for row in FAMILIES:
        file_name, family, style = row[0], row[1], row[2]
        shutil.copy2(os.path.join(build_dir, file_name), os.path.join(target, file_name))
        print(f"  {file_name:<22} {family} {style}")
    print(f"fc-cache -f {target}")
    run(["fc-cache", "-f", target], capture=True)


def uninstall(target: str) -> None:
    for row in FAMILIES:
        path = os.path.join(target, row[0])
        if os.path.exists(path):
            os.remove(path)
    if os.path.isdir(target) and not [f for f in os.listdir(target) if not f.startswith(".")]:
        shutil.rmtree(target)
    run(["fc-cache", "-f", target], capture=True)
    print(f"원복 완료: {target}")


def probe(prefix: str) -> int:
    """WPF 가 family 이름을 물리 face 로 해석하는지 확인한다 (实测 게이트).

    csc.exe(wine) 는 'z:/tmp/x/ProbeKr.cs' 를 넘기면 디렉터리 부분을 버리고
    cwd 기준 'ProbeKr.cs' 로 해석한다 (实测: error CS1504 'z:\tmp\ProbeKr.cs').
    그래서 **cwd 를 소스 폴더로 잡고 파일명만** 넘긴다.
    """
    if not os.path.exists(PROBE):
        print("  (ProbeKr.cs 이 없어 검증 생략)")
        return 0
    env = wine_env(prefix)
    # wine 은 새 프로세스를 붙일 때마다 폰트 목록을 새로 만든다. csc 의 cwd 트릭(위 주석) 때문에
    # exe 실행도 같은 cwd 에서 파일명만으로 돌린다.
    with tempfile.TemporaryDirectory(prefix="aladin-probe-") as tmp:
        cs = os.path.join(tmp, "ProbeKr.cs")
        exe = os.path.join(tmp, "ProbeKr.exe")
        shutil.copy2(PROBE, cs)
        done = run(["wine", CSC, "-nologo", "-target:exe", "-out:ProbeKr.exe",
                    *[f"-r:{r}" for r in WPF_REFS], "ProbeKr.cs"], capture=True, env=env, cwd=tmp)
        if not os.path.exists(exe):
            print("  probe 컴파일 실패:\n" + ((done.stdout or "") + (done.stderr or ""))[-1200:])
            return 1
        out = run(["wine", "ProbeKr.exe"], capture=True, env=env, cwd=tmp)
        lines = [ln for ln in ((out.stdout or "") + (out.stderr or "")).splitlines()
                 if ln.startswith(("request", "SystemFonts", "SystemFontFamilies"))]
        print("\n".join(lines))
        bad = [ln for ln in lines if ln.startswith("request") and "TryGetGlyphTypeface=False" in ln]
        critical = [ln for ln in bad if ln.split("'")[1] in WPF_CRITICAL]
        shadowed = [ln for ln in bad if ln not in critical]
        print(f"\nWPF 크롬 필수 family 미해결 {len(critical)} 개")
        for ln in critical:
            print("  " + ln)
        if shadowed:
            names = ", ".join(sorted({ln.split("'")[1] for ln in shadowed}))
            print(f"참고 (WPF 크롬 무관, prefix 그림자): {names}")
            print("  → wine prefix drive_c/windows/Fonts 에 같은 이름의 기존 폰트 파일이 있으면")
            print("    WPF 는 그 파일에 family 를 묶는다(实测). 깨끗한 prefix 에선 발생하지 않는다.")
        return 1 if critical else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="알라딘 뷰어 WPF 한글 폰트 패치 (fontconfig 사용자 디렉터리)")
    ap.add_argument("--prefix", default=os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine-aladin")),
                    help="WPF 해석 검증에 쓸 wine prefix (--no-probe 쓰면 안 써도 됨)")
    ap.add_argument("--skeleton-dir", default="/usr/share/fonts/truetype/msttcorefonts",
                    help="원본 Arial TrueType 디렉터리 (winetricks corefonts 가 설치한 곳)")
    ap.add_argument("--noto-dir", default="/usr/share/fonts/opentype/noto",
                    help="Noto Sans CJK .ttc 디렉터리 (fonts-noto-cjk)")
    ap.add_argument("--target", default=user_font_dir(), help="설치할 폰트 디렉터리")
    ap.add_argument("--uninstall", action="store_true", help="설치한 폰트 삭제")
    ap.add_argument("--no-restart", action="store_true", help="wineserver 종료 생략 (앱 실행 중일 때)")
    ap.add_argument("--no-probe", action="store_true", help="WPF 해석 검증 생략")
    args = ap.parse_args()

    target = os.path.abspath(os.path.expanduser(args.target))

    if args.uninstall:
        uninstall(target)
        print("wineserver 를 재시작해야 앱이 이전 상태로 돌아갑니다: wineserver -k")
        return 0

    missing = [p for p in (os.path.join(args.skeleton_dir, "Arial.ttf.orig-aladin"),
                           os.path.join(args.skeleton_dir, "Arial.ttf"),
                           os.path.join(args.noto_dir, "NotoSansCJK-Regular.ttc"))
               if not os.path.exists(p)]
    if not any(os.path.exists(os.path.join(args.skeleton_dir, n)) for n in ("Arial.ttf.orig-aladin", "Arial.ttf")):
        missing.append(f"{args.skeleton_dir}/Arial.ttf (winetricks corefonts 필요)")
    for p in missing:
        if not os.path.exists(p):
            print(f"!! 필요 파일 없음: {p}", file=sys.stderr)
    if missing:
        return 1

    with tempfile.TemporaryDirectory(prefix="aladin-kr-") as build:
        build_fonts(build, args.skeleton_dir, args.noto_dir)
        print(f"== 설치 대상: {target}")
        install(target, build)

    if args.no_restart:
        print("== wineserver 재시작 건너뜀 (--no-restart): 앱을 이미 켜 두었다면 재시작 후 적용된다")
    else:
        print("== wineserver 재시작 (실행 중인 알라딘 뷰어가 종료됩니다)")
        run(["wineserver", "-k"], env=wine_env(args.prefix))
        subprocess.run(["sleep", "3"])

    if not args.no_probe:
        prefix = os.path.abspath(os.path.expanduser(args.prefix))
        if not os.path.isdir(os.path.join(prefix, "drive_c")):
            print(f"== 검증 생략: wine prefix 없음 ({prefix}) — ./wine_aladin.sh prefix 먼저")
            return 0
        print("== WPF 해석 검증 (기대: 모든 family TryGetGlyphTypeface=True)")
        return probe(prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
