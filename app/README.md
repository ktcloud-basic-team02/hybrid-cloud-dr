# app

DR 시나리오 테스트용 향수 쇼핑몰. 한정 상품(재고 1개) 1종과 일반 상품 5종

## 실행

docker compose up -d --build

http://localhost:5000 접속. 스키마가 바뀌었을 때는 docker compose down -v 후 다시 실행한다.

## 환경변수

* APP_ENV : aws 또는 onprem. 화면 배지와 메트릭 라벨에 쓰인다.
* DB_HOST , DB_USER , DB_PASSWORD , DB_NAME : 해당 환경의 MySQL / MariaDB 연동 정보.
* INIT_DB : 1이면 시작할 때 테이블 초기화 및 데이터 적재를 수행한다.

## 엔드포인트

* GET /health : DB 연결 상태 확인.
* GET /metrics : Prometheus 메트릭 (shop_orders_total, shop_sessions 등).
* POST /api/reset : 전체 데이터 초기화 및 재고 원복.

회원 정보(users), 장바구니(carts), 주문(orders) 및 상세(order_items)는 모두 MySQL DB에 안전하게 저장되며, 로그는 컨테이너의 /var/log/shop/app.log 경로에 기록된다.
