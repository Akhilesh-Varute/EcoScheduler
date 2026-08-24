"use client";

import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { ApiError, ScheduleInput } from "@/lib/types";
import ScheduleForm from "@/components/ScheduleForm";

export default function NewSchedulePage() {
  const router = useRouter();

  async function handleCreate(input: ScheduleInput) {
    try {
      await apiFetch("/schedules", { method: "POST", body: input });
      router.push("/dashboard/schedules");
    } catch (err) {
      throw new Error(
        err instanceof ApiError ? err.message : "Failed to create schedule"
      );
    }
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-6 text-lg font-semibold text-slate-900">New schedule</h1>
      <ScheduleForm onSubmit={handleCreate} submitLabel="Create schedule" />
    </div>
  );
}
