[ -t 1 ] || return 0
NAT_IP="10.0.1.49"
echo "---- 보안 요약 ($USER) ----"

# 1. 실패한 SSH 로그인 (최근 24시간)
fails=$(sudo -n journalctl -u ssh -u ssh.socket --since "24 hours ago" --no-pager 2>/dev/null | grep -c "Failed password\|Invalid user")
[ "${fails:-0}" -ge 5 ] && flag=" [주의]" || flag=""
echo "실패한 SSH 시도(24h): ${fails:-0}회$flag"

# 2. 직전 접속 (시간 + 계정 + 방식), NAT 외 IP면 경고
prev=$(last -n 2 -a -w "$USER" 2>/dev/null | grep -v "still logged in" | grep -E "pts/|tty" | head -1)
if [ -z "$prev" ]; then
  prev=$(last -n 3 -a -w "$USER" 2>/dev/null | grep -E "pts/|tty" | sed -n '2p')
fi
if [ -n "$prev" ]; then
  p_tty=$(echo "$prev" | awk '{print $2}')
  p_time=$(echo "$prev" | awk '{print $4" "$5" "$6}')
  p_ip=$(echo "$prev" | awk '{print $NF}')
  case "$p_tty" in pts/*) method="SSH" ;; tty*|ttyS*) method="콘솔" ;; *) method="$p_tty" ;; esac
  line="이전 접속: $p_time | 계정 $USER | 방식 $method($p_tty)"
  if [ -n "$p_ip" ] && [ "$p_ip" != "$NAT_IP" ] && [ "$p_ip" != "$p_tty" ]; then
    line="$line | 출발지 $p_ip [주의: NAT 외 접속]"
  fi
  echo "$line"
fi

# 3. 패스워드 만료 7일 이내만
exp=$(chage -l "$USER" 2>/dev/null | awk -F': ' '/Password expires/{print $2}')
if [ -n "$exp" ] && [ "$exp" != "never" ]; then
  d=$(( ( $(date -d "$exp" +%s) - $(date +%s) ) / 86400 ))
  [ "$d" -le 7 ] && echo "패스워드 만료: ${d}일 후 ($exp)"
fi

# 4. 24시간 내 변경된 중요 설정 (최대 3개, 호스트 키 제외)
chg=$(sudo -n find /etc/ssh /etc/sudoers.d /etc/pam.d -type f -mtime -1 ! -name 'ssh_host_*' 2>/dev/null | head -3)
[ -n "$chg" ] && echo "최근 변경된 설정: $(echo $chg | tr '\n' ' ')"
echo "-----------------------------"
