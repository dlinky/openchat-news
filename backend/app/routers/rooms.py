from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.models import ChatRoom, ChatMessage

router = APIRouter(prefix="/rooms", tags=["rooms"])


class RoomCreate(BaseModel):
    name: str
    tags: List[str] = []


class RoomUpdate(BaseModel):
    tags: List[str]


class RoomResponse(BaseModel):
    id: int
    name: str
    tags: List[str]

    class Config:
        from_attributes = True


@router.get("", response_model=List[RoomResponse])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatRoom).order_by(ChatRoom.name))
    return result.scalars().all()


@router.patch("/{room_id}", response_model=RoomResponse)
async def update_room_tags(room_id: int, body: RoomUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다")
    room.tags = body.tags
    await db.commit()
    await db.refresh(room)
    return room


@router.get("/coverage")
async def rooms_coverage(db: AsyncSession = Depends(get_db)):
    """채팅방별 마지막 메시지 날짜 및 global max 반환"""
    rows_result = await db.execute(
        select(ChatRoom.id, ChatRoom.name, func.max(ChatMessage.chat_date).label("max_date"))
        .join(ChatMessage, ChatMessage.room_id == ChatRoom.id, isouter=True)
        .group_by(ChatRoom.id, ChatRoom.name)
        .order_by(ChatRoom.name)
    )
    rows = rows_result.all()

    if not rows:
        return {"global_max_date": None, "rooms": []}

    global_max = max((r.max_date for r in rows if r.max_date is not None), default=None)

    rooms_data = [
        {
            "id": r.id,
            "name": r.name,
            "max_date": str(r.max_date) if r.max_date else None,
            "stale": bool(r.max_date and global_max and r.max_date < global_max),
        }
        for r in rows
    ]

    return {
        "global_max_date": str(global_max) if global_max else None,
        "rooms": rooms_data,
    }


@router.delete("/{room_id}", status_code=204)
async def delete_room(room_id: int, db: AsyncSession = Depends(get_db)):
    """채팅방 및 관련 데이터 전체 삭제 (messages, daily_summaries 포함)"""
    result = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다")
    await db.delete(room)
    await db.commit()
