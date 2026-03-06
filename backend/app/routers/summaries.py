from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import Optional
from app.database import get_db
from app.models.models import DailyDigest, WeeklyDigest, MonthlyDigest

router = APIRouter(prefix="/summaries", tags=["summaries"])


class DigestResponse(BaseModel):
    id: int
    content_md: Optional[str]

    class Config:
        from_attributes = True


class NavItem(BaseModel):
    label: str
    value: str


class NavGroup(BaseModel):
    type: str  # daily, weekly, monthly
    items: list[NavItem]


@router.get("/nav")
async def get_nav(db: AsyncSession = Depends(get_db)):
    """사이드바 네비게이션용 날짜 목록"""
    daily_result = await db.execute(
        select(DailyDigest.date).order_by(DailyDigest.date.desc()).limit(30)
    )
    daily_dates = daily_result.scalars().all()

    weekly_result = await db.execute(
        select(WeeklyDigest.year, WeeklyDigest.week, WeeklyDigest.date_from, WeeklyDigest.date_to)
        .order_by(WeeklyDigest.year.desc(), WeeklyDigest.week.desc())
        .limit(12)
    )
    weekly_rows = weekly_result.all()

    monthly_result = await db.execute(
        select(MonthlyDigest.year, MonthlyDigest.month)
        .order_by(MonthlyDigest.year.desc(), MonthlyDigest.month.desc())
        .limit(12)
    )
    monthly_rows = monthly_result.all()

    def format_date_kr(d: date) -> str:
        return f"{d.month}월 {d.day}일"

    def format_week_kr(year: int, week: int, date_from: date, date_to: date) -> str:
        # ISO 주차를 월 기준 주차로 변환
        month = date_from.month
        month_start = date_from.replace(day=1)
        week_of_month = (date_from.day - 1) // 7 + 1
        return f"{month}월 {week_of_month}주차"

    return {
        "daily": [
            {"label": format_date_kr(d), "value": str(d)}
            for d in daily_dates
        ],
        "weekly": [
            {
                "label": format_week_kr(r.year, r.week, r.date_from, r.date_to),
                "value": f"{r.year}-W{r.week:02d}",
                "date_from": str(r.date_from),
                "date_to": str(r.date_to),
            }
            for r in weekly_rows
        ],
        "monthly": [
            {"label": f"{r.year}년 {r.month}월", "value": f"{r.year}-{r.month:02d}"}
            for r in monthly_rows
        ],
    }


@router.get("/daily/{date_str}")
async def get_daily(date_str: str, db: AsyncSession = Depends(get_db)):
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)")

    result = await db.execute(select(DailyDigest).where(DailyDigest.date == d))
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="해당 날짜의 다이제스트가 없습니다")
    return {"date": str(d), "content_md": digest.content_md}


@router.get("/weekly/{year_week}")
async def get_weekly(year_week: str, db: AsyncSession = Depends(get_db)):
    try:
        year, week = year_week.split("-W")
        year, week = int(year), int(week)
    except Exception:
        raise HTTPException(status_code=400, detail="형식이 올바르지 않습니다 (YYYY-WXX)")

    result = await db.execute(
        select(WeeklyDigest).where(WeeklyDigest.year == year, WeeklyDigest.week == week)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="해당 주차의 다이제스트가 없습니다")
    return {
        "year": year,
        "week": week,
        "date_from": str(digest.date_from),
        "date_to": str(digest.date_to),
        "content_md": digest.content_md,
    }


@router.get("/monthly/{year_month}")
async def get_monthly(year_month: str, db: AsyncSession = Depends(get_db)):
    try:
        year, month = year_month.split("-")
        year, month = int(year), int(month)
    except Exception:
        raise HTTPException(status_code=400, detail="형식이 올바르지 않습니다 (YYYY-MM)")

    result = await db.execute(
        select(MonthlyDigest).where(MonthlyDigest.year == year, MonthlyDigest.month == month)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="해당 월의 다이제스트가 없습니다")
    return {"year": year, "month": month, "content_md": digest.content_md}
