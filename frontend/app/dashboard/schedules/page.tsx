"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { ApiError, Schedule, SchedulesListResponse } from "@/lib/types";
import ScheduleTable from "@/components/ScheduleTable";
import Spinner from "@/components/Spinner";

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<SchedulesListResponse>("/schedules");
      setSchedules(res.schedules);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDelete(scheduleId: string) {
    if (!confirm("Delete this schedule? This cannot be undone.")) return;
    try {
      await apiFetch(`/schedules/${scheduleId}`, { method: "DELETE" });
      setSchedules((prev) => prev.filter((s) => s.scheduleId !== scheduleId));
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to delete schedule");
    }
  }

  async function handleToggleEnabled(scheduleId: string, enabled: boolean) {
    try {
      await apiFetch(`/schedules/${scheduleId}`, {
        method: "PUT",
        body: { enabled },
      });
      setSchedules((prev) =>
        prev.map((s) => (s.scheduleId === scheduleId ? { ...s, enabled } : s))
      );
    } catch (err) {
      alert(
        err instanceof ApiError ? err.message : "Failed to update schedule"
      );
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-900">Schedules</h1>
        <Link
          href="/dashboard/schedules/new"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          New schedule
        </Link>
      </div>

      {loading && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4" />
          Loading…
        </p>
      )}
      {error && (
        <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {!loading && !error && (
        <ScheduleTable
          schedules={schedules}
          onDelete={handleDelete}
          onToggleEnabled={handleToggleEnabled}
        />
      )}
    </div>
  );
}
