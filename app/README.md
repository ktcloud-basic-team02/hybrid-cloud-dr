# app

DR 시나리오 테스트용 향수 쇼핑몰. 한정 상품(재고 1개) 1종과 일반 상품 5종

## 실행

docker compose up -d --build

http://localhost:5000 접속. DB는 shop이며 db/ 폴더의 SQL(01_schema, 02_products)이 처음 한 번 적재된다. 스키마가 바뀌었을 때는 docker compose down -v 후 다시 실행한다.

## 환경변수

* SERVER_ENV : aws 또는 onprem(소문자). 화면 배지, 주문의 env 컬럼, 메트릭 라벨에 쓰인다.
* DB_HOST , DB_USER , DB_PASSWORD , DB_NAME : 해당 환경의 MySQL / MariaDB 연동 정보.

## DB 대기 시간 제한

`db.py`에서 PyMySQL 연결 대기를 3초(`connect_timeout`), 읽기·쓰기 대기를 각각 5초(`read_timeout`, `write_timeout`)로 제한합니다. 환경변수가 아닌 코드 설정이며, HTTP 요청 전체나 트랜잭션 전체의 제한 시간은 아닙니다.

로컬 DB 일시 정지 테스트에서 상품 조회 실패까지의 대기가 30.78초에서 5.06초로 줄었습니다. 변경 후 DB 읽기 시간 초과를 확인했고, 테스트 중 Gunicorn worker timeout이나 컨테이너 재시작은 관찰되지 않았습니다. DB 재개 후 정상 조회를 확인했습니다. 연결·쓰기 제한 자체와 EKS 환경은 별도 검증이 필요합니다.

상세 결과: [2026-10-19 테스트 기록](../tests/2026-10-19-results.md)

## 엔드포인트

* GET /health : DB 연결 상태 확인.
* GET /metrics : Prometheus 메트릭 (shop_orders_total, shop_sessions 등).
* POST /api/reset : 전체 데이터 초기화 및 재고 원복.

회원(users), 상품(products), 주문(orders)은 MySQL shop DB에 저장되고(주문 상품은 items 컬럼에 JSON), 장바구니는 로그인 세션(쿠키)에 담기며, 로그는 컨테이너의 /var/log/shop/app.log 경로에 기록된다.
