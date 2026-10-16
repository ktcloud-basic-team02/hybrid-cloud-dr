# 앱 업데이트 및 롤백

## 이번 설정

| 설정 | 의미 |
| --- | --- |
| maxUnavailable: 0 | 계획된 업데이트에서 가용 파드를 의도적으로 줄이지 않음 |
| maxSurge: 1 | 목표 개수보다 새 파드 1개를 추가해 교체. 자원 여유 필요 |
| minReadySeconds: 10 | 새 파드가 Ready를 10초 유지해야 가용으로 판단 |
| progressDeadlineSeconds: 300 | 배포 진행이 300초 동안 없으면 실패 상태 표시. 전체 배포 시간 제한이나 자동 롤백이 아님 |
| preStop sleep 10 | 정상 종료 시작 시 엔드포인트 변경 전파를 위해 10초 대기 |
| terminationGracePeriodSeconds: 60 | preStop 포함 60초 유예 후 필요 시 강제 종료 |
| revisionHistoryLimit: 3 | 과거 ReplicaSet 3개 보관 |

Gunicorn 기반 PR #3 이미지로 실행하는 것을 전제로 합니다.
일반적인 Gunicorn graceful timeout은 30초이며, 이미지 실행 옵션이 달라지면 유예 시간도 점검합니다.
preStop은 인위적인 대기이지 모든 요청 완료나 무중단을 보장하는 기능은 아닙니다.
강제 삭제, 노드 중단, AZ 장애에서는 정상 종료 절차가 실행되지 않을 수 있습니다.

## 적용 전

실제 대상 context, namespace, 이미지 주소를 확인합니다. 아래 예시는 로컬 전용입니다.
운영에서는 docker-desktop/beaver-local을 실제 대상으로 변경해야 합니다.

```powershell
kubectl --context docker-desktop -n beaver-local get deployment shop
kubectl --context docker-desktop -n beaver-local get deployment shop -o jsonpath='{.spec.template.spec.containers[0].image}'
kubectl --context docker-desktop -n beaver-local rollout history deployment/shop
```

기존 정상 이미지 주소와 revision을 기록합니다. 이미지 태그는 덮어쓰지 않는 고유 태그 또는 digest를 사용합니다.
이 문서는 실행 절차이며 이미지 값이 정해지기 전 그대로 복붙하지 않습니다.

## 새 이미지 배포

```powershell
kubectl --context docker-desktop -n beaver-local set image deployment/shop shop=<NEW_IMAGE_URI>
kubectl --context docker-desktop -n beaver-local rollout status deployment/shop --timeout=360s
kubectl --context docker-desktop -n beaver-local get pods -o wide
```

set image는 이미지 필드만 변경하여 HPA가 조절한 replicas를 건드리지 않습니다.
실패한 새 파드가 Pending/ImagePullBackOff/준비 검사 실패 상태이면 기존 정상 파드가 유지될 수 있습니다.
rollout 명령 시간 초과와 실제 Deployment 실패 상태는 구분하여 describe/events/logs를 확인합니다.

## 장애 시 되돌리기

```powershell
kubectl --context docker-desktop -n beaver-local describe deployment shop
kubectl --context docker-desktop -n beaver-local rollout history deployment/shop
kubectl --context docker-desktop -n beaver-local rollout undo deployment/shop --to-revision=<KNOWN_GOOD_REVISION>
kubectl --context docker-desktop -n beaver-local rollout status deployment/shop --timeout=360s
```

history에서 확인한 정상 revision 번호를 지정합니다. 무조건 직전 버전이 정상이라고 가정하지 않습니다.
Deployment 롤백은 파드 템플릿만 되돌립니다. DB 데이터/스키마, ConfigMap/Secret 내용은 복구하지 않습니다.
DB 비밀번호 변경이나 스키마 변경이 함께 있었다면 앱 버전 호환성을 별도로 확인합니다.
ConfigMap/Secret을 환경변수로 주입하면 기존 파드 값은 자동 갱신되지 않습니다.

## 검증 상태

설정/절차 작성 단계입니다. 이 변경으로 실제 클러스터 업데이트나 롤백은 실행하지 않았습니다.
향후 Ingress를 통한 반복 요청 기록과 함께 정상 업데이트 및 실패 배포 복구를 확인합니다.
