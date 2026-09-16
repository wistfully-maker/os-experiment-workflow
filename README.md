# experiment-report-workflow

课程实验报告的端到端工作流 Skill，适用于 WorkBuddy AI 助手。**支持任意课程的实验报告生成**，只需提供实验指导文件和报告模板 .docx。

## 功能简介

本 Skill 覆盖课程实验的完整生命周期，自动完成以下工作：

1. **需求分析 + 模板格式提取** — 从实验指导文件中提取实验要求，从模板 .docx 中自动提取格式信息
2. **环境检查 + 自主判断环境** — 探测信号，**自己判定**该用哪套截图方法；只有信号不足时才问用户
3. **实验执行与截图** — 按判定结果走对应方式，采集**真实终端**截图
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

## 执行环境：自己判断，不用你回答

Phase 2 会**自主判定**该走哪套截图方法，不再一上来就问"代码在哪跑"。判定依据三类硬信号：

| 优先级 | 信号 | 来源 |
|--------|------|------|
| 1（最权威） | 实验指导文件里写明的平台 | Phase 1 读指导文件时留意"实验环境"一节 |
| 2 | 本机是否已具备实验所需的可执行程序 | PATH + 常见安装目录探测 |
| 3 | 是否存在可用的 SSH 目标 | 解析 `~/.ssh/config`，可选真连一次 |

```bash
python scripts/detect_env.py --needs mongod,mongosh --guide-platform windows --ssh-alias master
#  ▶ 判定结果 : windows-local
#    理由     : 指导文件明确要求 Windows 平台，且本机所需工具齐备
#    → 同时给出该环境的：必读文档 / 截图执行方式 / 裁剪方式 / 用户需先做什么 / 注意事项
```

判定不出来（信号不足或互相矛盾）才回头问用户，并说明**是哪个信号不足**。

### 为什么必须区分环境：两套方法的能力差异

判定不是"代码在哪跑"的问题，而是**AI 在这个环境里能做到什么**：

| 能力 | Windows 本机 | Linux VM（SSH） |
|------|--------------|-----------------|
| AI 自己"打开"终端 | ❌ **平台禁止** | ✅ 不需要 GUI 终端 |
| AI 自己执行命令 | ✅ 本地 shell | ✅ ssh |
| 命令回显真实性 | ✅ 用户窗口内 PSReadLine 回显 | ✅ `expect` 驱动 `bash -i` |
| AI 程序化"发输入" | ✅ 驱动**用户已开**的窗口 | ✅ expect |
| 提权命令 | ⚠️ **驱动不了提权窗口**（UIPI），但可抓屏 → 用户敲、AI 抓 | ✅ `sudo` 直接在 ssh 里用 |
| 抓图 / 裁剪 | `ImageGrab` 抓窗口 / `crop_console.py` | `gnome-screenshot -w` / `crop_screenshots.py` |
| 每次要用户做的 | **手动开一个普通终端窗口** | 保证 X 桌面已登录未锁屏 |

一句话：**Linux VM 全流程都能程序化完成；Windows 能驱动但开不了窗口，且提权窗口是盲区。**
选错环境不是效率问题，而是**有些步骤根本做不下去**——所以判定要在 Phase 2 一次定死，
Phase 3 中途不换。详见 [`references/environment-detection.md`](references/environment-detection.md)。

### Linux VM 截图

窗口模式截图（`gnome-screenshot -w`）保证尺寸恒定、不受桌面其它窗口干扰；
裁剪采用**统一宽度 + 紧贴内容**：

```bash
python scripts/crop_screenshots.py raw/ cropped/ --skip-top 37 --margin 8 --uniform-width
```

- **统一宽度** → 所有图缩放到报告同一宽度时，文字大小一致
- **紧贴内容** → 底部不留大片空白

两种裁剪（统一尺寸 / 不留白）可由同一批原图产出，**无需重新截图**。

> Linux VM 上 **不能用 gnome-terminal**——root 身份下无法连接桌面会话 dbus，
> 会报 `Error constructing proxy for org.gnome.Terminal`。改用 xterm（不依赖 dbus）。
> 截图前还必须唤醒屏幕并解锁会话（`xset dpms force on` + `loginctl unlock-session`），
> 否则截到全黑或锁屏页。

### Windows 截图

平台禁止程序化启动终端，所以**终端必须用户手动打开**；开好之后 AI 用
`scripts/winterm.py` 驱动它（激活窗口 → 剪贴板粘贴命令 → 抓窗口区域），
再用 `scripts/crop_console.py` 裁成纯控制台内容。

```bash
python scripts/winterm.py resize --hwnd <H> --w 1760 --h 1500 --x 60 --y 15
python scripts/winterm.py batch  --hwnd <H> --steps steps.json --outdir raw --paste-all
python scripts/crop_console.py raw/s01.png out/s01.png --top 62 --side 12 --bottom-inset 20
```

三个最容易踩的坑（完整 9 条见 [`environments/windows-local.md`](environments/windows-local.md)）：

- **逐字符打字会被 mongosh 的自动补全弹窗打断**（输入 `.` 就弹补全，回车被吃掉）→ 命令一律**剪贴板粘贴**
- **抢焦点失败必须立刻中止**，否则按键会打到别的窗口里 → `winterm.py` 已做校验，失败即 `exit(3)`
- **窗口行数决定一张图能放多少内容**：1240px≈43 行，1500px≈53 行；不够会把命令滚出画面

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

### 4. 各环境额外前置

**Linux VM（仅该环境需要）** —— 虚拟机需具备：`xterm`、`gnome-screenshot`、`xset`、
**`expect`**、`loginctl`、一个等宽字体（英文用 `DejaVu Sans Mono`，含中文用 `WenQuanYi Micro Hei Mono`）。

**Windows 本机（仅该环境需要）** —— 无需额外安装任何工具（`winterm.py` 只用
Python 标准库 + Pillow）。但要知道两条平台限制：

- AI **开不了**终端窗口 → 每次要请你手动开一个「普通」PowerShell 窗口
- AI **驱动不了**提权窗口（UIPI）→ 需要管理员权限的命令由你自己敲、AI 抓屏

**macOS 本机** —— 无需额外配置。

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
│   ├── linux-vm-ssh.md               # Linux VM（SSH）环境配置（VM 特有内容）
│   └── windows-local.md              # Windows 本机环境（平台限制 / 协作分工 / 裁剪偏移 / 9 条踩坑）
├── references/
│   ├── environment-detection.md      # 执行环境自主判定（能力矩阵 / 判定信号 / 路由表）
│   ├── report_format.md              # 报告格式规范（固定规则 + 需提取项说明）
│   └── screenshot-quality.md         # 截图质量规范（真实终端 / 行数预算 / 裁剪策略 / QC 清单）
└── scripts/
    ├── extract_template_format.py    # 从模板 .docx 提取格式信息
    ├── detect_env.py                 # 执行环境自主判定（本机系统 / 所需程序 / SSH 目标）
    ├── vm_shot.sh                    # Linux VM 截图脚本（expect 驱动真实终端）
    ├── winterm.py                    # Windows 终端驱动（激活 / 粘贴 / 抓窗口 / 批量步骤表）
    ├── crop_console.py               # Windows 终端截图裁剪（去窗口装饰 + 裁空白）
    ├── crop_screenshots.py           # 截图裁剪（统一尺寸 / 统一宽+紧贴高）
    ├── build_report.py               # 报告生成（信息表动态填充）
    └── verify_report_format.py       # 格式校验（逐项比对）
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
- **WPS 生成的模板里 Normal 样式常没有 `w:default="1"` 标记**——用 python-docx 新建的段落
  若不带 `pStyle`，Word 会退回内置默认字体字号，与模板正文不一致。
  新建段落务必**显式** `p.style = doc.styles['Normal']`；具体字号从模板正文 run 上读
  （如 `<w:sz w:val="24"/>` = 12pt 小四）
- **模板章节名不标准时不要硬改模板去迁就脚本**，写一个针对该模板的生成器，
  复用 `build_report.py` 里可复用的部分（信息表填充 / 红字清理 / 代码块与图片格式）
- 如果使用 Linux VM SSH 环境截图，**截图前必须**唤醒屏幕并解锁会话
  （`xset dpms force on` + `loginctl unlock-session`），否则截到全黑或锁屏页
- 如果使用 Windows 环境截图，**终端必须由用户手动打开**（平台禁止程序化启动终端窗口）；
  提权窗口 AI 驱动不了，改成"用户敲命令、AI 抓屏"
- 截图数量多时，注意控制每个命令脚本的输出行数，避免命令被滚出画面
  （详见 `references/screenshot-quality.md`）
- 报告生成后建议人工复核内容准确性

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v4.0.0 | 2026-09-16 | **执行环境自主判定 + Windows 本机链路**：新增 `scripts/detect_env.py`（按"指导文件平台 > 本机工具 > SSH 目标"三类信号自动判定走哪套截图方法）与 `references/environment-detection.md`（能力矩阵 / 判定流程 / 路由表）；新增 `scripts/winterm.py` + `scripts/crop_console.py` 与 `environments/windows-local.md`；Phase 2 由"询问用户"改为"自主判定，信号不足才问"；修正 Phase 3 中「方式 B」重复编号；补充 WPS 模板 pStyle 缺失、模板章节名不标准等实战经验 |
| v3.0.0 | 2026-09-11 | **截图链路与真实终端大改**：改用 `expect` 驱动真实交互式 bash（弃用 echo 画提示符 / 管道喂命令）；新增 `scripts/vm_shot.sh`、`references/screenshot-quality.md`；裁剪新增 `--uniform-width`/`--skip-top`/`--margin`；新增 `scripts/verify_report_format.py`；`build_report.py` 修复 3 个会损坏报告的 bug 并支持 `--data-file`；新增 `.gitattributes` 统一 LF |
| v2.0.0 | 2026-06-25 | 通用化改造：支持多课程、多执行环境；信息表动态填充；新增模板格式自动提取 |
| v1.0.0 | 2026-06-25 | 初始版本，绑定操作系统课程 |

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

## 作者

wistfully-maker
