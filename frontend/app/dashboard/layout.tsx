"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AuthContext, getCurrentUserFromToken, clearToken } from "@/lib/auth";
import type { User } from "@/lib/types";
import Nav from "@/components/Nav";
import Spinner from "@/components/Spinner";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<(User & { permissions: string[] }) | null>(
    null
  );
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    const current = getCurrentUserFromToken();
    setUser(current);
    setLoading(false);
    if (!current) {
      router.replace("/login");
    }
  }, [router]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function logout() {
    clearToken();
    setUser(null);
    router.replace("/login");
  }

  function mergeUser(partial: Partial<User>) {
    setUser((prev) => (prev ? { ...prev, ...partial } : prev));
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 text-slate-500">
        <Spinner className="h-5 w-5" />
        Loading…
      </div>
    );
  }

  if (!user) {
    // redirect already triggered in refresh(); render nothing while it happens
    return null;
  }

  return (
    <AuthContext.Provider value={{ user, loading, refresh, logout, mergeUser }}>
      <div className="min-h-screen bg-slate-50">
        <Nav />
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </div>
    </AuthContext.Provider>
  );
}
