"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  ApiError,
  Schedule,
  SchedulesListResponse,
  SavingsReport,
  SavingsReportResponse,
} from "@/lib/types";
import Spinner from "@/components/Spinner";

type ReportType = "summary" | "schedule" | "account";

function money(n: number): string {
  return `$${n.toFixed(2)}`;
}

function hours(n: number): string {
  return `${n.toFixed(1)}h`;
}

export default function SavingsPage() {
  const { user } = useAuth();
  const isTrusted = user?.role === "admin" || user?.role === "finance";
  const [reportType, setReportType] = useState<ReportType>(
    isTrusted ? "summary" : "schedule"
  );
  const [scheduleId, setScheduleId] = useState("");
  const [accountId, setAccountId] = useState(user?.awsAccounts?.[0] ?? "");
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [report, setReport] = useState<SavingsReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canView =
    user?.role === "admin" ||
    user?.role === "finance" ||
    (user?.permissions ?? []).includes("view_savings");

  useEffect(() => {
    if (!canView) return;
    apiFetch<SchedulesListResponse>("/schedules")
      .then((res) => {
        setSchedules(res.schedules);
        if (res.schedules.length > 0) setScheduleId(res.schedules[0].scheduleId);
      })
      .catch(() => {
        // Non-fatal - schedule dropdown just stays empty if this fails.
      });
  }, [canView]);

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const params = new URLSearchParams({ type: reportType });
      if (reportType === "schedule" && scheduleId) params.set("scheduleId", scheduleId);
      if (reportType === "account" && accountId) params.set("accountId", accountId);

      const res = await apiFetch<SavingsReportResponse>(
        `/savings/report?${params.toString()}`
      );
      setReport(res.report);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }, [reportType, scheduleId, accountId]);

  useEffect(() => {
    if (!canView) return;
    if (reportType === "schedule" && !scheduleId) return;
    if (reportType === "account" && !accountId) return;
    loadReport();
  }, [canView, reportType, scheduleId, accountId, loadReport]);

  if (!canView) {
    return (
      <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
        Your role doesn&apos;t have permission to view savings reports (admin
        and finance only).
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-900">Savings</h1>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-4">
        <select
          value={reportType}
          onChange={(e) => setReportType(e.target.value as ReportType)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        >
          {isTrusted && <option value="summary">Summary (last 30 days)</option>}
          <option value="schedule">By schedule</option>
          <option value="account">By AWS account</option>
        </select>

        {reportType === "schedule" && (
          <select
            value={scheduleId}
            onChange={(e) => setScheduleId(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          >
            {schedules.length === 0 && <option value="">No schedules</option>}
            {schedules.map((s) => (
              <option key={s.scheduleId} value={s.scheduleId}>
                {s.name}
              </option>
            ))}
          </select>
        )}

        {reportType === "account" && (
          <input
            type="text"
            placeholder="123456789012"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm font-mono focus:border-slate-500 focus:outline-none"
          />
        )}
      </div>

      {loading && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="h-4 w-4" />
          Loading…
        </p>
      )}
      {error && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      {report && (
        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase text-slate-500">Cost saved</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">
                {money(report.totalCostSaved)}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase text-slate-500">Hours saved</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">
                {hours(report.totalHoursSaved)}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase text-slate-500">
                {report.type === "account" ? "Schedules" : "Instances"}
              </p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">
                {report.type === "account" ? report.scheduleCount : report.instanceCount}
              </p>
            </div>
          </div>

          <p className="text-xs text-slate-500">
            {report.startDate} to {report.endDate}
          </p>

          {report.type === "schedule" && report.instances.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Instance</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Hours saved</th>
                    <th className="px-4 py-3">Cost saved</th>
                  </tr>
                </thead>
                <tbody>
                  {report.instances.map((inst) => (
                    <tr key={inst.instanceId} className="border-b border-slate-100 last:border-0">
                      <td className="px-4 py-3 font-mono text-xs">{inst.instanceId}</td>
                      <td className="px-4 py-3">{inst.instanceType}</td>
                      <td className="px-4 py-3">{hours(inst.hoursSaved)}</td>
                      <td className="px-4 py-3">{money(inst.costSaved)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {report.type === "account" && report.schedules.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Schedule</th>
                    <th className="px-4 py-3">Instances</th>
                    <th className="px-4 py-3">Hours saved</th>
                    <th className="px-4 py-3">Cost saved</th>
                  </tr>
                </thead>
                <tbody>
                  {report.schedules.map((s) => (
                    <tr key={s.scheduleId} className="border-b border-slate-100 last:border-0">
                      <td className="px-4 py-3">{s.scheduleName}</td>
                      <td className="px-4 py-3">{s.instanceCount}</td>
                      <td className="px-4 py-3">{hours(s.hoursSaved)}</td>
                      <td className="px-4 py-3">{money(s.costSaved)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
