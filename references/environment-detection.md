# 执行环境自主判定

Phase 2 要做的事：**自己判断这个实验该用哪一套截图方法**，而不是每次都去问用户。
只有判定不出唯一结论时，才允许回头问。

---

## 一、先理解两类环境的本质差异

判定的核心不是"代码在哪跑"，而是**AI 在这个环境里能做到什么**。
两套截图方法之所以不同，根源是下面这张能力矩阵：

| 能力 | Windows 本机 | Linux VM（SSH） |
|------|--------------|-----------------|
| AI 能否自己"打开"终端 | ❌ **平台禁止**程序化启动终端窗口 | ✅ 不需要 GUI 终端，ssh 进来即可 |
| AI 能否自己执行命令 | ✅ 本地 shell | ✅ ssh |
| 命令回显是否真实 | ✅ 用户窗口内由 PSReadLine 回显 | ✅ `expect` 驱动 `bash -i`，由行规程回显 |
| AI 能否程序化"发输入" | ✅ 可驱动**用户已打开**的窗口（剪贴板粘贴 + 键盘） | ✅ expect 直接驱动 |
| 提权（管理员/root）命令 | ⚠️ **驱动不了提权窗口**（UIPI 拦截跨完整性级别输入），但**抓屏不受限** → 用户敲、AI 抓图 | ✅ `sudo` 直接在 ssh 里用，无此限制 |
| 抓图方式 | PIL `ImageGrab` 抓窗口区域 | `gnome-screenshot -w` 抓 X 桌面 |
| 裁剪脚本 | `scripts/crop_console.py` | `scripts/crop_screenshots.py` |
| 每次要用户做的 | **手动开一个普通终端窗口** | 保证 X 桌面已登录未锁屏 |

**一句话结论**：

- **Windows**：能驱动、但**开不了窗口**，且提权窗口是盲区 → 需要用户开窗口，提权命令要用户敲
- **Linux VM**：**什么都能程序化做**（开不了 GUI 窗口也无所谓，因为根本不需要 GUI），代价是 VM 的 X 会话必须活着

> 这就是为什么 Linux VM 的流程更"自动"，而 Windows 必须拉用户配合。
> 选错环境不是效率问题，而是**有些步骤根本做不下去**。

---

## 二、判定信号（按优先级）

### 信号 1：实验指导文件里写明的平台 —— 最权威，一票定音

仔细读指导文件的"实验环境"一节。常见写法：

```
操作系统：Windows10/Windows11          → windows
数据库软件：MongoDB Community Server   → （配合上面判断）
实验环境：CentOS 7 / Ubuntu 22.04       → linux
在 Linux 服务器上完成以下操作…          → linux
```

**指导文件写了平台就照办**，哪怕本机也能跑——因为老师就是在那个环境里验收的。
反例：指导文件写"掌握 Windows 平台下 MongoDB 的安装"，那即使你有 Linux VM 也必须走本机。

### 信号 2：本机是否已具备实验所需的可执行程序

用 `shutil.which` + 常见安装目录浅扫（`scripts/detect_env.py` 已实现）。
需要哪些程序，从 Phase 1 的实验步骤里提取（如 `mongod`、`mongosh`、`gcc`、`make`）。

### 信号 3：是否存在可用的 SSH 目标

解析 `~/.ssh/config` 拿到别名与 `HostName/User/Port`；
必要时用 `ssh -o BatchMode=yes -o ConnectTimeout=6 <alias> echo ok` 真连一次
（`--test-ssh`）。**只测一次**，不要反复重试。

---

## 三、判定流程

```bash
python scripts/detect_env.py \
    --needs mongod,mongosh \
    --guide-platform windows \
    --ssh-alias master \
    --test-ssh
```

输出示例：

```
  本机系统        : windows
  指导文件平台    : windows
  所需程序        :
      ✅ mongod       D:\software\mongoDB\bin\mongod.exe
      ✅ mongosh      D:\software\mongosh.EXE
  SSH config 别名 : master, vm-lalala, vm-hadoop
  选定 SSH 别名   : master  ->  lalala@192.168.5.135
  ▶ 判定结果      : windows-local
    理由          : 指导文件明确要求 Windows 平台，且本机所需工具齐备
```

判定逻辑（脚本里已固化）：

```
1. 指导文件写明 windows
     → 本机系统确实是 windows？
         是 → windows-local（缺工具则先补齐，**不要因为缺工具就改跳 Linux**）
         否 → need-user（与要求不符，必须问用户）
2. 指导文件写明 linux
     → 有可用 SSH 目标 → linux-vm-ssh
     → 没有            → need-user
3. 指导文件没写平台
     → 本机所需工具齐   → <local_os>-local（环节最少，优先本机）
     → 本机缺工具 + 有 SSH → linux-vm-ssh
     → 都没有            → need-user
```

判定结果是 **`need-user`** 时，才按 Phase 2 检查点的口径去问用户，并说明**是哪个信号不足**。

---

## 四、确定环境后怎么走

判定结果 → 直接查下面这张路由表：

| verdict | 环境必读文档 | 截图执行 | 裁剪 | 用户必须先做 |
|---------|--------------|----------|------|--------------|
| `windows-local` | `environments/windows-local.md` | `scripts/winterm.py`（驱动用户开的窗口） | `scripts/crop_console.py` | 手动开一个**普通** PowerShell 窗口 |
| `linux-vm-ssh` | `environments/linux-vm-ssh.md` | `scripts/vm_shot.sh` | `scripts/crop_screenshots.py` | 确认 VM 的 X 桌面已登录未锁屏 |
| `darwin-local` | （无） | `screencapture` | `scripts/crop_screenshots.py` | 无 |
| `need-user` | — | — | — | 向用户说明原因并请其明确环境 |

---

## 五、两条硬经验

1. **环境切换的代价很高**——整套截图要重做。所以判定信号要一次问全、
   在 Phase 2 就定死，**Phase 3 中途不要改环境**。
   （本轮实战教训：先在本机把 26 张图都采完，才发现提权那两步在 Windows 下驱动不了，
   只能临时改成"用户敲命令、AI 抓屏"的混合模式。）

2. **提权盲区要提前规划**。判定为 `windows-local` 时，**先扫一遍实验步骤里有没有需要管理员/root 的命令**
   （`net start/stop <服务>`、改系统配置、写 Program Files 等），有的话**在做 Phase 3 计划时就把它们单独列出来**，
   安排成"用户敲命令 + AI 抓屏"，别等做一半才发现。
