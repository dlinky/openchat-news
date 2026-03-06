"""요약 생성 라우터 — SSE 스트리밍, 배치 방식"""
import calendar
import datetime as dt
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.models import (
    ChatRoom, ChatMessage, DailySummary,
    DailyDigest, WeeklyDigest, MonthlyDigest,
)
from app.services import gemini as gemini_svc

router = APIRouter(prefix="/generate", tags=["generate"])


# ─── 배치 헬퍼 ────────────────────────────────────────────────────────────────

async def _ensure_daily_digest(db: AsyncSession, target_date: dt.date) -> None:
    """일간 다이제스트가 없을 때만 생성. 이미 있으면 스킵."""
    existing = await db.execute(select(DailyDigest).where(DailyDigest.date == target_date))
    if existing.scalar_one_or_none():
        return

    rooms_result = await db.execute(select(ChatRoom))
    rooms = rooms_result.scalars().all()
    room_summaries = []

    for room in rooms:
        msgs_result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.room_id == room.id,
                ChatMessage.chat_date == target_date,
                ChatMessage.message_type == "text",
            )
            .order_by(ChatMessage.sent_at)
        )
        messages = msgs_result.scalars().all()
        if not messages:
            continue

        structured = await gemini_svc.summarize_room_daily(
            room_name=room.name, messages=messages, target_date=target_date
        )
        topics = structured.get("topics", [])
        summary_md = json.dumps(structured, ensure_ascii=False)

        existing_ds = await db.execute(
            select(DailySummary).where(
                DailySummary.room_id == room.id, DailySummary.date == target_date
            )
        )
        ds = existing_ds.scalar_one_or_none()
        if ds:
            ds.summary_md = summary_md
            ds.topics = topics
        else:
            db.add(DailySummary(
                room_id=room.id, date=target_date,
                summary_md=summary_md, topics=topics,
            ))
        await db.flush()
        room_summaries.append({"room": room, "structured": structured})

    if not room_summaries:
        return

    digest_md = await gemini_svc.combine_daily_digest(room_summaries, target_date)
    db.add(DailyDigest(date=target_date, content_md=digest_md))
    await db.commit()


async def _ensure_weekly_digest(db: AsyncSession, year: int, week: int) -> None:
    """주간 다이제스트가 없을 때만 생성 (일간 배치 포함). 이미 있으면 스킵."""
    existing = await db.execute(
        select(WeeklyDigest).where(WeeklyDigest.year == year, WeeklyDigest.week == week)
    )
    if existing.scalar_one_or_none():
        return

    date_from = dt.date.fromisocalendar(year, week, 1)
    date_to = dt.date.fromisocalendar(year, week, 7)

    dates_result = await db.execute(
        select(ChatMessage.chat_date).distinct()
        .where(ChatMessage.chat_date >= date_from, ChatMessage.chat_date <= date_to)
    )
    for d in sorted(dates_result.scalars().all()):
        await _ensure_daily_digest(db, d)

    daily_result = await db.execute(
        select(DailyDigest)
        .where(DailyDigest.date >= date_from, DailyDigest.date <= date_to)
        .order_by(DailyDigest.date)
    )
    dailies = daily_result.scalars().all()
    if not dailies:
        return

    content_md = await gemini_svc.summarize_weekly(dailies, year, week)
    db.add(WeeklyDigest(
        year=year, week=week, content_md=content_md,
        date_from=date_from, date_to=date_to,
    ))
    await db.commit()


# ─── 엔드포인트 ───────────────────────────────────────────────────────────────

@router.get("/available")
async def get_available():
    """생성 가능한 날짜/주/월 목록 반환 (메시지는 있지만 다이제스트 미생성 항목 포함)"""
    async with AsyncSessionLocal() as db:
        msg_dates_result = await db.execute(
            select(ChatMessage.chat_date).distinct().order_by(ChatMessage.chat_date.desc())
        )
        msg_dates: set[dt.date] = set(msg_dates_result.scalars().all())

        digest_dates_result = await db.execute(select(DailyDigest.date))
        digest_dates: set[dt.date] = set(digest_dates_result.scalars().all())

        weekly_result = await db.execute(select(WeeklyDigest.year, WeeklyDigest.week))
        weekly_done = {f"{r.year}-W{r.week:02d}" for r in weekly_result.all()}

        monthly_result = await db.execute(select(MonthlyDigest.year, MonthlyDigest.month))
        monthly_done = {f"{r.year}-{r.month:02d}" for r in monthly_result.all()}

    daily = sorted(
        [{"value": str(d), "has_digest": d in digest_dates} for d in msg_dates],
        key=lambda x: x["value"],
        reverse=True,
    )

    weeks: dict[str, dict] = {}
    for d in msg_dates:
        iso = d.isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
        if key not in weeks:
            date_from = dt.date.fromisocalendar(iso.year, iso.week, 1)
            date_to = dt.date.fromisocalendar(iso.year, iso.week, 7)
            month = date_from.month
            week_of_month = (date_from.day - 1) // 7 + 1
            weeks[key] = {
                "value": key,
                "label": f"{month}월 {week_of_month}주차",
                "date_from": str(date_from),
                "date_to": str(date_to),
                "has_digest": key in weekly_done,
            }
    weekly = sorted(weeks.values(), key=lambda x: x["value"], reverse=True)

    months: dict[str, dict] = {}
    for d in msg_dates:
        key = f"{d.year}-{d.month:02d}"
        if key not in months:
            months[key] = {
                "value": key,
                "label": f"{d.year}년 {d.month}월",
                "has_digest": key in monthly_done,
            }
    monthly = sorted(months.values(), key=lambda x: x["value"], reverse=True)

    return {"daily": daily, "weekly": weekly, "monthly": monthly}


@router.post("/daily/{date_str}")
async def generate_daily(date_str: str):
    """일간 다이제스트 생성 (SSE 스트리밍)"""
    try:
        target_date = dt.date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="날짜 형식 오류 (YYYY-MM-DD)")

    async def event_stream():
        async with AsyncSessionLocal() as db:
            rooms_result = await db.execute(select(ChatRoom))
            rooms = rooms_result.scalars().all()
            total = len(rooms)
            room_summaries = []
            progress = 0

            for room in rooms:
                msgs_result = await db.execute(
                    select(ChatMessage)
                    .where(
                        ChatMessage.room_id == room.id,
                        ChatMessage.chat_date == target_date,
                        ChatMessage.message_type == "text",
                    )
                    .order_by(ChatMessage.sent_at)
                )
                messages = msgs_result.scalars().all()
                if not messages:
                    continue

                progress += 1
                yield f"data: {json.dumps({'status': 'processing', 'progress': progress, 'total': total}, ensure_ascii=False)}\n\n"

                structured = await gemini_svc.summarize_room_daily(
                    room_name=room.name, messages=messages, target_date=target_date
                )
                topics = structured.get("topics", [])
                summary_md = json.dumps(structured, ensure_ascii=False)

                existing_ds = await db.execute(
                    select(DailySummary).where(
                        DailySummary.room_id == room.id,
                        DailySummary.date == target_date,
                    )
                )
                ds = existing_ds.scalar_one_or_none()
                if ds:
                    ds.summary_md = summary_md
                    ds.topics = topics
                else:
                    db.add(DailySummary(
                        room_id=room.id, date=target_date,
                        summary_md=summary_md, topics=topics,
                    ))
                await db.flush()
                room_summaries.append({"room": room, "structured": structured})

            if not room_summaries:
                yield f"data: {json.dumps({'status': 'error', 'message': '해당 날짜에 메시지가 없습니다'}, ensure_ascii=False)}\n\n"
                return

            yield f"data: {json.dumps({'status': 'combining'}, ensure_ascii=False)}\n\n"

            digest_md = await gemini_svc.combine_daily_digest(
                room_summaries=room_summaries, target_date=target_date
            )

            existing_digest = await db.execute(
                select(DailyDigest).where(DailyDigest.date == target_date)
            )
            dd = existing_digest.scalar_one_or_none()
            if dd:
                dd.content_md = digest_md
            else:
                db.add(DailyDigest(date=target_date, content_md=digest_md))
            await db.commit()

            yield f"data: {json.dumps({'status': 'done', 'date': date_str}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/weekly/{year_week}")
async def generate_weekly(year_week: str):
    """주간 다이제스트 생성 (SSE, 일간 배치 포함)"""
    try:
        year_str, week_str = year_week.split("-W")
        year, week = int(year_str), int(week_str)
    except Exception:
        raise HTTPException(status_code=400, detail="형식 오류 (YYYY-WXX)")

    date_from = dt.date.fromisocalendar(year, week, 1)
    date_to = dt.date.fromisocalendar(year, week, 7)

    async def event_stream():
        async with AsyncSessionLocal() as db:
            # 1. 해당 주 메시지 있는 날짜 조회 (없으면 거부)
            dates_result = await db.execute(
                select(ChatMessage.chat_date).distinct()
                .where(ChatMessage.chat_date >= date_from, ChatMessage.chat_date <= date_to)
            )
            dates_with_msgs = sorted(dates_result.scalars().all())

            if not dates_with_msgs:
                yield f"data: {json.dumps({'status': 'error', 'message': '해당 주의 채팅 데이터가 없습니다'}, ensure_ascii=False)}\n\n"
                return

            # 2. 일간 배치
            for d in dates_with_msgs:
                existing_dd = await db.execute(select(DailyDigest).where(DailyDigest.date == d))
                if existing_dd.scalar_one_or_none():
                    continue
                yield f"data: {json.dumps({'status': 'batch_daily', 'date': str(d)}, ensure_ascii=False)}\n\n"
                await _ensure_daily_digest(db, d)

            # 3. 주간 다이제스트 생성
            yield f"data: {json.dumps({'status': 'combining'}, ensure_ascii=False)}\n\n"

            daily_result = await db.execute(
                select(DailyDigest)
                .where(DailyDigest.date >= date_from, DailyDigest.date <= date_to)
                .order_by(DailyDigest.date)
            )
            dailies = daily_result.scalars().all()

            if not dailies:
                yield f"data: {json.dumps({'status': 'error', 'message': '해당 주의 일간 데이터가 없습니다'}, ensure_ascii=False)}\n\n"
                return

            content_md = await gemini_svc.summarize_weekly(dailies, year, week)

            existing_wd = await db.execute(
                select(WeeklyDigest).where(WeeklyDigest.year == year, WeeklyDigest.week == week)
            )
            wd = existing_wd.scalar_one_or_none()
            if wd:
                wd.content_md = content_md
            else:
                db.add(WeeklyDigest(
                    year=year, week=week, content_md=content_md,
                    date_from=date_from, date_to=date_to,
                ))
            await db.commit()

            yield f"data: {json.dumps({'status': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/monthly/{year_month}")
async def generate_monthly(year_month: str):
    """월간 다이제스트 생성 (SSE, 주간/일간 배치 포함)"""
    try:
        year_str, month_str = year_month.split("-")
        year, month = int(year_str), int(month_str)
    except Exception:
        raise HTTPException(status_code=400, detail="형식 오류 (YYYY-MM)")

    last_day = calendar.monthrange(year, month)[1]
    period_end = dt.date(year, month, last_day)
    month_start = dt.date(year, month, 1)

    async def event_stream():
        async with AsyncSessionLocal() as db:
            # 1. 해당 월에 채팅 데이터가 있는지 확인
            msg_check = await db.execute(
                select(func.count()).select_from(ChatMessage)
                .where(ChatMessage.chat_date >= month_start, ChatMessage.chat_date <= period_end)
            )
            if not msg_check.scalar_one():
                yield f"data: {json.dumps({'status': 'error', 'message': '해당 월의 채팅 데이터가 없습니다'}, ensure_ascii=False)}\n\n"
                return

            # 2. 해당 월에 포함된 주차 산출 (date_from이 월 시작 이후인 주만)
            weeks_in_month: dict[str, tuple[int, int]] = {}
            for offset in range(last_day):
                d = month_start + dt.timedelta(days=offset)
                iso = d.isocalendar()
                key = f"{iso.year}-W{iso.week:02d}"
                if key not in weeks_in_month:
                    w_date_from = dt.date.fromisocalendar(iso.year, iso.week, 1)
                    if w_date_from >= month_start:
                        weeks_in_month[key] = (iso.year, iso.week)

            # 3. 주간 배치
            for key in sorted(weeks_in_month.keys()):
                w_year, w_week = weeks_in_month[key]
                existing_wd = await db.execute(
                    select(WeeklyDigest).where(
                        WeeklyDigest.year == w_year, WeeklyDigest.week == w_week
                    )
                )
                if existing_wd.scalar_one_or_none():
                    continue
                yield f"data: {json.dumps({'status': 'batch_weekly', 'week': key}, ensure_ascii=False)}\n\n"
                await _ensure_weekly_digest(db, w_year, w_week)

            # 4. 월간 다이제스트 생성
            yield f"data: {json.dumps({'status': 'combining'}, ensure_ascii=False)}\n\n"

            weekly_result = await db.execute(
                select(WeeklyDigest)
                .where(
                    WeeklyDigest.date_from >= month_start,
                    WeeklyDigest.date_from <= period_end,
                )
                .order_by(WeeklyDigest.week)
            )
            weeklies = weekly_result.scalars().all()

            if not weeklies:
                yield f"data: {json.dumps({'status': 'error', 'message': '해당 월의 주간 데이터가 없습니다'}, ensure_ascii=False)}\n\n"
                return

            content_md = await gemini_svc.summarize_monthly(weeklies, year, month)

            existing_md = await db.execute(
                select(MonthlyDigest).where(
                    MonthlyDigest.year == year, MonthlyDigest.month == month
                )
            )
            md = existing_md.scalar_one_or_none()
            if md:
                md.content_md = content_md
            else:
                db.add(MonthlyDigest(year=year, month=month, content_md=content_md))
            await db.commit()

            yield f"data: {json.dumps({'status': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
