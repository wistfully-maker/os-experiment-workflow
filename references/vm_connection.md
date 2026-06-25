# VM 连接与截图参考

## 基本信息

| 项 | 值 |
|----|-----|
| 操作系统 | CentOS 7 (Core), Kernel 3.10 |
| IP | 192.168.5.135 |
| 用户 | lalala |
| 免密密钥 | `/c/Users/李冠桥/.ssh/id_rsa` |
| 工作目录 | `/home/lalala/program_sec/os/experiment{N}/` |
| GCC 版本 | 4.8.5 |

## SSH 连接命令（在 WorkBuddy 沙箱中使用）

```bash
ssh -i /c/Users/李冠桥/.ssh/id_rsa \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    lalala@192.168.5.135 '命令'
```

## 截图工作流（关键！）

### 前提条件

- **用户必须在 VM 图形界面中登录**（GDM 不能处于锁屏状态）
- SSH 会话 ≠ X 图形桌面，命令在 SSH 伪终端中执行，截图需要显示在 X 桌面上
- **不能在 SSH 中直接截图**——gnome-screenshot 只能拍 X 显示器 :0 上的内容

### 完整步骤

#### 步骤 1：用户解锁 GDM

用户在 VMware/VirtualBox 控制台中登录，使桌面可见。**如果没有这一步，截图将全是 GDM 锁屏蓝屏。**

#### 步骤 2：在 X 桌面上启动 gnome-terminal

```bash
ssh ... lalala@192.168.5.135 '
export DISPLAY=:0
export XAUTHORITY=/home/lalala/.Xauthority

# 启动终端窗口，执行命令，保持打开
gnome-terminal --maximize -- bash -c "
echo '=== 命令标题 ==='
echo
echo '[lalala@master dir]$ 命令1'
命令1
echo
echo '[lalala@master dir]$ 命令2'
命令2
sleep 12  # 保持窗口打开供截图
" &
sleep 3  # 等待窗口渲染
'
```

#### 步骤 3：执行截图

```bash
ssh ... lalala@192.168.5.135 '
sudo bash /home/lalala/vm_screenshot.sh lalala /tmp/exp{N}_X.png
'
```

#### 步骤 4：SCP 拉回本地

```bash
scp -i /c/Users/李冠桥/.ssh/id_rsa \
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    lalala@192.168.5.135:/tmp/exp{N}_X.png \
    /d/program_sec/操作系统/实验报告/实验{N}/screenshots/exp{N}_X.png
```

#### 步骤 5：清理终端窗口

```bash
ssh ... lalala@192.168.5.135 'pkill -f gnome-terminal'
```

**⚠️ 必须清理！** 否则多个终端窗口叠加，下一轮截图会包含旧窗口。

### 关键教训

1. **gnome-terminal 参数 `--disable-factory` 不被支持**（CentOS 7），不要使用
2. **不要用 `sudo -u lalala gnome-terminal`**——XAuth 权限可能导致窗口无法显示，直接用 lalala 身份
3. **每轮截图后必须 pkill gnome-terminal**
4. **截图脚本需要 sudo**（lalala 用户已配置无密码 sudo）
5. **如果截图结果为全黑**→ GDM 已进入屏保/锁屏，需用户手动解锁
6. **如果截图结果为蓝屏**→ GDM 锁屏未解除
7. **xdotool / wmctrl 未安装在 CentOS 7 上**，不要依赖它们
8. **xterm 不可用**（未安装），只能用 gnome-terminal

### gnome-terminal 参数

| 参数 | 效果 |
|------|------|
| `--maximize` | 全屏启动（推荐，让命令占尽可能大面积） |
| `-- bash -c '...'` | 执行 bash 命令 |
| `&` | 后台运行，SSH 可以继续执行后续命令 |
| `sleep N` | 保持终端打开 N 秒（需 > 截图延迟） |

### 截图脚本位置

VM 上：`/home/lalala/vm_screenshot.sh`
用法：`sudo bash /home/lalala/vm_screenshot.sh lalala /tmp/output.png`
