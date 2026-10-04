# app

테스트용 쇼핑몰 앱. 재고 1개짜리 한정 상품을 주문할 수 있다.

## 실행

    docker compose up -d --build

브라우저에서 http://localhost:8080 접속.

## 환경변수

- `APP_ENV`: `aws` 또는 `onprem`. 화면 배지와 메트릭 라벨에 쓰인다
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: 해당 환경의 MySQL
- `INIT_DB`: 1이면 시작할 때 테이블을 만든다. 복제를 받는 쪽 DB는 0

## 엔드포인트

- `GET /health`: DB 연결까지 확인
- `GET /metrics`: Prometheus 메트릭 (`shop_orders_total`, `shop_sessions`)
- `POST /api/reset`: 재고 1개로 되돌리고 주문 삭제 (테스트용)

로그인 정보와 장바구니는 메모리에만 있고, 로그는 컨테이너의 `/var/log/shop/app.log`에만 쌓인다.
