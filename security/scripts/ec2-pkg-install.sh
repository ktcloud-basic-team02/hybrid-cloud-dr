#!/bin/bash
# 1. 기본 패키지 + MySQL 클라이언트 (RDS 접속 확인용)
sudo apt-get update -y
sudo apt-get install -y curl unzip mysql-client

# 2. Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# 3. AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -q awscliv2.zip && sudo ./aws/install
rm -rf aws awscliv2.zip

# 4. kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl

# 5. Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# 5-1 TailScale 설치 후 새 인증키로 IP할당 받기
sudo systemctl enable --now tailscaled
sudo tailscale up --authkey="tskey-auth-key" --hostname="$(hostname)"
tailscale ip -4

# 5-2 Tailscale 새 인스턴스에 적용시 사용
sudo systemctl stop tailscaled
sudo rm -f /var/lib/tailscale/tailscaled.state
sudo systemctl start tailscaled
sleep 5
sudo tailscale up --authkey="tskey-auth-key" --hostname="$(hostname)" --force-reauth

# 6. 설치 후 버전확인
docker --version
aws --version
kubectl version --client
mysql --version
tailscale version

# 로그인시 설치정보 표기
grep -n bashrc ~/.profile

sudo tee /etc/profile.d/versions.sh > /dev/null <<'EOF'
[ -t 1 ] || return 0
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
EOF


# vim 설치
sudo apt-get update -y
sudo apt-get install -y vim
sudo timedatectl set-timezone Asia/Seoul
sudo update-alternatives --set editor /usr/bin/vim.basic

# 한국시간으로 변경
date
timedatectl | grep "Time zone"
vi --version | head -1