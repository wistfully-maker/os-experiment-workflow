# experiment-report-workflow

课程实验报告的端到端工作流 Skill，适用于 WorkBuddy AI 助手。**支持任意课程的实验报告生成**，只需提供实验指导文件和报告模板 .docx。

## 功能简介

本 Skill 覆盖课程实验的完整生命周期，自动完成以下工作：

1. **需求分析 + 模板格式提取** — 从实验指导文件中提取实验要求，从模板 .docx 中自动提取格式信息
2. **环境检查** — 确认截图工具、模板文件、指导文件是否就绪
3. **实验执行与截图** — 根据执行环境（本机 / Linux VM SSH）编写代码、运行、采集真实截图
4. **报告撰写** — 按模板格式自动生成 .docx 实验报告（信息表动态填充，非硬编码）
5. **格式校验** — 与模板并行对比，自动修复格式差异

## 支持的执��环境

| 环境 | 说明 | 截图工具 |
|------|------|----------|
| Windows 本机 | 代码在本地运行 | desktop-screenshot（MCP） |
| macOS 本机 | 代码在本地运行 | screencapture |
| Linux VM（SSH） | 代码在远程 Linux 上运行 | gnome-screenshot（需 X 桌面） |

## 安装方法

### 1. 安装 Skill（WorkBuddy 用户）

在 WorkBuddy 对话中输入：
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
├── LICENSE                         # MIT License
├── environments/
│   └── linux-vm-ssh.md          # Linux VM（SSH）环境配置
├── references/
│   └── report_format.md          # 报告格式规范（固定规则 + 需提取项说明）
└── scripts/
    ├── extract_template_format.py  # 从模板 .docx 提取格式信息
    ├── build_report.py            # 报告生成脚本（信息表动态填充）
    └── crop_screenshots.py       # 截图裁剪脚本
```

## 格式规则说明

格式规则分为两部分：

| 类型 | 说明 | 示例 |
|------|------|------|
| **固定规则** | 不依赖模板，所有报告必须遵守 | 截图编号 `图X.Y`、代码块 Consolas 9pt + #F2F2F2 底纹 |
| **模板提取规则** | 因课程/模板而异，Phase 1 自动提取 | 信息表结构、章节标题格式、正文格式、页边距 |

如果模板格式不清晰，AI 会**主动询问用户**，不会猜测。

## 注意事项

- 模板 .doc 文件需先另存为 .docx（Transitional OOXML 格式，非 Strict）
- 如果使用 Linux VM SSH 环境截图，需要 VM 图形界面处于登录状态（非 GDM 锁屏）
- 报告生成后建议人工复核内容准确性
- 信息表标签名因模板而异，AI 会从模板中动态读取，无需手动配置

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v2.0.0 | 2026-06-25 | 通用化改造：支持多课程、多执行环境；信息表动态填充；新增模板格式自动提取 |
| v1.0.0 | 2026-06-25 | 初始版本，绑定操作系统课程 |

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

## 作者

wistfully-maker
