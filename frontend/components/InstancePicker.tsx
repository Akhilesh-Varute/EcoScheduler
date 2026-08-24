"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ApiError, Ec2Instance, Ec2ListResponse } from "@/lib/types";
import Spinner from "@/components/Spinner";

interface Props {
  accountId: string;
  onAccountIdChange: (accountId: string) => void;
  selectedInstanceIds: string[];
  onSelectedInstanceIdsChange: (ids: string[]) => void;
}

const STATE_STYLES: Record<string, string> = {
  running: "bg-green-100 text-green-700",
  stopped: "bg-slate-200 text-slate-600",
  pending: "bg-amber-100 text-amber-700",
  stopping: "bg-amber-100 text-amber-700",
  terminated: "bg-red-100 text-red-700",
};

export default function InstancePicker({
  accountId,
  onAccountIdChange,
  selectedInstanceIds,
  onSelectedInstanceIdsChange,
}: Props) {
  const { user } = useAuth();
  const [instances, setInstances] = useState<Ec2Instance[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  const knownAccounts = user?.awsAccounts ?? [];

  async function loadInstances(forAccountId: string) {
    if (!forAccountId) return;
    setLoading(true);
    setError(null);
    setHasLoaded(false);
    try {
      const res = await apiFetch<Ec2ListResponse>(
        `/ec2/list?accountId=${encodeURIComponent(forAccountId)}`
      );
      setInstances(res.instances);
      setHasLoaded(true);
    } catch (err) {
      setInstances([]);
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to load instances for this account"
      );
    } finally {
      setLoading(false);
    }
  }

  // Auto-load when editing a schedule that already has an accountId set.
  useEffect(() => {
    if (accountId) {
      loadInstances(accountId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggleInstance(instanceId: string) {
    if (selectedInstanceIds.includes(instanceId)) {
      onSelectedInstanceIdsChange(
        selectedInstanceIds.filter((id) => id !== instanceId)
      );
    } else {
      onSelectedInstanceIdsChange([...selectedInstanceIds, instanceId]);
    }
  }

  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">
        AWS account
      </label>

      {knownAccounts.length > 0 ? (
        <div className="flex gap-2">
          <select
            value={accountId}
            onChange={(e) => {
              onAccountIdChange(e.target.value);
              if (e.target.value) loadInstances(e.target.value);
            }}
            required
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          >
            <option value="">Select an account…</option>
            {knownAccounts.map((acc) => (
              <option key={acc} value={acc}>
                {acc}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="flex gap-2">
          <input
            type="text"
            required
            placeholder="123456789012"
            value={accountId}
            onChange={(e) => onAccountIdChange(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono focus:border-slate-500 focus:outline-none"
          />
          <button
            type="button"
            onClick={() => loadInstances(accountId)}
            disabled={!accountId || loading}
            className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {loading && <Spinner className="h-3.5 w-3.5" />}
            Load instances
          </button>
        </div>
      )}
      {knownAccounts.length === 0 && (
        <p className="mt-1 text-xs text-slate-500">
          No AWS accounts are assigned to your user — enter one directly (admin
          access bypasses the account-ownership check).
        </p>
      )}

      <div className="mt-3">
        {loading && (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner className="h-4 w-4" />
            Loading instances…
          </p>
        )}

        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        {!loading && !error && hasLoaded && instances.length === 0 && (
          <p className="rounded-md border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">
            No instances found in this account.
          </p>
        )}

        {!loading && instances.length > 0 && (
          <div className="max-h-64 overflow-y-auto rounded-md border border-slate-200">
            {instances.map((inst) => {
              const checked = selectedInstanceIds.includes(inst.instanceId);
              return (
                <label
                  key={inst.instanceId}
                  className={`flex cursor-pointer items-center gap-3 border-b border-slate-100 px-3 py-2 text-sm last:border-0 hover:bg-slate-50 ${
                    checked ? "bg-slate-50" : ""
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleInstance(inst.instanceId)}
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  <div className="flex-1">
                    <div className="font-medium text-slate-900">{inst.name}</div>
                    <div className="font-mono text-xs text-slate-500">
                      {inst.instanceId} · {inst.instanceType}
                    </div>
                  </div>
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      STATE_STYLES[inst.state] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {inst.state}
                  </span>
                </label>
              );
            })}
          </div>
        )}
      </div>

      {selectedInstanceIds.length > 0 && (
        <p className="mt-2 text-xs text-slate-500">
          {selectedInstanceIds.length} instance
          {selectedInstanceIds.length === 1 ? "" : "s"} selected
        </p>
      )}
    </div>
  );
}
