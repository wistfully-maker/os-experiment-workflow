#!/usr/bin/env python3
"""
从实验报告模板 .docx 中提取格式信息，输出为 JSON。

用法：
    python extract_template_format.py <模板.docx> [输出.json]

输出 JSON 结构：
{
  "info_table": {
    "rows": 3,
    "cols": 11,
    "labels": ["课程名称", "实验名称", ...],
    "col_widths": [1500, 3200, ...]
  },
  "sections": [
    {"title": "一、实验目的", "font": "宋体", "size": 14, "color": "365F91", "bold": true},
    ...
  ],
  "body_format": {"font": "宋体", "size": 10.5},
  "page_margins": {"top": 1134, "bottom": 1134, "left": 1134, "right": 1134},
  "image_width": 5.5
}
"""

import sys
import json
import os
from docx import Document
from docx.shared import Pt, Inches
from docx.oxml.ns import qn


def get_run_format(run):
    """提取一个 Run 的格式信息"""
    info = {}
    if run.font.name:
        info["font"] = run.font.name
        # 东亚字体名
        rpr = run._element.rPr
        if rpr is not None:
            ea = rpr.rFonts.get(qn("w:eastAsia"))
            if ea:
                info["font_eastasia"] = ea
    if run.font.size:
        info["size"] = round(run.font.size.pt, 1)
    if run.font.color and run.font.color.rgb:
        info["color"] = str(run.font.color.rgb)
    info["bold"] = run.font.bold if run.font.bold is not None else False
    info["italic"] = run.font.italic if run.font.italic is not None else False
    return info


def extract_info_table(doc):
    """提取信息表结构；若不存在表格，则尝试从段落中提取"姓名、学号、班级"等标签行"""
    # 优先提取表格
    if doc.tables:
        table = doc.tables[0]
        rows = len(table.rows)
        cols = len(table.columns)
        labels = []
        col_widths = []

        for row in table.rows:
            cell = row.cells[0]
            text = cell.text.strip()
            if text:
                labels.append(text)

        for cell in table.rows[0].cells:
            if cell.width and cell.width != 914400:  # 914400 = 1 inch (default)
                col_widths.append(int(cell.width))
            else:
                col_widths.append(None)

        return {
            "rows": rows,
            "cols": cols,
            "labels": labels,
            "col_widths": col_widths,
            "_type": "table",
            "_note": "labels 为信息表第一列所有标签，填充报告时需按这些标签名动态填充"
        }

    # 无表格时，尝试从段落中识别 "姓名：... 学号：... 班级：" 等标签行
    info_labels = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        # 常见信息表标签
        possible_labels = ["姓名", "学号", "班级", "课程名称", "实验名称", "实验日期", "指导老师"]
        matched = []
        for label in possible_labels:
            if label + "：" in text or label + ":" in text:
                matched.append(label)
        if matched:
            return {
                "rows": 1,
                "cols": len(matched) * 2,
                "labels": matched,
                "col_widths": [],
                "_type": "paragraph",
                "_note": "模板中未使用表格，信息表以段落形式出现；labels 为识别出的标签名"
            }

    return None


def extract_section_titles(doc):
    """提取章节标题格式（支持"一、"编号或【标题】括号两种风格）"""
    sections = []
    section_keywords = ["实验目的", "实验内容", "实验步骤", "实验结果", "实验总结"]
    numbered_prefixes = ["一、", "二、", "三、", "四、", "五、", "六、", "七、"]

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        is_section = False
        # 编号风格："一、实验目的"
        if any(text.startswith(prefix) for prefix in numbered_prefixes):
            is_section = True
        # 括号风格："【实验目的】"
        if text.startswith("【") and text.endswith("】"):
            inner = text[1:-1]
            if any(keyword in inner for keyword in section_keywords):
                is_section = True
        # 无编号但有明确章节关键词
        if not is_section:
            for keyword in section_keywords:
                if text.startswith(keyword):
                    is_section = True
                    break

        if is_section and para.runs:
            run = para.runs[0]
            fmt = get_run_format(run)
            alignment = None
            if para.alignment is not None:
                alignment = int(para.alignment)
            fmt["alignment"] = alignment
            sections.append({
                "title": text,
                **fmt
            })
    return sections


def extract_body_format(doc):
    """提取正文段落格式（取第一个非标题、非信息表、非标题页、非空段落）"""
    section_keywords = ["实验目的", "实验内容", "实验步骤", "实验结果", "实验总结"]
    info_labels = ["姓名", "学号", "班级", "课程名称", "实验名称", "实验日期", "指导老师"]

    # 先找到第一个章节标题的位置
    first_section_index = None
    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        if any(text.startswith(prefix) for prefix in ["一、", "二、", "三、", "四、", "五、", "六、", "七、"]):
            first_section_index = idx
            break
        if text.startswith("【") and text.endswith("】"):
            if any(kw in text[1:-1] for kw in section_keywords):
                first_section_index = idx
                break
        if any(text.startswith(kw) for kw in section_keywords):
            first_section_index = idx
            break

    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue

        # 跳过章节标题之前的段落（通常是封面大标题）
        if first_section_index is not None and idx < first_section_index:
            continue

        # 跳过章节标题（编号风格和括号风格）
        if any(text.startswith(prefix) for prefix in ["一、", "二、", "三、", "四、", "五、", "六、", "七、"]):
            continue
        if text.startswith("【") and text.endswith("】"):
            continue
        if any(text.startswith(kw) for kw in section_keywords):
            continue

        # 跳过信息表行（如"姓名：  学号：  班级："）
        is_info_line = False
        for label in info_labels:
            if label + "：" in text or label + ":" in text:
                is_info_line = True
                break
        if is_info_line:
            continue

        if para.runs:
            return get_run_format(para.runs[0])
    return {"font": "宋体", "size": 10.5, "_note": "未能从模板提取，使用默认值"}


def extract_page_margins(doc):
    """提取页边距（单位：DXA）"""
    section = doc.sections[0]
    return {
        "top": int(section.top_margin.emu) if section.top_margin else 1440,
        "bottom": int(section.bottom_margin.emu) if section.bottom_margin else 1440,
        "left": int(section.left_margin.emu) if section.left_margin else 1440,
        "right": int(section.right_margin.emu) if section.right_margin else 1440,
    }


def extract_image_width(doc):
    """提取模板中第一张图片的宽度（英寸）"""
    for para in doc.paragraphs:
        for run in para.runs:
            if run._element.findall(".//" + qn("w:drawing")):
                # 简化处理：返回默认值
                pass
    return 5.5  # 默认值


def main():
    if len(sys.argv) < 2:
        print("用法：python extract_template_format.py <模板.docx> [输出.json]")
        sys.exit(1)
    
    template_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(template_path):
        print(f"错误：文件不存在 —— {template_path}")
        sys.exit(1)
    
    doc = Document(template_path)
    
    result = {
        "info_table": extract_info_table(doc),
        "sections": extract_section_titles(doc),
        "body_format": extract_body_format(doc),
        "page_margins": extract_page_margins(doc),
        "image_width": extract_image_width(doc),
        "_instructions": {
            "info_table_labels": "JSON 中的 info_table.labels 列出了信息表所有标签，生成报告时需动态填充这些标签对应的内容",
            "sections": "sections 列出了所有章节标题及其格式，生成报告时需按此格式设置章节标题",
            "missing_items": "如果某项值为 null 或包含 _note 字段，说明未能从模板自动提取，需要询问用户"
        }
    }
    
    json_output = json.dumps(result, ensure_ascii=False, indent=2)
    
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"格式信息已提取并保存至：{output_path}")
    else:
        print(json_output)

    # 打印需用户确认的项（使用ASCII符号，避免终端编码问题）
    print("\n=== 需用户确认的项 ===")
    if result["info_table"] is None:
        print("[!] 未找到信息表，请确认模板是否包含信息表。")
    else:
        labels = result["info_table"]["labels"]
        print(f"信息表标签（共 {len(labels)} 个）：{labels}")
        print("  请确认每个标签对应的填写内容（如：课程名称 -> 操作系统）：")

    if not result["sections"]:
        print("[!] 未能自动识别章节标题，请手动确认章节结构。")
    else:
        print(f"识别到 {len(result['sections'])} 个章节：")
        for sec in result["sections"]:
            print(f"  - {sec['title']}")


if __name__ == "__main__":
    main()
