"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUserFromToken } from "@/lib/auth";
import Spinner from "@/components/Spinner";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const user = getCurrentUserFromToken();
    router.replace(user ? "/dashboard/schedules" : "/login");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center gap-2 text-slate-500">
      <Spinner className="h-5 w-5" />
      Loading…
    </div>
  );
}
