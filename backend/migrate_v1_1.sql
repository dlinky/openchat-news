-- ChatDigest v1.1 마이그레이션
-- 채팅방 이름 끝에 붙은 참여 인원수 숫자 제거
-- 예: "스터디방 42" → "스터디방"
--
-- 실행 방법 (홈서버):
--   docker compose exec db psql -U postgres -d chatdigest -f /path/to/migrate_v1_1.sql
-- 또는 로컬 개발:
--   psql -U postgres -d chatdigest -f migrate_v1_1.sql

BEGIN;

UPDATE chat_rooms
SET name = regexp_replace(name, '\s+\d+$', '')
WHERE name ~ '\s+\d+$';

-- 이름 정리 후 중복이 생긴 경우 확인 (수동 처리 필요)
-- SELECT name, COUNT(*) FROM chat_rooms GROUP BY name HAVING COUNT(*) > 1;

COMMIT;
