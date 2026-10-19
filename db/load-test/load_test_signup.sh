#!/bin/bash
# 작성자: 정혜빈 / 작성일: 2026-10-16
# 목적: 홈페이지(signup) 통한 "회원가입 폭주" 부하 테스트
# 방식: while + curl
# 대상: /signup (POST, username/password 필드), app.py:97 db.create_user() 확인
# 기대 결과: 같은 username으로 50번 시도 -> 1건만 성공(로그인 페이지로 리다이렉트),
#            나머지 49건은 "이미 존재하는 아이디입니다" 에러 페이지 반환

TEST_USERNAME="loadtest_$(date +%s)"
COUNT=0
MAX=50

echo "테스트 대상 아이디: $TEST_USERNAME"
echo "===== 부하 테스트 시작 ====="

while [ $COUNT -lt $MAX ]; do
  curl -s -X POST http://localhost:5002/signup \
    -d "username=${TEST_USERNAME}&password=testpass123" \
    -o /dev/null -w "요청 $COUNT: HTTP %{http_code}\n" &
  COUNT=$((COUNT + 1))
done

wait
echo "===== 완료: ${MAX}건 요청 전송 끝 ====="
echo "테스트 아이디: $TEST_USERNAME"
