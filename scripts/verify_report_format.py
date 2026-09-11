#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 5：格式校验 —— 逐项比对「模板」与「生成报告」的格式。

用法:
    python verify_report_format.py <模板.docx> <生成报告.docx> [--figs N] [--body-font 宋体] [--body-size 10.5]

检查分两类：
  A 固定规则（不依赖模板）：图注、代码块、图编号、信息表位置、红色说明文字
  B 模板规则：页边距、章节标题、正文、表格结构、图片宽度

输出：通过清单 + 差异清单（❌ 表示需要修复）。有差异时退出码为 1。
"""
import argparse
import os
import re
import sys

from docx import Document
from docx.oxml.ns import qn

W = qn("w:eastAsia")
OK, BAD = [], []


def check(name, actual, expect, hint=""):
    if actual == expect:
        OK.append((name, str(actual)))
    else:
        BAD.append((name, str(actual), str(expect), hint))


def run_font(r):
    """返回 (中文字体, 字号pt, 加粗)"""
    fam = None
    if r is not None:
        rPr = r._element.rPr
        if rPr is not None and rPr.rFonts is not None:
            fam = rPr.rFonts.get(W) or r.font.name
    return fam, (r.font.size.pt if (r is not None and r.font.size) else None), \
        (r.font.bold if r is not None else None)


def shading_of(p):
    pPr = p._element.pPr
    if pPr is None:
        return None
    shd = pPr.find(qn("w:shd"))
    return shd.get(qn("w:fill")) if shd is not None else None


ap = argparse.ArgumentParser(description="实验报告格式校验")
ap.add_argument("template", help="模板 .docx")
ap.add_argument("report", help="生成的报告 .docx")
ap.add_argument("--figs", type=int, default=20, help="预期图片/图注数量")
ap.add_argument("--body-font", default="宋体", help="正文中文字体")
ap.add_argument("--body-size", type=float, default=10.5, help="正文字号(pt)")
ap.add_argument("--img-width", type=float, default=5.5, help="图片宽度(inch)")
a = ap.parse_args()

TPL, RPT = a.template, a.report
NF = a.figs

tpl = Document(TPL)
rpt = Document(RPT)

print("=" * 74)
print("A. 固定规则（不依赖模板）")
print("=" * 74)

# A1 图注：宋体 9pt 加粗 居中
caps = [p for p in rpt.paragraphs if re.match(r"^图\d+\.\d+ ", p.text.strip())]
check("图注数量", len(caps), NF)
bad_cap = []
for p in caps:
    fam, sz, bold = run_font(p.runs[0] if p.runs else None)
    if not (fam == "宋体" and sz == 9.0 and bold is True and p.alignment is not None
            and "CENTER" in str(p.alignment)):
        bad_cap.append((p.text.strip()[:22], fam, sz, bold, str(p.alignment)))
check("图注格式(宋体9pt加粗居中)", bad_cap if bad_cap else "全部合规", "全部合规")

# A2 图编号 图X.Y 且连续
nums = [re.match(r"^图(\d+)\.(\d+)", p.text.strip()).groups() for p in caps]
seq = [(int(a), int(b)) for a, b in nums]
expect_seq = [(3, i) for i in range(1, NF + 1)]
check("图编号格式与连续性", seq, expect_seq, "应为 图3.1~图3.%d" % NF + "")

# A3 代码块：Consolas 9pt + #F2F2F2 底纹
code_ps = [p for p in rpt.paragraphs if shading_of(p) == "F2F2F2"]
bad_code = []
for p in code_ps:
    r = p.runs[0] if p.runs else None
    fam = r.font.name if r is not None else None
    sz = r.font.size.pt if (r is not None and r.font.size) else None
    if not (fam == "Consolas" and sz == 9.0):
        bad_code.append((p.text.strip()[:26], fam, sz))
check("代码块数量(>0)", len(code_ps) > 0, True)
check("代码块格式(Consolas 9pt + #F2F2F2)", bad_code if bad_code else "全部合规", "全部合规")

# A4 信息表位于文档开头（第一个表格出现在第一个章节标题之前）
body = rpt.element.body
first_tbl_i, first_sec_i = None, None
ti = si = 0
for ch in body.iterchildren():
    tag = ch.tag.split("}")[1]
    if tag == "tbl" and first_tbl_i is None:
        first_tbl_i = ti + si
    if tag == "p":
        txt = "".join(n.text or "" for n in ch.iter(qn("w:t")))
        if re.match(r"^[一二三四五]、", txt.strip()) and first_sec_i is None:
            first_sec_i = ti + si
        si += 1
check("信息表在章节之前", (first_tbl_i is not None and first_sec_i is not None
                          and first_tbl_i < first_sec_i), True)

# A5 无红色说明文字残留
reds = []
for p in rpt.paragraphs:
    for r in p.runs:
        try:
            c = r.font.color
            rgb = c.rgb if c is not None else None
        except Exception:
            rgb = None
        if rgb is not None and str(rgb) == "FF0000" and r.text.strip():
            reds.append(r.text.strip()[:26])
check("无红色说明文字残留", reds if reds else 0, 0)

# A6 章节齐全（需含"五、实验总结"）
secs = [p.text.strip() for p in rpt.paragraphs
        if re.match(r"^[一二三四五六]、", p.text.strip()) and len(p.text.strip()) < 12]
check("章节清单", secs,
      ["一、实验目的", "二、实验内容", "三、实验步骤", "四、实验结果", "五、实验总结"])

print("\n" + "=" * 74)
print("B. 模板规则（从模板提取的格式）")
print("=" * 74)

# B1 页边距
def margins(d):
    s = d.sections[0]
    return (s.top_margin, s.bottom_margin, s.left_margin, s.right_margin)

check("页边距(上下/左右 EMU)", margins(rpt), margins(tpl))

# B2 章节标题格式（以"一、实验目的"为样本）
def secfmt(d):
    for p in d.paragraphs:
        if p.text.strip() == "一、实验目的":
            return run_font(p.runs[0] if p.runs else None)
    return None

check("章节标题格式(字体,字号,加粗)", secfmt(rpt), secfmt(tpl))

# B3 正文格式（取"二、实验内容"下第一条正文）
def bodyfmt(d):
    ps = d.paragraphs
    for i, p in enumerate(ps):
        if p.text.strip() == "二、实验内容":
            for q in ps[i + 1:i + 4]:
                if q.text.strip():
                    fam, sz, _ = run_font(q.runs[0] if q.runs else None)
                    return (fam, sz)
    return None

check("正文格式(字体,字号)", bodyfmt(rpt), (a.body_font, a.body_size),
      "若模板另有说明，可用 --body-font/--body-size 指定")

# B4 信息表结构
def tblshape(d):
    t = d.tables[0]
    return (len(t.rows), len(t.columns))

check("信息表结构(行数,列数)", tblshape(rpt), tblshape(tpl))

# B5 图片宽度
ws = sorted({round(s.width.inches, 2) for s in rpt.inline_shapes})
check("图片宽度(inch)", ws, [round(a.img_width, 2)])
check("图片数量", len(rpt.inline_shapes), NF)

# B6 空段落残留（注意：图片段落的文字也是空的，需排除含 <w:drawing> 的段落）
def is_real_empty(p):
    if p.text.strip():
        return False
    if p._element.findall('.//' + qn("w:drawing")):
        return False
    return True

empties = sum(1 for p in rpt.paragraphs if is_real_empty(p))
img_ps = sum(1 for p in rpt.paragraphs if p._element.findall('.//' + qn("w:drawing")))
check("空白段落数(不含图片段落)", empties <= 25, True,
      "实际=%d（其中图片段落 %d 个）" % (empties, img_ps))

print("\n【通过项】")
for n, v in OK:
    print("  ✅ %-34s %s" % (n, v))

print("\n【差异清单】")
if not BAD:
    print("  无 —— 全部通过 🎉")
else:
    for n, a, e, h in BAD:
        print("  ❌ %-34s 实际=%s  期望=%s  %s" % (n, a, e, h))

print("\n通过 %d 项，差异 %d 项" % (len(OK), len(BAD)))
sys.exit(1 if BAD else 0)
