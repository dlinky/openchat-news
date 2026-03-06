const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: "include",
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export const auth = {
  login: (password: string) =>
    request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    }),
  logout: () => request("/auth/logout", { method: "POST" }),
  verify: () => request<{ authenticated: boolean }>("/auth/verify"),
};

// ─── Upload ──────────────────────────────────────────────────────────────────

export interface UploadPreview {
  room_name: string;
  date_from: string | null;
  date_to: string | null;
  total_message_count: number;
  new_dates: string[];
  skipped_dates: string[];
  existing_room: boolean;
}

export interface UploadResult {
  room_id: number;
  room_name: string;
  inserted_messages: number;
  new_dates: string[];
  skipped_dates: string[];
}

export const upload = {
  preview: (file: File): Promise<UploadPreview> => {
    const form = new FormData();
    form.append("file", file);
    return request("/upload/preview", { method: "POST", body: form });
  },
  commit: (file: File): Promise<UploadResult> => {
    const form = new FormData();
    form.append("file", file);
    return request("/upload/commit", { method: "POST", body: form });
  },
};

// ─── Rooms ───────────────────────────────────────────────────────────────────

export interface Room {
  id: number;
  name: string;
  tags: string[];
}

export interface RoomCoverage {
  id: number;
  name: string;
  max_date: string | null;
  stale: boolean;
}

export interface CoverageData {
  global_max_date: string | null;
  rooms: RoomCoverage[];
}

async function requestNoBody(path: string, init?: RequestInit): Promise<void> {
  const res = await fetch(`${BASE_URL}${path}`, { credentials: "include", ...init });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string })?.detail ?? `HTTP ${res.status}`);
  }
}

export const rooms = {
  list: () => request<Room[]>("/rooms"),
  updateTags: (id: number, tags: string[]) =>
    request<Room>(`/rooms/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
    }),
  coverage: () => request<CoverageData>("/rooms/coverage"),
  deleteRoom: (id: number) => requestNoBody(`/rooms/${id}`, { method: "DELETE" }),
};

// ─── Summaries ───────────────────────────────────────────────────────────────

export interface NavData {
  daily: { label: string; value: string }[];
  weekly: { label: string; value: string; date_from: string; date_to: string }[];
  monthly: { label: string; value: string }[];
}

export interface DigestContent {
  content_md: string;
  date?: string;
  date_from?: string;
  date_to?: string;
  year?: number;
  week?: number;
  month?: number;
}

export const summaries = {
  nav: () => request<NavData>("/summaries/nav"),
  daily: (date: string) => request<DigestContent>(`/summaries/daily/${date}`),
  weekly: (yearWeek: string) => request<DigestContent>(`/summaries/weekly/${yearWeek}`),
  monthly: (yearMonth: string) => request<DigestContent>(`/summaries/monthly/${yearMonth}`),
};

// ─── Generate ────────────────────────────────────────────────────────────────

export interface AvailableDate {
  value: string;
  has_digest: boolean;
}
export interface AvailableWeek {
  value: string;
  label: string;
  date_from: string;
  date_to: string;
  has_digest: boolean;
}
export interface AvailableMonth {
  value: string;
  label: string;
  has_digest: boolean;
}
export interface AvailableItems {
  daily: AvailableDate[];
  weekly: AvailableWeek[];
  monthly: AvailableMonth[];
}

export const generate = {
  available: () => request<AvailableItems>("/generate/available"),
  daily: (date: string) =>
    fetch(`${BASE_URL}/generate/daily/${date}`, {
      method: "POST",
      credentials: "include",
    }),
  weekly: (yearWeek: string) =>
    fetch(`${BASE_URL}/generate/weekly/${yearWeek}`, {
      method: "POST",
      credentials: "include",
    }),
  monthly: (yearMonth: string) =>
    fetch(`${BASE_URL}/generate/monthly/${yearMonth}`, {
      method: "POST",
      credentials: "include",
    }),
};
