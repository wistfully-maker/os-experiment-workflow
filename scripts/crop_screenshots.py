"""裁剪 VM 全屏截图，去除桌面空白和标题栏，只保留终端内容区域。

用法：
    python crop_screenshots.py <输入目录> <输出目录> [--crops CROPS_JSON]

    --crops: JSON 字符串，指定每张图的裁剪参数。
             格式: {"1": [left, top, right, bottom], ...}
             如果不指定，使用自动检测（基于暗像素密度分析）。

示例：
    python crop_screenshots.py ./screenshots ./screenshots/cropped \
        --crops '{"1": [5,90,650,550], "2": [5,90,650,700]}'

注意：
    - 裁剪使用 PIL 坐标系 (left, top, right, bottom)
    - left=5 去左边框, top=90 跳过菜单栏, right≈650 只到代码内容区域
    - 全屏截图通常为 2329×1360px（CentOS 7 GNOME 桌面分辨率不同可调）
"""

import argparse
import json
import os
from PIL import Image


def auto_crop(img_path, margin=30):
    """自动检测裁剪边界：找暗像素(文字)的最小外接矩形"""
    img = Image.open(img_path)
    w, h = img.size

    # 跳过标题栏区域（前 90 行）
    head_skip = 90

    # 水平方向文字边界
    min_x, max_x = w, 0
    for x in range(0, w, 5):
        dark = sum(
            1 for y in range(head_skip, min(700, h), 5)
            if sum(img.getpixel((x, y))) < 300
        )
        if dark > 0:
            min_x = min(min_x, x)
            max_x = max(max_x, x)

    # 垂直方向文字最后一行
    last_y = head_skip
    for y in range(min(700, h - 1), head_skip, -5):
        dark = sum(
            1 for x in range(min_x, max_x, 5)
            if sum(img.getpixel((x, y))) < 300
        )
        if dark > 2:
            last_y = y
            break

    left = max(0, min_x - margin)
    top = head_skip
    right = min(w, max_x + 50)
    bottom = min(h, last_y + margin)

    return {
        "left": left, "top": top,
        "right": right, "bottom": bottom,
        "width": right - left, "height": bottom - top,
    }


def main():
    parser = argparse.ArgumentParser(description="裁剪 VM 全屏截图")
    parser.add_argument("input_dir", help="原始截图目录")
    parser.add_argument("output_dir", help="裁剪后输出目录")
    parser.add_argument("--crops", help='JSON裁剪参数，如 \'{"1":[5,90,650,550]}\'')
    parser.add_argument("--prefix", default="exp", help="截图文件名前缀")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 解析裁剪参数
    crop_params = {}
    if args.crops:
        crop_params = json.loads(args.crops)

    # 扫描输入目录中的截图文件
    png_files = sorted([f for f in os.listdir(args.input_dir) if f.endswith('.png')])

    for fname in png_files:
        img_path = os.path.join(args.input_dir, fname)

        # 尝试从文件名提取序号
        import re
        match = re.search(r'(\d+)', fname)
        idx = match.group(1) if match else fname

        # 获取裁剪参数
        if str(int(idx)) in crop_params:
            l, t, r, b = crop_params[str(int(idx))]
        elif idx in crop_params:
            l, t, r, b = crop_params[idx]
        else:
            info = auto_crop(img_path)
            l, t, r, b = info["left"], info["top"], info["right"], info["bottom"]
            print(f"  {fname}: 自动检测 -> ({l},{t},{r},{b}) {info['width']}x{info['height']}")

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
