# Linux VM（SSH）环境配置

本文件描述实验在**远程 Linux 虚拟机**（通过 SSH 连接）上执行时的环境规范。

> **通用截图质量规范（真实终端原则、行数预算、裁剪策略、QC 清单）见
> `references/screenshot-quality.md`** —— 那部分与执行环境无关，本文件只写
> Linux VM 特有的内容。
>
> **2026-09 实测修订**：早期版本推荐 `gnome-terminal` + 全屏截图 + 固定像素裁剪，
> 在 CentOS 7.9 + GNOME Classic 环境下**不可用**（root 身份下 gnome-terminal 无法连接
> 会话 dbus）。现改为 **xterm + `gnome-screenshot -w` 窗口截图**，全部结论均来自实测。

---

## 环境特征

| 项目 | 说明 |
|------|------|
| 连接方式 | SSH（`ssh user@host`） |
| 命令执行位置 | 远程 Linux（SSH 伪终端） |
| 截图方式 | 在远程 X 桌面用 **xterm** 显示命令，用 `gnome-screenshot -w` 截窗口 |
| 关键约束 | SSH 伪终端 ≠ X display；截图需要 X 桌面**已解锁且屏幕未被 DPMS 关闭** |

---

## 连接参数（示例）

| 参数 | 示例值 |
|------|---------|
| IP 地址 | `192.168.5.135` |
| 主机名 | `master` |
| 登录用户 | `hadoop`（或 `lalala`） |
| SSH 密钥 | `~/.ssh/id_rsa` |
| **桌面会话用户** | `lalala`（X display `:0` 的持有者，与登录用户可能不同！） |

---

## SSH 命令模板

```bash
# 屏蔽 known_hosts 写入：用户名含中文时，Git Bash 路径编码会报错
SSH="ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
     -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@host"
SCP="scp -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no \
     -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

$SCP scripts/vm_shot.sh steps/s01.sh user@host:/tmp/
$SSH 'sed -i "s/\r$//" /tmp/*.sh; sudo bash /tmp/vm_shot.sh /tmp/s01.png /tmp/s01.sh'
$SCP user@host:/tmp/s01.png ./screenshots/raw/
```

> **CRLF**：Windows 本地编辑的 `.sh` 上传后必须先 `sed -i 's/\r$//' 文件`，
> 否则远程 bash 报 `$'\r': command not found`。

> **SSH 操作必须前台执行**：若宿主环境有文件系统沙箱（如 WorkBuddy），
> 后台任务读不到 `~/.ssh/id_rsa`，会报 `Permission denied (publickey)`。
> 前台执行可走提权通道绕过沙箱。

---

## 权限模型

| 需求 | 做法 | 说明 |
|------|------|------|
| 以 root 执行实验命令 | `sudo -n`（NOPASSWD） | 先确认 `sudo -n true` 成功；不满足则需用户配置或提供密码 |
| 读桌面用户的 Xauthority | **必须以 root 运行截图脚本** | `/home/<桌面用户>/.Xauthority` 通常是 `600`，普通用户读不到 |
| 解锁桌面 | `loginctl unlock-session <SID>` | **免密码**，root 可直接解锁 GNOME 锁屏 |

---

## 截图链路

### 一、确认桌面会话

```bash
who -u                       # 看 :0 的持有者
loginctl list-sessions       # 看 Type/Active，确认 x11 会话处于活动状态
ls /tmp/.X11-unix/           # 应看到 X0
```

### 二、环境就绪（漏了任何一项都会白截）

| 问题 | 现象 | 处理 |
|------|------|------|
| DPMS 关屏 | 截图**纯黑**（`xset q` 显示 `Monitor is Off`） | `xset -dpms; xset s off; xset dpms force on` |
| 会话已锁 | 截图是**蓝色时钟锁屏页**（`LockedHint=yes`） | `loginctl unlock-session <SID>` |
| **PackageKit 抢 yum 锁** | yum 命令刷出 ≈40 行 `waiting for it to exit`，**把开头命令挤出画面** | `systemctl stop packagekit; systemctl mask packagekit; rm -f /var/run/yum.pid` |

> PackageKit 这一条是踩出来的：GNOME 桌面的后台包管理器会定期占用 yum 锁。
> 症状极其隐蔽——日志里看是"命令执行正常"，但截图的**开头命令消失了**。

### 三、执行与截图（用技能自带脚本）

```bash
scp scripts/vm_shot.sh user@host:/tmp/
sudo bash /tmp/vm_shot.sh /tmp/s01.png /tmp/steps/s01.sh
```

`scripts/vm_shot.sh` 已封装：唤醒屏幕、解锁会话、清理残留、**expect 驱动真实交互式
bash**、轮询 done 标记等命令跑完、窗口截图、留存会话记录。
可配置项见脚本头部注释（`SHOT_GEO` / `SHOT_BG` / `SHOT_FONT` / `SHOT_DESKTOP_USER` …）。

**产出**：`/tmp/s01.png`（窗口截图）+ `/tmp/_shot_log.txt`（会话记录，撰写报告用）。

### 四、VM 实测的裁剪参数

```bash
python scripts/crop_screenshots.py raw/ cropped/ \
    --skip-top 37 --margin 8 --uniform-width
```

| 参数 | 值 | 说明 |
|------|-----|------|
| `--skip-top` | `37` | GNOME 标题栏高度，实测固定 37px；**不跳过会被当成内容** |
| `--margin` | `8` | 紧贴内容；留白版可用 30 |
| `--uniform-width` | — | 统一宽度 + 高度紧贴（推荐） |

实测尺寸对照（xterm 几何 `108x32` + DejaVu Sans Mono fs=14）：

| 阶段 | 尺寸 |
|------|------|
| 窗口截图 | `1207 × 777`（恒定） |
| 紧贴裁剪后 | 宽 `1197` 恒定，高随内容（实测 331~653） |

---

## 为什么必须用 xterm，不能是 gnome-terminal

root 身份下启动 gnome-terminal 会失败：

```
Error constructing proxy for org.gnome.Terminal:/org/gnome/Terminal/Factory0:
Could not connect: No such file or directory
```

原因：gnome-terminal 通过会话 dbus 与 `gnome-terminal-server` 通信，而

- `/run/user/<uid>/bus` 在该环境下**不存在**（实际总线是 abstract socket，
  形如 `unix:abstract=/tmp/dbus-XXXX`）
- root 身份无法访问桌面用户的会话总线

已尝试并失败的方式：`sudo -u <用户> ... gnome-terminal`、
`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`、`unix:abstract=...`。

**xterm 不依赖 dbus，是可靠方案。**

### 字体选择

| 输出内容 | 推荐字体 |
|----------|----------|
| 纯英文（命令与输出都是英文，最常见） | `DejaVu Sans Mono` —— 系统标准等宽字体，**最像真实终端** |
| 含中文 | `WenQuanYi Micro Hei Mono`（文泉驿等宽微米黑） |

xterm **不做字体回退**，所以字体选错时中文会直接变成方块。

> 副作用：两种字体的字符宽度不同，**换字体会改变窗口宽度**，
> 裁剪矩形要跟着重新测量。

---

## 命令脚本的写法

1. **只写真正的命令**，不要 `echo` 提示符（提示符由 bash 输出）。
2. **不要用 heredoc**：多行输入会让 PS2 提示符渲染错乱（`> > > >` 挤在一行且命令丢失）。
   写文件请用逐行 `echo ... >` / `>>`：

```bash
mkdir -p /etc/docker
echo '{' > /etc/docker/daemon.json
echo '  "registry-mirrors": ["https://docker.m.daocloud.io"]' >> /etc/docker/daemon.json
echo '}' >> /etc/docker/daemon.json
cat /etc/docker/daemon.json
```

3. **控制输出行数**（见 `references/screenshot-quality.md` §三）：
   `yum -q`、`| tail -N`、`| grep -v '^$'`。

---

## 关键教训

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| 截图全黑 | DPMS 关屏 | `xset dpms force on` |
| 截图是锁屏页 | GNOME 会话已锁 | `loginctl unlock-session <SID>` |
| gnome-terminal 起不来 | root 无法连接桌面会话 dbus | 改用 **xterm** |
| 中文显示为方块 | 字体缺 CJK 字形 | 用 `WenQuanYi Micro Hei Mono` |
| **开头命令被挤出画面** | PackageKit 抢 yum 锁刷 ≈40 行 | `systemctl stop/mask packagekit` |
| 同上 | `yum makecache` 因死镜像刷大量进度行 | 用 `yum -q`；长输出 `\| tail -N` |
| heredoc 渲染错乱 | 多行输入与 PS2 提示符交互异常 | 写文件用逐行 `echo >` / `>>` |
| 裁剪图右侧出现黑带 | `PIL.Image.crop()` 越界会**补黑边** | 裁剪矩形宽度须精确等于图片宽度 |
| 换字体后裁剪错位 | 字体字符宽度不同会改变窗口宽度 | 换字体后重新测量裁剪矩形 |
| 后台任务读不到 SSH 密钥 | 宿主沙箱限制后台进程读 `~/.ssh` | SSH 操作放前台执行 |

---

## 工具链检查清单

Phase 2 环境检查时对 Linux VM 额外检查：

| 工具 | 检查命令 | 用途 | 缺失时 |
|------|----------|------|--------|
| xterm | `which xterm` | 在 X 桌面显示终端（**首选**） | 装 `xterm` |
| gnome-screenshot | `which gnome-screenshot` | 截图 | 装 `gnome-screenshot` |
| xset | `which xset` | 唤醒屏幕 / 关 DPMS | 装 X 工具集 |
| xwininfo | `which xwininfo` | 查询窗口几何（调试） | 装 `xorg-x11-utils` |
| loginctl | `which loginctl` | 解锁会话 | systemd-logind |
| **expect** | `which expect` | **驱动真实交互式 bash** | 装 `expect`（必需！） |
| 中文/等宽字体 | `fc-list :spacing=mono family` | xterm 字体 | 装 `wqy-microhei-fonts` / `dejavu-sans-mono-fonts` |
| sudo 免密 | `sudo -n true` | 非交互执行 root 命令 | 需用户配置 NOPASSWD |

> `gnome-terminal` 不再作为必需项（root 身份下不可用）。
> `xdotool` / `wmctrl` / `scrot` / ImageMagick `import` 通常**未安装**，不要依赖。
