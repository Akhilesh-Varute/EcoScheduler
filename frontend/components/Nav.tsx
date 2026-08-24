"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

export default function Nav() {
  const { user, logout } = useAuth();

  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-6">
          <Link href="/dashboard/schedules" className="font-semibold text-slate-900">
            EcoScheduler
          </Link>
          <Link
            href="/dashboard/accounts/new"
            className="text-sm text-slate-600 hover:text-slate-900"
          >
            Connect AWS account
          </Link>
          {(user?.role === "admin" ||
            user?.role === "finance" ||
            (user?.permissions ?? []).includes("view_savings")) && (
            <Link
              href="/dashboard/savings"
              className="text-sm text-slate-600 hover:text-slate-900"
            >
              Savings
            </Link>
          )}
        </div>

        <div className="flex items-center gap-4 text-sm">
          {user && (
            <span className="text-slate-500">
              {user.email}{" "}
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium uppercase text-slate-600">
                {user.role}
              </span>
            </span>
          )}
          <button
            onClick={logout}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            Log out
          </button>
        </div>
      </div>
    </nav>
  );
}
