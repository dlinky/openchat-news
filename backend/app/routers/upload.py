from fastapi import APIRouter, UploadFile, File, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import Optional
from app.database import get_db
from app.models.models import ChatRoom, ChatMessage
from app.services.parser import parse_kakao_file, get_date_range, drop_last_date

router = APIRouter(prefix="/upload", tags=["upload"])


class UploadPreview(BaseModel):
    room_name: str
    date_from: Optional[str]
    date_to: Optional[str]
    total_message_count: int
    new_dates: list[str]
    skipped_dates: list[str]
    existing_room: bool


class UploadResult(BaseModel):
    room_id: int
    room_name: str
    inserted_messages: int
    new_dates: list[str]
    skipped_dates: list[str]


async def _get_existing_dates(db: AsyncSession, room_id: int) -> set[date]:
    """DB에 이미 메시지가 있는 날짜 집합 반환"""
    result = await db.execute(
        select(ChatMessage.chat_date)
        .where(ChatMessage.room_id == room_id)
        .distinct()
    )
    return set(result.scalars().all())


@router.post("/preview", response_model=UploadPreview)
async def preview_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")

    parsed = drop_last_date(parse_kakao_file(text))
    date_from, date_to = get_date_range(parsed)

    result = await db.execute(select(ChatRoom).where(ChatRoom.name == parsed.room_name))
    existing_room = result.scalar_one_or_none()

    existing_dates: set[date] = set()
    if existing_room:
        existing_dates = await _get_existing_dates(db, existing_room.id)

    dates_in_file: set[date] = {
        m.chat_date for m in parsed.messages if m.message_type != "system"
    }
    new_dates = sorted(dates_in_file - existing_dates)
    skipped_dates = sorted(dates_in_file & existing_dates)

    return UploadPreview(
        room_name=parsed.room_name,
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
        total_message_count=len([m for m in parsed.messages if m.message_type != "system"]),
        new_dates=[str(d) for d in new_dates],
        skipped_dates=[str(d) for d in skipped_dates],
        existing_room=existing_room is not None,
    )


@router.post("/commit", response_model=UploadResult)
async def commit_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")

    parsed = drop_last_date(parse_kakao_file(text))

    # 채팅방 조회 또는 생성
    result = await db.execute(select(ChatRoom).where(ChatRoom.name == parsed.room_name))
    room = result.scalar_one_or_none()
    if not room:
        room = ChatRoom(name=parsed.room_name, tags=[])
        db.add(room)
        await db.flush()

    # 이미 DB에 있는 날짜 확인
    existing_dates = await _get_existing_dates(db, room.id)

    dates_in_file: set[date] = {m.chat_date for m in parsed.messages}
    new_dates = sorted(dates_in_file - existing_dates)
    skipped_dates = sorted(dates_in_file & existing_dates)

    # 새로운 날짜의 메시지만 삽입 (기존 날짜는 완전히 무시)
    new_date_set = set(new_dates)
    new_messages = [
        ChatMessage(
            room_id=room.id,
            sender=m.sender,
            content=m.content,
            message_type=m.message_type,
            sent_at=m.sent_at,
            chat_date=m.chat_date,
        )
        for m in parsed.messages
        if m.chat_date in new_date_set
    ]
    db.add_all(new_messages)
    await db.commit()

    return UploadResult(
        room_id=room.id,
        room_name=room.name,
        inserted_messages=len(new_messages),
        new_dates=[str(d) for d in new_dates],
        skipped_dates=[str(d) for d in skipped_dates],
    )
