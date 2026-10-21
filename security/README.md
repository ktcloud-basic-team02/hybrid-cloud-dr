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
 
