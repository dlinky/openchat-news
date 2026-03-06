"use client";

import { useEffect, useState } from "react";
import { rooms, type Room } from "@/lib/api";

export function RoomSettings() {
  const [roomList, setRoomList] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    rooms.list().then((data) => { setRoomList(data); setLoading(false); });
  }, []);

  if (loading) return <p className="text-sm text-neutral-400 p-4">로딩 중...</p>;

  if (roomList.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-neutral-400 text-sm gap-2">
        <p>등록된 채팅방이 없습니다.</p>
        <p className="text-xs">파일을 업로드하면 채팅방이 자동 등록됩니다.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-4">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-neutral-900">채팅방 목록</h1>
        <p className="text-sm text-neutral-500 mt-1">
          토픽 태그는 요약 생성 시 Gemini가 자동으로 분류합니다.
        </p>
      </div>

      {roomList.map((room) => (
        <div key={room.id} className="rounded-xl border border-neutral-100 p-4">
          <p className="font-medium text-sm text-neutral-900">{room.name}</p>
        </div>
      ))}
    </div>
  );
}
