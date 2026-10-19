#!/bin/bash
# =====================================================
# 스크립트명: backup_to_s3.sh
# 작성자: 정혜빈
# 작성일: 2026-10-15
# 목적: EC2(Primary) shop DB를 덤프 떠서 S3에 백업
# 실행 위치: EC2 (hyebin 계정)
#
# 사용법:
#   export S3_BUCKET=<버킷 이름>   # ~/.bashrc에 넣어두면 매번 안 해도 됨
#   ./backup_to_s3.sh
#
# 전제/주의사항:
#   - appuser는 평소 RELOAD/FLUSH_TABLES/PROCESS 권한이 없어서,
#     이 스크립트 안에서 "임시로 부여 → 백업 → 회수"하는 방식으로 동작함
#   - root 비밀번호를 1번 입력하면 권한 부여/회수에 같이 사용함
#   - 권한 부여/회수는 SQL_LOG_BIN=0으로 실행해서 Replica(VM)로 복제되지 않음
#   - 덤프 파일은 ~/tmp 아래 임시 폴더에 만들고, S3 업로드 확인 후 삭제함
#     (EC2의 덤프는 S3 업로드를 위한 중간 파일, 보관은 S3에서만 함)
#   - [테스트 단계 전용] 추후 운영자 권한(Role)이 생기면
#     권한 부여/회수 로직은 제거하고 전용 백업 계정으로 교체 예정
#
# 수정 이력:
#   2026-10-15 정혜빈 - 최초 작성
#   2026-10-15 정혜빈 - 중간 실패 시에도 권한 상태를 반드시 눈에 띄게 알려주는 안전장치 추가
#   2026-10-17 정혜빈 - GRANT/REVOKE에 SET SQL_LOG_BIN=0 적용
#                      (10/16 GRANT/REVOKE가 VM으로 복제되어 복제가 멈춘 장애 재발 방지)
#   2026-10-17 정혜빈 - 덤프를 ~/tmp 임시 폴더에 생성, S3 업로드 확인 후 로컬 삭제
#                      (팀 피드백: 자원 관리, 서버에 백업 파일이 쌓이지 않게)
#   2026-10-19 정혜빈 - 버킷 이름을 환경 변수(S3_BUCKET)로 분리
#                      (git 업로드용, AWS 계정 번호 노출 방지)
#   ※ 본문에서 [10/17 수정], [10/19 수정] 표시가 붙은 줄이 위 수정 건으로 바뀐 부분
# =====================================================

set -e

# [10/19 수정] 버킷 이름을 스크립트에 직접 쓰지 않고 환경 변수로 받음 (없으면 즉시 중단)
BUCKET="${S3_BUCKET:?S3_BUCKET 환경 변수를 설정하세요 (예: export S3_BUCKET=버킷이름)}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# [10/17 수정] 덤프 저장 위치를 홈(~/)에서 ~/tmp 아래 임시 폴더로 변경
#   - 실행할 때마다 backup_XXXXXX 형태의 새 폴더를 만들어 이름 충돌 방지
#   - FILE_NAME을 따로 둔 이유: 5번 단계에서 S3 파일 크기 비교에 사용
mkdir -p ~/tmp
TMP_DIR=$(mktemp -d ~/tmp/backup_XXXXXX)
FILE_NAME="shop_backup_${TIMESTAMP}.sql"
BACKUP_FILE="${TMP_DIR}/${FILE_NAME}"

# ===== 안전장치: 스크립트가 "어떤 이유로든" 끝날 때 자동 실행되는 부분 =====
cleanup_and_report() {
  EXIT_CODE=$?
  # [10/17 수정] 성공/실패와 상관없이 임시 폴더는 항상 정리 (실패 시 찌꺼기 방지)
  rm -rf "${TMP_DIR:-}"
  echo ""
  echo "########################################################"
  if [ $EXIT_CODE -ne 0 ]; then
    echo "🚨🚨🚨 스크립트가 중간에 실패했습니다! (종료 코드: $EXIT_CODE) 🚨🚨🚨"
    echo "🚨 appuser 권한이 아직 회수 안 됐을 수 있습니다!"
    echo "🚨 아래 쿼리로 반드시 확인하세요:"
    echo "    SHOW GRANTS FOR 'appuser'@'localhost';"
    echo "🚨 RELOAD/FLUSH_TABLES/PROCESS 가 보이면 수동으로 REVOKE 하세요."
    # [10/17 수정] 수동 회수 때도 복제되지 않도록 안내 추가
    echo "    (수동 REVOKE 시에도 SET SQL_LOG_BIN=0; 을 앞에 붙일 것)"
  else
    echo "✅ 스크립트 정상 완료. 권한 회수 및 임시 파일 정리 완료."
  fi
  echo "########################################################"
}
trap cleanup_and_report EXIT   # 성공/실패/중단 "무조건" 이 함수가 마지막에 실행됨
# ===========================================================

echo "===== 1. appuser 임시 권한 부여 (복제 제외) ====="
read -s -p "MySQL root 비밀번호: " MYSQL_ROOT_PW; echo
# [10/17 수정] SET SQL_LOG_BIN=0 추가: 이 GRANT가 binlog에 안 남아서 VM으로 복제되지 않음
mysql -u root -p"${MYSQL_ROOT_PW}" -e "SET SQL_LOG_BIN=0; GRANT RELOAD, FLUSH_TABLES, PROCESS ON *.* TO 'appuser'@'localhost'; FLUSH PRIVILEGES;"

echo "===== 2. mysqldump 실행 ====="
read -s -p "appuser 비밀번호: " APP_PW; echo
mysqldump -u appuser -p"${APP_PW}" --single-transaction --set-gtid-purged=ON --no-tablespaces shop > "$BACKUP_FILE"

echo "===== 3. 덤프 파일 검증 ====="
FILE_SIZE=$(stat -c%s "$BACKUP_FILE")
echo "파일 크기: ${FILE_SIZE} bytes"
if [ "$FILE_SIZE" -lt 1000 ]; then
  echo "❌ 경고: 파일이 너무 작습니다."
  exit 1
fi

INSERT_COUNT=$(grep -c "^INSERT INTO" "$BACKUP_FILE" || true)
echo "INSERT 문 개수: ${INSERT_COUNT}"
if [ "$INSERT_COUNT" -eq 0 ]; then
  echo "❌ 경고: INSERT 문이 없습니다."
  exit 1
fi
echo "✅ 검증 통과"

echo "===== 4. S3 업로드 ====="
aws s3 cp "$BACKUP_FILE" "s3://${BUCKET}/db-backups/"

echo "===== 5. S3 업로드 확인 (크기 비교) ====="
# [10/17 수정] 파일명 존재 여부만 보던 것을 "크기 비교"로 강화
#   - 업로드가 중간에 끊겨 불완전한 파일이 올라간 경우도 잡아냄
#   - 크기가 같을 때만 로컬 덤프 삭제 (확인 전에 지우면 백업이 사라질 수 있음)
S3_SIZE=$(aws s3 ls "s3://${BUCKET}/db-backups/${FILE_NAME}" | awk '{print $3}')
echo "로컬 크기: ${FILE_SIZE} / S3 크기: ${S3_SIZE:-없음}"
if [ "$S3_SIZE" != "$FILE_SIZE" ]; then
  echo "❌ 경고: S3 파일이 없거나 크기가 다릅니다."
  exit 1
fi
echo "✅ S3 업로드 확인 완료 → 로컬 덤프 삭제"
rm -f "$BACKUP_FILE"

echo "===== 6. appuser 임시 권한 회수 (복제 제외) ====="
# [10/17 수정] SET SQL_LOG_BIN=0 추가: 이 REVOKE도 VM으로 복제되지 않음
mysql -u root -p"${MYSQL_ROOT_PW}" -e "SET SQL_LOG_BIN=0; REVOKE RELOAD, FLUSH_TABLES, PROCESS ON *.* FROM 'appuser'@'localhost'; FLUSH PRIVILEGES;"

# [10/17 수정] 로컬 파일은 지워졌으므로 S3 경로를 안내
echo "===== 완료! S3 경로: s3://${BUCKET}/db-backups/${FILE_NAME} ====="
