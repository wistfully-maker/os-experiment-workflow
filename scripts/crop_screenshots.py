"""裁剪截图：去除标题栏与桌面空白，只保留终端内容区域。

用法：
    python crop_screenshots.py <输入目录> <输出目录> [选项]

三种裁剪策略（优先级：--rect > --crops > 自动检测）：

  1. 统一尺寸（任务书要求"尺寸统一"时）：
       --rect "l,t,r,b"          所有图用同一个矩形
  2. 统一宽度 + 紧贴内容（**推荐用于实验报告**）：
       --skip-top 37 --margin 8 --uniform-width
     · 宽度取所有图的公共外接 → 各图缩放到同一显示宽度时"文字大小一致"
     · 高度各自紧贴内容 → 不留空白
  3. 完全紧贴（非报告用途，如文档插图）：
       --skip-top 37 --margin 8

窗口截图（gnome-screenshot -w）顶部有 GNOME 标题栏，需用 --skip-top 37 跳过，
否则标题栏会被当成内容。

注意：
    - 裁剪使用 PIL 坐标系 (left, top, right, bottom)
    - **PIL 的 Image.crop() 越界会补黑边，不会自动裁剪**，
      裁剪矩形的宽度必须精确等于图片宽度，否则右侧会出现黑带
    - 自动检测基于"背景色众数 + 内容外接矩形"，深色/浅色终端都适用
"""

import argparse
import json
import os
from PIL import Image


def auto_crop(img_path, margin=8, skip_top=0):
    """自动检测裁剪边界：以背景色为基准，求内容的最小外接矩形（紧贴内容）。

    不假设"深色文字 + 浅色背景"（早期实现写死 sum(pixel) < 300，
    在深色终端下会把整片背景误判为文字，结果完全不可用）。

    做法：把像素颜色量化后取出现最多的颜色作为背景色，
    再求所有"与背景色差异超过阈值"的像素的外接矩形。

    参数:
        margin   —— 内容外扩的边距（px）。默认 8，做"紧贴内容"用；
                    留白版可给 30。
        skip_top —— 忽略顶部 N 像素再分析。窗口截图时用来跳过
                    GNOME 标题栏（实测固定 37px），否则标题栏会被当成内容。
    """
    img = Image.open(img_path).convert('RGB')
    w, h = img.size
    px = img.load()

    y0 = max(0, int(skip_top))

    # 1) 量化统计，找背景色（出现次数最多）
    buckets = {}
    for y in range(y0, h, 4):
        for x in range(0, w, 4):
            r, g, b = px[x, y]
            key = (r // 16, g // 16, b // 16)
            buckets[key] = buckets.get(key, 0) + 1
    if not buckets:
        return {"left": 0, "top": 0, "right": w, "bottom": h,
                "width": w, "height": h, "bg": None}
    bg_key = max(buckets, key=buckets.get)
    bg = tuple(v * 16 + 8 for v in bg_key)

    # 2) 求内容外接矩形
    def is_content(p):
        return abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 90

    min_x, max_x, min_y, max_y = w, 0, h, y0
    for y in range(y0, h, 2):
        for x in range(0, w, 2):
            if is_content(px[x, y]):
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y

    if max_x <= min_x or max_y <= min_y:
        return {"left": 0, "top": y0, "right": w, "bottom": h,
                "width": w, "height": h - y0, "bg": bg}

    left = max(0, min_x - margin)
    top = max(y0, min_y - margin)
    right = min(w, max_x + margin + 1)
    bottom = min(h, max_y + margin + 1)

    return {
        "left": left, "top": top,
        "right": right, "bottom": bottom,
        "width": right - left, "height": bottom - top,
        "bg": bg,
    }


def main():
    parser = argparse.ArgumentParser(
        description="裁剪截图：去除标题栏与桌面空白，只保留终端内容区域")
    parser.add_argument("input_dir", help="原始截图目录")
    parser.add_argument("output_dir", help="裁剪后输出目录")
    parser.add_argument("--crops", help='JSON裁剪参数，如 \'{"1":[5,90,650,550]}\'')
    parser.add_argument("--rect", help='统一裁剪矩形 "l,t,r,b"，对所有图片生效，'
                                       '用于保证"截图尺寸大小统一"（优先级最高）')
    parser.add_argument("--skip-top", type=int, default=0,
                        help='自动裁剪时忽略顶部 N 像素（窗口截图用 37 跳过 GNOME 标题栏）')
    parser.add_argument("--margin", type=int, default=8,
                        help='自动裁剪时内容外扩边距(px)，紧贴内容用 8，留白版可用 30')
    parser.add_argument("--uniform-width", action="store_true",
                        help='统一宽度模式：所有图取同一个左右边界（=各图内容的公共外接），'
                             '高度各自紧贴内容。推荐用于实验报告——'
                             '宽度一致才能保证各图缩放到同一宽度时“文字大小一致”，'
                             '高度紧贴则不留空白')
    parser.add_argument("--prefix", default="exp", help="截图文件名前缀")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 解析裁剪参数
    crop_params = {}
    if args.crops:
        crop_params = json.loads(args.crops)

    fixed_rect = None
    if args.rect:
        fixed_rect = tuple(int(v) for v in args.rect.split(','))
        print(f"使用统一裁剪矩形: {fixed_rect}")

    # 扫描输入目录中的截图文件
    png_files = sorted([f for f in os.listdir(args.input_dir) if f.endswith('.png')])

    # ── 统一宽度模式：先跑一遍求出所有图的公共左右边界 ──
    common_lr = None
    if args.uniform_width and fixed_rect is None:
        ls, rs = [], []
        for fname in png_files:
            info = auto_crop(os.path.join(args.input_dir, fname),
                             margin=args.margin, skip_top=args.skip_top)
            ls.append(info["left"])
            rs.append(info["right"])
        common_lr = (min(ls), max(rs))
        print(f"统一宽度模式：公共左右边界 = {common_lr}（宽 {common_lr[1]-common_lr[0]}px）")

    for fname in png_files:
        img_path = os.path.join(args.input_dir, fname)

        # 尝试从文件名提取序号
        import re
        match = re.search(r'(\d+)', fname)
        idx = match.group(1) if match else fname

        # 获取裁剪参数
        if fixed_rect is not None:
            l, t, r, b = fixed_rect
        elif str(int(idx)) in crop_params:
            l, t, r, b = crop_params[str(int(idx))]
        elif idx in crop_params:
            l, t, r, b = crop_params[idx]
        else:
            info = auto_crop(img_path, margin=args.margin, skip_top=args.skip_top)
            l, t, r, b = info["left"], info["top"], info["right"], info["bottom"]
            if common_lr is not None:
                # 宽度取公共边界，高度保留本图的内容高度
                l, r = common_lr
            print(f"  {fname}: 自动检测(背景色{info.get('bg')}) -> ({l},{t},{r},{b}) "
                  f"{r-l}x{b-t}")

        img = Image.open(img_path)
        cropped = img.crop((l, t, r, b))
        out_path = os.path.join(args.output_dir, fname)
        cropped.save(out_path, 'PNG')

        orig_sz = os.path.getsize(img_path)
        new_sz = os.path.getsize(out_path)
        pct = (1 - new_sz / orig_sz) * 100
        print(f"  {fname}: {img.size} -> {cropped.size}, {orig_sz//1024}KB -> {new_sz//1024}KB (节省{pct:.0f}%)")

    print(f"\n全部完成，输出目录: {args.output_dir}")


if __name__ == "__main__":
    main()
