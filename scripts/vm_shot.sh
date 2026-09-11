#!/bin/bash
# =============================================================================
# vm_shot.sh —— 在 Linux VM 的 X 桌面上执行命令脚本并截图（真实终端版）
# =============================================================================
#
# 用法:
#   sudo bash vm_shot.sh <输出png> <命令脚本.sh>
#
# 示例:
#   sudo bash vm_shot.sh /tmp/s01.png /tmp/steps/s01.sh
#
# 产物:
#   <输出png>            窗口截图（尺寸恒定，随窗口几何而定）
#   /tmp/_shot_log.txt   终端会话完整记录（撰写报告正文的原始依据）
#
# -----------------------------------------------------------------------------
# 可配置项（环境变量，均有默认值）:
#   SHOT_DESKTOP_USER   X display 持有者用户名           默认 lalala
#   SHOT_XAUTH          Xauthority 路径                  默认 /home/$SHOT_DESKTOP_USER/.Xauthority
#   SHOT_DISPLAY        X display                        默认 :0
#   SHOT_GEO            窗口几何                         默认 108x32+40+140
#   SHOT_FONT           字体                             默认 DejaVu Sans Mono
#   SHOT_FSIZE          字号(pt)                         默认 14
#   SHOT_BG             终端配色 black|white             默认 black
#   SHOT_WORKDIR        登录后 shell 的工作目录          默认 /root
#   SHOT_WAITMAX        等待命令执行完的最长秒数         默认 900
#
#   注意 SHOT_GEO 的行数决定"一屏能显示多少行"：
#   行数 = 窗口行数，命令脚本的输出必须 <= 行数-1 行，
#   否则最早的命令会被滚出画面（截图里就看不到"执行了什么"）。
# =============================================================================
#
# ★ 为什么用 expect 驱动真实交互式 bash ★
#
#   目标：截图里的提示符与命令回显必须是**真实终端产生的**，而不是脚本画出来的。
#
#   ❌ 错误做法 1：在命令脚本里 echo "[root@master ~]# xxx" 再执行命令
#      → 提示符是普通文本、命令无 tty 回显、输出一次性刷出，一眼看出是脚本生成
#
#   ❌ 错误做法 2：用管道定时喂命令
#        ( while read -r l; do printf '%s\n' "$l"; sleep 0.8; done < cmds ) \
#            | script -q -c "bash -i" /dev/null
#      → 与 bash 的提示符输出、readline 重绘存在竞态，表现为：
#        · 提示符连续堆积、命令回显整个丢失
#        · "没有输出的命令"(mkdir/docker tag/systemctl start) 其命令行
#          会被下一个提示符覆盖掉，截图里看不到执行了什么
#
#   ✅ 正确做法：expect「发一条 → 等提示符返回 → 再发下一条」
#      · 提示符由 bash 自己的 PS1 输出
#      · 命令由 tty 行规程回显（等同人手敲入）
#      · 输出与提示符自然交错，最后停在一个空提示符上
#      · 画面里没有任何一个像素是后期绘制的
#
#      唯一"非人为"之处是按键由程序注入而非手敲，但终端本身无法区分，
#      渲染路径与真实操作完全相同。
# =============================================================================

set -u

OUT="${1:?用法: vm_shot.sh <输出png> <命令脚本.sh>}"
CMDS="${2:?用法: vm_shot.sh <输出png> <命令脚本.sh>}"

DUSER="${SHOT_DESKTOP_USER:-lalala}"
XAUTH="${SHOT_XAUTH:-/home/$DUSER/.Xauthority}"
XDISP="${SHOT_DISPLAY:-:0}"
GEO="${SHOT_GEO:-108x32+40+140}"
FONT="${SHOT_FONT:-DejaVu Sans Mono}"
FSIZE="${SHOT_FSIZE:-14}"
BG="${SHOT_BG:-black}"
WORKDIR="${SHOT_WORKDIR:-/root}"
WAITMAX="${SHOT_WAITMAX:-900}"
TAG="REPORT_SHOT"

case "$BG" in
  black) FGI="#e6e6e6"; BGI="#0c0c0c" ;;
  *)     FGI="#000000"; BGI="#ffffff" ;;
esac

EXP="/tmp/_vm_shot.exp"
DONE="/tmp/_shot_done"
LOG="/tmp/_shot_log.txt"

export DISPLAY="$XDISP"
export XAUTHORITY="$XAUTH"

# ── 1) 唤醒屏幕（否则截图纯黑：xset q 会显示 Monitor is Off） ──
xset -dpms 2>/dev/null
xset s off 2>/dev/null
xset dpms force on 2>/dev/null

# ── 2) 解锁 GNOME 会话（免密码；否则截到蓝色锁屏页） ──
SID=$(loginctl list-sessions --no-legend 2>/dev/null | awk -v u="$DUSER" '$3==u {print $1; exit}')
if [ -n "${SID:-}" ]; then
  loginctl unlock-session "$SID" 2>/dev/null
fi
sleep 1

# ── 3) 清理上次残留 ──
pkill -f "xterm .*${TAG}" 2>/dev/null
rm -f "$DONE" "$EXP" "$LOG"
sleep 1

# ── 4) 生成 expect 脚本 ──
cat > "$EXP" << EXPEOF
#!/usr/bin/expect -f
set timeout 900
log_user 0
spawn bash -i
sleep 0.5
log_user 1
expect -re {\[root@[^\]]*\]# $}
set fh [open "$CMDS" r]
while {[gets \$fh line] >= 0} {
    set l [string trimright \$line]
    if {\$l eq ""} { continue }
    send -- "\$l\r"
    expect -re {\[root@[^\]]*\]# $}
}
close \$fh
exec touch $DONE
after 900000
EXPEOF
chmod +x "$EXP"

# ── 5) 启动 xterm ──
#   cd $WORKDIR 是必须的：否则 PS1 的 \W 会显示成 /home/xxx 而不是 ~
#   | tee 保留会话记录，报告正文可直接引用真实输出
nohup xterm -geometry "$GEO" -fa "$FONT" -fs "$FSIZE" \
    -bg "$BGI" -fg "$FGI" -bw 1 -title "$TAG" \
    -e bash -c "cd $WORKDIR && expect -f $EXP | tee $LOG" >/dev/null 2>&1 &

# ── 6) 等命令执行完（轮询 done 标记，而不是盲等固定秒数） ──
#   慢命令如 yum install 可能要几分钟，必须等它真正跑完再截图
i=0
while [ ! -f "$DONE" ] && [ "$i" -lt "$WAITMAX" ]; do
  sleep 1
  i=$((i + 1))
done
[ -f "$DONE" ] || echo "WARN: 等待超时（${WAITMAX}s），命令可能仍在执行"
sleep 3   # 等最后几行渲染完

# ── 7) 窗口模式截图（尺寸恒定，且不受桌面其它窗口干扰） ──
rm -f "$OUT" 2>/dev/null
gnome-screenshot -w -f "$OUT" 2>/dev/null
sleep 1

# ── 8) 清理终端，避免影响下一张截图 ──
pkill -f "xterm .*${TAG}" 2>/dev/null

if [ -f "$OUT" ]; then
  echo "SAVED $OUT $(stat -c %s "$OUT") bytes (等待 ${i}s)"
else
  echo "FAILED: 截图未生成"
  exit 1
fi
