"""从模板 + JSON 数据生成实验报告 .docx。

支持任意课程实验报告模板，信息表标签动态读取，章节结构动态匹配。

用法：
    python build_report.py <模板路径> <输出路径> <截图目录> --data <JSON字符串>

JSON 数据格式（DATA_SCHEMA）：
{
  "title": "实验一：实验环境搭建与使用",
  "type": "验证型",
  "objectives": ["目的1", "目的2"],
  "content_items": ["内容1", "内容2"],
  "info_table": {
    "课程名称": "操作系统",
    "学生姓名": "张三",
    "学号": "20240001"
  },
  "steps": [
    {
      "title": "1. 步骤标题",
      "desc": "步骤描述",
      "code": ["命令1", "命令2"],
      "image": "截图文件名.png",
      "caption": "图3.1 描述"
    }
  ],
  "results": ["结果1", "结果2"],
  "summary": "实验总结文字"
}

注意：
  - info_table 的键名必须与模板信息表中的标签文字完全一致
  - 如果模板信息表标签含冒号（如"课程名称："），则 JSON 键名也需含冒号
"""

import argparse
import json
import os
import re
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


# ── 工具函数 ─────────────────────────────────────────────

def set_text(para, text, font_name=None, font_size=None, bold=None, color=None):
    """设置段落文本，保留第一个 run 的格式"""
    for run in para.runs:
        run.text = ''
    if para.runs:
        r = para.runs[0]
        r.text = text
        if font_name:
            r.font.name = font_name
        if font_size:
            r.font.size = font_size
        if bold is not None:
            r.font.bold = bold
        if color:
            r.font.color.rgb = color
    else:
        r = para.add_run(text)
        if font_name:
            r.font.name = font_name
        if font_size:
            r.font.size = font_size
        if bold is not None:
            r.font.bold = bold
        if color:
            r.font.color.rgb = color


def add_paragraph_after(doc, after_para, text,
                       font_name='宋体', font_size=Pt(10.5),
                       bold=False, alignment=None,
                       first_line_indent=None,
                       space_before=None, space_after=None):
    """在指定段落后插入新段落，返回新段落"""
    new_p = doc.add_paragraph()
    after_para._element.addnext(new_p._element)
    run = new_p.add_run(text)
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    run.font.size = font_size
    run.font.bold = bold
    if alignment is not None:
        new_p.alignment = alignment
    pf = new_p.paragraph_format
    if first_line_indent:
        pf.first_line_indent = first_line_indent
    if space_before:
        pf.space_before = space_before
    if space_after:
        pf.space_after = space_after
    return new_p


def add_code_paragraph(doc, after_para, code_text):
    """添加代码段落：灰色底纹 #F2F2F2，Consolas 9pt"""
    new_p = doc.add_paragraph()
    after_para._element.addnext(new_p._element)
    pPr = new_p._element.get_or_add_pPr()
    shd = pPr.makeelement(qn('w:shd'), {
        qn('w:fill'): 'F2F2F2',
        qn('w:val'): 'clear',
    })
    pPr.append(shd)
    run = new_p.add_run(f'  {code_text}')
    run.font.name = 'Consolas'
    run.font.size = Pt(9)
    return new_p


def add_image_paragraph(doc, after_para, image_path, caption, width_inches=5.5):
    """添加 图片 + 图注（图片在上，图注在下，均居中）"""
    # 图片段落
    img_p = doc.add_paragraph()
    after_para._element.addnext(img_p._element)
    img_run = img_p.add_run()
    img_run.add_picture(image_path, width=Inches(width_inches))
    img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 图注段落（图片下方）
    cap_p = doc.add_paragraph()
    img_p._element.addnext(cap_p._element)
    cap_run = cap_p.add_run(caption)
    cap_run.font.name = '宋体'
    cap_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    cap_run.font.size = Pt(9)
    cap_run.font.bold = True
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 空行
    sp_p = doc.add_paragraph()
    cap_p._element.addnext(sp_p._element)
    return sp_p


def get_cell_text(cell):
    """获取表格单元格的纯文本"""
    return cell.text.strip()


# ── 信息表动态填充 ─────────────────────────────────────

def fill_info_table(doc, info_data: dict):
    """
    动态填充信息表。
    info_data: {"标签名": "填写内容", ...}
    逻辑：遍历信息表第一列所有单元格，找到标签名后，
          在对应行的其他列填写内容。
    """
    if not doc.tables:
        print("⚠️  未找到信息表（Table 0），跳过信息表填充。")
        return

    table = doc.tables[0]
    filled = 0

    for row_idx, row in enumerate(table.rows):
        first_cell_text = get_cell_text(row.cells[0])
        # 尝试精确匹配
        if first_cell_text in info_data:
            # 填写到第二列（通常第二列是内容列）
            if len(row.cells) > 1:
                set_text(row.cells[1].paragraphs[0], info_data[first_cell_text])
                filled += 1
        else:
            # 尝试模糊匹配（忽略冒号、空格）
            clean_label = re.sub(r'[：:\s]', '', first_cell_text)
            for key, val in info_data.items():
                clean_key = re.sub(r'[：:\s]', '', key)
                if clean_label == clean_key:
                    if len(row.cells) > 1:
                        set_text(row.cells[1].paragraphs[0], val)
                        filled += 1
                    break

    print(f"信息表填充完成：{filled} 项")


# ── 章节动态匹配 ───────────────────────────────────────

def find_section_indices(paras):
    """
    动态识别模板中所有章节标题的段落索引。
    返回：{"实验目的": idx, "实验内容": idx, "实验步骤": idx, "实验结果": idx, "实验总结": idx}
    """
    indices = {}
    for idx, para in enumerate(paras):
        text = para.text.strip()
        for key in ["实验目的", "实验内容", "实验步骤", "实验结果", "实验总结"]:
            if key in text:
                indices[key] = idx
                break
    return indices


# ── 主流程 ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="生成课程实验报告 .docx")
    parser.add_argument("template_path", help="模板 .docx 文件路径")
    parser.add_argument("output_path", help="输出 .docx 文件路径")
    parser.add_argument("screenshot_dir", help="截图目录（裁剪后的）")
    parser.add_argument("--data", required=True, help="实验内容 JSON 字符串")
    args = parser.parse_args()

    data = json.loads(args.data)
    screenshot_dir = os.path.abspath(args.screenshot_dir)

    doc = Document(args.template_path)
    paras = doc.paragraphs

    # ── 1. 填充信息表（动态） ──
    info = data.get("info_table", {})
    if info:
        fill_info_table(doc, info)
    else:
        print("⚠️  JSON 中无 info_table 数据，跳过信息表填充。")

    # ── 2. 动态识别章节位置 ──
    section_idx = find_section_indices(paras)
    print(f"章节识别结果：{section_idx}")

    # ── 3. 填充"实验目的" ──
    obj_idx = section_idx.get("实验目的")
    if obj_idx is not None:
        for j, obj in enumerate(data.get("objectives", [])):
            target_idx = obj_idx + 1 + j
            if target_idx < len(paras):
                set_text(paras[target_idx], obj,
                         font_name='宋体', font_size=Pt(10.5))
    else:
        print("⚠️  未找到'实验目的'章节，跳过。")

    # ── 4. 填充"实验内容" ──
    content_idx = section_idx.get("实验内容")
    if content_idx is not None:
        for j, item in enumerate(data.get("content_items", [])):
            target_idx = content_idx + 1 + j
            if target_idx < len(paras):
                set_text(paras[target_idx], item,
                         font_name='宋体', font_size=Pt(10.5))
    else:
        print("⚠️  未找到'实验内容'章节，跳过。")

    # ── 5. 填充"实验步骤" ──
    step_idx = section_idx.get("实验步骤")
    if step_idx is not None:
        insert_after = paras[step_idx]
        for step in data.get("steps", []):
            # 小标题
            tp = add_paragraph_after(
                doc, insert_after,
                step.get("title", ""),
                font_name='宋体', font_size=Pt(10.5), bold=True,
                space_before=Pt(12), space_after=Pt(3)
            )
            insert_after = tp

            # 描述
            dp = add_paragraph_after(
                doc, insert_after,
                step.get("desc", ""),
                font_name='宋体', font_size=Pt(10.5),
                first_line_indent=Pt(21), space_after=Pt(3)
            )
            insert_after = dp

            # 代码行
            for code_line in step.get("code", []):
                cp = add_code_paragraph(doc, insert_after, code_line)
                insert_after = cp

            # 截图
            image_filename = step.get("image")
            if image_filename:
                image_path = os.path.join(screenshot_dir, image_filename)
                if os.path.exists(image_path):
                    ip = add_image_paragraph(
                        doc, insert_after,
                        image_path, step.get("caption", "")
                    )
                    insert_after = ip
                else:
                    print(f"⚠️  截图文件不存在：{image_path}")
                    wp = add_paragraph_after(
                        doc, insert_after,
                        f"【截图：{step.get('caption', '')}】",
                        font_name='宋体', font_size=Pt(10.5), bold=True,
                        color=RGBColor(0xFF, 0, 0)
                    )
                    insert_after = wp
    else:
        print("⚠️  未找到'实验步骤'章节，跳过。")

    # ── 6. 填充"实验结果" ──
    result_idx = section_idx.get("实验结果")
    if result_idx is not None:
        insert_after = paras[result_idx]
        for line in data.get("results", []):
            rp = add_paragraph_after(
                doc, insert_after,
                line,
                font_name='宋体', font_size=Pt(10.5),
                first_line_indent=Pt(21), space_after=Pt(3)
            )
            insert_after = rp
    else:
        print("⚠️  未找到'实验结果'章节，跳过。")

    # ── 7. 填充"实验总结" ──
    summary_idx = section_idx.get("实验总结")
    if summary_idx is not None:
        summary_text = data.get("summary", "")
        add_paragraph_after(
            doc, paras[summary_idx],
            summary_text,
            font_name='宋体', font_size=Pt(10.5),
            first_line_indent=Pt(21), space_after=Pt(3)
        )
    else:
        print("⚠️  未找到'实验总结'章节，跳过。")

    # ── 保存 ──
    doc.save(args.output_path)
    size_kb = os.path.getsize(args.output_path) // 1024
    print(f"✅ 报告已生成：{args.output_path}（{size_kb} KB）")


if __name__ == "__main__":
    main()
