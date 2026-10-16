# 쇼핑몰 Kubernetes 배포 초안

| 파일 | 역할 |
| --- | --- |
| app.yaml | 앱 Deployment, ConfigMap, Service, namespace |
| hpa.yaml | CPU 목표 60%, 파드 2~6개 |
| ingress.example.yaml | NGINX를 통해 shop Service로 연결하는 접속 규칙 |
| pdb.yaml | 계획된 파드 퇴거 시 최소 가용 파드 1개 보호 |
| secrets.env.example | DB_USER, DB_PASSWORD, SECRET_KEY 입력 항목 |
| ROLLOUT.md | 기존 업데이트·롤백 참고 절차 |

## 적용 전

1. 실제 kubectl context를 확인합니다.
2. app.yaml의 이미지와 DB 주소를 실제 값으로 바꿉니다. PR #3의 Gunicorn 이미지를 사용합니다.
3. beaver namespace를 생성하고 shop-secrets를 준비합니다.
   DB_USER/DB_PASSWORD/SECRET_KEY 세 키가 필수입니다. 모든 파드에서 같은 임의 세션 키를 사용합니다.
   실제 값은 Git에 올리지 않습니다. secrets.env는 Git 제외입니다.
4. HPA용 Metrics Server, IngressClass에 맞는 컨트롤러가 필요합니다.
5. Ingress의 클래스와 도메인을 실제 값으로 변경합니다. 로컬에서 확인한 값은 nginx, shop.localhost입니다.

app.yaml, hpa.yaml, pdb.yaml, 설정한 Ingress 파일을 각각 kubectl apply -f로 적용합니다.
로컬에서는 namespace를 beaver-local로 바꾼 복사본을 사용하며 원본의 EKS 초안과 구분합니다.
폴더 전체를 무조건 apply하지 않습니다. Ingress 자리표시자가 남아 있으면 적용하지 않습니다.

## 알아둘 점

- 파드 개수는 HPA에서 관리하여 Deployment에 replicas를 지정하지 않습니다.
  HPA 반영 전 최초 기본 파드 수는 1개일 수 있습니다.
- /live는 생존 검사, /health는 DB 연결을 포함한 준비 검사입니다.
- preStop에서 10초 대기하고 종료 유예는 60초입니다. 무중단 보장은 아닙니다.
- 파드는 비root UID/GID 10001로 실행하고 컨테이너 권한 상승과 Linux capabilities를 제한합니다.
  이미지의 앱 파일은 해당 계정이 읽을 수 있어야 하고 쓰기 경로가 있으면 별도 권한이 필요합니다.
  Docker 이미지의 실행 사용자와 앱 파일 소유권도 UID/GID 10001로 통일했습니다.
  shop:test 이미지로 로컬 Kubernetes 파드 실행, UID/GID 10001 및 사이트 접속을 확인했습니다.
  이 설정이 SECRET_KEY를 생성/암호화하는 것은 아닙니다. Secret 필수 참조는 별도로 유지합니다.
- AZ/노드 분산은 선호 설정입니다. 실제 EKS 배치를 확인해야 합니다.
- CPU/메모리 값과 HPA 범위는 초기값입니다. HPA가 노드를 늘리지는 않습니다.
- PDB는 drain 등 eviction 요청을 제한합니다. 직접 pod delete, 갑작스러운 노드/AZ 장애를 막지 않습니다.
  정상 파드가 1개뿐이면 해당 파드의 drain이 대기할 수 있습니다.
  Deployment 롤링 업데이트는 PDB가 아닌 maxUnavailable/maxSurge 설정으로 제어됩니다.
- Secret/ConfigMap 변경은 실행 중 앱 환경변수에 자동 반영되지 않으므로 파드 교체가 필요합니다.
- 실제 ALB, TLS, 도메인, DB 장애 전환 연결 방식은 환경 확정 후 반영합니다.
- 앱 DB 타임아웃과 주문 재시도 중복 방지는 개발 담당과 별도 조정합니다.

## 확인 상태

기존 로컬 배포에서 앱 실행·DB 연결, 파드 자동 복구, HPA 확장·축소, NGINX 접속을 확인했습니다.
이번 Secret 필수 참조와 종료 설정은 로컬 API 서버 dry-run을 통과했습니다.
PDB 실제 drain 동작과 실제 EKS 배포는 아직 검증하지 않았습니다.
