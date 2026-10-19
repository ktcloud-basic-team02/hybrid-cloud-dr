# backup
S3 백업과 복원 스크립트
- `backup_to_s3.sh`: mysqldump로 백업 후 S3 업로드 (권한 명령 복제 제외, 임시 파일 자동 정리)
- `restore_test.sh`: S3 덤프를 별도 DB에 복원하고 복구 시간(RTO) 측정 (예정)
