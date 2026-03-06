"use client";

import { useCallback, useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { upload, type UploadPreview, type UploadResult } from "@/lib/api";
import { GeneratePanel } from "@/components/generate/GeneratePanel";

type Step = "idle" | "loading_previews" | "previews_ready" | "committing" | "all_done";

interface FilePair {
  file: File;
  preview?: UploadPreview;
  error?: string;
}

interface FileResult {
  file: File;
  result?: UploadResult;
  error?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export function UploadModal({ open, onClose }: Props) {
  const [step, setStep] = useState<Step>("idle");
  const [filePairs, setFilePairs] = useState<FilePair[]>([]);
  const [results, setResults] = useState<FileResult[]>([]);
  const [dragging, setDragging] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setStep("idle");
    setFilePairs([]);
    setResults([]);
    setGlobalError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleFiles = async (selected: File[]) => {
    const txtFiles = selected.filter((f) => f.name.endsWith(".txt"));
    if (txtFiles.length === 0) {
      setGlobalError(".txt 파일만 업로드할 수 있습니다");
      return;
    }
    setGlobalError(null);
    setStep("loading_previews");

    const pairs: FilePair[] = await Promise.all(
      txtFiles.map(async (file) => {
        try {
          const preview = await upload.preview(file);
          return { file, preview };
        } catch (e: unknown) {
          return { file, error: e instanceof Error ? e.message : "미리보기 실패" };
        }
      })
    );

    setFilePairs(pairs);
    setStep("previews_ready");
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(Array.from(e.dataTransfer.files));
  }, []);

  const handleCommit = async () => {
    const uploadable = filePairs.filter((p) => p.preview && p.preview.new_dates.length > 0);
    setStep("committing");

    const uploadResults: FileResult[] = [];
    for (const pair of uploadable) {
      try {
        const result = await upload.commit(pair.file);
        uploadResults.push({ file: pair.file, result });
      } catch (e: unknown) {
        uploadResults.push({ file: pair.file, error: e instanceof Error ? e.message : "업로드 실패" });
      }
    }

    setResults(uploadResults);
    setStep("all_done");
  };

  const totalNewDates = filePairs.reduce(
    (sum, p) => sum + (p.preview?.new_dates.length ?? 0),
    0
  );
  const totalInserted = results.reduce(
    (sum, r) => sum + (r.result?.inserted_messages ?? 0),
    0
  );

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>파일 업로드 / 요약 생성</DialogTitle>
        </DialogHeader>

        {/* ── idle: 파일 선택 ── */}
        {step === "idle" && (
          <div className="space-y-4">
            <div
              className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 cursor-pointer transition-colors ${
                dragging ? "border-orange-400 bg-orange-50" : "border-neutral-200 hover:border-orange-300"
              }`}
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <span className="text-3xl mb-2">📂</span>
              <p className="text-sm text-neutral-500 text-center">
                파일을 드래그하거나 클릭하여 선택
              </p>
              <p className="text-xs text-neutral-400 mt-1">카카오톡 내보내기 .txt — 여러 파일 동시 선택 가능</p>
              <input
                ref={inputRef}
                type="file"
                accept=".txt"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) handleFiles(Array.from(e.target.files));
                }}
              />
            </div>
            {globalError && <p className="text-sm text-red-500 text-center">{globalError}</p>}
            <div className="border-t pt-3">
              <p className="text-xs text-neutral-400 text-center mb-2">파일 없이 요약만 생성하려면</p>
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-xs text-neutral-500"
                onClick={() => setStep("all_done")}
              >
                요약 생성 바로 시작
              </Button>
            </div>
          </div>
        )}

        {/* ── loading_previews ── */}
        {step === "loading_previews" && (
          <div className="flex flex-col items-center py-8 gap-3">
            <div className="h-6 w-6 rounded-full border-2 border-orange-400 border-t-transparent animate-spin" />
            <p className="text-sm text-neutral-500">파일 분석 중...</p>
          </div>
        )}

        {/* ── previews_ready: 전체 미리보기 ── */}
        {step === "previews_ready" && (
          <div className="space-y-4">
            <div className="space-y-3">
              {filePairs.map((pair, i) => (
                <div key={i} className="rounded-lg border p-3 text-sm space-y-2">
                  <p className="font-medium text-neutral-700 truncate">
                    {pair.preview?.room_name ?? pair.file.name}
                  </p>
                  {pair.error ? (
                    <p className="text-red-500 text-xs">{pair.error}</p>
                  ) : pair.preview ? (
                    <div className="flex gap-3 text-xs text-neutral-500">
                      <span>
                        <Badge variant="default" className="bg-orange-500 text-white mr-1">
                          {pair.preview.new_dates.length}일
                        </Badge>
                        신규
                      </span>
                      {pair.preview.skipped_dates.length > 0 && (
                        <span>
                          <Badge variant="secondary" className="mr-1">
                            {pair.preview.skipped_dates.length}일
                          </Badge>
                          건너뜀
                        </span>
                      )}
                      <span className="ml-auto">
                        {pair.preview.date_from} ~ {pair.preview.date_to}
                      </span>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>

            {totalNewDates === 0 && (
              <p className="text-sm text-center text-neutral-400">추가할 새 날짜가 없습니다.</p>
            )}

            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={reset}>취소</Button>
              <Button
                onClick={() => setStep("all_done")}
                variant="ghost"
                className="text-xs text-neutral-500"
              >
                업로드 건너뛰고 생성
              </Button>
              <Button
                onClick={handleCommit}
                disabled={totalNewDates === 0}
                className="bg-orange-500 hover:bg-orange-600 text-white"
              >
                업로드 확인
              </Button>
            </div>
          </div>
        )}

        {/* ── committing ── */}
        {step === "committing" && (
          <div className="flex flex-col items-center py-8 gap-3">
            <div className="h-6 w-6 rounded-full border-2 border-orange-400 border-t-transparent animate-spin" />
            <p className="text-sm text-neutral-500">저장 중...</p>
          </div>
        )}

        {/* ── all_done: 결과 + GeneratePanel ── */}
        {step === "all_done" && (
          <div className="space-y-4">
            {results.length > 0 && (
              <div className="rounded-lg bg-orange-50 border border-orange-100 px-4 py-3 text-sm space-y-1">
                <p className="font-medium text-orange-700">업로드 완료</p>
                {results.map((r, i) => (
                  r.result ? (
                    <p key={i} className="text-xs text-neutral-600">
                      {r.result.room_name} — {r.result.new_dates.length}일 / {r.result.inserted_messages.toLocaleString()}개 메시지
                    </p>
                  ) : (
                    <p key={i} className="text-xs text-red-500">{r.file.name}: {r.error}</p>
                  )
                ))}
              </div>
            )}

            <div className="rounded-lg border border-neutral-100 bg-neutral-50">
              <GeneratePanel />
            </div>

            <Button variant="outline" className="w-full" onClick={handleClose}>
              닫기
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
