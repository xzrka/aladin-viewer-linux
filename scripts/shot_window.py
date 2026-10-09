#!/usr/bin/env python3
"""합성된 데스크톱 화면에서 특정 창 영역만 잘라 PNG 로 저장한다.

XGetImage 를 창 자체에 걸면 컴포지터 환경에서 줄무늬로 깨진다.
루트 창은 합성 결과가 그려진 버퍼이므로 루트에서 좌표계만 정확히 알면 된다.
창의 절대 좌표는 상위 체인을 따라 다니며 합산한다.

usage: shot_window.py <window_id> <out.png>
"""
import sys

from PIL import Image
from Xlib import X, Xutil
from Xlib.display import Display


def absolute(d, win):
    """top-level(자식 없는) 창까지 올라가며 절대 좌표를 만든다."""
    x = y = 0
    cur = win
    while True:
        g = cur.get_geometry()
        x += g.x
        y += g.y
        parent = cur.query_tree().parent
        if parent is None or parent.id == d.screen().root.id:
            return x, y, g.width, g.height
        cur = parent


def main():
    wid, out = int(sys.argv[1]), sys.argv[2]
    d = Display()
    win = d.create_resource_object("window", wid)
    # WPF 창은 'WM_STATE 를 가진 최상위 창'이 화면에 뜬 창이다. 자식(자주 1036x621) 을
    # 넘기면 절대 좌표가 0,0 이 되므로, 같은 트리의 최상위를 찾아 그 크기로 잡는다.
    top = win
    while True:
        parent = top.query_tree().parent
        if parent is None or parent.id == d.screen().root.id:
            break
        top = parent
    x, y, wpx, hpx = absolute(d, top)
    print(f"window {top.id} abs=({x},{y}) {wpx}x{hpx}")
    x = max(0, x)
    y = max(0, y)
    wpx = min(wpx, d.screen().width_in_pixels - x)
    hpx = min(hpx, d.screen().height_in_pixels - y)
    img = d.screen().root.get_image(x, y, wpx, hpx, X.ZPixmap, 0xFFFFFFFF)
    Image.frombytes("RGB", (wpx, hpx), img.data, "raw", "BGR", 0, 0).save(out)
    print(f"saved {out} {wpx}x{hpx}")


if __name__ == "__main__":
    sys.exit(main())
