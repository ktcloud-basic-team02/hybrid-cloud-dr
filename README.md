# AWS 기반 고가용성 아키텍처 구축 및 장애 주입 검증

<p>
  <img src="https://img.shields.io/badge/AWS-FF9900?style=flat&logo=amazon-aws&logoColor=white"/>
  <img src="https://img.shields.io/badge/Amazon%20EKS-FF9900?style=flat&logo=amazonaws&logoColor=white"/>
  <img src="https://img.shields.io/badge/Amazon%20CloudWatch-FF4F8B?style=flat&logo=amazoncloudwatch&logoColor=white"/>
  <img src="https://img.shields.io/badge/Kubernetes-326CE5?style=flat&logo=kubernetes&logoColor=white"/>
  <img src="https://img.shields.io/badge/Terraform-844FBA?style=flat&logo=terraform&logoColor=white"/>
  <img src="https://img.shields.io/badge/Ubuntu-E95420?style=flat&logo=ubuntu&logoColor=white"/>
  <img src="https://img.shields.io/badge/MySQL-4479A1?style=flat&logo=mysql&logoColor=white"/>
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white"/>
</p>

> **Multi-AZ EKS 및 MySQL 환경에서 다양한 인프라 장애(Pod, Node, AZ, DB) 발생 시 서비스 연속성과 데이터 정합성을 검증한다.**

AWS 서울 리전에 쇼핑몰 서비스를 Multi-AZ 기반 EKS와 MySQL로 구축하고, 파드·노드·AZ·DB 장애 테스트를 통해 서비스 연속성과 데이터 정합성을 검증한다. 부하 변동으로 파드가 확장·축소되는 중에도 주문 데이터가 유실·중복 없이 유지되는지 확인한다. 가용성, 복구 시간, 정합성 결과는 CloudWatch로 관측해 시연한다.

---

* **프로젝트 기간:** 2026.09.30 ~ 2026.10.29 (30일)
* **주요 목표:**
  1. Pod / Node / AZ 장애 주입을 통한 서비스 가용성 및 RTO 측정
  2. DB Failover 발생 시 주문 유실·중복·재고 음수 방지 검증
  3. 트래픽 변동에 따른 HPA Auto Scaling 정상 동작 확인
  4. CloudWatch 대시보드를 통한 인프라 및 DB 상태 실시간 관측
---

## 1. 시스템 아키텍처

* **AWS Region:** `ap-northeast-2` (Seoul)
* **Compute:** AWS EKS (Ubuntu EKS-optimized Node Group / Multi-AZ)
* **Database:** EC2 MySQL (Primary/Replica Multi-AZ 구성) + 온프레미스 VM 백업
* **Network & Security:** Private Subnet 위주 구성 (VPC Endpoints 적용으로 ECR/S3 통신), Security Group, IAM
* **Monitoring:** Amazon CloudWatch Dashboard

---

## 2. 주요 기술 스택

| 구분 | 기술 스택 |
| --- | --- |
| **Infrastructure** | AWS EKS, EC2, VPC, ECR, CloudWatch, Terraform (IaC) |
| **Container & Orchestration** | Kubernetes, Docker, Helm, HPA |
| **Backend & DB** | Python (Flask), MySQL |
| **CI/CD & Security** | GitHub Actions, Trivy, Hadolint |
| **Connectivity** | Tailscale (온프레미스 백업 연동) |

---

## 3. 장애 주입 및 검증 시나리오

1. **Pod Level:** 특정 서비스 Pod를 강제 종료 시 Kubernetes Self-Healing 동작 및 요청 처리율 확인
2. **Node Level:** EKS 워커 노드 다운 시 Pod 재배치 및 서비스 지연 시간 측정
3. **AZ Level:** 단일 Availability Zone 전체 장애 주입 시 Multi-AZ Failover 검증
4. **DB Level:** MySQL Primary 장애 발생 시 Replica 전환 중 주문 데이터 무결성 검증

---

## 4. 팀원 및 역할 분담

* **김영배:** AWS VPC/서브넷 및 Multi-AZ 전체 아키텍처 설계, IaC 보조
* **박진호:** 컨테이너 이미지 관리, EKS 배포 매니페스트 작성, DB 보조
* **양희연:** 샘플 쇼핑몰 앱(Flask) 개발, CloudWatch 대시보드 모니터링
* **오영빈:** IaC (Terraform) 기반 인프라 자동화 구축, 보안 보조
* **정재우:** 인프라 보안 (Security Group, IAM, Secret)
* **정혜빈:** EC2 MySQL Primary/Replica 구성, 데이터베이스 백업
