#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实验执行环境自主判定。

目的：让工作流自己判断该用「Windows 本机终端」还是「Linux VM(SSH)」那一套截图方法，
而不是每次都去问用户。判定的依据是三类硬信号：

  1. 实验指导文件里写明的平台（最权威，有就一票定音）
  2. 本机是否已具备实验所需的可执行程序
  3. 是否存在可用的 SSH 目标（~/.ssh/config 里能解析出主机；可选真连一下）

用法：
    python detect_env.py --needs mongod,mongosh --ssh-alias master --guide-platform windows
    python detect_env.py --needs gcc,make --guide-platform linux --test-ssh
    python detect_env.py --needs python3 --json

退出码恒为 0（这是**建议性**探测，不是校验）。
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys

IS_WIN = os.name == 'nt'

# 找可执行文件时额外扫的根目录（浅扫，深度受限，避免拖慢）
DEFAULT_ROOTS_WIN = [
    r'C:\Program Files', r'C:\Program Files (x86)',
    os.path.expandvars(r'%LOCALAPPDATA%\Programs'),
    r'D:\software', r'D:\Program Files',
]
DEFAULT_ROOTS_POSIX = ['/usr/local/bin', '/usr/bin', '/opt']


def find_exe(name, roots, max_depth=4):
    """先在 PATH 里找，再在给定根目录下浅扫。返回绝对路径或 None。"""
    p = shutil.which(name)
    if p:
        return p
    if IS_WIN and not name.lower().endswith('.exe'):
        p = shutil.which(name + '.exe')
        if p:
            return p
    wanted = [name.lower() + '.exe', name.lower()] if IS_WIN else [name.lower()]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        base_depth = root.rstrip('\\/').count(os.sep)
        for cur, dirs, files in os.walk(root):
            if cur.count(os.sep) - base_depth >= max_depth:
                dirs[:] = []
                continue
            # 跳过明显的无关大目录
            dirs[:] = [d for d in dirs if d.lower() not in
                       ('node_modules', '.git', 'cache', 'temp', 'tmp', 'logs', 'data')]
            for f in files:
                if f.lower() in wanted:
                    return os.path.join(cur, f)
    return None


def parse_ssh_config():
    """解析 ~/.ssh/config，返回 {alias: {hostname, user, port}}。"""
    cfg = os.path.expanduser('~/.ssh/config')
    hosts = {}
    if not os.path.isfile(cfg):
        return hosts
    cur = None
    try:
        with open(cfg, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                line = line.split('#')[0].strip()
                if not line:
                    continue
                m = re.match(r'^Host\s+(.+)$', line, re.I)
                if m:
                    aliases = m.group(1).split()
                    # 过滤通配项
                    cand = [a for a in aliases if not any(c in a for c in '*?!')]
                    cur = cand[0] if cand else None
                    if cur:
                        hosts.setdefault(cur, {})
                    continue
                if cur is None:
                    continue
                m = re.match(r'^\s*(\w+)\s+(.+?)\s*$', line)
                if m:
                    k, v = m.group(1).lower(), m.group(2)
                    if k in ('hostname', 'user', 'port'):
                        hosts[cur][k] = v
    except Exception:
        pass
    return hosts


def ssh_reachable(alias, timeout=6):
    """真连一下（BatchMode 免交互），只做一次轻量探测。"""
    try:
        r = subprocess.run(
            ['ssh', '-o', 'BatchMode=yes', '-o', f'ConnectTimeout={timeout}',
             '-o', 'StrictHostKeyChecking=accept-new', alias, 'echo __ok__'],
            capture_output=True, text=True, timeout=timeout + 6)
        return '__ok__' in (r.stdout or '')
    except Exception:
        return False


def verdict_of(guide_platform, tools, ssh_alias, ssh_info, ssh_ok, local_os):
    """判定逻辑，按优先级返回 (verdict, reason)。"""
    missing = [k for k, v in tools.items() if not v]
    has_ssh = bool(ssh_alias and ssh_info is not None)
    ssh_ready = has_ssh and (ssh_ok is not False)

    # 1) 指导文件写明了平台 —— 最权威
    if guide_platform == 'windows':
        if local_os != 'windows':
            return 'need-user', (
                f'指导文件要求 Windows，但当前系统是 {local_os}，与要求不符，需与用户确认')
        if missing:
            return 'windows-local', (
                f'指导文件明确要求 Windows 平台 → 走本机终端截图。'
                f'但本机缺少 {"、".join(missing)}，**先把工具装齐再开始 Phase 3**')
        return 'windows-local', '指导文件明确要求 Windows 平台，且本机所需工具齐备'

    if guide_platform == 'linux':
        if has_ssh and ssh_ok is not False:
            return 'linux-vm-ssh', '指导文件要求 Linux，且检测到可用 SSH 目标'
        if ssh_alias and not has_ssh:
            return 'need-user', (
                f'指导文件要求 Linux，但 ~/.ssh/config 里找不到别名 {ssh_alias!r}，请用户确认连接方式')
        return 'need-user', '指导文件要求 Linux，但没有可用的 SSH 目标，需询问用户'

    # 2) 指导文件没说平台 —— 看本机工具是否齐备
    if not missing:
        return f'{local_os}-local', (
            f'指导文件未写明平台；本机所需工具（{"、".join(tools)}）齐备 → 优先走本机，环节最少')

    # 3) 本机缺工具，看有没有 SSH 目标
    if has_ssh and ssh_ok is not False:
        return 'linux-vm-ssh', (
            f'指导文件未写明平台；本机缺少 {"、".join(missing)}，'
            f'但检测到可用 SSH 目标 {ssh_alias!r} → 走 SSH')
    if has_ssh:
        return 'need-user', (
            f'本机缺少 {"、".join(missing)}；SSH 目标 {ssh_alias!r} 存在但连不上，需用户确认')
    return 'need-user', (
        f'指导文件未写明平台、本机缺少 {"、".join(missing)}、且没有检测到 SSH 目标，需询问用户')


PLAYBOOK = {
    'windows-local': {
        'env_doc': 'environments/windows-local.md',
        'capture': 'scripts/winterm.py（驱动用户手动打开的终端 + 抓窗口区域）',
        'crop': 'scripts/crop_console.py --top 62 --side 12 --bottom-inset 20',
        'user_action': '手动打开一个**普通**（非管理员）PowerShell 窗口并保持前台；'
                       '管理员权限的命令另开提权窗口，由用户自己敲、AI 只抓屏',
        'caveats': ['平台禁止程序化启动终端窗口，终端必须用户手动开',
                    '抢焦点失败必须立刻中止，绝不能继续发按键',
                    '命令一律用剪贴板粘贴发送，避开 mongosh 等 REPL 的自动补全弹窗',
                    '先按行数预算估算窗口高度（1240px≈43 行，1500px≈53 行）'],
    },
    'linux-vm-ssh': {
        'env_doc': 'environments/linux-vm-ssh.md',
        'capture': 'scripts/vm_shot.sh（expect 驱动真实交互式 bash + gnome-screenshot -w）',
        'crop': 'scripts/crop_screenshots.py --skip-top 37 --margin 8 --uniform-width',
        'user_action': '保证 VM 的 X 桌面已登录且未锁屏（截图前脚本会 xset/loginctl 唤醒）',
        'caveats': ['不能用 gnome-terminal（root 下连不上 dbus），用 xterm',
                    '截图前必须 xset dpms force on + loginctl unlock-session',
                    '脚本上传后先 sed -i \'s/\\r$//\' 去 CRLF'],
    },
    'darwin-local': {
        'env_doc': None,
        'capture': 'screencapture 命令',
        'crop': 'scripts/crop_screenshots.py',
        'user_action': '无（本机可见终端）',
        'caveats': ['macOS 没有「禁止启动终端」的限制，可直接开 Terminal 执行'],
    },
    'need-user': {
        'env_doc': None,
        'capture': None, 'crop': None,
        'user_action': '向用户说明判定不确定的原因，请其明确执行环境',
        'caveats': ['不要猜——环境选错会让整套截图白做'],
    },
}


def main():
    ap = argparse.ArgumentParser(description='实验执行环境自主判定')
    ap.add_argument('--guide-platform', choices=['windows', 'linux', 'unknown'],
                    default='unknown',
                    help='从实验指导文件里读到的平台要求（最权威的信号）')
    ap.add_argument('--needs', default='',
                    help='实验所需的可执行程序，逗号分隔，如 mongod,mongosh')
    ap.add_argument('--ssh-alias', default='',
                    help='候选 SSH 别名（不填则自动取 ~/.ssh/config 里第一个可用别名）')
    ap.add_argument('--test-ssh', action='store_true',
                    help='真的试连一次 SSH（慢几秒，但结论最准）')
    ap.add_argument('--search-roots', default='',
                    help='额外搜索根目录，逗号分隔（PATH 找不到可执行文件时用）')
    ap.add_argument('--json', action='store_true', help='以 JSON 输出')
    a = ap.parse_args()

    local_os = ('windows' if IS_WIN else
                'darwin' if platform.system() == 'Darwin' else 'linux')

    needs = [x.strip() for x in a.needs.split(',') if x.strip()]
    roots = DEFAULT_ROOTS_WIN if IS_WIN else DEFAULT_ROOTS_POSIX
    if a.search_roots:
        roots = [x.strip() for x in a.search_roots.split(',') if x.strip()] + roots

    tools = {n: find_exe(n, roots) for n in needs}

    ssh_hosts = parse_ssh_config()
    alias = a.ssh_alias.strip()
    if not alias and ssh_hosts:
        alias = sorted(ssh_hosts)[0]
    ssh_info = ssh_hosts.get(alias) if alias else None
    ssh_ok = None
    if alias and a.test_ssh and ssh_info is not None:
        ssh_ok = ssh_reachable(alias)

    verdict, reason = verdict_of(a.guide_platform, tools, alias, ssh_info, ssh_ok, local_os)
    play = PLAYBOOK[verdict]

    result = {
        'local_os': local_os,
        'guide_platform': a.guide_platform,
        'needs': needs,
        'local_tools': {k: v for k, v in tools.items()},
        'missing_tools': [k for k, v in tools.items() if not v],
        'ssh_config_hosts': list(ssh_hosts.keys()),
        'ssh_alias': alias or None,
        'ssh_info': ssh_info,
        'ssh_test': ssh_ok,
        'verdict': verdict,
        'reason': reason,
        'playbook': play,
    }

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print('=' * 66)
    print('  实验执行环境判定')
    print('=' * 66)
    print(f'  本机系统        : {local_os}')
    print(f'  指导文件平台    : {a.guide_platform}')
    print(f'  所需程序        :')
    for k, v in tools.items():
        print(f'      {"✅" if v else "❌"} {k:<12} {v or "未找到"}')
    if not needs:
        print('      (未指定 --needs)')
    print(f'  SSH config 别名 : {", ".join(ssh_hosts) or "（无配置或解析不到）"}')
    print(f'  选定 SSH 别名   : {alias or "（无）"}'
          + (f'  ->  {ssh_info.get("user","?")}@{ssh_info.get("hostname","?")}' if ssh_info else ''))
    if a.test_ssh:
        print(f'  SSH 实连测试    : {"✅ 通" if ssh_ok else ("❌ 不通" if ssh_ok is False else "未测")}')
    print('-' * 66)
    print(f'  ▶ 判定结果      : {verdict}')
    print(f'    理由          : {reason}')
    print('-' * 66)
    if play['env_doc']:
        print(f'  环境必读文档    : {play["env_doc"]}')
    if play['capture']:
        print(f'  截图执行方式    : {play["capture"]}')
        print(f'  裁剪方式        : {play["crop"]}')
    print(f'  需要用户做的    : {play["user_action"]}')
    if play['caveats']:
        print('  该环境注意事项  :')
        for c in play['caveats']:
            print(f'      · {c}')
    print('=' * 66)


if __name__ == '__main__':
    main()
