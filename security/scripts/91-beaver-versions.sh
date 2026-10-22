[ -t 1 ] || return 0
[ -n "$BEAVER_SHOW_BANNER" ] || [ "$USER" != "ubuntu" ] || [ -z "$SSH_CONNECTION" ] || return 0

echo "Welcome to $(. /etc/os-release; echo $PRETTY_NAME) ($(uname -s) $(uname -r) $(uname -m))"
echo

LF="/var/tmp/.beaver-last/$USER"
if [ -f "$LF" ]; then
  echo "Last login: $(cat "$LF")"
else
  echo "Last login: 첫 접속입니다"
fi
date '+%b %d %H:%M' > "$LF" 2>/dev/null
chmod 600 "$LF" 2>/dev/null
echo

echo "===== Beaver Team Infra5 Installed Versions ====="
echo "OS         : $(. /etc/os-release; echo $PRETTY_NAME)"
echo "Kernel     : $(uname -r)"
echo "Docker     : $(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')"
echo "containerd : $(containerd --version 2>/dev/null | awk '{print $3}')"
echo "kubelet    : $(kubelet --version 2>/dev/null | awk '{print $2}')"
echo "kubectl    : $(kubectl version --client 2>/dev/null | awk '/Client Version/{print $3}')"
echo "AWS CLI    : $(aws --version 2>/dev/null | awk '{print $1}' | cut -d/ -f2)"
echo "MySQL      : $(mysql --version 2>/dev/null | awk '{print $3}')"
echo "Tailscale  : $(tailscale version 2>/dev/null | head -1)"
if [ -f /etc/eks/release ]; then
  echo "EKS AMI    : $(. /etc/eks/release; echo ${BASE_AMI_ID:-$AMI_ID})"
fi
echo "================================================="
