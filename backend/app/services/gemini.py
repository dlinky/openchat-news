"""Gemini API 연동 서비스"""
import asyncio
import json
import logging
import re
from datetime import date
from typing import Any
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)
_MODEL = "gemini-2.5-flash"
_sem = asyncio.Semaphore(30)  # 최대 동시 Gemini 호출 수


async def _generate(prompt: str) -> str:
    """비동기 Gemini 호출 (120초 타임아웃, 동시 호출 세마포어)"""
    async with _sem:
        logger.info("Gemini 호출 시작 (프롬프트 %d자)", len(prompt))
        try:
            response = await asyncio.wait_for(
                _client.aio.models.generate_content(
                    model=_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                ),
                timeout=120.0,
            )
            logger.info("Gemini 호출 완료")
            return response.text
        except asyncio.TimeoutError:
            logger.error("Gemini 호출 타임아웃 (120초 초과, 프롬프트 %d자)", len(prompt))
            raise Exception("Gemini API 타임아웃")


def _extract_json(text: str) -> Any:
    """마크다운 코드블록 제거 후 JSON 파싱"""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    return json.loads(cleaned)


async def summarize_room_daily(room_name: str, messages: list[Any], target_date: date) -> dict:
    """채팅방 하루치 메시지를 분석하여 토픽별 구조화된 요약 반환.

    반환 형식:
    {
        "topics": ["AI 도구", "개발 팁"],
        "points": [
            {"topic": "AI 도구", "title": "GPT Pro 할인", "content": "..."},
            ...
        ]
    }
    """
    msg_lines = "\n".join(
        f"[{m.sent_at.strftime('%H:%M')}] {m.sender}: {m.content}"
        for m in messages
        if m.content
    )

    prompt = f"""아래는 카카오 오픈채팅방의 {target_date.strftime('%Y년 %m월 %d일')} 대화 내역입니다.

{msg_lines}

위 대화를 분석하여 **아래 JSON 형식으로만** 응답하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다.

{{
  "topics": ["토픽1", "토픽2"],
  "points": [
    {{
      "topic": "토픽명",
      "title": "항목 제목",
      "content": "2~4문장 설명"
    }}
  ]
}}

규칙:
- topics: 이 채팅방 대화에서 도출된 분야/주제 태그 (예: "AI 도구", "개발 팁", "비즈니스", "커뮤니티")
- points: 실질적인 정보, 팁, 논의 내용만 포함 (인사, 이모티콘, 단순 반응 제외)
- 각 point의 topic은 topics 배열 중 하나와 일치해야 함
- 대화 내용이 없거나 정보성 내용이 없으면 {{"topics": [], "points": []}} 반환

우선순위 토픽 — 아래에 해당하는 내용은 반드시 별도 point로 분리하고 topic을 명확히 구분:
- 개인사업자 (세금, 계약, 사업 운영, 프리랜서 계약)
- 1인개발 / 바이브코딩 (솔로 개발, AI 코딩 도구 활용, 개발 워크플로우, vibe coding)
- 고충 / 문제 해결 (막히는 점, 실패 사례, 어려움 공유)
- 아이디어 (새 기능, 서비스, 사업 아이디어 제안)
- 리뷰 요청 (피드백 요청, 코드 리뷰, 서비스 리뷰)"""

    raw = await _generate(prompt)
    try:
        return _extract_json(raw)
    except Exception:
        # 파싱 실패 시 빈 구조 반환
        return {"topics": [], "points": []}


async def combine_daily_digest(room_summaries: list[dict], target_date: date) -> str:
    """각 채팅방의 토픽별 포인트를 통합하여 분야별 마크다운 다이제스트 생성"""

    # 토픽별로 포인트 집계
    topic_map: dict[str, list[dict]] = {}
    for rs in room_summaries:
        room_name = rs["room_name"]
        structured = rs["structured"]  # {"topics": [...], "points": [...]}
        for point in structured.get("points", []):
            topic = point.get("topic", "기타")
            if topic not in topic_map:
                topic_map[topic] = []
            topic_map[topic].append({
                "title": point.get("title", ""),
                "content": point.get("content", ""),
                "room": room_name,
            })

    if not topic_map:
        return "_오늘은 공유된 정보가 없습니다._"

    # 토픽별 섹션을 Gemini에게 보기 좋게 정리 요청
    sections_text = ""
    for topic, points in topic_map.items():
        sections_text += f"\n### {topic}\n"
        for p in points:
            sections_text += f"- **{p['title']}**: {p['content']}\n"

    prompt = f"""{target_date.strftime('%Y년 %m월 %d일')} 오픈채팅 다이제스트 원문입니다:

{sections_text}

위 내용을 뉴스레터 형식의 한국어 마크다운으로 다듬어 주세요.

규칙:
- 각 토픽 섹션은 ## 이모지 토픽명 으로 시작 (적절한 이모지 선택)
- 각 항목은 **굵은 제목** + 설명 단락 형식
- 같은 토픽 내 중복/유사 내용은 하나로 합치기
- 날짜 헤더 작성 금지 (UI에서 표시함)
- 마크다운만 출력, 추가 설명 없음

가중치 규칙:
1. 우선순위 토픽(개인사업자, 1인개발/바이브코딩, 고충, 아이디어, 리뷰 요청)에 해당하는 섹션 중
   내용이 가장 풍부한 2개를 "핵심 섹션"으로 선정
2. 핵심 섹션은 일반 섹션보다 3배 분량으로 작성:
   - 각 항목에 맥락, 논의 흐름, 실용적 인사이트까지 서술
   - 다양한 관점과 구체적 내용을 풍부하게 포함
3. 핵심 섹션은 문서 상단에 배치"""

    return await _generate(prompt)


async def summarize_weekly(dailies: list[Any], year: int, week: int) -> str:
    """일간 다이제스트들을 주간으로 요약"""
    combined = "\n\n".join(
        f"### {d.date.strftime('%m월 %d일')}\n{d.content_md}" for d in dailies
    )

    prompt = f"""{year}년 {week}주차의 일간 다이제스트입니다:

{combined}

위 내용을 **주간 뉴스레터** 형식으로 재구성해 주세요.

규칙:
- 한 주 동안의 주요 흐름과 트렌드를 분야별로 정리
- 반복적으로 언급된 주제는 "이번 주 주목" 섹션에 강조
- 각 섹션은 ## 이모지 분야명
- 간결하고 읽기 쉽게 작성
- 마크다운만 출력"""

    return await _generate(prompt)


async def summarize_monthly(weeklies: list[Any], year: int, month: int) -> str:
    """주간 다이제스트들을 월간으로 요약"""
    combined = "\n\n".join(
        f"### {w.date_from.strftime('%m월 %d일')} ~ {w.date_to.strftime('%m월 %d일')}\n{w.content_md}"
        for w in weeklies
    )

    prompt = f"""{year}년 {month}월의 주간 다이제스트입니다:

{combined}

위 내용을 **월간 뉴스레터** 형식으로 재구성해 주세요.

규칙:
- 이달의 주요 이슈와 트렌드를 분야별로 정리
- 특히 중요했던 사건/정보는 강조
- 각 섹션은 ## 이모지 분야명
- 간결하고 통찰력 있게 작성
- 마크다운만 출력"""

    return await _generate(prompt)
