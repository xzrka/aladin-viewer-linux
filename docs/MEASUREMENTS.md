# 측정 기록 — WPF 크롬 한글 □□□

Wine 11.0 + winetricks dotnet48 + AladinEbookViewer 1.9.0.5 에서 직접 관측한 결과만 적었습니다.
모든 판정 기준은 WPF 의 `Typeface.TryGetGlyphTypeface()` — 이 값이 False 면 그 family 는
WPF 안의 last-resort face(라틴 전용) 로 그려져 한글이 □ 가 됩니다.

재현에 쓰는 툴:

```bash
W='C:/windows/Microsoft.NET/Framework/v4.0.30319/WPF'
CSC='C:/windows/Microsoft.NET/Framework/v4.0.30319/csc.exe'
WINEPREFIX=~/.wine-aladin LC_ALL=C LANG=C wine "$CSC" -nologo -target:exe -out:z:/tmp/ProbeKr.exe \
  -r:"$W/PresentationCore.dll" -r:"$W/PresentationFramework.dll" -r:"$W/WindowsBase.dll" \
  -r:'C:/windows/Microsoft.NET/Framework/v4.0.30319/System.Xaml.dll' z:/tmp/ProbeKr.cs
WINEPREFIX=~/.wine-aladin LC_ALL=C LANG=C wine /tmp/ProbeKr.exe
```

`z:` 접두사가 필요합니다. `csc.exe` 는 `/tmp/x.cs` 같은 POSIX 경로를 스위치로 오인해
`fatal error CS2007: Unrecognized option` 을 냅니다.

---

## 1. 초기 상태

```
SystemFonts.CaptionFontFamily: Source=Noto Sans CJK KR  Baseline=1.16  TryGetGlyphTypeface=True
SystemFontFamilies count=286
request 'Segoe UI':  Source=Segoe UI  Baseline=0.921630859375  TryGetGlyphTypeface=False
request 'Arial':     Source=Arial     Baseline=0.921630859375  TryGetGlyphTypeface=True
```

- Wine 의 .NET 이 보는 family 는 286개, `Segoe UI` 는 목록에 없다.
- `Baseline=0.921630859375` 는 last-resort face 의 값이다. `Arial` 은 True 이지만 Baseline 이
  last-resort 와 똑같다 → 이름은 통하고 face 는 없다.
- 앱 바이너리 문자열에서 폰트 이름: `Arial`, `Arial Bold`, `Arial Italic`, `Arial Bold Italic`, `CREMA_MYUNGJO2B`, `SEOULNAMSAN`, `UnDinaru`, `NanumGothic` … (XAML 기본값 `Segoe UI` 는 XAML 쪽에서 온다)

## 2. fontconfig 로 이름을 붙여주면 되는가 → 안 된다

| 시도 | 결과 |
|---|---|
| `<alias><family>Arial</family><accept><family>Noto Sans CJK KR</family></accept></alias>` | WPF 286 그대로, 한글 □ |
| `<match target="pattern"><test name="family">Arial</test><edit name="family">Noto Sans CJK KR</edit></match>` | WPF 목록 286 그대로, 한글 □ |
| `$XDG_DATA_HOME/fonts/retagged-Noto.ttf` (name ID1/16 = "Segoe UI") | `fc-match "Segoe UI"` 는 그 파일을 골라준다. WPF 는 `TryGetGlyphTypeface=False` |
| registry `FontLink\SystemLink`, `LinkFont` 주입 + `wineserver -k` | WPF 0 효과. `FamilyTypeface.GetGlyphs('가')` = 0 글리프 |

→ WPF 는 family 문자열로 자기 파서를 통과하는 **물리 파일**을 찾는다. fontconfig 의 이름 치환/정규화는 이 층을 지나간다.

## 3. 재테깅 파일이 거부되는 이유

`NotoSansCJK-Regular.ttc` 의 name 테이블만 고친 파일(리테깅) 은 WPF 가 face 로 거부한다.
 같은 glyf 데이터를 **원본 Arial TrueType 구조에 심은** 파일은 통과한다.
즉 원인은 name 이 아니라 **파일 구조(파싱)** 다. WPF 의 OpenType 파서는 CFF/CFF2 와
리테깅된 name/OS2 조합에서 face 를 만들지 않는다.

## 4. CFF 외곽선을 TrueType 로 이식하면 통과한다

Noto CFF cubic 외곽선을 `Cu2QuPen`(allow_reverse_direction, max_err=1.0/em2048) 으로 2차 베지어로 변환해
Arial(TrueType, em 2048) glyf 에 2.048 배 스케일로 심고, name ID1/16 을 `Arial` 로 바꾸면:

```
request 'Arial': ... TryGetGlyphTypeface=True
FamilyTypeface.GetGlyphs('가') → 11172+ 글리프, hhea ascender/descender = 1854/-431
```

`FontFamily("Arial")` 으로 `로그인 비밀번호 전체보기 123 ABC` 이 라인과 같은 높이로 렌더되는 것을
픽셀 계측으로 확인(한글 글리프 높이 = 라틴 x-height/ascender 스케일과 일치).

이식할 때 지킬 것:

- 원본 Arial TrueType 를 **그대로 골격**으로 쓴다 (테이블 구조·메트릭 유지). 글리프를 늘린 뒤
  `hdmx/vdmx/LTSH/DSIG` 같은 device-metric 테이블은 원본과 어긋나므로 서브셋 전에 떨어낸다.
- `head.fontRevision = 99.0` → fontconfig 는 같은 family 에서 fontversion 순으로 고른다.
- name ID 1/2/4/6/16/17 만 아니라 **ID 3(unique), 5(version) 도 함께** 맞춘다.

## 5. wine prefix 에 설치하면 도리어 실패한다 (중요)

`make_kr_fonts.py` 로 43 face 를 만들어 두 곳에 같은 파일로 설치하고 비교:

| 설치 위치 | `SystemFontFamilies` | `Segoe UI` |
|---|---|---|
| `~/.local/share/fonts/aladin-wine-kr/` 뿐 | 299 (286 + 13) | **True** |
| 위 + `drive_c/windows/Fonts` 복사 + `HKLM\Software\Microsoft\Windows\CurrentVersion\Fonts` reg add | 286 | **False** (43개 전부 False) |
| 레지스트리 값 삭제 + prefix 파일 원복 (`*.orig-aladin` → 원 이름) | 299 | **True** |

파일은 바이트 단위로 비교해 glyf/loca/cmap/hmtx/maxp/hhea/post/name/OS2 가 같은 상태였다
(차이는 name 테이블 문구, head.checkSumAdjustment, OS/2 codepage bit 뿐).
`name` ID 1~6/16/17 재작성, Mac(platformID 1) 레코드 추가, codepage bit, fontRevision 99,
name ID 3 에 표기 문자열을 넣는 경우까지 각각 분리 실험(`ZZOne`~`ZZSeven`) — 전부 True.
→ 원인은 파일이 아니라 **등록 경로** 다. 레지스트리가 그 family 를 prefix 파일로 묶는 순간
MS 파서가 그 파일 face 를 거부한다. fontconfig 가 발견한 같은 바이트의 사본은 통과한다.

**결론: WPF 용 폰트는 fontconfig 사용자 디렉터리에만 둔다. prefix 와 레지스트리는 건드리지 않는다.**

## 6. FONTCONFIG_FILE 은 WPF 에게 통하지 않는다

`FONTCONFIG_FILE=$WINEPREFIX/aladin-fonts.conf` (시스템 config include + prefix 폰트 디렉터리 `<dir>`)
를 주고 실행 → `SystemFontFamilies count=286` 그대로, `Segoe UI` False.
Wine 의 GDI/CEF 텍스트 경로에는 영향이 있으나 WPF 의 폰트 열거는 이 변수를 보지 않는다.

## 7. 실행 자체가 죽는 두 가지 (폰트와 무관)

| 조건 | 결과 |
|---|---|
| `LANG=en_US.UTF-8` | 1초 내 종료. `Failed to create secure store file. Exiting.` + CEF `locale/ko.pak` 파싱 실패 (`Invalid argument`), wine `err:ntdll:Rtlntrapsignature` |
| ibus XIM 연결 상태에서 한글 조합 | `AccessViolationException at user32.dll.DispatchMessage` (WPF 메시징 크래시) |

→ `LANG=C LC_ALL=C`, `XMODIFIERS=none`(=`NO_IME=1`). 앱 ID/비밀번호는 영문·숫자라 실사용 지장 없음.

## 8. 스크린샷 계측

XGetImage 는 이 HiDPI + Xinerama(6400x2160) 환경에서 창에 걸면 줄무늬로 나온다.
루트 창에서 절대좌표로 잘라내는 방식(`scripts/shot_window.py`)을 넣어두었지만 계측의 최종 판정 기준은
`ProbeKr` 의 `TryGetGlyphTypeface` 과 육안 확인을 쓴다.

---

## 9. 앱은 자기 폰트 이름을 wine 레지스트리에 요구한다 (도서 로딩)

WPF 와는 **다른 층**이다. 앱은 ebook 본문(CEF/GDI) 을 그리며 자기 폰트 이름을 하드코딩으로
요청하고, Wine 의 GDI 는 `HKLM\Software\Microsoft\Windows\CurrentVersion\Fonts` 의
"가족 이름 (TrueType)" → 파일 매핑으로 그 이름을 푼다.

| 단계 | 측정 |
|---|---|
| 조사·실험 중 `reg delete` 로 앱 폰트 매핑 41개 삭제 | **도서가 열리지 않음** (사용자 보고) |
| `fonts_ttf.reg` 의 36개 매핑을 `reg add` 로 복원 | 등록 확인 32/32 (나머지는 Segoe UI* — 의도적 미등록), 앱 정상 기동 |
| `HKLM\…\Fonts` 에 `Segoe UI (TrueType)` = `segoeui.ttf` 를 **살려둔 채** ProbeKr 실행 | `TryGetGlyphTypeface('Segoe UI') = False` (6개 family 미해결) |
| `Segoe UI*` 매핑만 삭제하고 폰트 파일은 원복 → ProbeKr | **미해결 0 개** |
| 레지스트리가 가리키는 `segoeui*.ttf` 4개를 한글 병합 face 로 교체 → ProbeKr | 여전히 False → 생성 폰트는 레지스트리 경로에서 MS 파서를 통과하지 못한다 |

**결론 (이 저장소의 최종 설계)**
- WPF 가 쓰는 이름(`Segoe UI`, `Arial` …)은 **fontconfig 만** 쓰게 하고 레지스트리에 등록하지 않는다.
- 앱 ebook 이 쓰는 이름(`SEOULNAMSAN`, `UnDinaru`, `CREMA_MYUNGJO2B`, `Nanum*`, `Batang` …)만
  prefix `C:\windows\Fonts` + 레지스트리에 등록한다 (원본은 `.orig-aladin` 백업).
- 두 이름을 같은 이름 공간에서 겹치게 하면 둘 중 하나가 죽는다. `register_prefix_fonts.py` 의
  `WPF_NAMES` 가 그 중복을 자동 제외한다.

## 10. 앱 바이너리 무변경 확인 (repro)

```bash
# 클린 설치본과 설치된 앱의 SHA-256 대조
cp setup.exe ~/tmp/setup.exe           # wine 은 한글 경로를 C 로케일에서 못 연다 → ASCII 경로
WINEPREFIX=~/tmp/verifyprefix WINEARCH=win32 wineboot -u
WINEPREFIX=~/tmp/verifyprefix wine ~/tmp/setup.exe /VERYSILENT /NORESTART /SUPPRESSMSGBOXES /DIR='c:\aladin_orig'
# 설치 트리 265개 파일 해시 비교 → 262 동일, 차이 3 = unins000.dat(설치경로 문자열), GPUCache/index, GPUCache/data_1
```

`.exe` / `.dll` / `.config` 은 전부 동일. `AladinEbookViewer.exe` = `b6747a706d1d49a5…` (원본과 동일)
