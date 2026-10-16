# 쇼핑몰 EKS 배포 초안

현재 실제 EKS에 적용하지 않은 초안입니다. 앱 Docker 이미지 생성은 PR #3에서 관리합니다.
이 폴더는 앱 배포 설정만 포함하며 DB 서버와 ALB를 새로 만들지 않습니다.

| 파일 | 역할 |
| --- | --- |
| app.yaml | namespace, ConfigMap, Deployment, ClusterIP Service |
| hpa.yaml | CPU 사용률에 따라 앱 파드 2~6개로 확장 |
| ingress.example.yaml | 설치된 NGINX 컨트롤러에 연결할 앱 경로 템플릿 |
| secrets.env.example | 실제 인증값 없이 필요한 키만 제공 |

## 먼저 확보할 정보

- EKS 계정/리전/클러스터 이름 및 kubectl 접근 권한.
- 실제로 push된 앱 이미지의 ECR 주소와 고유 태그. Gunicorn 이미지 사용.
- 노드 CPU 아키텍처와 이미지 아키텍처 일치 여부.
- 실제 MySQL의 사설 주소 및 shop용 앱 계정.
- 노드/파드에서 DB까지 네트워크 연결과 MySQL 계정의 접속 호스트 권한.
- 두 AZ의 Ready 노드, 충분한 CPU/메모리, CPU HPA용 Metrics Server.
- 기존 ALB/Ingress 구성과 담당자. 확인 전 외부 노출 리소스는 추가하지 않음.

## 설정값 입력

app.yaml의 두 자리표시자를 실제 값으로 변경합니다.

- REPLACE_WITH_DB_PRIVATE_HOST: 앱 파드가 접속할 DB 사설 주소. 127.0.0.1은 사용하지 않음.
- REPLACE_WITH_ECR_IMAGE_AND_TAG: 노드가 pull할 수 있는 이미지 주소와 고유 태그.

secrets.env.example을 secrets.env로 복사한 뒤 실제 값으로 입력합니다.
secrets.env는 Git에서 제외됩니다. 인증값을 PR/화면 캡처/채팅에 공유하지 않습니다.
SECRET_KEY는 모든 파드에서 동일하게 사용하는 충분히 긴 임의 값입니다.
Kubernetes Secret의 base64는 암호화가 아닙니다. 팀의 별도 Secret 관리 방식이 있으면 그것을 따릅니다.

## 배포 순서

아래 명령은 실제 클러스터와 설정값을 확인한 다음 실행합니다. k8s 폴더 기준입니다.

```bash
kubectl config current-context
kubectl get nodes -L topology.kubernetes.io/zone
kubectl get pods -A

kubectl create namespace beaver --dry-run=client -o yaml | kubectl apply -f -
kubectl -n beaver create secret generic shop-secrets --from-env-file=secrets.env

kubectl apply --dry-run=server -f app.yaml
kubectl apply -f app.yaml
kubectl -n beaver rollout status deployment/shop --timeout=180s
kubectl -n beaver get pods -o wide

kubectl -n beaver port-forward service/shop 5003:80
```

Secret 생성 명령은 최초 1회용입니다. shop-secrets가 이미 있으면 담당자와 확인한 뒤 갱신합니다.
포트 포워딩은 명령을 실행한 장비의 localhost:5003에 연결합니다.
EC2에서 실행했다면 PC에서 볼 때 별도 SSH 터널이 필요합니다.

## HPA 적용

앱 기본 배포와 DB 연결이 정상일 때 진행합니다.

```bash
kubectl top pods -n beaver
kubectl apply --dry-run=server -f hpa.yaml
kubectl apply -f hpa.yaml
kubectl -n beaver get hpa
```

CPU 목표 60%는 requests.cpu=100m 기준 비율입니다. 메모리/CPU 값과 파드 상한 6개는 초기 제안입니다.
실제 부하와 노드 용량에 맞게 조정합니다. HPA는 노드를 자동 증설하지 않습니다.
HPA 적용 후 app.yaml의 replicas: 2를 재적용하면 파드 수가 일시적으로 재설정될 수 있습니다.

## 구성 의도

- 파드 2개, 롤링 업데이트 시 maxUnavailable=0으로 가용 파드를 유지하도록 요청합니다.
  새 파드를 위한 여유 자원이 없으면 업데이트가 지연될 수 있습니다.
- /live는 프로세스 생존 검사, /health는 DB 연결을 포함한 준비 상태 검사입니다.
  DB 장애 때문에 앱을 반복 재시작하지 않도록 liveness는 /live를 사용합니다.
- AZ/노드 분산은 ScheduleAnyway로 선호만 지정합니다. 두 AZ 분산을 보장하지 않으므로
  배포 후 실제 노드/AZ 배치를 확인해야 합니다. 한 AZ 장애 시 재배치를 제한하지 않기 위한 초안입니다.
- 모든 파드는 shop-secrets의 동일한 세션 키를 사용합니다. 주문 재시도 중복 방지는 앱의 별도 과제입니다.
- 사용자 요청은 Service까지 준비했습니다. ALB/Ingress 연결은 기존 컨트롤러 확인 후 추가합니다.

## 검증 범위

앱 코드의 포트 5000, DB 환경변수, /live, /health, POD_NAME/NODE_NAME 경로를 대조했습니다.
실제 EKS에서 dry-run, 이미지 pull, DB 연결, AZ 분산 및 HPA 동작은 아직 검증하지 않았습니다.

## Ingress 준비

ingress.example.yaml은 템플릿입니다. 폴더 전체를 일괄 apply하지 마세요.
먼저 kubectl get ingressclass와 kubectl get deployments,daemonsets -A로 설치된 컨트롤러를 확인합니다.
NGINX라는 이름만으로 구현체를 특정하지 않으며 실제 컨트롤러/차트 버전과 지원 상태를 확인한 후 설치합니다.
REPLACE_WITH_INGRESS_CLASS를 설치된 NGINX IngressClass 이름으로 교체하고 로컬에서는 namespace도 beaver-local로 바꿉니다.
host는 필수로 명시합니다(F5 NGINX 컨트롤러 요구 조건).
템플릿의 shop.example.com을 실제 도메인으로 바꾸고 로컬에서는 shop.localhost로 사용합니다.
해당 host의 / 이하 경로를 같은 namespace의 shop Service 80으로 전달합니다.
실제 도메인/TLS 설정은 운영 환경 확정 후 추가합니다.
이 템플릿은 ALB를 생성하거나 ALB와 NGINX를 연결하지 않습니다.
ALB→NGINX 구성에는 NGINX 대상 Service, ALB 대상 등록 및 헬스체크 설정이 별도로 필요합니다.
ingressClassName을 alb로 바꿔 shop에 직접 연결하면 NGINX를 거치지 않는 다른 구성이므로 혼용하지 않습니다.
