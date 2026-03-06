"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { UploadModal } from "@/components/upload/UploadModal";
import { summaries, auth, type NavData } from "@/lib/api";

type ViewType = "daily" | "weekly" | "monthly";

export function Sidebar({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const [nav, setNav] = useState<NavData | null>(null);
  const [openSection, setOpenSection] = useState<ViewType>("daily");
  const [uploadOpen, setUploadOpen] = useState(false);

  const fetchNav = useCallback(async () => {
    try {
      const data = await summaries.nav();
      setNav(data);
    } catch {}
  }, []);

  useEffect(() => { fetchNav(); }, [fetchNav]);

  const handleLogout = async () => {
    await auth.logout();
    router.push("/login");
  };

  const navItem = (href: string, label: string) => {
    const active = pathname === href;
    return (
      <Link
        key={href}
        href={href}
        onClick={onClose}
        className={`block px-3 py-1.5 rounded-md text-sm transition-colors ${
          active
            ? "bg-orange-50 text-orange-600 font-medium"
            : "text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900"
        }`}
      >
        {label}
      </Link>
    );
  };

  const SectionHeader = ({ type, label }: { type: ViewType; label: string }) => (
    <button
      onClick={() => setOpenSection(openSection === type ? ("" as ViewType) : type)}
      className="flex w-full items-center justify-between px-1 py-1 text-xs font-semibold text-neutral-400 uppercase tracking-wide hover:text-neutral-600 transition-colors"
    >
      {label}
      <span className="text-neutral-300">{openSection === type ? "▲" : "▼"}</span>
    </button>
  );

  return (
    <div className="flex h-full flex-col">
      {/* 로고 */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-neutral-100">
        <Link href="/" className="text-lg font-bold tracking-tight">
          Chat<span className="text-orange-500">Digest</span>
        </Link>
        <button
          onClick={handleLogout}
          className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors"
        >
          로그아웃
        </button>
      </div>

      <ScrollArea className="flex-1 px-3 py-3">
        <div className="space-y-4">
          {/* 일간 */}
          <div>
            <SectionHeader type="daily" label="일간" />
            {openSection === "daily" && (
              <div className="mt-1 space-y-0.5">
                {nav?.daily.length === 0 && (
                  <p className="px-3 py-2 text-xs text-neutral-400">데이터 없음</p>
                )}
                {nav?.daily.map((d) =>
                  navItem(`/daily/${d.value}`, d.value.replace(/^\d{4}-/, "").replace(/-(\d+)$/, " $1일").replace(/-/, "월 "))
                )}
              </div>
            )}
          </div>

          {/* 주간 */}
          <div>
            <SectionHeader type="weekly" label="주간" />
            {openSection === "weekly" && (
              <div className="mt-1 space-y-0.5">
                {nav?.weekly.length === 0 && (
                  <p className="px-3 py-2 text-xs text-neutral-400">데이터 없음</p>
                )}
                {nav?.weekly.map((w) =>
                  navItem(`/weekly/${w.value}`, w.label)
                )}
              </div>
            )}
          </div>

          {/* 월간 */}
          <div>
            <SectionHeader type="monthly" label="월간" />
            {openSection === "monthly" && (
              <div className="mt-1 space-y-0.5">
                {nav?.monthly.length === 0 && (
                  <p className="px-3 py-2 text-xs text-neutral-400">데이터 없음</p>
                )}
                {nav?.monthly.map((m) =>
                  navItem(`/monthly/${m.value}`, m.label)
                )}
              </div>
            )}
          </div>

          <Separator />

          {/* 설정 */}
          {navItem("/settings", "채팅방 설정")}
        </div>
      </ScrollArea>

      {/* 하단 버튼 영역 */}
      <div className="border-t border-neutral-100 p-3">
        <Button
          variant="outline"
          size="sm"
          className="w-full text-xs"
          onClick={() => setUploadOpen(true)}
        >
          파일 업로드 / 요약 생성
        </Button>
      </div>

      <UploadModal
        open={uploadOpen}
        onClose={() => {
          setUploadOpen(false);
          fetchNav();
        }}
      />
    </div>
  );
}
