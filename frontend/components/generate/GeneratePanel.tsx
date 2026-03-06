"use client";

import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  generate, rooms,
  type AvailableItems, type RoomCoverage,
} from "@/lib/api";

type GenType = "daily" | "weekly" | "monthly";

type LogEntry = { text: string; type: "info" | "batch" | "done" | "error" };

interface CoverageDialog {
  staleRooms: RoomCoverage[];
  decisions: Record<number, "keep" | "delete">;
  pendingType: "weekly" | "monthly";
  pendingValue: string;
}

interface BatchConfirmDialog {
  type: "weekly" | "monthly";
  value: string;
  missingDaily: number;
  missingWeekly: number;
}

interface Props {
  onGenerated?: () => void;
}

function getMonthLastDay(yearMonth: string): string {
  const [year, month] = yearMonth.split("-").map(Number);
  return new Date(year, month, 0).toISOString().split("T")[0];
}

export function GeneratePanel({ onGenerated }: Props) {
  const [available, setAvailable] = useState<AvailableItems | null>(null);
  const [loading, setLoading] = useState(true);

  const [selectedDaily, setSelectedDaily] = useState("");
  const [selectedWeekly, setSelectedWeekly] = useState("");
  const [selectedMonthly, setSelectedMonthly] = useState("");

  const [activeType, setActiveType] = useState<GenType | null>(null);
  const [progressText, setProgressText] = useState<string | null>(null);
  const [logLines, setLogLines] = useState<LogEntry[]>([]);
  const [running, setRunning] = useState(false);

  const [coverageDialog, setCoverageDialog] = useState<CoverageDialog | null>(null);
  const [batchConfirmDialog, setBatchConfirmDialog] = useState<BatchConfirmDialog | null>(null);

  const fetchAvailable = async () => {
    try {
      const data = await generate.available();
      setAvailable(data);
      if (data.daily.length > 0) setSelectedDaily(data.daily[0].value);
      if (data.weekly.length > 0) setSelectedWeekly(data.weekly[0].value);
      if (data.monthly.length > 0) setSelectedMonthly(data.monthly[0].value);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAvailable(); }, []);

  // ── SSE 이벤트 처리 ────────────────────────────────────────────────────────

  function handleSseEvent(evt: Record<string, unknown>) {
    if (evt.status === "processing") {
      setProgressText(`데이터 분석 중... (${evt.progress}/${evt.total})`);
    } else if (evt.status === "combining") {
      setProgressText(null);
      setLogLines((prev) => [...prev, { text: "다이제스트 생성 중...", type: "info" }]);
    } else if (evt.status === "batch_daily") {
      setLogLines((prev) => [
        ...prev,
        { text: `${evt.date} 일간 생성 중...`, type: "batch" },
      ]);
    } else if (evt.status === "batch_weekly") {
      setLogLines((prev) => [
        ...prev,
        { text: `${evt.week} 주간 생성 중...`, type: "batch" },
      ]);
    } else if (evt.status === "done") {
      setProgressText(null);
      setLogLines((prev) => [...prev, { text: "완료!", type: "done" }]);
    } else if (evt.status === "error") {
      setProgressText(null);
      setLogLines((prev) => [
        ...prev,
        { text: (evt.message as string) || "오류 발생", type: "error" },
      ]);
    }
  }

  async function readSse(res: Response) {
    if (!res.body) throw new Error("스트림 없음");
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          handleSseEvent(evt);
          if (evt.status === "done") {
            await fetchAvailable();
            onGenerated?.();
          }
        } catch {}
      }
    }
  }

  // ── 일간 생성 ──────────────────────────────────────────────────────────────

  const runDaily = async () => {
    if (!selectedDaily || running) return;
    setActiveType("daily");
    setProgressText(null);
    setLogLines([]);
    setRunning(true);
    try {
      const res = await generate.daily(selectedDaily);
      await readSse(res);
    } catch (e: unknown) {
      setLogLines([{ text: e instanceof Error ? e.message : "오류", type: "error" }]);
    } finally {
      setRunning(false);
    }
  };

  // ── 주간/월간 — 커버리지 체크 후 생성 ────────────────────────────────────

  async function runGenerate(type: "weekly" | "monthly", value: string) {
    setRunning(true);
    try {
      const res = type === "weekly"
        ? await generate.weekly(value)
        : await generate.monthly(value);
      await readSse(res);
    } catch (e: unknown) {
      setLogLines((prev) => [
        ...prev,
        { text: e instanceof Error ? e.message : "오류", type: "error" },
      ]);
    } finally {
      setRunning(false);
    }
  }

  async function checkCoverageAndRun(type: "weekly" | "monthly", value: string) {
    setActiveType(type);
    setProgressText(null);
    setLogLines([]);

    // 하위 요약 누락 확인 (available 상태 기반, 동기)
    let missingDaily = 0;
    let missingWeekly = 0;

    if (type === "weekly") {
      const weekItem = available!.weekly.find((w) => w.value === value);
      if (weekItem) {
        missingDaily = available!.daily.filter(
          (d) => d.value >= weekItem.date_from && d.value <= weekItem.date_to && !d.has_digest
        ).length;
      }
    } else {
      const monthStart = `${value}-01`;
      const monthEnd = getMonthLastDay(value);
      missingDaily = available!.daily.filter(
        (d) => d.value >= monthStart && d.value <= monthEnd && !d.has_digest
      ).length;
      missingWeekly = available!.weekly.filter(
        (w) => w.date_from >= monthStart && w.date_from <= monthEnd && !w.has_digest
      ).length;
    }

    if (missingDaily > 0 || missingWeekly > 0) {
      setBatchConfirmDialog({ type, value, missingDaily, missingWeekly });
      return;
    }

    await checkStaleRoomsAndRun(type, value);
  }

  async function checkStaleRoomsAndRun(type: "weekly" | "monthly", value: string) {
    setRunning(true);
    let coverage;
    try {
      coverage = await rooms.coverage();
    } catch (e: unknown) {
      setLogLines([{ text: "커버리지 확인 실패: " + (e instanceof Error ? e.message : "오류"), type: "error" }]);
      setRunning(false);
      return;
    }

    const staleRooms = coverage.rooms.filter((r) => r.stale);
    if (staleRooms.length > 0) {
      setCoverageDialog({
        staleRooms,
        decisions: Object.fromEntries(staleRooms.map((r) => [r.id, "keep" as const])),
        pendingType: type,
        pendingValue: value,
      });
      setRunning(false);
      return;
    }

    await runGenerate(type, value);
  }

  async function onBatchConfirm() {
    if (!batchConfirmDialog) return;
    const { type, value } = batchConfirmDialog;
    setBatchConfirmDialog(null);
    await checkStaleRoomsAndRun(type, value);
  }

  async function onCoverageConfirm() {
    if (!coverageDialog) return;
    const { decisions, pendingType, pendingValue } = coverageDialog;
    setCoverageDialog(null);
    setRunning(true);

    for (const [id, action] of Object.entries(decisions)) {
      if (action === "delete") {
        try { await rooms.deleteRoom(Number(id)); } catch {}
      }
    }

    await runGenerate(pendingType, pendingValue);
  }

  // ── 렌더 ──────────────────────────────────────────────────────────────────

  if (loading) return <div className="p-4 text-sm text-neutral-400">로딩 중...</div>;
  if (!available) return null;

  return (
    <>
      <div className="p-4 space-y-5">
        <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wide">요약 생성</p>

        {/* 일간 */}
        <div className="space-y-1">
          <p className="text-xs text-neutral-500">일간</p>
          <div className="flex gap-2">
            <select
              value={selectedDaily}
              onChange={(e) => setSelectedDaily(e.target.value)}
              disabled={running || available.daily.length === 0}
              className="flex-1 text-sm rounded-md border border-neutral-200 px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-orange-400 disabled:opacity-50"
            >
              {available.daily.length === 0 && <option>날짜 없음</option>}
              {available.daily.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.value} {d.has_digest ? "✓" : ""}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              onClick={runDaily}
              disabled={running || available.daily.length === 0}
              className="bg-orange-500 hover:bg-orange-600 text-white text-xs"
            >
              생성
            </Button>
          </div>
        </div>

        {/* 주간 */}
        <div className="space-y-1">
          <p className="text-xs text-neutral-500">주간</p>
          <div className="flex gap-2">
            <select
              value={selectedWeekly}
              onChange={(e) => setSelectedWeekly(e.target.value)}
              disabled={running || available.weekly.length === 0}
              className="flex-1 text-sm rounded-md border border-neutral-200 px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-orange-400 disabled:opacity-50"
            >
              {available.weekly.length === 0 && <option>주차 없음</option>}
              {available.weekly.map((w) => (
                <option key={w.value} value={w.value}>
                  {w.label} {w.has_digest ? "✓" : ""}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              onClick={() => checkCoverageAndRun("weekly", selectedWeekly)}
              disabled={running || available.weekly.length === 0}
              className="bg-orange-500 hover:bg-orange-600 text-white text-xs"
            >
              생성
            </Button>
          </div>
        </div>

        {/* 월간 */}
        <div className="space-y-1">
          <p className="text-xs text-neutral-500">월간</p>
          <div className="flex gap-2">
            <select
              value={selectedMonthly}
              onChange={(e) => setSelectedMonthly(e.target.value)}
              disabled={running || available.monthly.length === 0}
              className="flex-1 text-sm rounded-md border border-neutral-200 px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-orange-400 disabled:opacity-50"
            >
              {available.monthly.length === 0 && <option>월 없음</option>}
              {available.monthly.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label} {m.has_digest ? "✓" : ""}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              onClick={() => checkCoverageAndRun("monthly", selectedMonthly)}
              disabled={running || available.monthly.length === 0}
              className="bg-orange-500 hover:bg-orange-600 text-white text-xs"
            >
              생성
            </Button>
          </div>
        </div>

        {/* 진행 상태 */}
        {(progressText || logLines.length > 0) && (
          <div className="rounded-lg border border-neutral-100 bg-neutral-50 p-3 space-y-1">
            <p className="text-xs font-medium text-neutral-400 mb-2">
              {activeType === "daily" ? "일간" : activeType === "weekly" ? "주간" : "월간"} 생성 진행
            </p>

            {progressText && (
              <div className="flex items-center gap-2 text-xs text-neutral-600">
                <div className="h-3 w-3 rounded-full border border-orange-400 border-t-transparent animate-spin" />
                <span>{progressText}</span>
              </div>
            )}

            {logLines.map((entry, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span>
                  {entry.type === "done" ? "✅" : entry.type === "error" ? "❌" : entry.type === "batch" ? "⚙️" : "🔗"}
                </span>
                <span className={entry.type === "error" ? "text-red-500" : "text-neutral-600"}>
                  {entry.text}
                </span>
              </div>
            ))}

            {running && !progressText && (
              <div className="flex items-center gap-2 text-xs text-neutral-400 pt-1">
                <div className="h-3 w-3 rounded-full border border-orange-400 border-t-transparent animate-spin" />
                <span>처리 중...</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 배치 생성 확인 대화상자 */}
      {batchConfirmDialog && (
        <Dialog open onOpenChange={(open) => { if (!open) setBatchConfirmDialog(null); }}>
          <DialogContent className="max-w-sm">
            <DialogHeader>
              <DialogTitle>하위 요약 자동 생성</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-neutral-600">
              {batchConfirmDialog.type === "weekly" ? "선택한 주에" : "선택한 월에"}{" "}
              생성되지 않은 하위 요약이 있습니다. 자동으로 생성한 후 진행합니다.
            </p>
            <div className="space-y-1 text-sm text-neutral-700">
              {batchConfirmDialog.missingDaily > 0 && (
                <p>• 일간 요약 <span className="font-medium">{batchConfirmDialog.missingDaily}개</span></p>
              )}
              {batchConfirmDialog.missingWeekly > 0 && (
                <p>• 주간 요약 <span className="font-medium">{batchConfirmDialog.missingWeekly}개</span></p>
              )}
            </div>
            <div className="flex gap-2 justify-end pt-2">
              <Button variant="outline" onClick={() => setBatchConfirmDialog(null)}>취소</Button>
              <Button onClick={onBatchConfirm} className="bg-orange-500 hover:bg-orange-600 text-white">
                확인 후 생성
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* 채팅방 커버리지 대화상자 */}
      {coverageDialog && (
        <Dialog open onOpenChange={(open) => { if (!open) { setCoverageDialog(null); setRunning(false); } }}>
          <DialogContent className="max-w-sm">
            <DialogHeader>
              <DialogTitle>채팅방 데이터 확인</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-neutral-600">
              일부 채팅방의 데이터가 최신 날짜보다 뒤처져 있습니다.
              각 채팅방을 요약에 포함할지 선택하세요.
            </p>
            <div className="space-y-3">
              {coverageDialog.staleRooms.map((room) => (
                <div key={room.id} className="rounded-lg border p-3 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium">{room.name}</span>
                    <span className="text-neutral-400 text-xs">마지막: {room.max_date}</span>
                  </div>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                      <input
                        type="radio"
                        name={`room-${room.id}`}
                        checked={coverageDialog.decisions[room.id] === "keep"}
                        onChange={() =>
                          setCoverageDialog((prev) =>
                            prev ? { ...prev, decisions: { ...prev.decisions, [room.id]: "keep" } } : null
                          )
                        }
                      />
                      그대로 유지
                    </label>
                    <label className="flex items-center gap-1.5 text-sm cursor-pointer text-red-600">
                      <input
                        type="radio"
                        name={`room-${room.id}`}
                        checked={coverageDialog.decisions[room.id] === "delete"}
                        onChange={() =>
                          setCoverageDialog((prev) =>
                            prev ? { ...prev, decisions: { ...prev.decisions, [room.id]: "delete" } } : null
                          )
                        }
                      />
                      채팅방 삭제
                    </label>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2 justify-end pt-2">
              <Button
                variant="outline"
                onClick={() => { setCoverageDialog(null); setRunning(false); }}
              >
                취소
              </Button>
              <Button
                onClick={onCoverageConfirm}
                className="bg-orange-500 hover:bg-orange-600 text-white"
              >
                확인 후 생성
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
