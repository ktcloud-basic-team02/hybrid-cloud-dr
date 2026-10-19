# Database
EC2 MySQL Primary 기반 DB 구성, 복제, 백업·복원, 무결성 검증 관련 스크립트와 설정을 관리합니다.

## 폴더 구조

| 폴더 | 내용 |
|---|---|
| `backup/` | S3 백업 스크립트, 복원 스크립트 |
| `replication/` | Primary·Replica 복제 설정 |
| `load-test/` | 부하 테스트 스크립트 (k6, while/curl) |
| `integrity/` | 데이터 무결성 검증 쿼리 |

## 주의
- 비밀번호, AWS Access Key 등 비밀 정보는 커밋하지 않습니다.
- 필요한 값은 환경 변수로 받습니다.

## 담당(DB)
정혜빈,박진호
