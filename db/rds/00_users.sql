-- 00_users.sql : beaver-rds DB 계정·권한
-- [2026-10-21 작성] 정혜빈 (DB)
-- [2026-10-21 수정] shop_backup PROCESS 권한 제거 (--no-tablespaces 사용으로 불필요)
--
-- 실행: admin 계정으로 실행 (admin 비밀번호는 Secrets Manager에서 조회)
-- <...> 자리는 openssl rand로 만든 랜덤 비밀번호로 바꿔서 실행 (실제 비밀번호를 git에 올리지 말 것)
-- 실행 후 Kubernetes Secret(shop-db-secret, shop-backup-secret)도 같은 비밀번호로 갱신
-- 스냅샷으로 RDS를 복원하면 계정이 그대로 있으므로 이 파일은 필요 없음 (새로 만들 때만 사용)
-- 실행 순서: 00_users.sql → 01_schema.sql → 02_products.sql

-- 앱 계정: shop 데이터 읽기·쓰기만, 팀 VPC(10.0.x)에서만 접속
CREATE USER IF NOT EXISTS 'appuser'@'10.0.%' IDENTIFIED BY '<APP_PASSWORD>';
GRANT SELECT, INSERT, UPDATE, DELETE ON shop.* TO 'appuser'@'10.0.%';

-- 백업 계정: 읽기 + mysqldump용, 데이터 변경 불가
CREATE USER IF NOT EXISTS 'shop_backup'@'10.0.%' IDENTIFIED BY '<BACKUP_PASSWORD>';
GRANT SELECT, SHOW VIEW, TRIGGER, EVENT, LOCK TABLES ON shop.* TO 'shop_backup'@'10.0.%';

-- 확인
SHOW GRANTS FOR 'appuser'@'10.0.%';
SHOW GRANTS FOR 'shop_backup'@'10.0.%';
