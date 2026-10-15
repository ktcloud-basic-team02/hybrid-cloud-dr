# app

DR 시나리오 테스트용 향수 쇼핑몰. 한정 상품(재고 1개) 1종과 일반 상품 5종

## 실행

docker compose up -d --build

http://localhost:5000 접속. DB는 shop이며 db/ 폴더의 SQL(01_schema, 02_products)이 처음 한 번 적재된다. 스키마가 바뀌었을 때는 docker compose down -v 후 다시 실행한다.

## 환경변수

* SERVER_ENV : aws 또는 onprem(소문자). 화면 배지, 주문의 env 컬럼, 메트릭 라벨에 쓰인다.
* DB_HOST , DB_USER , DB_PASSWORD , DB_NAME : 해당 환경의 MySQL / MariaDB 연동 정보.

## 엔드포인트

* GET /health : DB 연결 상태 확인.
* GET /metrics : Prometheus 메트릭 (shop_orders_total, shop_sessions 등).
* POST /api/reset : 전체 데이터 초기화 및 재고 원복.

회원(users), 상품(products), 주문(orders)은 MySQL shop DB에 저장되고(주문 상품은 items 컬럼에 JSON), 장바구니는 로그인 세션(쿠키)에 담기며, 로그는 컨테이너의 /var/log/shop/app.log 경로에 기록된다.
