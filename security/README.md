# Beaver Team Infra5 - EKS 인프라 구축 기록

2026-10-20 ~ 10-21 작업 정리 (EKS 노드 구성 ~ 대시보드 셋팅)

## 1. 구성 개요

| 항목 | 내용 |
|---|---|
| 리전 | ap-northeast-2 (서울) |
| EKS | beaver-eks-test (Kubernetes 1.36, 노드 v1.36.2) |
| 노드 그룹 | beaver-prod-mng (t3.medium, Canonical EKS Ubuntu 24.04 AMI) |
| Ingress | Ingress-NGINX v1.15.1 (K8s 1.36은 공식 호환표 미검증) |
| 로드밸런서 | NLB (Ingress-NGINX 서비스가 자동 생성) |
| 메트릭 | metrics-server (`kubectl top`, HPA 사용 가능) |
| NAT | NAT 인스턴스 (iptables MASQUERADE) |
| 접속 | Tailscale, VPC 환경 CloudShell |
| DB | RDS MySQL 8.4 LTS (담당 팀원 연동 예정) |

## 2. 작업 내용

### 2-1. 서버 도구 설치
- Docker, AWS CLI v2, kubectl, mysql 클라이언트 8.4, Tailscale
- 로그인 배너(`/etc/profile.d/versions.sh`), vim 공통 설정, 한국시간(KST)

### 2-2. NAT 인스턴스 (프라이빗 서브넷 아웃바운드)
- 소스/대상 확인 중지
- `net.ipv4.ip_forward=1`, `iptables -t nat ... MASQUERADE`
- NAT 보안 그룹: VPC 대역(10.0.0.0/16) 인바운드 허용
- 프라이빗 라우팅 테이블: `0.0.0.0/0 -> NAT ENI`
- NAT와 프라이빗 인스턴스는 서로 다른 서브넷에 배치

### 2-3. EKS 워커 노드
- 노드 역할 `beaver-eks-node-role`에 정책 3개 연결
  - AmazonEKSWorkerNodePolicy, AmazonEKS_CNI_Policy, AmazonEC2ContainerRegistryReadOnly
- 인스턴스 프로파일 생성 (테스트 EC2 조인 검증용)
- 시작 템플릿: Canonical EKS 이미지 + MIME 사용자 데이터
- 
----------------------------------------------------------------------------------------
- MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="==BOUNDARY=="

--==BOUNDARY==
Content-Type: text/x-shellscript; charset="us-ascii"

#!/bin/bash
/etc/eks/bootstrap.sh beaver-eks-test

--==BOUNDARY==--
----------------------------------------------------------------------------------------\


- 시작 템플릿에는 서브넷, IAM 프로파일을 넣지 않음 (노드 그룹이 지정)

### 2-4. Ingress-NGINX / metrics-server
- 설치 위치: VPC 환경 CloudShell (클러스터 API가 프라이빗 전용)

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.15.1/deploy/static/provider/aws/deploy.yaml
```

- NLB 생성을 위해 퍼블릭 서브넷에 태그 추가
  - `kubernetes.io/role/elb=1`
  - `kubernetes.io/cluster/beaver-eks-test=shared`
- 테스트 앱 + Ingress로 `200 OK` 확인 후 삭제
- metrics-server: 서비스 셀렉터에서 `k8s-app` 제거 후 정상화

### 2-5. 대시보드 (Flask + Gunicorn, 포트 9100)
- 경로: `/opt/beaver-dashboard` (전용 계정 `dashboard`, 독립 venv)
- systemd 서비스 `beaver-dashboard`
- Tailscale IP로만 접속 (보안 그룹에서 9100 미개방)
- 서비스 상태: kubelet, containerd, docker, tailscaled, ssh, chrony, ssm-agent, 대시보드
- MySQL 카드: `/etc/beaver-dashboard.env`(DB_HOST, DB_USER, DB_PASSWORD) 설정 시 표시

## 3. 이슈 및 해결

| 이슈 | 원인 | 해결 |
|---|---|---|
| NodeCreationFailure 반복 | 사용자 데이터 누락, 관리용 서버 AMI의 깨진 kubeconfig, 노드 역할 정책 없음 | Canonical EKS 이미지 + MIME 사용자 데이터 + 정책 3개 |
| 프라이빗 아웃바운드 불가 | MASQUERADE 누락, NAT SG 인바운드 누락, 서브넷 라우팅 중복 | NAT 설정 및 라우팅 분리 |
| NLB 생성 실패 | 서브넷 태그 없음 | 퍼블릭 서브넷에 elb 태그 추가 |
| metrics-server MissingEndpoints | 재적용으로 서비스 셀렉터 변경 | 셀렉터에서 `k8s-app` 제거 |
| 노드에서 kubectl Forbidden | 노드 역할로 인증됨 (정상) | VPC CloudShell에서 작업 |
| 대시보드 ssh "중지" 표시 | Ubuntu 24.04 소켓 활성화 (`ssh.service`만 확인) | `ssh.socket`으로 변경 |
| 접속자 좀비 세션 | 창 강제 종료 후 세션 잔존 | `pkill -t`, sshd keepalive 설정 |

## 4. 운영 메모
- 노드는 교체될 수 있으므로 팀 작업 공간으로 쓰지 않음 (관리용 EC2 또는 VPC CloudShell 사용)
- 임시 비밀번호, Tailscale 인증키는 저장소에 올리지 않고 폐기/교체
- 로드밸런서(NLB)는 시간당 요금 발생, 테스트 후 서비스 삭제로 정리
- ALB 사용 여부는 팀 설계 확정 후 AWS Load Balancer Controller 도입 검토

## 5. EC2 팀원 전체 유저 등록 및 로그인 방식으로 변경. 로그인시 각종 이력들 뜨도록 설정
- SSH 접속시 EC2에 설치된 패키지 버전 정보 표시
- SSH 접속시 먼저 아이디 및 비밀번호를 물어보도록 설정
- 실패한 SSH 시도, 마지막 접속 IP 방식, 패스워드 만료 예정일(7일이내만 표시), 최근 변경된 중요 24시간내 변경된것만 파일 최대 3개
- 마지막 접속 IP 방식에서 -> 시간 + 접속 계정 + 방식, 다른대역에서 접속시만 강조되도록 변경

## 6. SSH 로그인 설정 및 보안 및 로그 표시

SSH로 접속하면 **계정 입력 → 비밀번호 확인 → 정보 표시** 순서로 동작한다.
스크립트는 `/etc/profile.d/`에 파일명 숫자 순서(90 → 91 → 92)로 실행된다.

| 파일 | 역할 |
|---|---|
| `90-beaver-login.sh` | 로그인(`login:`), 5회 실패 시 60초 제한, 없는 계정(FAKE) 동일 처리 |
| `91-beaver-versions.sh` | Welcome, 이전 로그인 시각, 설치 버전 표시 |
| `92-beaver-security-summary.sh` | 서버 점검 결과 표시 |

### 보안 기능
- **로그인 전 정보 비노출**: 접속 직후에는 `login:`만 표시 (MOTD, Last login 비활성화)
- **로그인 실패 제한**: 5회 실패 시 60초 이용 제한 후 로그인 화면으로 복귀, 제한 중 재시도 시 남은 시간 안내
- **FAKE 계정 처리**: 존재하지 않는 아이디도 같은 화면·문구·지연·제한을 적용하여 계정 존재 여부를 알 수 없음
- **실제 잠금**: PAM(`pam_faillock`, deny=5, unlock_time=60)이 처리하고 스크립트는 안내를 담당

### 로그인 후 표시
1. `'아이디' 아이디로 로그인되었습니다.`
2. Welcome, 이전 로그인 시각
3. 설치 버전 (OS, Kernel, Docker, containerd, kubelet, kubectl, AWS CLI, MySQL, Tailscale)
4. 점검 결과

### 점검 결과 (정상이면 "이상 없음", 이상 시에만 상세 표시)
| 분류 | 점검 내용 | 경고 기준 |
|---|---|---|
| 서비스 | kubelet, containerd, 실패한 서비스 | 중지·실패 |
| 연결 | Tailscale | 연결 끊김 |
| 자원 | 디스크, 메모리 | 90% 이상 |
| 보안 | SSH 로그인 실패, 허용 경로 외 접속, 설정 파일 변경, 패스워드 만료 | 실패 5회 이상 / 외부 접속 / 1시간 내 변경 / 7일 이내 |

- 파일명·오류 원문은 숨기고 **개수와 확인 명령만** 안내
- 해결되면 다음 로그인부터 자동으로 사라짐

## 7. SSM(Systems Manager Session Manager) + Tailscale SSH 허용 + 외부 접속 테스트

### 접속 방식 비교
| 방식 | 용도 | 특징 |
|---|---|---|
| Tailscale SSH | 평소 접속 | 키(pem) 없이 Tailscale 계정으로 인증 |
| Session Manager (SSM) | 비상/예비 접속 | SSH 포트(22)·pem 없이 IAM 인증, 접속 기록 남음 |
| 일반 SSH (NAT 경유, pem) | 로그인 보안 시연 | `login:` 화면과 점검 스크립트 동작 |

### SSM 설정
- 노드 IAM 역할(`beaver-eks-node-role`)에 `AmazonSSMManagedInstanceCore` 정책 연결
- 같은 역할을 쓰는 노드는 새로 생성/교체되어도 **자동으로 SSM에 등록**됨
- 확인: `aws ssm describe-instance-information` 에서 `Online` 확인

### Windows 접속 (Session Manager)
1. AWS CLI 설치 확인 (`aws --version`)
2. `aws configure` 로 본인 IAM 사용자 액세스 키 등록 (리전 `ap-northeast-2`)
3. Session Manager 플러그인 설치 후 `session-manager-plugin` 으로 확인
4. 접속: `aws ssm start-session --target <인스턴스ID> --region ap-northeast-2`
5. 접속 후 `sudo su - ubuntu`
- 키 없이 쓰려면 콘솔(Systems Manager > Session Manager > 세션 시작)에서 브라우저로 접속

### Tailscale SSH 허용
- 노드: `tailscale up --ssh --advertise-tags=tag:aws-app`
- Tailscale 정책(Access controls)의 `ssh` 규칙에 `tag:aws-app` 대상 `ubuntu` 접속 허용 추가
- 접속: `ssh ubuntu@<Tailscale IP>`

### 외부 접속 테스트
- Tailscale 연결 상태에서 외부 PC(Windows PowerShell)로 SSH 접속 확인
- SSM 목록에서 노드 `Online` 확인 후 세션 접속 확인
- 로그인 실패 5회 제한, FAKE 계정 동작 확인

### 주의 사항
- 액세스 키·인증키·비밀번호는 문서, 깃, 채팅에 기록하지 않는다
- 노드가 교체되면 인스턴스 ID와 Tailscale IP가 바뀐다 (사용자 데이터에 `--ssh`, 태그 설정 포함 필요)
- SSM 접속은 `login:` 화면을 거치지 않고 접속 기록은 Session Manager 히스토리에 남는다
