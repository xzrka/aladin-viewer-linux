#!/usr/bin/env python3
"""WPF 가 요청하는 family 이름마다 **한글 glyf 를 심은 TrueType** 을 만든다.

왜 필요한가 (Wine 11.0 + .NET 4.8实测):
  · WPF 의 XAML 기본 폰트 이름은 "Segoe UI". 이 이름이 Wine 의 폰트 목록에서
    물리 face 로 해석되지 않으면 WPF 는 자기 안의 last-resort face(라틴 전용) 를 쓴다.
    → 앱 창 제목(Non-Client, Wine caption font) 은 한글이 나오고,
      툴바/로그인 버튼/입력장 placeholder(= Segoe UI) 만 □ 로 남는 원인이 이것이다.
  · 기존 "리테깅" 폰트(name 테이블만 바꾼 TTF) 은 WPF OpenType 파서가 face 로 거부한다
    (实测: TryGetGlyphTypeface("Segoe UI") == False, Baseline 0.921630859375 = last-resort).
  · 반면 **원본 Arial TrueType 에 Noto CJK 외곽선을 em 2048 스케일로 병합한 파일**은
    WPF 가 face 로 해석하고 한글까지 렌더한다(实测).

만드는 법:
  1) 원본 msttcorefonts Arial(TrueType, em 2048) 을 골격으로 쓴다 → 라틴 메트릭/구조 유지.
  2) Noto Sans CJK 의 한글 음절/자모/CJK 구두점 glyf 를 2.048 배 스케일로 병합한다
     (CFF cubic → Cu2QuPen 으로 2차 베지어 변환, em 1000 → 2048 환산).
  3) name 테이블만 요청된 family 이름으로 바꾼다. head.fontRevision = 99.0
     → fontconfig 이름 경쟁에서 이긴다(같은 family 는 fontversion 우선).

 라이선스: 이 스크립트가 읽는 원본 폰트는 사용자 시스템의 사본이다.
   - Arial (msttcorefonts, Microsoft EULA) : 재배포 금지 → 이 저장소에 포함하지 않는다.
   - Noto Sans CJK (SIL OFL)              : 재단/이름변경 허용.
"""
from __future__ import annotations

import argparse
import os
import sys

from fontTools import subset
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, TTCollection

# 서브셋에 남길 문자 범위 (라틴 + 구두점 + 기호 + 한글 + CJK 구두점 + 전각)
KEEP_RANGES = [
    (0x0020, 0x007E), (0x00A0, 0x00FF), (0x2000, 0x206D), (0x20A0, 0x20BF),
    (0x2190, 0x21BB), (0x25A0, 0x25FF), (0x3000, 0x303E), (0x3130, 0x318F),
    (0x1100, 0x11FF), (0xAC00, 0xD7A3), (0xFF01, 0xFF60), (0xFFE0, 0xFFE6),
]
# (Noto 파일, name ID1 family, name ID2 style) — Noto CJK 에는 italic 이 없어 Regular/Bold 로 대용한다.
NOTO = {
    "Regular": ("NotoSansCJK-Regular.ttc", "Noto Sans CJK KR", "Regular"),
    "Bold": ("NotoSansCJK-Bold.ttc", "Noto Sans CJK KR", "Bold"),
    "Italic": ("NotoSansCJK-Regular.ttc", "Noto Sans CJK KR", "Regular"),
    "Bold Italic": ("NotoSansCJK-Bold.ttc", "Noto Sans CJK KR", "Bold"),
    "Light": ("NotoSansCJK-Light.ttc", "Noto Sans CJK KR Light", "Regular"),
    "Semibold": ("NotoSansCJK-DemiLight.ttc", "Noto Sans CJK KR DemiLight", "Regular"),
}
# (out file, WPF family, style, 원본 TrueType skeleton, win32 registry value name)
FAMILIES = [
    ("segoeui.ttf", "Segoe UI", "Regular", "Arial.ttf.orig-aladin", "Segoe UI (TrueType)"),
    ("segoeuib.ttf", "Segoe UI", "Bold", "Arial_Bold.ttf.orig-aladin", "Segoe UI Bold (TrueType)"),
    ("seguisb.ttf", "Segoe UI Semibold", "Semibold", "Arial_Bold.ttf.orig-aladin", "Segoe UI Semibold (TrueType)"),
    ("seguisli.ttf", "Segoe UI Light", "Light", "Arial.ttf.orig-aladin", "Segoe UI Light (TrueType)"),
    ("segoeuii.ttf", "Segoe UI", "Italic", "Arial_Italic.ttf.orig-aladin", "Segoe UI Italic (TrueType)"),
    ("segoeuiz.ttf", "Segoe UI", "Bold Italic", "Arial_Bold_Italic.ttf.orig-aladin", "Segoe UI Bold Italic (TrueType)"),
    ("seguisym.ttf", "Segoe UI Symbol", "Regular", "Arial.ttf.orig-aladin", "Segoe UI Symbol (TrueType)"),
    ("segoeui-emoji.ttf", "Segoe UI Emoji", "Regular", "Arial.ttf.orig-aladin", "Segoe UI Emoji (TrueType)"),
    ("malgun.ttf", "Malgun Gothic", "Regular", "Arial.ttf.orig-aladin", "Malgun Gothic (TrueType)"),
    ("malgunbd.ttf", "Malgun Gothic", "Bold", "Arial_Bold.ttf.orig-aladin", "Malgun Gothic Bold (TrueType)"),
    ("malgunsl.ttf", "Malgun Gothic", "Light", "Arial.ttf.orig-aladin", "Malgun Gothic Semilight (TrueType)"),
    ("arial.ttf", "Arial", "Regular", "Arial.ttf.orig-aladin", "Arial (TrueType)"),
    ("arialbd.ttf", "Arial", "Bold", "Arial_Bold.ttf.orig-aladin", "Arial Bold (TrueType)"),
    ("ariali.ttf", "Arial", "Italic", "Arial_Italic.ttf.orig-aladin", "Arial Italic (TrueType)"),
    ("arialbi.ttf", "Arial", "Bold Italic", "Arial_Bold_Italic.ttf.orig-aladin", "Arial Bold Italic (TrueType)"),
    ("ariblk.ttf", "Arial Black", "Regular", "Arial_Bold.ttf.orig-aladin", "Arial Black (TrueType)"),
    ("micross.ttf", "Microsoft Sans Serif", "Regular", "Arial.ttf.orig-aladin", "Microsoft Sans Serif (TrueType)"),
    ("tahoma.ttf", "Tahoma", "Regular", "Arial.ttf.orig-aladin", "Tahoma (TrueType)"),
    ("tahomabd.ttf", "Tahoma", "Bold", "Arial_Bold.ttf.orig-aladin", "Tahoma Bold (TrueType)"),
    ("gulim.ttf", "Gulim", "Regular", "Arial.ttf.orig-aladin", "Gulim (TrueType)"),
    ("gulimbd.ttf", "Gulim", "Bold", "Arial_Bold.ttf.orig-aladin", "Gulim Bold (TrueType)"),
    ("gulimche.ttf", "GulimChe", "Regular", "Arial.ttf.orig-aladin", "GulimChe (TrueType)"),
    ("dotum.ttf", "Dotum", "Regular", "Arial.ttf.orig-aladin", "Dotum (TrueType)"),
    ("dotumbd.ttf", "Dotum", "Bold", "Arial_Bold.ttf.orig-aladin", "Dotum Bold (TrueType)"),
    ("dotumche.ttf", "DotumChe", "Regular", "Arial.ttf.orig-aladin", "DotumChe (TrueType)"),
    ("batang.ttf", "Batang", "Regular", "Arial.ttf.orig-aladin", "Batang (TrueType)"),
    ("batangbd.ttf", "Batang", "Bold", "Arial_Bold.ttf.orig-aladin", "Batang Bold (TrueType)"),
    ("gungsuh.ttf", "Gungsuh", "Regular", "Arial.ttf.orig-aladin", "Gungsuh (TrueType)"),
    ("meiryo.ttf", "Meiryo", "Regular", "Arial.ttf.orig-aladin", "Meiryo (TrueType)"),
    ("yugothic.ttf", "Yu Gothic UI", "Regular", "Arial.ttf.orig-aladin", "Yu Gothic UI (TrueType)"),
    ("nanumgothic.ttf", "NanumGothic", "Regular", "Arial.ttf.orig-aladin", "NanumGothic (TrueType)"),
    ("nanummyeongjo.ttf", "NanumMyeongjo", "Regular", "Arial.ttf.orig-aladin", "NanumMyeongjo (TrueType)"),
    ("nanumpen.ttf", "NanumPen", "Regular", "Arial.ttf.orig-aladin", "NanumPen (TrueType)"),
    ("undinaru.ttf", "UnDinaru", "Regular", "Arial.ttf.orig-aladin", "UnDinaru (TrueType)"),
    ("seoulnamsan.ttf", "SeoulNamsan", "Regular", "Arial.ttf.orig-aladin", "SeoulNamsan (TrueType)"),
    ("seoulhangangb.ttf", "SeoulHangangB", "Regular", "Arial.ttf.orig-aladin", "SeoulHangangB (TrueType)"),
    ("crema_myungjo2b.ttf", "CREMA_MYUNGJO2B", "Regular", "Arial.ttf.orig-aladin", "CREMA_MYUNGJO2B (TrueType)"),
    ("msyh.ttf", "Microsoft YaHei UI", "Regular", "Arial.ttf.orig-aladin", "Microsoft YaHei UI (TrueType)"),
    ("msgothic.ttf", "MS Gothic", "Regular", "Arial.ttf.orig-aladin", "MS Gothic (TrueType)"),
    ("msmincho.ttf", "MS Mincho", "Regular", "Arial.ttf.orig-aladin", "MS Mincho (TrueType)"),
    ("msgothicp.ttf", "MS PGothic", "Regular", "Arial.ttf.orig-aladin", "MS PGothic (TrueType)"),
    ("simsun.ttf", "SimSun", "Regular", "Arial.ttf.orig-aladin", "SimSun (TrueType)"),
    ("mingliu.ttf", "PMingLiU", "Regular", "Arial.ttf.orig-aladin", "PMingLiU (TrueType)"),
]
FALLBACK_SKELETON = "Arial.ttf.orig-aladin"
MAX_ERR = 1.0            # em 2048 기준 2차 곡선 근사 허용 오차
REVISION = 99.0          # fontconfig 이름 경쟁용 (fontversion 우선)


def find_face(path: str, family: str, style: str) -> TTFont:
    """ttc 안에서 name ID1(family)+ID2(style) 로 face 를 고른다."""
    fonts = TTCollection(path, lazy=True).fonts if path.lower().endswith(".ttc") else [TTFont(path, lazy=True)]
    for font in fonts:
        if font["name"].getDebugName(1) == family and font["name"].getDebugName(2) == style:
            return font
    for font in fonts:                      # 스타일이 없으면 Regular 로 대용
        if font["name"].getDebugName(1) == family:
            print(f"  note: {os.path.basename(path)} 에 {family} {style} 없음 -> Regular 사용", file=sys.stderr)
            return font
    return None


def merge_hangul(base: TTFont, src: TTFont) -> int:
    """src(Noto, em 1000) 의 한글 glyf 를 base(Arial, em 2048) 좌표계로 병합한다."""
    scale = base["head"].unitsPerEm / src["head"].unitsPerEm
    glyf, hmtx = base["glyf"], base["hmtx"]
    cmap_sub = next(t for t in base["cmap"].tables if t.isUnicode() and t.platformID == 3)
    have = dict(base["cmap"].getBestCmap())
    order = list(base.getGlyphOrder())
    src_set, src_cmap = src.getGlyphSet(), src.getBestCmap()
    src_hmtx = src["hmtx"]

    wanted = {c for lo, hi in KEEP_RANGES for c in range(lo, hi + 1)}
    added = 0
    for code in sorted(src_cmap):
        name = src_cmap[code]
        if code not in wanted or code in have or name not in src_set:
            continue
        pen = TTGlyphPen(glyf.glyphs)
        try:
            src_set[name].draw(Cu2QuPen(TransformPen(pen, (scale, 0, 0, scale, 0, 0)), MAX_ERR, reverse_direction=True))
            glyph = pen.glyph()
        except Exception:
            continue
        dst = f"kr{added:05d}"
        glyph.recalcBounds(glyf)
        glyf[dst] = glyph
        adv = getattr(src_set[name], "width", None)
        hmtx[dst] = (round((adv if adv is not None else src_hmtx[name][0]) * scale), max(0, glyph.xMin))
        cmap_sub.cmap[code] = dst
        order.append(dst)
        added += 1

    base.setGlyphOrder(order)
    glyf.glyphOrder = order
    base["maxp"].numGlyphs = len(order)

    # 글리프를 늘린 뒤 원본 device metric 과 어긋나면 fontTools 서브셋이 깨진다 → 제거
    for drop in ("hdmx", "vdmx", "VDMX", "LTSH", "DSIG", "PCLT"):
        if drop in base:
            del base[drop]

    subsetter = subset.Subsetter()
    subsetter.populate(unicodes=sorted(wanted))
    subsetter.subset(base)
    base["maxp"].recalc(base)
    return added


def rename(base: TTFont, family: str, style: str) -> None:
    os2 = base["OS/2"]
    os2.ulUnicodeRange1 |= (1 << 7) | (1 << 10) | (1 << 5)   # Hangul syllables / Jamo / CJK symbols
    os2.ulUnicodeRange2 |= (1 << 2)                          # Hangul Jamo Extended
    os2.usFirstCharIndex = 0x20
    os2.usLastCharIndex = 0xFFE6
    os2.ulCodePageRange1 |= (1 << 0) | (1 << 1) | (1 << 2)   # 1252 Latin1 / Wansung / Johab
    full = f"{family} {style}".strip()
    ps = family.replace(" ", "") + style.replace(" ", "")

    # 원본(Arial) 의 name ID 1~6 기록을 **플랫폼 구분 없이** 다 지운다.
    # Windows(platformID 3) 기록만 덮어쓰면 Mac(platformID 1) 기록의 "Arial" 이 남아
    # WPF(PresentationNative) 가 그 옛 이름을 먼저 주우러 family 등록이 깨진다
    # (实测: 재테깅만 남기면 TryGetGlyphTypeface False,清理 후 True).
    base["name"].names = [n for n in base["name"].names if n.nameID not in (1, 2, 3, 4, 5, 6, 16, 17)]
    records = {
        1: family, 16: family, 2: style, 17: style,
        4: full, 6: ps, 5: f"Version {REVISION:.1f}; {full}",
        3: f"{full} (Hangul)",
    }
    for name_id, value in records.items():
        base["name"].setName(value, name_id, 3, 1, 0x409)      # Windows
        base["name"].setName(value, name_id, 1, 0, 0)          # Mac (platform 1) 도 같은 이름
    base["head"].fontRevision = REVISION
    if "CFF " in base:                                        # CFF skeleton 을 쓸 때 name/table 일치
        base["CFF "].cff.fontName = ps


def main() -> int:
    ap = argparse.ArgumentParser(description="WPF family 이름용 한글 병합 TrueType 생성")
    ap.add_argument("outdir", help="출력 디렉터리 (wine prefix 의 drive_c/windows/Fonts 권장)")
    ap.add_argument("--skeleton-dir", default="/usr/share/fonts/truetype/msttcorefonts",
                    help="원본 TrueType(Arial) 이 있는 디렉터리")
    ap.add_argument("--noto-dir", default="/usr/share/fonts/opentype/noto",
                    help="Noto Sans CJK .ttc 가 있는 디렉터리")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    faces: dict[tuple[str, str], TTFont] = {}
    made = 0
    for out_name, family, style, skeleton, _reg in FAMILIES:
        skeleton_path = os.path.join(args.skeleton_dir, skeleton)
        if not os.path.exists(skeleton_path):
            skeleton_path = os.path.join(args.skeleton_dir, FALLBACK_SKELETON)
        if not os.path.exists(skeleton_path):
            print(f"!! 원본 Arial 없음: {skeleton_path} (winetricks corefonts 선행 필요)", file=sys.stderr)
            return 1
        key = (style, family)
        if key not in faces:
            ttc, src_family, src_style = NOTO[style]
            face = find_face(os.path.join(args.noto_dir, ttc), src_family, src_style)
            if face is None:
                print(f"!! {family} {style}: {ttc} 안에서 {src_family} {src_style} face 를 찾지 못했습니다.", file=sys.stderr)
                return 1
            faces[key] = face
        base = TTFont(skeleton_path)
        added = merge_hangul(base, faces[key])
        if not added:
            print(f"!! {family} {style}: 한글 glyf 병합 0 개", file=sys.stderr)
            return 1
        rename(base, family, style)
        out_path = os.path.join(args.outdir, out_name)
        base.save(out_path)
        made += 1
        print(f"  {out_name:<22} {family} {style:<11} glyphs={base['maxp'].numGlyphs:<6} 병합 {added}")
    print(f"생성 완료 {made} 개 -> {args.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
