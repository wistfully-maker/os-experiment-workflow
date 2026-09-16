#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
驱动一个「用户已经打开的」Windows 终端窗口：激活 -> 输入 -> 截图。

不做任何进程创建。只对已存在的窗口发键盘输入并抓窗口区域。

用法:
  python winterm.py list
  python winterm.py type  --title PowerShell --text "net start MongoDB" [--wait 3] [--enter]
  python winterm.py shot  --title PowerShell --out s01.png [--pad 0]
  python winterm.py batch --title PowerShell --steps steps.json
"""
import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

user32 = ctypes.windll.user32

# ---------- DPI ----------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

# ---------- SendInput ----------
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTunion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTunion)]


def _send(*inputs):
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    sent = user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT))
    return sent


def _char_input(ch, up=False):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki = KEYBDINPUT(
        wVk=0, wScan=ord(ch),
        dwFlags=KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0),
        time=0, dwExtraInfo=None)
    return inp


def type_text(text, delay=0.012):
    """按 Unicode 逐字符发送，避免 SendKeys 的转义坑。"""
    for ch in text:
        _send(_char_input(ch, False), _char_input(ch, True))
        time.sleep(delay)


def press_enter():
    VK_RETURN = 0x0D
    for up in (False, True):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki = KEYBDINPUT(
            wVk=VK_RETURN, wScan=0,
            dwFlags=KEYEVENTF_KEYUP if up else 0,
            time=0, dwExtraInfo=None)
        _send(inp)
        time.sleep(0.03)


# ---------- 剪贴板 ----------
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

_k32 = ctypes.windll.kernel32
_k32.GlobalAlloc.restype = ctypes.c_void_p
_k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
_k32.GlobalLock.restype = ctypes.c_void_p
_k32.GlobalLock.argtypes = [ctypes.c_void_p]
_k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
user32.OpenClipboard.argtypes = [ctypes.c_void_p]


def set_clipboard(text):
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not user32.OpenClipboard(None):
        raise RuntimeError("OpenClipboard 失败")
    try:
        user32.EmptyClipboard()
        h = _k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            raise RuntimeError("GlobalAlloc 失败")
        p = _k32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        _k32.GlobalUnlock(h)
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            raise RuntimeError("SetClipboardData 失败")
    finally:
        user32.CloseClipboard()


def press_ctrl_v():
    VK_CONTROL, VK_V = 0x11, 0x56
    seq = [(VK_CONTROL, False), (VK_V, False), (VK_V, True), (VK_CONTROL, True)]
    for vk, up in seq:
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki = KEYBDINPUT(
            wVk=vk, wScan=0,
            dwFlags=KEYEVENTF_KEYUP if up else 0,
            time=0, dwExtraInfo=None)
        _send(inp)
        time.sleep(0.03)


# ---------- 窗口 ----------
def list_windows():
    res = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, l):
        if user32.IsWindowVisible(h):
            n = user32.GetWindowTextLengthW(h)
            if n:
                b = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(h, b, n + 1)
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                res.append({"hwnd": int(h), "pid": pid.value, "title": b.value})
        return True

    user32.EnumWindows(cb, 0)
    return res


def find_window(title_sub):
    cands = [w for w in list_windows() if title_sub.lower() in w["title"].lower()]
    if not cands:
        return None
    return cands[0]


def resolve_win(title=None, hwnd=None):
    """优先按句柄定位（避免在命令行里出现敏感字样）。"""
    if hwnd:
        h = int(hwnd)
        if not user32.IsWindow(h):
            return None
        n = user32.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(h, b, n + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        return {"hwnd": h, "pid": pid.value, "title": b.value}
    if title:
        return find_window(title)
    return None


def press_alt_tap():
    """轻点一下 ALT，用来解除 Windows 对 SetForegroundWindow 的限制。"""
    VK_MENU = 0x12
    for up in (False, True):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki = KEYBDINPUT(
            wVk=VK_MENU, wScan=0,
            dwFlags=KEYEVENTF_KEYUP if up else 0,
            time=0, dwExtraInfo=None)
        _send(inp)
        time.sleep(0.05)


def activate(hwnd, settle=0.5):
    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    time.sleep(0.15)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    time.sleep(settle)
    if user32.GetForegroundWindow() == hwnd:
        return True
    # 抢焦点失败：Windows 会拦非前台进程的 SetForegroundWindow，先用 ALT 解禁再试一次
    press_alt_tap()
    time.sleep(0.15)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    time.sleep(settle)
    return user32.GetForegroundWindow() == hwnd


def get_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def shot(hwnd, out, pad=0):
    # 打印窗口时前台窗口需稳定
    l, t, r, b = get_rect(hwnd)
    bbox = (max(0, l - pad), max(0, t - pad), r + pad, b + pad)
    im = ImageGrab.grab(bbox=bbox)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out)
    print(f"shot -> {out}  {im.size[0]}x{im.size[1]}  rect=({l},{t},{r},{b})", flush=True)
    return im


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")

    def add_target(p):
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--title")
        g.add_argument("--hwnd")

    p = sub.add_parser("type")
    add_target(p)
    p.add_argument("--text", default="")
    p.add_argument("--wait", type=float, default=0.0)
    p.add_argument("--enter", action="store_true")

    p = sub.add_parser("paste")
    add_target(p)
    p.add_argument("--text", required=True)
    p.add_argument("--wait", type=float, default=0.0)
    p.add_argument("--enter", action="store_true")

    p = sub.add_parser("shot")
    add_target(p)
    p.add_argument("--out", required=True)
    p.add_argument("--pad", type=int, default=0)

    p = sub.add_parser("batch")
    add_target(p)
    p.add_argument("--steps", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--paste-all", action="store_true",
                   help="所有命令行都改用剪贴板粘贴发送，避开 mongosh 自动补全弹窗干扰")

    p = sub.add_parser("resize")
    add_target(p)
    p.add_argument("--w", type=int, required=True)
    p.add_argument("--h", type=int, required=True)
    p.add_argument("--x", type=int, default=80)
    p.add_argument("--y", type=int, default=40)

    a = ap.parse_args()

    if a.cmd == "list":
        for w in list_windows():
            print(w["hwnd"], w["pid"], w["title"])
        return

    w = resolve_win(getattr(a, "title", None), getattr(a, "hwnd", None))
    if not w:
        print("ERROR: 找不到目标窗口", file=sys.stderr)
        sys.exit(2)
    hwnd = w["hwnd"]
    print(f"target hwnd={hwnd} pid={w['pid']} title={w['title']!r}", flush=True)

    if a.cmd == "resize":
        user32.ShowWindow(hwnd, 9)
        time.sleep(0.2)
        user32.MoveWindow(hwnd, a.x, a.y, a.w, a.h, True)
        time.sleep(0.5)
        l, t, r, b = get_rect(hwnd)
        print(f"resized -> ({l},{t})-({r},{b})  {r-l}x{b-t}", flush=True)
        return

    if a.cmd == "type":
        if not activate(hwnd):
            print("ABORT: 无法把目标窗口切到前台，出于安全不发任何按键", file=sys.stderr)
            sys.exit(3)
        if a.text:
            type_text(a.text)
        if a.enter:
            press_enter()
        if a.wait:
            time.sleep(a.wait)
        return

    if a.cmd == "paste":
        if not activate(hwnd):
            print("ABORT: 无法把目标窗口切到前台，出于安全不粘贴", file=sys.stderr)
            sys.exit(3)
        set_clipboard(a.text)
        time.sleep(0.2)
        press_ctrl_v()
        if a.enter:
            time.sleep(0.5)
            press_enter()
        if a.wait:
            time.sleep(a.wait)
        return

    if a.cmd == "shot":
        activate(hwnd)
        shot(hwnd, a.out, a.pad)
        return

    if a.cmd == "batch":
        steps = json.load(open(a.steps, encoding="utf-8"))
        for i, st in enumerate(steps, 1):
            # 安全退出：只有当前窗口标题里含指定字样（说明确实在 mongosh 里）才发 exit，
            # 避免误把 PowerShell 窗口关掉
            if st.get("quit_if"):
                cur = resolve_win(None, hwnd)
                title = (cur or {}).get("title", "")
                if st["quit_if"].lower() in title.lower():
                    if not activate(hwnd):
                        print(f"ABORT step{i}: 无法把窗口切到前台，停止整个批次", file=sys.stderr)
                        sys.exit(3)
                    type_text("exit", delay=0.012)
                    press_enter()
                    time.sleep(1.2)
                    print(f"step{i}: 已退出 mongosh（标题命中 {st['quit_if']!r}）", flush=True)
                else:
                    print(f"step{i}: 当前标题 {title!r} 不含 {st['quit_if']!r}，跳过 exit", flush=True)

            lines = st.get("type", [])
            if isinstance(lines, str):
                lines = [lines]
            if not activate(hwnd):
                print(f"ABORT step{i}: 无法把窗口切到前台，停止整个批次", file=sys.stderr)
                sys.exit(3)
            for ln in lines:
                if a.paste_all:
                    set_clipboard(ln)
                    time.sleep(0.15)
                    press_ctrl_v()
                    time.sleep(0.35)
                    press_enter()
                else:
                    type_text(ln, delay=st.get("delay", 0.012))
                    press_enter()
                time.sleep(st.get("line_wait", 0.6))

            # 多行整块粘贴：避免 mongosh 逐行重绘把屏幕刷满
            pastes = st.get("paste", [])
            if isinstance(pastes, str):
                pastes = [pastes]
            for tx in pastes:
                set_clipboard(tx)
                time.sleep(0.25)
                press_ctrl_v()
                time.sleep(st.get("paste_settle", 1.0))
                if st.get("paste_enter", True):
                    press_enter()
                time.sleep(st.get("paste_wait", 1.5))

            time.sleep(st.get("wait", 1.2))
            out = st.get("shot")
            if out:
                shot(hwnd, os.path.join(a.outdir, out), st.get("pad", 0))
        print("batch done", flush=True)


if __name__ == "__main__":
    main()
