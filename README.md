# Aladin Viewer on Linux

**알라딘 Ebook PC Viewer 를 Ubuntu / Pop!_OS + Wine 에서 — 한글 □□□ 없이, 도서까지 열리게**

Windows 전용 **알라딘 Ebook PC Viewer**(`AladinEbookViewer.exe`, .NET Framework 4.8 WPF + CEF)를
Linux(Wine) 에 돌리면 세 가지가 깨집니다. 이 저장소는 그 원인을 측정으로 규명하고,
**앱 바이너리를 한 바이트도 수정하지 않고** 전부 고치는 스크립트 모음입니다.

| 위치 | 기본 상태 | 원인 |
|---|---|---|
| 창 제목 · 탭 라벨 | 정상 | Wine 캡션 폰트가 Noto CJK 를 골라서 |
| 툴바 · 로그인 버튼 · 입력장 | **□□□** | WPF 기본 폰트 `"Segoe UI"` 가 Wine 에 없음 |
| ebook 본문 (도서 열기) | **안 열림** | 앱이 요구하는 폰트 이름이 wine 레지스트리에 없음 |

→ 해결 후: 창 제목·툴바·버튼·입력장은 물론 **도서 본문까지** 한글로 나옵니다.

> **Running the Windows-only Aladin EPUB reader on Linux/Wine.**
> Fixes the □ (missing-glyph) UI text and the book-loading failure — two separate font-resolution
> layers (WPF ← fontconfig, app ebook rendering ← wine registry). No patching of `setup.exe`,
> `AladinEbookViewer.exe` or any DLL (verified by SHA-256 against a clean install).

---

## TL;DR

```bash
sudo bash install_wine.sh                                    # 1) WineHQ wine 11 + winetricks
./wine_aladin.sh prefix                                      # 2) 32bit prefix + corefonts + dotnet48 (30~60분)
./wine_aladin.sh fonts                                       # 3) WPF + ebook 폰트 등록 (root 불필요)
SETUP=~/다운로드/AladinEbookViewerSetup_1.9.0.5.exe ./wine_aladin.sh install   # 4) 앱 설치
./wine_aladin.sh run                                         # 5) 실행
```

`./wine_aladin.sh fonts` 가 이 저장소의 핵심입니다. 폰트를 **두 군데에 나눠** 설치합니다.

| 누가 쓰는 이름 | 폰트 이름 | 설치 위치 | 근거 |
|---|---|---|---|
| WPF (툴바·로그인·입력장) | `Segoe UI`, `Arial` … | fontconfig 사용자 디렉터리 | WPF 는 fontconfig 만 봄 |
| 앱 ebook 렌더링 (도서 본문) | `SEOULNAMSAN`, `UnDinaru`, `CREMA_MYUNGJO2B`, `Nanum*`, `Batang` … | wine prefix `C:\windows\Fonts` + 레지스트리 | GDI/CEF 는 `HKLM\…\Fonts` 매핑을 봄 |

**두 이름을 한곳에 섞으면 안 됩니다.** WPF 가 쓰는 이름(`Segoe UI`)을 레지스트리에 등록하면
WPF 가 fontconfig 사본 대신 그 파일을 쓰고 MS 파서가 생성 파일을 거부해 크롬이 다시 □ 가 됩니다
(실측, 아래 측정 9 참조).

---

## 왜 □□□ 가 되나 (측정 결과)

| 확인 항목 | 측정 결과 |
|---|---|
| 앱이 요청하는 폰트 이름 | `Arial`, `Arial Black`, `Arial Italic`, `Arial Bold Italic`, 그리고 XAML 기본값 **`Segoe UI`** |
| Wine 11 기본 .NET 폰트 목록 | 286 family — **`Segoe UI` 없음** |
| `TryGetGlyphTypeface("Segoe UI")` | **False** (물리 face 로 해석 안 됨) |
| 그 경우 WPF 의 동작 | 자기 안에 있는 **last-resort face(라틴 전용)** 로 그림 → 한글만 □ |
| `FontFamily("Arial").FamilyTypeface.TryGetGlyphTypeface()` | True, Baseline = **0.921630859375** (last-resort 와 동일 → 이름만 통하고 face 는 없음) |

Wine 의 `.NET 4.8` 은 **WPF** 를 내장하지 않습니다. `PresentationNative_cor32.dll` 은 MS 의 네이티브 바이너리이고,
이 코드는 폰트를 **fontconfig 가 스캔하는 디렉터리**에서 찾아 family 이름과 연결합니다.
Wine 을 빌드한 리눅스 배포판의 fontconfig 에 `Segoe UI` 파일이 없으면 그 이름은 벽에 부딪힙니다.
WPF 는 폰트가 없으면 **빈 상자를 그리지 않고 조용히 자체 기본 얼굴로 대체**하므로, 오류 없이 □만 남습니다.

### 효과 없었던 것들 (실측)

| 시도 | 결과 |
|---|---|
| fontconfig `<alias>`/`<map>` 으로 Arial → Noto | **0 효과** (WPF 는 `FontFamily` 문자열로 family 를 직접 해석) |
| `.local/share/fonts` 에 `NotoSansCJK.ttf` 리테깅 (name 테이블만 변경) | fontconfig 는 찾지만 **WPF OpenType 파서가 face 로 거부** (`TryGetGlyphTypeface=False`) |
| CFF(Noto) 를 glyf(Arial) 에Cu2Qu 변환으로 이식 | glyf 자체는 유효 (GDI/CEF 에서 한글 렌더 성공) — **WPF 는 여전히 face 거부** |
| wine prefix `drive_c/windows/Fonts` + `HKLM\...\Fonts` 레지스트리 등록 | **도리어 실패** (아래 박스) |
| `FONTCONFIG_FILE` 로 prefix 전용 config | WPF 폰트 목록 **286 그대로** (WPF 는 이 변수를 안 봄) |
|registry `FontLink\SystemLink` / `LinkFont` 주입 | WPF **0 효과** (`FamilyTypeface.GetGlyphs("가")` = 0 글리프) |

> **prefix + 레지스트리 등록이 실패한 이유 (핵심 측정)**
> 같은 폰트 파일을 `~/.local/share/fonts/` 에만 두면 `TryGetGlyphTypeface=True`,
> 같은 파일을 `drive_c/windows/Fonts` 에 복사하고 레지스트리 값까지 주면 **43개 family 전부 False**.
> → WPF 는 레지스트리가 가리키는 파일로 family 를 해석하려 하고, 그 경로에서 MS 파서가 우리 파일을 거부합니다.
> → 그래서 이 스크립트는 **prefix 와 레지스트리에 손대지 않습니다.** 앱 바이너리도 수정하지 않습니다.

### 동작하는 처방

**WPF 가 요청하는 family 이름을 그대로 이름으로 갖는, 한글 glyf 를 심은 TrueType** 를 만들어
**fontconfig 사용자 폰트 디렉터리**(`$XDG_DATA_HOME/fonts/aladin-wine-kr`)에 두면 됩니다.

1. 원본 **Arial TrueType**(em 2048, `winetricks corefonts` 가 깔아준 파일)을 골격으로 쓴다 — 라틴 메트릭과 테이블 구조가 MS 파서에 통과됩니다.
2. **Noto Sans CJK** 의 한글 음절·자모·CJK 구두점 glyf 를 **2.048 배 스케일**로 병합합니다
   (CFF cubic → `Cu2QuPen` 2차 베지어 변환, em 1000 → 2048 환산).
3. `name` 테이블만 요청된 이름으로 바꿉니다 (`Segoe UI`, `Malgun Gothic`, `Gulim`, `Dotum`, `Tahoma`, `Arial`, ... 43개 face).
   `head.fontRevision = 99.0` → 같은 이름을 두고 벌이는 경쟁에서 fontconfig(fontversion 우선) 를 이깁니다.

`TryGetGlyphTypeface` 가 43개 family 전부 **True** 로 바뀌고, 앱의 툴바·로그인 버튼·입력장까지 한글로 렌더됩니다.

---

## 설치

### 0) 준비물

```bash
sudo apt install -y fontconfig python3-fonttools     # 폰트 빌드/캐시 도구
sudo apt install -y fonts-noto-cjk                   # 한글 외곽선 원본 (SIL OFL)
```

`install_wine.sh` 가 winetricks `corefonts` 를 설치하고, 그 원본 Arial 이 폰트 생성의 골격이 됩니다.
(Arial 은 Microsoft EULA 이므로 이 저장소에 포함하지 않습니다 — 사용자 시스템의 사본을 그 자리에서 읽습니다.)

### 1) Wine

```bash
sudo bash install_wine.sh
```

Ubuntu 22.04 / Pop!_OS 22.04 기본 wine 6.0.3 은 .NET Framework 4.8 을 지원하지 않습니다. **WineHQ 저장소**로 9.x 이상을 쓰세요
(여기서 검증한 버전: **wine-11.0**).

### 2) prefix

```bash
./wine_aladin.sh prefix
```

32bit prefix(`~/.wine-aladin`) + `corefonts` + VC++ 런타임 + `dotnet48`.
`dotnet48` 은 winetricks 에서 가장 취약한 단계라 2~3회 재시도가 정상입니다. 스크립트가 `dotnet472` 로 자동 폴백합니다.

### 3) 폰트 (핵심 — 두 층을 모두)

```bash
./wine_aladin.sh fonts
# 1/2  scripts/install_kr_fonts.py      → ~/.local/share/fonts/aladin-wine-kr/   (WPF 용)
# 2/2  scripts/register_prefix_fonts.py → $WINEPREFIX/drive_c/windows/Fonts + 레지스트리 (ebook 용)
```

- 1단계는 root 불필요·시스템 무변경, `--uninstall` 로 완전 원복.
- 2단계는 prefix 안에 쓰며, 덮어쓰기 전 원본은 `<파일이름>.orig-aladin` 으로 백업합니다
  (`register_prefix_fonts.py --uninstall` 이 복원). WPF 가 쓰는 이름은 등록하지 않습니다.
- 마지막에 두 검증을 자동으로 돌립니다:
  - `ProbeKr` → WPF family 의 `TryGetGlyphTypeface` (기대: **미해결 0 개**)
  - 레지스트리 조회 → ebook 폰트 등록 확인 (기대: **32/32**)

### 4) 앱 설치 후 실행

```bash
SETUP=~/다운로드/AladinEbookViewerSetup_1.9.0.5.exe ./wine_aladin.sh install
./wine_aladin.sh run
```

런처가 두 가지를 자동으로 처리합니다 (실측: 둘 다 빠지면 앱이 죽습니다):

- `LANG=C LC_ALL=C` — **UTF-8 로케일에서 앱이 1초 만에 종료**합니다 (`Failed to create secure store file`, CEF 로케일 파싱 실패).
- `NO_IME=1` (`XMODIFIERS=none`) — ibus/fcitx XIM 과 연결된 채로 한글을 조합하면 WPF 메시징이 `AccessViolation` 으로 크래시합니다.

### 5) 용량 정리 (선택)

```bash
./wine_aladin.sh trim     # pdb / TTS 음성 / 미사용 로케일 정리, TTS '읽어주기' 기능은 사라짐
./wine_aladin.sh size
```

---

## 검증

### 프로그램으로 확인

```bash
python3 scripts/install_kr_fonts.py            # 끝에 WPF 해석 검증을 포함
# 스크립트가 Wine 안의 .NET 4.8 csc.exe 로 scripts/ProbeKr.cs 를 컴파일해 family 마다
# TryGetGlyphTypeface 결과를 출력합니다.
```

`ProbeKr.cs` 는 WPF 가 각 family 이름을 **물리 face 로 해석하는지**(`TryGetGlyphTypeface`)를 봅니다.
`False` 가 남아 있으면 그 이름은 여전히 last-resort 얼굴로 그려져 □ 로 남습니다.

### 스크린샷

`scripts/shot_window.py <window_id> <out.png>` 는 합성된 데스크톱 화면에서 창 영역을 잘라 저장합니다.
HiDPI + 멀티모니터(이 측정 환경은 6400x2160 Xinerama)에서는 XGetImage 가 줄무늬로 깨져 나오므로,
실제 화면 육안 확인과 `ProbeKr` 결과를 기준으로 삼으세요.

---

## 문제 해결

| 증상 | 원인 / 해결 |
|---|---|
| 실행 직후 종료, 로그에 `Failed to create secure store file` | UTF-8 로케일. `LANG=C LC_ALL=C` 필수 (`wine_aladin.sh run` 이 처리) |
| 한글을 조합하는 순간 앱 종료, 로그에 `Unhandled exception: AccessViolation in user32.dll.DispatchMessage` | XIM(ibus) 입력. `NO_IME=1` → `XMODIFIERS=none` (기본 활성) |
| 툴바·버튼·입력장만 □, 창 제목·탭은 정상 | WPF 기본 폰트 `Segoe UI` 미해석. `./wine_aladin.sh fonts` 후 **wineserver 재시작** (wineserver 가 꺼지지 않으면 폰트 목록이 갱신되지 않습니다) |
| **도서가 안 열림 / 본문이 하얀 화면** | 앱이 ebook 렌더링에 쓰는 폰트 이름(`SEOULNAMSAN`, `UnDinaru`, `CREMA_MYUNGJO2B`, `Nanum*` …)이 레지스트리에서 빠지면 본문 렌더링이 죽습니다. `./wine_aladin.sh fonts` 의 2단계(`register_prefix_fonts.py`)가 되돌립니다. 실측 기록: docs/MEASUREMENTS.md 9 |
| 폰트를 설치했는데도 □ | ① `fc-cache -f ~/.local/share/fonts/aladin-wine-kr` ② `wineserver -k` ③ `python3 scripts/install_kr_fonts.py --no-probe` 로 검증 재실행 |
| ebook 본문까지 □ | ebook 은 CEF 이 `SEOULNAMSAN`/`UnDinaru`/`CREMA_MYUNGJO2B` 같은 앱 내장 이름을 씁니다. 이 스크립트가 그 이름들도 같은 처방으로 설치합니다 |
| `csc.exe` 가 `fatal error CS2007: Unrecognized option: '/tmp/...'` | csc 는 POSIX 경로를 스위치로 오인합니다. `z:/tmp/...` 형태로 넘기세요 (스크립트가 처리) |
| 폰트 파일이 2.5MB 나 됩니다 | 43 face × 1.2만 글리프. 원치 않으면 `make_kr_fonts.py` 의 `FAMILIES` 를 줄이세요 (적어도 `segoeui.ttf` 1 개면 WPF 크롬은 해결됩니다) |

---

## 이 저장소가 하지 않는 것

- **앱 바이너리 수정 없음** — `setup.exe`, `AladinEbookViewer.exe`, DLL, `.NET` 파생 파일 등 설치된 파일을 전혀 고치지 않습니다.
  (SHA-256 대조실측: 공식 설치 파일로 클린 설치한 265개 파일 중 262개 동일, 차이는 uninstaller DB + CEF GPU 캐시뿐)
- **시스템(루트) 폰트 디렉터리 수정 없음** — `$XDG_DATA_HOME/fonts` 에만 설치하므로 root 가 필요 없고, `--uninstall` 로 완전히 되돌립니다.
- **저작권 폰트 미포함** — Arial(msttcorefonts, MS EULA), 앱 내장 폰트(알라딘/제작사) 는 저장소에 없습니다.
  빌드 스크립트가 사용자 시스템에 이미 있는 사본을 그 자리에서 읽습니다.
- **wine prefix 폰트 디렉터리 / 레지스트리 수정 없음** — 위 측정 결과에 따라 의도적으로 피합니다.

## 라이선스

- 스크립트: MIT (LICENSE 참고)
- 이 저장소는 알라딘의 소프트웨어/폰트/상표를 포함하지 않습니다. `setup.exe` 는 이용자 본인이 받아야 합니다.
- 생성 폰트의 원본: Noto Sans CJK (SIL OFL), Arial (msttcorefonts, Microsoft EULA — 배포 금지, 그 자리에서 읽기만).

## 측정 환경

| 항목 | 값 |
|---|---|
| OS | Pop!_OS 22.04 (jammy), X11, HiDPI 6400x2160 Xinerama |
| Wine | wine-11.0 (WineHQ), 32bit prefix |
| .NET | winetricks `dotnet48` (WPF 4.0.30319, PresentationNative_cor32.dll) |
| 앱 | AladinEbookViewer 1.9.0.5 (설치 파일 397MB, `setup.exe`) |
| 폰트 도구 | fontTools 4.x, fontconfig 2.13.1, fonts-noto-cjk |
