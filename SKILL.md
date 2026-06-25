---
name: os-experiment-workflow
description: >
  操作系统课程实验的端到端工作流：从需求分析、环境检查、实验执行与截图采集，
  到 python-docx 生成符合格式要求的实验报告，再到与模板对比校验格式。
  适用于操作系统课程的 4 次实验（验证型/设计型/综合型）。
version: "1.0.0"
trigger_keywords:
  - 操作系统实验
  - 实验报告
  - 实验一/二/三/四
  - 进程控制
  - 进程调度
  - 进程同步
  - 内存管理
  - 实验环境搭建
agent_created: true
bundled_files:
  - references/vm_connection.md
  - references/report_format.md
  - scripts/crop_screenshots.py
  - scripts/build_report.py
dependencies:
  python:
    - python-docx>=0.8.11
    - Pillow>=9.0.0
---

# 操作系统实验端到端工作流

## 总览

本 Skill 覆盖操作系统课程实验的完整生命周期，分为 **5 个阶段**，每个阶段有明确的输入、动作、输出和检查点。

```
Phase 1: 需求分析    →  理解实验要求，明确做什么
Phase 2: 环境检查    →  确认本地+VM 工具链就绪
Phase 3: 实验执行    →  写代码、编译运行、截图
Phase 4: 报告撰写    →  按模板格式生成 .docx
Phase 5: 格式校验    →  与模板对比、修复差异
```

**核心原则**：
- 每个 Phase 结束时**必须停下来等用户确认**再进入下一 Phase
- 遇到工具缺失时**明确告知用户**，不要默默跳过
- 所有截图必须**真实采集自 VM 终端**，不得生成模拟图片

---

## Phase 1: 需求分析

### 输入
- 用户提供的实验指导文件（通常是 .pptx 或 .docx 或 .md）

### 动作

1. **读取实验指导文件**，提取以下信息：
   - 实验编号（实验一/二/三/四）
   - 实验标题
   - 实验类型（验证型 / 设计型 / 综合型）
   - 实验目的（逐条列出）
   - 实验内容（逐条列出）
   - 实验步骤及相关命令/代码
   - 需要的截图数量（每个步骤的截图要求）

2. **整理输出需求清单**，格式如下：

```
## 实验{N}：{标题} — 需求清单

| 项目 | 内容 |
|------|------|
| 类型 | 验证型/设计型/综合型 |
| 实验目的 | 1. ... 2. ... |
| 实验内容 | 1. ... 2. ... |
| 实验步骤 | N 个步骤 |
| 预期截图 | N 张 |
```

3. **识别 VM 上需要的操作**：
   - 需要创建哪些文件？（C 源文件等）
   - 需要安装哪些工具？（gcc 已有，需确认）
   - 每个步骤的命令序列是什么？

### 输出
- 清晰的需求清单，以表格/列表形式呈现给用户

### 检查点
> **停下来问用户：**"以上是我对实验要求理解的需求清单，是否正确？有没有遗漏？确认后进入环境检查。"

---

## Phase 2: 环境检查

### 输入
- Phase 1 的需求清单

### 动作

#### 2.1 本地工具链检查

逐一检查以下工具是否可用，并记录状态：

| 工具 | 检查方式 | 用途 |
|------|----------|------|
| Python 3 | `python --version` | 运行脚本 |
| python-docx | `python -c "import docx"` | 生成报告 |
| Pillow (PIL) | `python -c "from PIL import Image"` | 裁剪截图 |
| SSH 客户端 | `ssh -V` | 连接 VM |
| SSH 密钥 | 检查 `~/.ssh/id_rsa` 或 `/c/Users/李冠桥/.ssh/id_rsa` | 免密登录 |

#### 2.2 VM 工具链检查

SSH 到 VM 检查：

| 工具 | 检查命令 | 用途 |
|------|----------|------|
| gcc | `gcc --version` | 编译 C 程序 |
| gnome-terminal | `which gnome-terminal` | 在 X 桌面显示终端 |
| 截图脚本 | `test -f /home/lalala/vm_screenshot.sh` | 捕获终端内容 |
| sudo | `sudo -n true` | 截图脚本需要 sudo |

#### 2.3 缺失项处理

如果任何工具缺失，**明确告知用户**：

- 本地工具缺失 → 告知安装命令（如 `pip install python-docx pillow`），询问是否安装
- VM 工具缺失 → 告知用户需要在 VM 上手动安装什么，询问是否继续
- GDM 状态 → 提醒用户截图前需要在 VM 图形界面登录

#### 2.4 明确哪些需要用户手动完成

必须告知用户以下事项需要手动操作：

> **需要你手动完成的部分：**
> 1. VM 图形界面登录（解锁 GDM）—— 截图前必须
> 2. 模板 .doc → .docx 转换 —— 用 WPS/Word 打开后"另存为 .docx"
> 3. [如果有工具缺失] 安装 xxx

### 输出
- 环境检查报告（就绪项 + 缺失项 + 用户需手动完成项）

### 检查点
> **停下来问用户：**"环境检查完成。以上工具就绪/缺失情况如上。缺失的工具是否需要我帮忙安装？需要你手动完成的部分是否清楚？确认后进入实验执行。"

---

## Phase 3: 实验执行与截图

### 输入
- Phase 1 的实验步骤和命令序列
- Phase 2 确认的环境就绪状态

### 动作

#### 3.1 创建 VM 工作目录

```bash
ssh ... lalala@192.168.5.135 'mkdir -p /home/lalala/program_sec/os/experiment{N}'
```

#### 3.2 编写代码并上传

- 在本地写好 C 源文件
- 通过 SCP 上传到 VM：

```bash
scp ... source.c lalala@192.168.5.135:/home/lalala/program_sec/os/experiment{N}/
```

#### 3.3 编译并验证

```bash
ssh ... lalala@192.168.5.135 'cd /home/lalala/program_sec/os/experiment{N} && gcc source.c -o program && echo "编译成功" || echo "编译失败"'
```

如果编译失败 → 修复代码，重新上传，直到成功。

#### 3.4 采集截图

**⚠️ 截图前必须确认：用户已登录 VM 图形界面（GDM 已解锁）。**

详细步骤见 `references/vm_connection.md` 的"截图工作流"一节。核心流程：

1. 在 X 桌面启动 gnome-terminal，执行命令序列
2. 运行截图脚本
3. SCP 拉回本地
4. **必须清理**：`pkill -f gnome-terminal`

**关键规则：**
- 每张截图的命令之间用 `echo` 显示提示行
- 最后加 `sleep 12` 确保窗口保持打开
- 截图后立即 pkill，避免多窗口叠加
- 如果截图全黑 → GDM 锁屏，需要用户手动解锁后重试
- 如果截图是蓝屏 → GDM 锁屏未解除

#### 3.5 截图裁剪

使用 `scripts/crop_screenshots.py`：

```bash
python scripts/crop_screenshots.py 实验{N}/screenshots/ 实验{N}/screenshots/cropped/
```

如果自动检测不精确，手动指定裁剪参数：

```bash
python scripts/crop_screenshots.py ... --crops '{"1":[5,90,650,550],"2":[5,90,650,600]}'
```

### 输出
- VM 上编译运行成功的程序
- 裁剪后的真实截图（存放在 `实验{N}/screenshots/cropped/`）

### 检查点
> **停下来问用户：**"截图已全部采集并裁剪完毕，共 N 张。请检查截图质量和内容是否满意？是否需要重截某张？确认后进入报告撰写。"

---

## Phase 4: 报告撰写

### 输入
- Phase 1 的需求清单（实验内容）
- Phase 3 的裁剪截图
- 模板 .docx 文件（用户需先将 .doc 另存为 .docx）

### 动作

#### 4.1 准备模板

- 用户将 `实验报告的格式.doc` 用 WPS/Word 另存为 `.docx`（**Transitional OOXML 格式**，非 Strict）
- AI 打开模板 .docx，分析段落结构，记录每个章节标题的段落索引

#### 4.2 准备实验数据 JSON

按照 `scripts/build_report.py` 的 DATA_SCHEMA 格式，将实验内容组织为 JSON：

```json
{
  "title": "实验一：实验环境搭建与使用",
  "type": "验证型",
  "objectives": ["目的1", "目的2", ...],
  "content_items": ["内容1", "内容2", ...],
  "steps": [
    {
      "title": "1. 步骤标题",
      "desc": "步骤描述",
      "code": ["命令1", "命令2"],
      "image": "截图文件名",
      "caption": "图3.X 描述"
    }
  ],
  "results": ["结果1", "结果2"],
  "summary": "实验总结文字"
}
```

#### 4.3 生成报告

```bash
python scripts/build_report.py 1 模板.docx 输出.docx 截图目录 --data 'JSON字符串'
```

#### 4.4 处理生成中的常见问题

- **模板 .docx 打不开** → 确认用户用的是 Transitional 格式，不是 Strict OOXML
- **截图路径找不到** → 检查截图文件名是否和 JSON 中一致
- **章节标题匹配失败** → 检查模板段落文本是否包含"实验目的""实验内容"等关键词
- **信息表未填充** → build_report.py 可能需要根据实际模板调整单元格索引

### 输出
- 实验报告 .docx 文件（v1 初版）

### 检查点
> **停下来问用户：**"报告 v1 已生成。请打开查看整体内容是否正确（不涉及格式细节，格式在 Phase 5 校验）。确认后进入格式校验。"

---

## Phase 5: 格式校验

### 输入
- Phase 4 生成的报告 .docx
- 模板 .docx（作为格式参照物）
- `references/report_format.md`（格式规范）

### 动作

#### 5.1 并行对比：生成报告 vs 模板

**同时打开两个文件**，逐项对比以下内容（对照 `references/report_format.md`）：

| 检查项 | 期望值 | 验证方式 |
|--------|--------|----------|
| 信息表结构 | 3行×11格，标签列 1500 DXA | 读取表格属性 |
| 文档大标题 | 宋体 三号(16pt) 加粗 居中 | 检查段落属性 |
| 章节标题(一~五) | 蓝色 四号(14pt) 加粗 | 检查 Run 颜色和字号 |
| 正文段落 | 宋体 五号(10.5pt) | 检查 Run 字体和字号 |
| 代码块字体 | Consolas 小五(9pt) | 逐一检查代码 Run |
| 代码块底纹 | #F2F2F2 | 检查 shading 属性 |
| 图注 | 宋体 9pt 加粗 居中 图X.Y | 正则 + 属性检查 |
| 图片宽度 | 约 5.5 英寸 | 检查图片尺寸 |
| 页边距 | 1134 DXA | 检查 section 属性 |
| 表格列宽 | 标签列 1500 DXA | 检查列宽度 |
| 章节顺序 | 一→二→三→四→五 | 检查段落顺序 |

#### 5.2 输出差异清单

列出所有不符合模板的差异项：

```
## 格式差异清单
1. ❌ 代码块字体是宋体 10.5pt → 应改为 Consolas 9pt
2. ❌ 代码块无底纹 → 应添加 #F2F2F2 底纹
3. ❌ 图注字号是 10.5pt → 应改为 9pt
4. ❌ ...
```

#### 5.3 逐项修复

对每个差异项，用 python-docx 修改报告文件：
- 能自动修复的 → 直接修复
- 需要手动调整的 → 告知用户具体操作

#### 5.4 修复后再次校验

修复完成后，重新运行检查清单，确保所有项目通过。

### 输出
- 修复后的最终报告 .docx
- 校验通过清单

### 检查点
> **停下来问用户：**"格式校验完成，以下项目已全部通过：[通过清单]。报告最终版已生成。请最终确认。"

---

## 附录：文件索引

### References（参考文档）

| 文件 | 内容 | 何时阅读 |
|------|------|----------|
| `references/vm_connection.md` | VM 连接参数、SSH 命令模板、截图工作流详细步骤 | Phase 2 环境检查、Phase 3 截图 |
| `references/report_format.md` | 报告格式规范（字体、字号、表格、图注、页边距） | Phase 4 报告撰写、Phase 5 格式校验 |

### Scripts（可执行脚本）

| 文件 | 功能 | 何时使用 |
|------|------|----------|
| `scripts/crop_screenshots.py` | 裁剪 VM 全屏截图，去除桌面空白 | Phase 3 截图后 |
| `scripts/build_report.py` | 从模板 + JSON 数据生成 .docx 报告 | Phase 4 报告撰写 |

---

## 快速参考：VM 一键命令模板

```bash
# SSH 别名（简化命令）
SSH_CMD="ssh -i /c/Users/李冠桥/.ssh/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null lalala@192.168.5.135"
SCP_CMD="scp -i /c/Users/李冠桥/.ssh/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# 创建工作目录
$SSH_CMD 'mkdir -p /home/lalala/program_sec/os/experiment{N}'

# 上传文件
$SCP_CMD local_file.c lalala@192.168.5.135:/home/lalala/program_sec/os/experiment{N}/

# 编译
$SSH_CMD 'cd /home/lalala/program_sec/os/experiment{N} && gcc file.c -o file'

# 截图
$SSH_CMD 'sudo bash /home/lalala/vm_screenshot.sh lalala /tmp/exp{N}_X.png'

# 拉回截图
$SCP_CMD lalala@192.168.5.135:/tmp/exp{N}_X.png ./screenshots/

# 清理终端
$SSH_CMD 'pkill -f gnome-terminal'
```
