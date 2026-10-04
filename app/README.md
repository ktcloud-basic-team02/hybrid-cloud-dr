# app

DR 시나리오 테스트용 신발 쇼핑몰. 한정 상품(재고 1개) 1종과 일반 상품 5종이 있다.

## 실행

    docker compose up -d --build

http://localhost:8080 접속. 스키마가 바뀌었을 때는 `docker compose down -v` 후 다시 실행한다.

## 환경변수

- `APP_ENV`: `aws` 또는 `onprem`. 화면 배지와 메트릭 라벨에 쓰인다
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: 해당 환경의 MySQL
- `INIT_DB`: 1이면 시작할 때 테이블을 만든다. 복제를 받는 쪽 DB는 0

## 엔드포인트

- `GET /health`: DB 연결까지 확인
- `GET /metrics`: `shop_orders_total`, `shop_sessions`
- `POST /api/reset`: 주문 삭제, 재고 초기화 (회원 정보는 유지)

회원 정보와 주문은 DB에 저장되고, 로그인 세션과 장바구니는 메모리에만 있다. 로그는 컨테이너의 `/var/log/shop/app.log`에만 쌓인다.
