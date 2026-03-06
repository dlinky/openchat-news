"""example.txt 파서 동작 확인"""
import sys
sys.path.insert(0, ".")

from app.services.parser import parse_kakao_file, get_date_range

with open("../example.txt", encoding="utf-8") as f:
    text = f.read()

result = parse_kakao_file(text)
date_from, date_to = get_date_range(result)

print(f"채팅방: {result.room_name}")
print(f"날짜범위: {date_from} ~ {date_to}")
print(f"전체 메시지 수: {len(result.messages)}")
print()

for m in result.messages:
    print(f"[{m.chat_date}] [{m.message_type}] {m.sender or 'SYSTEM'}: {m.content[:40] if m.content else ''}")
