"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { ApiError, Schedule, ScheduleInput } from "@/lib/types";
import ScheduleForm from "@/components/ScheduleForm";
import Spinner from "@/components/Spinner";

interface GetScheduleResponse {
  success: true;
  schedule: Schedule;
}

export default function EditSchedulePage() {
  const router = useRouter();
  const params = useParams<{ scheduleId: string }>();
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await apiFetch<GetScheduleResponse>(
          `/schedules/${params.scheduleId}`
        );
        if (!cancelled) setSchedule(res.schedule);
      } catch (err) {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError ? err.message : "Failed to load schedule"
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [params.scheduleId]);

  async function handleUpdate(input: ScheduleInput) {
    try {
      await apiFetch(`/schedules/${params.scheduleId}`, {
        method: "PUT",
        body: input,
      });
      router.push("/dashboard/schedules");
    } catch (err) {
      throw new Error(
        err instanceof ApiError ? err.message : "Failed to update schedule"
      );
    }
  }

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner className="h-4 w-4" />
        Loading…
      </p>
    );
  }

  if (loadError || !schedule) {
    return (
      <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
        {loadError ?? "Schedule not found"}
      </p>
    );
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-6 text-lg font-semibold text-slate-900">
        Edit schedule
      </h1>
      <ScheduleForm
        initial={schedule}
        onSubmit={handleUpdate}
        submitLabel="Save changes"
      />
    </div>
  );
}
