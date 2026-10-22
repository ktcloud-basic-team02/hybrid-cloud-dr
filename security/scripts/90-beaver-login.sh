# [팀원 계정으로 전환된 세션] 로그인 안내
if [ -n "$BEAVER_LOGIN_AS" ]; then
    echo "'$USER' 아이디로 로그인되었습니다."
    unset BEAVER_LOGIN_AS
    return 0
fi

# [ubuntu로 SSH 접속한 대화형 터미널] 계정 선택
[ -t 0 ] && [ -t 1 ] || return 0
[ "$USER" = "ubuntu" ] && [ -n "$SSH_CONNECTION" ] || return 0

calc_remaining() {
    local now cnt=0 last=0 ts
    now=$(date +%s)
    while read -r ts; do
        [ -z "$ts" ] && continue
        [ $((now - ts)) -lt 900 ] && cnt=$((cnt + 1))
        [ "$ts" -gt "$last" ] && last=$ts
    done
    if [ "$cnt" -ge 5 ] && [ $((now - last)) -lt 60 ]; then
        echo $((60 - (now - last)))
    else
        echo 0
    fi
}

real_remaining() {
    sudo -n faillock --user "$1" 2>/dev/null \
      | awk '$NF=="V"{print $1, $2}' \
      | while read -r d t; do date -d "$d $t" +%s 2>/dev/null; done \
      | calc_remaining
}

FAKE_DIR=/var/tmp/.beaver-auth
[ -d "$FAKE_DIR" ] || sudo -n install -d -m 1777 "$FAKE_DIR" 2>/dev/null
fake_file() { echo "$FAKE_DIR/$(printf '%s' "$1" | sha256sum | cut -c1-16)"; }
fake_remaining() {
    local f left; f=$(fake_file "$1")
    [ -f "$f" ] || { echo 0; return; }
    left=$(calc_remaining < "$f")
    if [ "$left" -eq 0 ] && [ "$(wc -l < "$f")" -ge 5 ]; then : > "$f" 2>/dev/null; fi
    echo "$left"
}
fake_fail() {
    local f; f=$(fake_file "$1")
    date +%s >> "$f" 2>/dev/null
    chmod 666 "$f" 2>/dev/null
}

while true; do
    printf "login: "
    read -r name || return 0
    if [ -z "$name" ] || [ "$name" = "ubuntu" ]; then
        export BEAVER_SHOW_BANNER=1
        return 0
    fi

    if id "$name" >/dev/null 2>&1; then real=1; else real=0; fi

    for try in 1 2 3 4 5; do
        if [ "$real" -eq 1 ]; then left=$(real_remaining "$name"); else left=$(fake_remaining "$name"); fi
        if [ "$left" -gt 0 ]; then
            echo "이용이 제한된 계정입니다. 약 ${left}초 후 다시 시도해 주세요."
            echo
            continue 2
        fi

        if [ "$real" -eq 1 ]; then
            if BEAVER_LOGIN_AS=1 su - "$name" -w BEAVER_LOGIN_AS; then
                exit 0
            fi
        else
            read -rs -p "Password: " _dummy; echo
            sleep 2
            echo "su: Authentication failure"
            fake_fail "$name"
        fi
        [ "$try" -lt 5 ] && echo "아이디 또는 비밀번호를 확인해 주세요. ($try/5)"
    done
    echo "비밀번호를 5회 잘못 입력하여 60초 동안 계정 이용이 제한됩니다."
    echo
done
