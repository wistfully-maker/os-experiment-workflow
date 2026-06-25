"""从模板生成操作系统实验报告 docx。

严格遵循模板的 "段落 + 小表格" 结构（非单一大表格）。

用法：
    python build_report.py <实验编号> <模板路径> <输出路径> <截图目录> [--data DATA_JSON]

    --data: JSON 字符串，包含实验内容。
            格式见下方 DATA_SCHEMA 注释。

模板结构（重要！）：
    模板 docx 必须是 Transitional OOXML 格式（非 Strict OOXML）。
    模板结构：
        P0-P3: 标题 "河南工业大学实验报告" + 空白段落
        Table0: 信息表 (3行×11格)
        P4-P7: 实验名称表 (1行×2格) + 空白
        P8: "一、实验目的" (蓝色标题段落)
        P9-P11: 目的内容段落
        P12: 空白
        P13: "二、实验内容" (蓝色标题段落)
        ...

DATA_SCHEMA:
{
  "title": "实验一：实验环境搭建与使用",
  "type": "验证型",
  "objectives": ["目的1", "目的2", ...],
  "content_items": ["内容1", "内容2", ...],
  "steps": [
    {
      "title": "1. 步骤标题",
      "desc": "步骤描述文字",
      "code": ["命令1", "命令2", ...],
      "image": "截图路径或null",
      "caption": "图3.X 截图描述"
    },
    ...
  ],
  "results": ["结果1", "结果2", ...],
  "summary": "实验总结文字"
}
"""

import argparse
import json
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


def set_text(para, text, font_name=None, font_size=None, bold=None, color=None):
    """设置段落文本，保留第一个 run 的格式"""
    for run in para.runs:
        run.text = ''
    if para.runs:
        para.runs[0].text = text
        if font_name:
            para.runs[0].font.name = font_name
        if font_size:
            para.runs[0].font.size = font_size
        if bold is not None:
            para.runs[0].font.bold = bold
        if color:
            para.runs[0].font.color.rgb = color
    else:
        run = para.add_run(text)
        if font_name:
            run.font.name = font_name
        if font_size:
            run.font.size = font_size
        if bold is not None:
            run.font.bold = bold
        if color:
            run.font.color.rgb = color


def add_paragraph_after(doc, after_para, text, font_name='宋体', font_size=Pt(10.5),
                        bold=False, alignment=None, first_line_indent=None,
                        space_before=None, space_after=None):
    """在指定段落后添加新段落"""
    new_p = doc.add_paragraph()
    after_para._element.addnext(new_p._element)
    run = new_p.add_run(text)
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    run.font.size = font_size
    run.font.bold = bold
    if alignment is not None:
        new_p.alignment = alignment
    if first_line_indent:
        new_p.paragraph_format.first_line_indent = first_line_indent
    if space_before:
        new_p.paragraph_format.space_before = space_before
    if space_after:
        new_p.paragraph_format.space_after = space_after
    return new_p


def add_code_paragraph(doc, after_para, code_text):
    """添加代码段落（灰色底纹 #F2F2F2, Consolas 9pt）"""
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
    """添加居中图片 + 图注（图片在上，图注在下）"""
    # 图片段落（先插入图片）
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

    # 空行（图注下方）
    sp_p = doc.add_paragraph()
    cap_p._element.addnext(sp_p._element)
    return sp_p


def main():
    parser = argparse.ArgumentParser(description="生成操作系统实验报告")
    parser.add_argument("exp_num", type=int, help="实验编号（1-4）")
    parser.add_argument("template_path", help="模板 docx 文件路径")
    parser.add_argument("output_path", help="输出 docx 文件路径")
    parser.add_argument("screenshot_dir", help="截图目录（裁剪后的）")
    parser.add_argument("--data", required=True, help="实验内容 JSON 字符串")
    args = parser.parse_args()

    data = json.loads(args.data)

    doc = Document(args.template_path)
    paras = doc.paragraphs

    # === 1. 检查并准备截图路径 ===
    screenshot_dir = os.path.abspath(args.screenshot_dir)

    # === 2. 填充信息表（Table 0：3行×11格） ===
    if doc.tables:
        info_table = doc.tables[0]
        # 按模板格式填充单元格（需根据实际模板结构调整）

    # === 3. 修改"一、实验目的" ===
    obj_idx = None
    for i, p in enumerate(paras):
        if '实验目的' in p.text and '四' not in p.text:
            obj_idx = i
            break
    if obj_idx is not None:
        for j, obj in enumerate(data.get('objectives', [])):
            idx = obj_idx + 1 + j
            if idx < len(paras) and j < len(data['objectives']):
                set_text(paras[idx], obj, font_name='宋体', font_size=Pt(10.5))

    # === 4. 修改"二、实验内容" ===
    content_idx = None
    for i, p in enumerate(paras):
        if p.text.strip() == '实验内容':
            content_idx = i
            break
    if content_idx is None:
        for i, p in enumerate(paras):
            if '实验内容' in p.text:
                content_idx = i
                break
    if content_idx is not None:
        for j, item in enumerate(data.get('content_items', [])):
            idx = content_idx + 1 + j
            if idx < len(paras) and j < len(data['content_items']):
                set_text(paras[idx], item, font_name='宋体', font_size=Pt(10.5))

    # === 5. 修改"三、实验步骤" ===
    step_idx = None
    for i, p in enumerate(paras):
        if '实验步骤' in p.text:
            step_idx = i
            break
    if step_idx is not None:
        insert_after = paras[step_idx]
        steps = data.get('steps', [])
        for section in steps:
            # 小标题
            tp = add_paragraph_after(doc, insert_after,
                section['title'], font_name='宋体', font_size=Pt(10.5), bold=True,
                space_before=Pt(12), space_after=Pt(3))
            insert_after = tp

            # 描述
            dp = add_paragraph_after(doc, insert_after,
                section['desc'], font_name='宋体', font_size=Pt(10.5),
                first_line_indent=Pt(21), space_after=Pt(3))
            insert_after = dp

            # 代码行
            for code_line in section.get('code', []):
                cp = add_code_paragraph(doc, insert_after, code_line)
                insert_after = cp

            # 截图
            image_path = section.get('image')
            if image_path:
                # 支持相对路径（相对于运行目录）
                if not os.path.isabs(image_path):
                    image_path = os.path.join(screenshot_dir, image_path)
                if os.path.exists(image_path):
                    ip = add_image_paragraph(doc, insert_after, image_path, section['caption'])
                    insert_after = ip
                else:
                    # 占位符
                    wp = add_paragraph_after(doc, insert_after,
                        f'【截图：{section["caption"]}】',
                        font_name='宋体', font_size=Pt(10.5), bold=True,
                        color=RGBColor(0xFF, 0, 0))
                    insert_after = wp

    # === 6. 修改"四、实验结果" ===
    result_idx = None
    for i, p in enumerate(paras):
        if '实验结果' in p.text:
            result_idx = i
            break
    if result_idx is not None:
        insert_after = paras[result_idx]
        for line in data.get('results', []):
            rp = add_paragraph_after(doc, insert_after,
                line, font_name='宋体', font_size=Pt(10.5),
                first_line_indent=Pt(21), space_after=Pt(3))
            insert_after = rp

    # === 7. 修改"五、实验总结" ===
    summary_idx = None
    for i, p in enumerate(paras):
        if '实验总结' in p.text:
            summary_idx = i
            break
    if summary_idx is not None:
        summary_text = data.get('summary', '')
        add_paragraph_after(doc, paras[summary_idx],
            summary_text, font_name='宋体', font_size=Pt(10.5),
            first_line_indent=Pt(21), space_after=Pt(3))

    # 保存
    doc.save(args.output_path)
    print(f'报告已生成: {args.output_path}')
    print(f'文件大小: {os.path.getsize(args.output_path) // 1024} KB')


if __name__ == "__main__":
    main()
