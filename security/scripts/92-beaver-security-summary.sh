[ -t 1 ] || return 0
[ -n "$BEAVER_SHOW_BANNER" ] || [ "$USER" != "ubuntu" ] || [ -z "$SSH_CONNECTION" ] || return 0

NAT_IP="10.0.1.49"
warn=()

# 1. 실패한 SSH 로그인 (24h) - 5회 이상일 때만
fails=$(sudo -n journalctl -u ssh -u ssh.socket --since "24 hours ago" --no-pager 2>/dev/null | grep -c "Failed password\|Invalid user")
[ "${fails:-0}" -ge 5 ] && warn+=("[주의] SSH 로그인 실패 ${fails}회 (24h) -> sudo journalctl -u ssh --since '24 hours ago'")

# 2. 직전 접속이 허용 경로(NAT, Tailscale) 외일 때만
prev=$(last -n 3 -a -w "$USER" 2>/dev/null | grep -E "pts/|tty" | sed -n '2p')
if [ -n "$prev" ]; then
  p_tty=$(echo "$prev" | awk '{print $2}')
  p_ip=$(echo "$prev" | awk '{print $NF}')
  if [ -n "$p_ip" ] && [ "$p_ip" != "$NAT_IP" ] && [ "$p_ip" != "$p_tty" ] && [[ "$p_ip" != 100.* ]]; then
    warn+=("[주의] 허용 경로 외 접속 기록 -> last -a $USER")
  fi
fi

# 3. 패스워드 만료 7일 이내일 때만
exp=$(chage -l "$USER" 2>/dev/null | awk -F': ' '/Password expires/{print $2}')
if [ -n "$exp" ] && [ "$exp" != "never" ]; then
  d=$(( ( $(date -d "$exp" +%s) - $(date +%s) ) / 86400 ))
  [ "$d" -le 7 ] && warn+=("[주의] 패스워드 만료 ${d}일 전 -> passwd")
fi

# 4. 현재 실패 상태인 서비스
failed=$(systemctl --failed --no-legend 2>/dev/null | wc -l)
[ "${failed:-0}" -gt 0 ] && warn+=("[경고] 실패한 서비스 ${failed}건 -> systemctl --failed")

# 5. 최근 10분 시스템 오류 로그
errs=$(sudo -n journalctl -p err --since "10 minutes ago" --no-pager -q 2>/dev/null | wc -l)
[ "${errs:-0}" -gt 0 ] && warn+=("[주의] 최근 10분 시스템 오류 ${errs}건 -> sudo journalctl -p err --since '10 minutes ago'")

# 6. 보안 설정 변경 (최근 1시간)
chg=$(sudo -n find /etc/ssh /etc/sudoers.d /etc/pam.d -type f -mmin -60 ! -name 'ssh_host_*' ! -name '*.bak' 2>/dev/null | wc -l)
[ "${chg:-0}" -gt 0 ] && warn+=("[주의] 보안 설정 변경 ${chg}건 (1시간) -> sudo find /etc/ssh /etc/sudoers.d /etc/pam.d -type f -mmin -60")

# 7. 디스크 90% 이상
disk=$(df / --output=pcent 2>/dev/null | tail -1 | tr -dc '0-9')
[ "${disk:-0}" -ge 90 ] && warn+=("[경고] 디스크 사용률 ${disk}% -> df -h")

# 8. 핵심 서비스 (kubelet, containerd)
for s in snap.kubelet-eks.daemon containerd; do
  systemctl is-active --quiet "$s" 2>/dev/null || warn+=("[경고] 서비스 중지: ${s##*.} -> systemctl status $s")
done

# 9. Tailscale 연결 확인
tailscale ip -4 >/dev/null 2>&1 || warn+=("[경고] Tailscale 연결 끊김 -> tailscale status")

# 10. 메모리 90% 이상
mem=$(free | awk '/Mem:/{printf "%d", $3/$2*100}')
[ "${mem:-0}" -ge 90 ] && warn+=("[경고] 메모리 사용률 ${mem}% -> free -h")

# 결과 출력
if [ "${#warn[@]}" -gt 0 ]; then
  echo "---- 점검 필요 (${#warn[@]}건) ----"
  printf '%s\n' "${warn[@]}"
  echo "-----------------------------"
else
  echo "점검 결과: 이상 없음"
fi
unset warn
