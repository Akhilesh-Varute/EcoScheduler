"use client";

import { useState, FormEvent } from "react";
import type { Schedule, ScheduleInput } from "@/lib/types";
import InstancePicker from "@/components/InstancePicker";
import TimezoneSelect from "@/components/TimezoneSelect";
import ScheduleTimingFields from "@/components/ScheduleTimingFields";
import Spinner from "@/components/Spinner";

interface Props {
  initial?: Schedule;
  onSubmit: (input: ScheduleInput) => Promise<void>;
  submitLabel: string;
}

export default function ScheduleForm({ initial, onSubmit, submitLabel }: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [accountId, setAccountId] = useState(initial?.accountId ?? "");
  const [instanceIds, setInstanceIds] = useState<string[]>(
    initial?.instanceIds ?? []
  );
  const [startCron, setStartCron] = useState(initial?.startCron ?? "0 8 * * 1-5");
  const [stopCron, setStopCron] = useState(initial?.stopCron ?? "0 19 * * 1-5");
  const [timezone, setTimezone] = useState(initial?.timezone ?? "UTC");
  const [dryRun, setDryRun] = useState(initial?.dryRun ?? false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function handleAccountIdChange(next: string) {
    setAccountId(next);
    // Switching accounts invalidates any previously picked instance IDs.
    setInstanceIds([]);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (instanceIds.length === 0) {
      setError("Select at least one instance");
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        accountId: accountId.trim(),
        instanceIds,
        startCron: startCron.trim(),
        stopCron: stopCron.trim(),
        timezone: timezone.trim() || "UTC",
        dryRun,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">Name</label>
        <input
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />
      </div>

      <InstancePicker
        accountId={accountId}
        onAccountIdChange={handleAccountIdChange}
        selectedInstanceIds={instanceIds}
        onSelectedInstanceIdsChange={setInstanceIds}
      />

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          Schedule timing
        </label>
        <ScheduleTimingFields
          startCron={startCron}
          stopCron={stopCron}
          onChange={(newStart, newStop) => {
            setStartCron(newStart);
            setStopCron(newStop);
          }}
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          Timezone
        </label>
        <TimezoneSelect value={timezone} onChange={setTimezone} />
        <p className="mt-1 text-xs text-slate-500">
          Cron fields above are interpreted in this timezone, then converted to
          UTC for the actual schedule.
        </p>
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={dryRun}
          onChange={(e) => setDryRun(e.target.checked)}
          className="h-4 w-4 rounded border-slate-300"
        />
        Dry-run mode — log actions without actually starting/stopping instances
      </label>

      {error && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
      >
        {submitting && <Spinner className="h-4 w-4" />}
        {submitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
