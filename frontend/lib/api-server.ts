/**
 * 서버 컴포넌트 전용 API 클라이언트
 * next/headers로 쿠키를 읽어 백엔드 요청에 포함시킵니다.
 */
import { cookies } from "next/headers";
import type { DigestContent } from "./api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function requestServer<T>(path: string): Promise<T> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token");

  const res = await fetch(`${BASE_URL}${path}`, {
    headers: token ? { Cookie: `access_token=${token.value}` } : {},
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export const summariesServer = {
  daily: (date: string) =>
    requestServer<DigestContent>(`/summaries/daily/${date}`),
  weekly: (yearWeek: string) =>
    requestServer<DigestContent>(`/summaries/weekly/${yearWeek}`),
  monthly: (yearMonth: string) =>
    requestServer<DigestContent>(`/summaries/monthly/${yearMonth}`),
};
