#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把终端窗口截图裁成「纯控制台内容」：
  1) 先按固定偏移去掉窗口边框 + 标题栏 + 标签栏（几何由 winterm.py resize 固定，所以偏移稳定）
  2) 再在控制台区域内按背景色裁掉右侧/下方的空白
用法:
  python crop_console.py in.png out.png [--top 62] [--side 12] [--margin 12] [--keep-bottom 10]
"""
import argparse
from collections import Counter

from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--top", type=int, default=62, help="控制台内容区上边界（去掉标题栏/标签栏）")
    ap.add_argument("--side", type=int, default=12, help="左右窗口边框宽度")
    ap.add_argument("--bottom-inset", type=int, default=12, help="底部窗口边框宽度")
    ap.add_argument("--margin", type=int, default=12, help="内容四周留白")
    ap.add_argument("--keep-bottom", type=int, default=10, help="底部额外保留几像素")
    ap.add_argument("--tol", type=int, default=10)
    a = ap.parse_args()

    im = Image.open(a.src).convert("RGB")
    W, H = im.size
    px = im.load()

    # 控制台内容区（去掉窗口装饰）
    cx0 = a.side
    cy0 = a.top
    cx1 = W - a.side
    cy1 = H - a.bottom_inset
    if cx1 <= cx0 or cy1 <= cy0:
        print("ERROR: 控制台区域为空，参数不对")
        return

    # 用区域内出现最多的颜色当背景色
    cnt = Counter()
    for y in range(cy0, cy1, 3):
        for x in range(cx0, cx1, 3):
            cnt[px[x, y]] += 1
    bg = cnt.most_common(1)[0][0]
    tol = a.tol

    def is_bg(c):
        return abs(c[0]-bg[0]) <= tol and abs(c[1]-bg[1]) <= tol and abs(c[2]-bg[2]) <= tol

    left, right, top, bottom = cx1, cx0, cy1, cy0
    for y in range(cy0, cy1):
        row_has = False
        for x in range(cx0, cx1, 2):
            if not is_bg(px[x, y]):
                row_has = True
                if x < left:
                    left = x
                if x > right:
                    right = x
        if row_has:
            if y < top:
                top = y
            bottom = y

    if left > right or top > bottom:
        print("WARN: 区域内没有检测到内容，只做去窗口装饰处理")
        out = im.crop((cx0, cy0, cx1, cy1))
        out.save(a.dst)
        print(f"   => {out.size[0]}x{out.size[1]}")
        return

    l = max(cx0, left - a.margin)
    r = min(cx1, right + a.margin)
    t = max(cy0, top - a.margin)
    b = min(cy1, bottom + a.margin + a.keep_bottom)

    out = im.crop((l, t, r, b))
    out.save(a.dst)
    print(f"crop -> {a.dst}")
    print(f"   原图 {W}x{H}  控制台区 ({cx0},{cy0})-({cx1},{cy1})  bg={bg}")
    print(f"   内容盒 ({l},{t})-({r},{b})  => {out.size[0]}x{out.size[1]}")


if __name__ == "__main__":
    main()
