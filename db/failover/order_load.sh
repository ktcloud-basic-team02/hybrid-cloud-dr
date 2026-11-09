#!/bin/bash
# =====================================================
# 스크립트명: order_load.sh
# 작성자: 정혜빈
# 작성일: 2026-10-25
# 목적: Multi-AZ 장애 전환 중 주문 유실 여부 확인용 부하 (0.5초마다 주문 1건)
# 사용법: read -s -p "session 쿠키: " SESSION_COOKIE; echo; export SESSION_COOKIE
#         ./order_load.sh   (Ctrl+C로 중단)
# 판정: 성공·실패 모두 302 → 이동 주소로 판단 (성공 /order/번호, 실패 /cart)
# 쿠키는 파일에 넣지 않고 환경 변수로만 입력
# =====================================================
if [ -z "$SESSION_COOKIE" ]; then echo "SESSION_COOKIE 먼저 설정"; exit 1; fi
OUT="order_result_$(date +%m%d_%H%M%S).log"
echo "결과 파일: $OUT"
i=0
while true; do
  i=$((i+1))
  ts=$(date +%H:%M:%S)
  r=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -m 15 \
    -X POST 'https://beaver-shop.cloud/checkout' \
    -H 'content-type: application/x-www-form-urlencoded' \
    -b "session=$SESSION_COOKIE" \
    --data-raw 'pay=card')
  case "$r" in
    *"/order"*) res="OK $(echo "$r" | grep -oE '[0-9]+$')" ;;
    *)          res="FAIL -" ;;
  esac
  echo "$ts $i $res $r" | tee -a "$OUT"
  sleep 0.5
done
