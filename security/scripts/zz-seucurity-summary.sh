sudo tee /etc/profile.d/zz-security-summary.sh > /dev/null <<'EOF'
[ -t 1 ] || return 0
echo "---- 보안 요약 ($USER) ----"

# 1. 실패한 SSH 로그인 (최근 24H)
fails=$(sudo -n journalctl -u ssh -u ssh.socket --since "24 hours ago" --no-pager 2>/dev/null | grep -c "Failed password\|Invalid user")
[ "${fails:-0}" -ge 5 ] && flag=" [주의]" || flag=""
echo "실패한 SSH 시도(24h): ${fails:-0}회$flag"

# 2. 마지막 접속
last -n 2 -a "$USER" 2>/dev/null | sed -n '2p' | awk '{print "이전 접속: "$4" "$5" "$6" "$7" "$NF}'

# 3. 패스워드 만료 7일 이내만
exp=$(chage -l "$USER" 2>/dev/null | awk -F': ' '/Password expires/{print $2}')
if [ -n "$exp" ] && [ "$exp" != "never" ]; then
  d=$(( ( $(date -d "$exp" +%s) - $(date +%s) ) / 86400 ))
  [ "$d" -le 7 ] && echo "패스워드 만료: ${d}일 후 ($exp)"
fi

# 4. 24H 내 변경된 중요 설정 (최대 3개)
chg=$(sudo -n find /etc/ssh /etc/sudoers.d /etc/pam.d -type f -mtime -1 2>/dev/null | head -3)
[ -n "$chg" ] && echo "최근 변경된 설정: $(echo $chg | tr '\n' ' ')"
echo "-----------------------------"
EOF