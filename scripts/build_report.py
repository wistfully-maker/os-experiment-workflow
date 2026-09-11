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


def remove_red_paragraphs(doc):
    """
    删除模板中用于"格式说明"的红色字体段落。

    绝大多数课程模板会在正文里放红色占位说明文字，并明确要求"正式提交时删除"。
    判定规则：段落内所有非空 Run 的颜色均为 FF0000。
    """
    removed = 0
    for para in list(doc.paragraphs):
        runs = [r for r in para.runs if r.text.strip()]
        if not runs:
            continue
        red_only = True
        for r in runs:
            rgb = None
            try:
                color = r.font.color
                if color is not None:
                    rgb = color.rgb
            except Exception:
                rgb = None
            if rgb is None or str(rgb) != 'FF0000':
                red_only = False
                break
        if red_only:
            para._element.getparent().remove(para._element)
            removed += 1
    if removed:
        print(f"已删除 {removed} 个红色说明段落")
    return removed


# ── 信息表动态填充 ─────────────────────────────────────

def fill_info_table(doc, info_data: dict):
    """
    动态填充信息表，支持两种模板形式：
    1. 表格形式：遍历表格第一列标签，在对应行第二列填写内容
    2. 段落形式：在文档开头查找形如"姓名：___  学号：___  班级：___"的行并替换
    """
    if not info_data:
        print("[!] JSON 中无 info_table 数据，跳过信息表填充。")
        return

    # 1. 表格形式
    if doc.tables:
        table = doc.tables[0]
        filled = 0
        for row in table.rows:
            cells = row.cells
            # 按"标签格, 内容格"成对扫描，兼容一行内多组键值
            # （如：学院 | __ | 专业班级 | __ | 姓名 | __）
            for k in range(0, max(len(cells) - 1, 0), 2):
                label_cell_text = get_cell_text(cells[k])
                if not label_cell_text:
                    continue
                val_cell = cells[k + 1]
                if val_cell is None:
                    continue
                matched = None
                if label_cell_text in info_data:
                    matched = info_data[label_cell_text]
                else:
                    clean_label = re.sub(r'[：:\s]', '', label_cell_text)
                    for key, val in info_data.items():
                        if re.sub(r'[：:\s]', '', key) == clean_label:
                            matched = val
                            break
                if matched is not None:
                    set_text(val_cell.paragraphs[0], matched)
                    filled += 1
        if filled > 0:
            print(f"信息表填充完成：{filled} 项")
            return

    # 2. 段落形式：寻找包含多个标签的段落
    info_labels = list(info_data.keys())
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        # 如果段落包含至少两个标签，视为信息表行
        matched_labels = [label for label in info_labels if label + "：" in text or label + ":" in text]
        if len(matched_labels) >= 2:
            new_text = text
            for label in matched_labels:
                val = info_data[label]
                # 替换 "标签：" 后的空白为实际值（使用 \g<1> 避免 val 以数字开头时被解析为分组号）
                new_text = re.sub(
                    rf'({re.escape(label)}[：:])\s*',
                    rf'\g<1>{val}    ',
                    new_text
                )
            # 保留第一个 run 的格式属性（如蓝色 #4472C4）
            if para.runs:
                first_run = para.runs[0]
                orig_font_name = first_run.font.name
                orig_size = first_run.font.size
                orig_color = first_run.font.color.rgb if first_run.font.color and first_run.font.color.rgb else None
                orig_bold = first_run.font.bold
                for run in para.runs:
                    run.text = ''
                if para.runs:
                    r = para.runs[0]
                    r.text = new_text
                else:
                    r = para.add_run(new_text)
                if orig_font_name:
                    r.font.name = orig_font_name
                if orig_size:
                    r.font.size = orig_size
                if orig_color:
                    r.font.color.rgb = orig_color
                if orig_bold is not None:
                    r.font.bold = orig_bold
            else:
                para.text = new_text
            print(f"信息表（段落形式）填充完成：{len(matched_labels)} 项")
            return

    print("[!] 未找到信息表（表格或段落形式），跳过信息表填充。")


# ── 章节动态匹配 ───────────────────────────────────────

def find_section_indices(paras):
    """
    动态识别模板中所有章节标题的段落索引。
    仅匹配本身就是章节标题的段落（短文本或含【】）。
    返回：{"实验目的": idx, "实验内容": idx, "实验步骤": idx, "实验结果": idx, "实验总结": idx}
    """
    indices = {}
    for idx, para in enumerate(paras):
        text = para.text.strip()
        if not text:
            continue
        for key in ["实验目的", "实验内容", "实验步骤", "实验结果", "实验总结"]:
            if key in text:
                # 检查是否是真正的章节标题：文本较短或包含【】
                if len(text) <= 15 or ('【' in text and '】' in text):
                    indices[key] = idx
                    break
                if text == key or text == f'【{key}】' or text.startswith(f'【{key}】'):
                    indices[key] = idx
                    break
    return indices


# ── 主流程 ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="生成课程实验报告 .docx")
    parser.add_argument("template_path", help="模板 .docx 文件路径")
    parser.add_argument("output_path", help="输出 .docx 文件路径")
    parser.add_argument("screenshot_dir", help="截图目录（裁剪后的）")
    parser.add_argument("--data", help="实验内容 JSON 字符串")
    parser.add_argument("--data-file", dest="data_file",
                        help="实验内容 JSON 文件路径（内容较长时用这个，避免命令行长度限制）")
    args = parser.parse_args()

    if args.data_file:
        with open(args.data_file, encoding="utf-8") as f:
            data = json.load(f)
    elif args.data:
        data = json.loads(args.data)
    else:
        parser.error("必须提供 --data 或 --data-file 之一")
    screenshot_dir = os.path.abspath(args.screenshot_dir)

    doc = Document(args.template_path)

    # ── 1. 填充信息表（动态） ──
    info = data.get("info_table", {})
    if info:
        fill_info_table(doc, info)
    else:
        print("[!] JSON 中无 info_table 数据，跳过信息表填充。")

    # ── 2. 删除模板中的红色说明段落（模板要求正式提交时删除） ──
    remove_red_paragraphs(doc)

    # ── 3. 动态识别章节位置 ──
    # 注意：必须在删除红色段落后重新获取，段落索引已发生变化
    paras = doc.paragraphs
    section_idx = find_section_indices(paras)
    print(f"章节识别结果：{section_idx}")

    # ── 4. 填充"实验目的"（插入式，避免覆盖后续章节标题） ──
    obj_idx = section_idx.get("实验目的")
    if obj_idx is not None:
        insert_after = paras[obj_idx]
        for obj in data.get("objectives", []):
            insert_after = add_paragraph_after(
                doc, insert_after, obj,
                font_name='宋体', font_size=Pt(10.5),
                first_line_indent=Pt(21), space_after=Pt(3)
            )
    else:
        print("[!] 未找到'实验目的'章节，跳过。")

    # ── 5. 填充"实验内容"（插入式） ──
    content_idx = section_idx.get("实验内容")
    if content_idx is not None:
        insert_after = paras[content_idx]
        for item in data.get("content_items", []):
            insert_after = add_paragraph_after(
                doc, insert_after, item,
                font_name='宋体', font_size=Pt(10.5),
                first_line_indent=Pt(21), space_after=Pt(3)
            )
    else:
        print("[!] 未找到'实验内容'章节，跳过。")

    # ── 6. 填充"实验步骤" ──
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
                    print(f"[!] 截图文件不存在：{image_path}")
                    wp = add_paragraph_after(
                        doc, insert_after,
                        f"【截图：{step.get('caption', '')}】",
                        font_name='宋体', font_size=Pt(10.5), bold=True,
                        color=RGBColor(0xFF, 0, 0)
                    )
                    insert_after = wp
    else:
        print("[!] 未找到'实验步骤'章节，跳过。")

    # ── 7. 填充"实验结果" ──
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
        print("[!] 未找到'实验结果'章节，跳过。")

    # ── 8. 填充"实验总结" ──
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
        print("[!] 未找到'实验总结'章节，跳过。")

    # ── 保存 ──
    doc.save(args.output_path)
    size_kb = os.path.getsize(args.output_path) // 1024
    print(f"[OK] 报告已生成：{args.output_path}（{size_kb} KB）")


if __name__ == "__main__":
    main()
