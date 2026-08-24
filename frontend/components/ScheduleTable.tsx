"use client";

import { useState } from "react";
import Link from "next/link";
import type { Schedule } from "@/lib/types";
import Spinner from "@/components/Spinner";

interface Props {
  schedules: Schedule[];
  onDelete: (scheduleId: string) => Promise<void>;
  onToggleEnabled: (scheduleId: string, enabled: boolean) => Promise<void>;
}

type PendingAction = { scheduleId: string; action: "toggle" | "delete" } | null;

export default function ScheduleTable({ schedules, onDelete, onToggleEnabled }: Props) {
  const [pending, setPending] = useState<PendingAction>(null);

  async function handleDeleteClick(scheduleId: string) {
    setPending({ scheduleId, action: "delete" });
    try {
      await onDelete(scheduleId);
    } finally {
      setPending(null);
    }
  }

  async function handleToggleClick(scheduleId: string, enabled: boolean) {
    setPending({ scheduleId, action: "toggle" });
    try {
      await onToggleEnabled(scheduleId, enabled);
    } finally {
      setPending(null);
    }
  }

  if (schedules.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
        No schedules yet.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3">Account</th>
            <th className="px-4 py-3">Instances</th>
            <th className="px-4 py-3">Start / Stop cron</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {schedules.map((s) => {
            const isTogglePending =
              pending?.scheduleId === s.scheduleId && pending.action === "toggle";
            const isDeletePending =
              pending?.scheduleId === s.scheduleId && pending.action === "delete";
            const isAnyPending = pending?.scheduleId === s.scheduleId;
            return (
              <tr key={s.scheduleId} className="border-b border-slate-100 last:border-0">
                <td className="px-4 py-3 font-medium text-slate-900">{s.name}</td>
                <td className="px-4 py-3 text-slate-600">{s.accountId}</td>
                <td className="px-4 py-3 text-slate-600">{s.instanceIds.length}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-600">
                  {s.startCron} / {s.stopCron}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${
                        s.enabled
                          ? "bg-green-100 text-green-700"
                          : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {s.enabled ? "enabled" : "disabled"}
                    </span>
                    {s.dryRun && (
                      <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                        dry-run
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => handleToggleClick(s.scheduleId, !s.enabled)}
                    disabled={isAnyPending}
                    className="mr-3 inline-flex items-center gap-1 text-slate-600 hover:text-slate-900 hover:underline disabled:opacity-50"
                  >
                    {isTogglePending && <Spinner className="h-3 w-3" />}
                    {s.enabled ? "Disable" : "Enable"}
                  </button>
                  <Link
                    href={`/dashboard/schedules/${s.scheduleId}`}
                    className="mr-3 text-slate-600 hover:text-slate-900 hover:underline"
                  >
                    Edit
                  </Link>
                  <button
                    onClick={() => handleDeleteClick(s.scheduleId)}
                    disabled={isAnyPending}
                    className="inline-flex items-center gap-1 text-red-600 hover:text-red-800 hover:underline disabled:opacity-50"
                  >
                    {isDeletePending && <Spinner className="h-3 w-3" />}
                    Delete
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
