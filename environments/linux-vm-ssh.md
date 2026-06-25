# Linux VM（SSH）环境配置

本文件描述当实验代码运行在**远程 Linux 虚拟机**（通过 SSH 连接）时的操作规范。

---

## 环境特征

| 项目 | 说明 |
|------|------|
| 连接方式 | SSH（`ssh user@host`） |
| 代码运行位置 | 远程 Linux 文件系统 |
| 截图方式 | 在远程 X 图形桌面上启动终端，用 `gnome-screenshot` 捕获 |
| 关键约束 | SSH 伪终端 ≠ X display，截图需要 X 桌面处于解锁状态 |

---

## VM 连接参数（示例）

以下为示例参数，实际使用时根据用户环境填写：

| 参数 | 示例值 |
|------|---------|
| IP 地址 | `192.168.x.x` |
| 用户名 | `lalala` |
| SSH 密钥 | `~/.ssh/id_rsa` |
| 工作目录 | `/home/<user>/program_sec/os/experiment{N}/` |
| 截图脚本 | `/home/<user>/vm_screenshot.sh` |

---

## SSH 命令模板

```bash
# 基础 SSH（在沙箱环境中需显式指定密钥）
SSH_CMD="ssh -i /path/to/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null user@host"

# SCP 上传
SCP_CMD="scp -i /path/to/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# 上传文件
$SCP_CMD local_file.c user@host:/remote/path/

# 远程执行命令
$SSH_CMD 'cd /remote/path && gcc file.c -o file && ./file'
```

---

## 截图工作流

### 前置条件

> **用户必须在 VM 图形界面中登录**（GDM 不能处于锁屏状态）。
> SSH 会话 ≠ X 图形桌面，命令在 SSH 伪终端中执行，截图需要显示在 X 桌面上。

### 步骤

1. **用户登录 VM 图形界面**（解锁 GDM）

2. **SSH 连接，设置 X 环境变量**：

```bash
export DISPLAY=:0
export XAUTHORITY=/home/<user>/.Xauthority
```

3. **在 X 桌面上启动终端并执行命令**：

```bash
gnome-terminal --maximize -- bash -c '命令1; 命令2; ...; sleep 12' &
sleep 3  # 等待窗口出现
```

4. **运行截图脚本**：

```bash
sudo bash /home/<user>/vm_screenshot.sh <user> /tmp/xxx.png
```

5. **SCP 拉回本地**：

```bash
scp -i /path/to/id_rsa user@host:/tmp/xxx.png local_path
```

6. **⚠️ 截图后必须清理**：

```bash
pkill -f gnome-terminal
```

---

## 截图后处理

全屏截图包含大量空白（桌面 + 终端空白区），需用 PIL 裁剪：

- 去掉标题栏/菜单栏（y < 90）
- 裁剪到文字内容区域（约 x:5-650, y:90-700，实际因内容而异）
- 裁剪后图片尺寸约 645×460~700px

使用 `scripts/crop_screenshots.py` 自动裁剪。

---

## 关键教训

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| 截图全黑 | GDM 锁屏，X 桌面不可见 | 用户手动登录图形界面后重试 |
| 截图蓝屏 | GDM 登录界面，无用户桌面 | 用户完成登录后重试 |
| gnome-terminal 无法启动 | dbus 连接问题 / XAUTHORITY 未设置 | 设置 `export XAUTHORITY=/home/<user>/.Xauthority` |
| `--disable-factory` 不支持 | CentOS 7 的 gnome-terminal 不支持该参数 | 移除该参数 |
| 多张截图内容叠加 | 上一张截图的终端窗口未清理 | 每张截图后执行 `pkill -f gnome-terminal` |

---

## 工具链检查清单

在 Phase 2 环境检查中，对 Linux VM 环境需额外检查：

| 工具 | 检查命令 | 用途 |
|------|----------|------|
| gcc | `gcc --version` | 编译 C 程序 |
| gnome-terminal | `which gnome-terminal` | 在 X 桌面显示终端 |
| 截图脚本 | `test -f /home/<user>/vm_screenshot.sh` | 捕获终端内容 |
| sudo | `sudo -n true` | 截图脚本需要 sudo |
| gnome-screenshot | `which gnome-screenshot` | 截图工具 |
| xterm（备选） | `which xterm` | gnome-terminal 失败时的备选终端 |
