# experiment-report-workflow

课程实验报告的端到端工作流 Skill，适用于 WorkBuddy AI 助手。**支持任意课程的实验报告生成**，只需提供实验指导文件和报告模板 .docx。

## 功能简介

本 Skill 覆盖课程实验的完整生命周期，自动完成以下工作：

1. **需求分析 + 模板格式提取** — 从实验指导文件中提取实验要求，从模板 .docx 中自动提取格式信息
2. **环境检查** — 确认截图工具、模板文件、指导文件是否就绪
3. **实验执行与截图** — 根据执行环境（本机 / Linux VM SSH）执行实验，采集**真实终端**截图
4. **报告撰写** — 按模板格式自动生成 .docx 实验报告（信息表动态填充，非硬编码）
5. **格式校验** — 与模板逐项对比，输出差异清单，自动修复

## 核心特性

### 截图：真实终端，不是"画"出来的

截图环节坚持一条原则：**提示符与命令回显必须由真实终端产生**，脚本不画任何一个像素。

| 反模式 | 后果 |
|--------|------|
| 在命令脚本里 `echo "[root@master ~]# xxx"` | 提示符是普通文本、命令无回显、输出一次性刷出 → **一眼看出是脚本生成** |
| 用管道定时喂命令给 `script` | 与 bash 提示符输出竞态 → 提示符堆积、**无输出命令的命令行丢失** |

正确做法：用 `expect` 驱动真实交互式 bash（`scripts/vm_shot.sh` 已实现），
提示符由 shell 的 PS1 输出、命令由 tty 行规程回显。详见 [`references/screenshot-quality.md`](references/screenshot-quality.md)。

### 截图：不留空白，且各图文字大小一致

窗口模式截图（`gnome-screenshot -w`）保证尺寸恒定、不受桌面其它窗口干扰；
裁剪采用**统一宽度 + 紧贴内容**：

```bash
python scripts/crop_screenshots.py raw/ cropped/ --skip-top 37 --margin 8 --uniform-width
```

- **统一宽度** → 所有图缩放到报告同一宽度时，文字大小一致
- **紧贴内容** → 底部不留大片空白

两种裁剪（统一尺寸 / 不留白）可由同一批原图产出，**无需重新截图**。

### 格式校验：一条命令跑完全部检查

```bash
python scripts/verify_report_format.py 模板.docx 报告.docx --figs 20
# 退出码 0 = 全部通过；1 = 有差异
```

覆盖固定规则（图注、代码块、图编号、信息表位置）、模板规则（页边距、章节标题、正文、图片宽度）与结构完整性共 15 项。

## 支持的执行环境

| 环境 | 说明 | 截图方式 |
|------|------|----------|
| Windows 本机 | 代码在本地运行 | desktop-screenshot（MCP） |
| macOS 本机 | 代码在本地运行 | `screencapture` |
| Linux VM（SSH） | 代码在远程 Linux 上运行 | **xterm + `gnome-screenshot -w`**（需 X 桌面，见 `environments/linux-vm-ssh.md`） |

> Linux VM 上 **不能用 gnome-terminal**——root 身份下无法连接桌面会话 dbus，
> 会报 `Error constructing proxy for org.gnome.Terminal`。改用 xterm（不依赖 dbus）。

## 安装方法

### 1. 安装 Skill（WorkBuddy 用户）

```
/install-skill experiment-report-workflow
```

或从本地安装：

```
/install-skill /path/to/experiment-report-workflow
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

依赖项：
- `python-docx>=0.8.11` — 生成 .docx 报告、提取模板格式
- `Pillow>=9.0.0` — 裁剪截图

### 3. 准备模板文件

> **⚠️ 前置条件**：将模板 `.doc` 用 WPS/Word 另存为 `.docx`（**Transitional OOXML 格式**，非 Strict）。

### 4. Linux VM 额外前置（仅该环境需要）

虚拟机需具备：`xterm`、`gnome-screenshot`、`xset`、**`expect`**、`loginctl`、
一个等宽字体（英文用 `DejaVu Sans Mono`，含中文用 `WenQuanYi Micro Hei Mono`）。

## 使用方法

安装 Skill 后，在 WorkBuddy 中直接描述实验任务即可，例如：

```
帮我完成操作系统实验二：进程控制与进程调度
```

或通用触发词：

```
完成实验报告
```

AI 会自动按 5 个阶段推进，每个阶段结束时等待用户确认。

## 项目结构

```
experiment-report-workflow/
├── SKILL.md                          # 核心流程编排（5 阶段工作流）
├── README.md                         # 本文件
├── requirements.txt                  # Python 依赖
├── LICENSE                           # MIT License
├── environments/
│   └── linux-vm-ssh.md               # Linux VM（SSH）环境配置（VM 特有内容）
├── references/
│   ├── report_format.md              # 报告格式规范（固定规则 + 需提取项说明）
│   └── screenshot-quality.md         # 截图质量规范（真实终端 / 行数预算 / 裁剪策略 / QC 清单）
└── scripts/
    ├── extract_template_format.py    # 从模板 .docx 提取格式信息
    ├── vm_shot.sh                    # Linux VM 截图脚本（expect 驱动真实终端）
    ├── crop_screenshots.py           # 截图裁剪（统一尺寸 / 统一宽+紧贴高）
    ├── build_report.py               # 报告生成（信息表动态填充）
    └── verify_report_format.py       # 格式校验（15 项逐项比对）
```

## 格式规则说明

| 类型 | 说明 | 示例 |
|------|------|------|
| **固定规则** | 不依赖模板，所有报告必须遵守 | 截图编号 `图X.Y`、代码块 Consolas 9pt + #F2F2F2 底纹 |
| **模板提取规则** | 因课程/模板而异，Phase 1 自动提取 | 信息表结构、章节标题格式、正文格式、页边距 |

如果模板格式不清晰，AI 会**主动询问用户**，不会猜测。

## 注意事项

- 模板 .doc 文件需先另存为 .docx（Transitional OOXML 格式，非 Strict）
- 若模板缺少必需的章节（如"实验总结"），可用「深拷贝现有章节标题段落的 XML 再改文字」
  的方式新增，以保证格式完全一致；插入位置须在 `<w:sectPr>` 之前
- 如果使用 Linux VM SSH 环境截图，**截图前必须**唤醒屏幕并解锁会话
  （`xset dpms force on` + `loginctl unlock-session`），否则截到全黑或锁屏页
- 截图数量多时，注意控制每个命令脚本的输出行数，避免命令被滚出画面
  （详见 `references/screenshot-quality.md`）
- 报告生成后建议人工复核内容准确性

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v3.0.0 | 2026-09-11 | **截图链路与真实终端大改**：改用 `expect` 驱动真实交互式 bash（弃用 echo 画提示符 / 管道喂命令）；新增 `scripts/vm_shot.sh`、`references/screenshot-quality.md`；裁剪新增 `--uniform-width`/`--skip-top`/`--margin`；新增 `scripts/verify_report_format.py`；`build_report.py` 修复 3 个会损坏报告的 bug 并支持 `--data-file`；新增 `.gitattributes` 统一 LF |
| v2.0.0 | 2026-06-25 | 通用化改造：支持多课程、多执行环境；信息表动态填充；新增模板格式自动提取 |
| v1.0.0 | 2026-06-25 | 初始版本，绑定操作系统课程 |

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

## 作者

wistfully-maker
