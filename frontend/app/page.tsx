"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { auth } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    auth
      .verify()
      .then(() => router.push("/daily"))
      .catch(() => router.push("/login"));
  }, [router]);

  return null;
}
