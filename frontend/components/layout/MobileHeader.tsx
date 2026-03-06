"use client";

import { useState } from "react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar } from "./Sidebar";

export function MobileHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="flex items-center justify-between border-b border-neutral-100 px-4 py-3 lg:hidden">
      <span className="text-base font-bold">
        Chat<span className="text-orange-500">Digest</span>
      </span>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <button className="p-1 text-neutral-500 hover:text-neutral-900">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <line x1="3" y1="5" x2="17" y2="5" />
              <line x1="3" y1="10" x2="17" y2="10" />
              <line x1="3" y1="15" x2="17" y2="15" />
            </svg>
          </button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 p-0">
          <Sidebar onClose={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
    </header>
  );
}
