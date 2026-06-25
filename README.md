# os-experiment-workflow

操作系统课程实验的端到端工作流 Skill，适用于 WorkBuddy AI 助手。

## 功能简介

本 Skill 覆盖操作系统课程实验的完整生命周期，自动完成以下工作：

1. **需求分析** — 从实验指导文件中提取实验目的、内容、步骤
2. **环境检查** — 确认本地 Python 依赖和 VM 工具链是否就绪
3. **实验执行** — 编写代码、编译运行、采集真实终端截图
4. **报告撰写** — 按模板格式自动生成 .docx 实验报告
5. **格式校验** — 与模板并行对比，自动修复格式差异

## 安装方法

### 1. 安装 Skill（WorkBuddy 用户）

在 WorkBuddy 对话中输入：
```
/install-skill os-experiment-workflow
```

或从本地安装：
```
/install-skill /path/to/os-experiment-workflow
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

依赖项：
- `python-docx>=0.8.11` — 生成 .docx 报告
- `Pillow>=9.0.0` — 裁剪截图

### 3. VM 环境准备（可选，用于真实截图）

如果使用虚拟机截图功能，需要确保：
- VM 已安装 `gcc`、`gnome-terminal`、`gnome-screenshot`
- VM 已配置免密 SSH 登录
- 截图脚本已部署到 VM（参见 `references/vm_connection.md`）

## 使用方法

安装 Skill 后，在 WorkBuddy 中直接描述实验任务即可，例如：

```
帮我完成操作系统实验二：进程控制与进程调度
```

AI 会自动按 5 个阶段推进，每个阶段结束时等待用户确认。

## 项目结构

```
os-experiment-workflow/
├── SKILL.md                    # 核心流程编排（5 阶段工作流）
├── README.md                   # 本文件
├── requirements.txt            # Python 依赖
├── LICENSE                    # MIT License
├── references/
│   ├── vm_connection.md       # VM 连接参数与截图步骤
│   └── report_format.md      # 报告格式规范
└── scripts/
    ├── build_report.py         # 报告生成脚本
    └── crop_screenshots.py    # 截图裁剪脚本
```

## 支持的实验

| 实验 | 标题 | 类型 |
|------|------|------|
| 实验一 | 实验环境搭建与使用 | 验证型 |
| 实验二 | 进程控制与进程调度 | 设计型 |
| 实验三 | 进程同步 | 设计型 |
| 实验四 | 内存管理 | 综合型 |

## 注意事项

- 模板 .doc 文件需先另存为 .docx（Transitional OOXML 格式，非 Strict）
- 截图功能需要 VM 图形界面处于登录状态（非 GDM 锁屏）
- 报告生成后建议人工复核内容准确性

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

## 作者

wistfully-maker
