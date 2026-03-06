"""
카카오톡 오픈채팅 내보내기 파일 파서

파일 형식:
  1행: "{채팅방이름} 님과 카카오톡 대화" 또는 "{채팅방이름} 님과의 채팅"
  2행: "저장한 날짜 : YYYY년 MM월 DD일 오전/오후 HH:MM"
  메시지: "YYYY년 MM월 DD일 오전/오후 HH:MM, 닉네임 : 내용"
  시스템: "YYYY년 MM월 DD일 오전/오후 HH:MM, 닉네임님이 들어왔습니다."
"""
import re
from datetime import datetime, date, timedelta
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ParsedMessage:
    sender: Optional[str]
    content: Optional[str]
    message_type: str  # text, image, emoticon, system
    sent_at: datetime
    chat_date: date  # 새벽 4시 기준


@dataclass
class ParsedFile:
    room_name: str
    messages: list[ParsedMessage] = field(default_factory=list)


# "YYYY년 MM월 DD일 오전/오후 HH:MM" 타임스탬프 파싱
_TS_PATTERN = re.compile(
    r"(\d{4})년\s+(\d{1,2})월\s+(\d{1,2})일\s+(오전|오후)\s+(\d{1,2}):(\d{2})"
)

# 메시지 라인: "타임스탬프, 닉네임 : 내용"
_MSG_PATTERN = re.compile(
    r"^(\d{4}년\s+\d{1,2}월\s+\d{1,2}일\s+(?:오전|오후)\s+\d{1,2}:\d{2}),\s+(.+?)\s+:\s+(.*)$"
)

# 시스템 라인: "타임스탬프, 닉네임님이 들어왔습니다/나갔습니다"
_SYSTEM_PATTERN = re.compile(
    r"^(\d{4}년\s+\d{1,2}월\s+\d{1,2}일\s+(?:오전|오후)\s+\d{1,2}:\d{2}),\s+(.+)$"
)

# 날짜 구분선 (시각만 있는 줄)
_DATE_SEPARATOR_PATTERN = re.compile(
    r"^\d{4}년\s+\d{1,2}월\s+\d{1,2}일\s+(?:오전|오후)\s+\d{1,2}:\d{2}$"
)


def _parse_timestamp(ts_str: str) -> datetime:
    m = _TS_PATTERN.search(ts_str)
    if not m:
        raise ValueError(f"타임스탬프 파싱 실패: {ts_str}")
    year, month, day, ampm, hour, minute = m.groups()
    hour = int(hour)
    if ampm == "오후" and hour != 12:
        hour += 12
    elif ampm == "오전" and hour == 12:
        hour = 0
    return datetime(int(year), int(month), int(day), hour, int(minute))


def _get_chat_date(sent_at: datetime) -> date:
    """새벽 4시 기준으로 날짜 반환 (00:00~03:59는 전날로 처리)"""
    if sent_at.hour < 4:
        return (sent_at - timedelta(days=1)).date()
    return sent_at.date()


def _classify_content(content: str) -> tuple[str, str]:
    """내용에서 메시지 타입과 실제 내용 반환"""
    stripped = content.strip()
    if stripped == "사진":
        return "image", stripped
    if stripped == "이모티콘":
        return "emoticon", stripped
    if stripped == "동영상":
        return "image", stripped
    if stripped == "파일":
        return "image", stripped
    return "text", stripped


def parse_kakao_file(text: str) -> ParsedFile:
    lines = text.splitlines()

    if not lines:
        raise ValueError("빈 파일입니다")

    # 1행: 채팅방 이름 추출
    first_line = lines[0].strip()
    # "XXX 님과 카카오톡 대화" 또는 "XXX 님과의 채팅"
    room_name_match = re.match(r"^(.+?)\s+님과", first_line)
    if room_name_match:
        room_name = re.sub(r"\s+\d+$", "", room_name_match.group(1)).strip()
    else:
        room_name = re.sub(r"\s+\d+$", "", first_line).strip()  # fallback

    messages: list[ParsedMessage] = []

    for line in lines[2:]:  # 1~2행 스킵
        line = line.strip()
        if not line:
            continue

        # 날짜만 있는 구분선 스킵
        if _DATE_SEPARATOR_PATTERN.match(line):
            continue

        # 메시지 라인 시도
        msg_match = _MSG_PATTERN.match(line)
        if msg_match:
            ts_str, sender, content = msg_match.groups()
            sent_at = _parse_timestamp(ts_str)
            msg_type, clean_content = _classify_content(content)
            messages.append(ParsedMessage(
                sender=sender.strip(),
                content=clean_content,
                message_type=msg_type,
                sent_at=sent_at,
                chat_date=_get_chat_date(sent_at),
            ))
            continue

        # 시스템 라인 시도 (들어왔습니다/나갔습니다)
        sys_match = _SYSTEM_PATTERN.match(line)
        if sys_match:
            ts_str, content = sys_match.groups()
            if any(kw in content for kw in ["들어왔습니다", "나갔습니다", "초대했습니다", "내보냈습니다"]):
                sent_at = _parse_timestamp(ts_str)
                messages.append(ParsedMessage(
                    sender=None,
                    content=content.strip(),
                    message_type="system",
                    sent_at=sent_at,
                    chat_date=_get_chat_date(sent_at),
                ))

    return ParsedFile(room_name=room_name, messages=messages)


def get_date_range(parsed: ParsedFile) -> tuple[Optional[date], Optional[date]]:
    dates = [m.chat_date for m in parsed.messages if m.message_type != "system"]
    if not dates:
        return None, None
    return min(dates), max(dates)


def drop_last_date(parsed: ParsedFile) -> ParsedFile:
    """마지막 날짜(하루가 완성되지 않은 데이터)를 제거하여 반환"""
    dates = [m.chat_date for m in parsed.messages if m.message_type != "system"]
    if not dates:
        return parsed
    last_date = max(dates)
    filtered = [m for m in parsed.messages if m.chat_date != last_date]
    return ParsedFile(room_name=parsed.room_name, messages=filtered)
