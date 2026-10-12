# 앱 운영·대기 모드

## 설정
- SERVICE_MODE=active: 기존 앱 요청 처리 허용
- SERVICE_MODE=standby: GET·HEAD·OPTIONS 외 요청을 503으로 차단
- 미설정 시 standby이며, 다른 값을 지정하면 앱 시작 실패
- SERVER_ENV는 onprem/aws 환경 식별용이며 운영 권한과 별개

## 대기 중 동작
로그인·회원가입·장바구니 변경·주문·DB 초기화 요청을 차단합니다.
조회 요청은 허용하지만 DB 연결이 필요할 수 있습니다.
차단 요청에 대한 실패 주문 기록은 DB에 저장하지 않습니다.

## 상태 확인 및 Kubernetes 적용
- /live: 앱 응답 가능 시 200. DB·운영 모드와 무관
- /health: active이고 DB 연결이 정상이면 200, 나머지는 503
- startupProbe와 livenessProbe는 /live 사용
- readinessProbe는 /health 사용
- standby에서는 readiness 실패로 Service의 트래픽 대상에서 제외됩니다.
- 기존 배포 설정을 그대로 사용하면 /health의 503으로 재시작될 수 있으므로 probe 변경이 필요합니다.

## 추후 전환 자동화 연계
현재 모드는 앱 시작 시 환경변수로 읽습니다.
설정을 바꾸려면 Pod 재생성이 필요합니다.
운영 상태 저장 위치와 Lambda 제어 방식이 결정되면 상태를 전달받는 부분을 연계합니다.
이번 기능은 DB 복제·승격·쓰기 차단이나 자동 장애 전환 전체를 구현하지 않습니다.
이미 처리 중인 요청의 종료와 양쪽 환경의 동시 쓰기 방지는 별도로 제어해야 합니다.

## 검증 범위
Flask 테스트 클라이언트와 DB 모의 객체로 다음을 확인했습니다.
- standby에서 변경 요청 차단 및 DB 연결 함수 미호출
- active에서 DB 정상 시 /health 200
- DB 장애 시 /health 503, /live 200

실제 DB를 이용한 주문, Kubernetes 배포, Lambda 연계는 아직 검증하지 않았습니다.
