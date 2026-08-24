"use client";

import { useState } from "react";

interface Props {
  startCron: string;
  stopCron: string;
  onChange: (startCron: string, stopCron: string) => void;
}

type Mode = "recurring" | "onetime" | "advanced";

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DEFAULT_DAYS = [1, 2, 3, 4, 5]; // Mon-Fri

function pad(n: number): string {
  return n.toString().padStart(2, "0");
}

function timeToParts(time: string): { hour: string; minute: string } {
  const [hour, minute] = time.split(":");
  return { hour: hour ?? "0", minute: minute ?? "0" };
}

function partsToTime(hour: string, minute: string): string {
  return `${pad(parseInt(hour || "0", 10))}:${pad(parseInt(minute || "0", 10))}`;
}

function parseDowField(dow: string): number[] | null {
  if (dow === "*") return [0, 1, 2, 3, 4, 5, 6];
  const parts = dow.split(",");
  const days: number[] = [];
  for (const part of parts) {
    if (part.includes("-")) {
      const [start, end] = part.split("-").map(Number);
      if (Number.isNaN(start) || Number.isNaN(end)) return null;
      for (let d = start; d <= end; d++) days.push(d);
    } else {
      const d = Number(part);
      if (Number.isNaN(d)) return null;
      days.push(d);
    }
  }
  return days;
}

interface ParsedCron {
  mode: Mode;
  days: number[];
  date: string;
  startTime: string;
  stopTime: string;
}

function parseInitial(startCron: string, stopCron: string): ParsedCron {
  const today = new Date();
  const fallback: ParsedCron = {
    mode: "recurring",
    days: DEFAULT_DAYS,
    date: `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`,
    startTime: "08:00",
    stopTime: "19:00",
  };

  const sParts = startCron.trim().split(/\s+/);
  const eParts = stopCron.trim().split(/\s+/);
  if (sParts.length !== 5 || eParts.length !== 5) {
    return { ...fallback, mode: "advanced" };
  }

  const [sMin, sHour, sDom, sMonth, sDow] = sParts;
  const [eMin, eHour, eDom, eMonth, eDow] = eParts;

  const startTime = partsToTime(sHour, sMin);
  const stopTime = partsToTime(eHour, eMin);

  if (sDom === "*" && sMonth === "*" && eDom === "*" && eMonth === "*") {
    const days = parseDowField(sDow);
    if (days) {
      return { mode: "recurring", days, date: fallback.date, startTime, stopTime };
    }
  }

  if (
    sDom !== "*" &&
    sMonth !== "*" &&
    eDom !== "*" &&
    eMonth !== "*" &&
    /^\d+$/.test(sDom) &&
    /^\d+$/.test(sMonth)
  ) {
    const year = today.getFullYear();
    const date = `${year}-${pad(parseInt(sMonth, 10))}-${pad(parseInt(sDom, 10))}`;
    return { mode: "onetime", days: DEFAULT_DAYS, date, startTime, stopTime };
  }

  return { ...fallback, mode: "advanced", startTime, stopTime };
}

export default function ScheduleTimingFields({ startCron, stopCron, onChange }: Props) {
  const [parsed, setParsed] = useState<ParsedCron>(() =>
    parseInitial(startCron, stopCron)
  );

  function emit(next: ParsedCron) {
    setParsed(next);
    if (next.mode === "advanced") {
      // Advanced mode edits startCron/stopCron directly via the raw inputs,
      // handled separately below - nothing to generate here.
      return;
    }
    const { hour: startHour, minute: startMinute } = timeToParts(next.startTime);
    const { hour: stopHour, minute: stopMinute } = timeToParts(next.stopTime);

    if (next.mode === "recurring") {
      const dow =
        next.days.length === 7 ? "*" : [...next.days].sort((a, b) => a - b).join(",");
      onChange(
        `${startMinute} ${startHour} * * ${dow}`,
        `${stopMinute} ${stopHour} * * ${dow}`
      );
    } else {
      const [, month, day] = next.date.split("-");
      const dayNum = parseInt(day, 10);
      const monthNum = parseInt(month, 10);
      onChange(
        `${startMinute} ${startHour} ${dayNum} ${monthNum} *`,
        `${stopMinute} ${stopHour} ${dayNum} ${monthNum} *`
      );
    }
  }

  function toggleDay(day: number) {
    const days = parsed.days.includes(day)
      ? parsed.days.filter((d) => d !== day)
      : [...parsed.days, day];
    emit({ ...parsed, days });
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-4 text-sm">
        {(["recurring", "onetime", "advanced"] as Mode[]).map((m) => (
          <label key={m} className="flex items-center gap-1.5 text-slate-700">
            <input
              type="radio"
              checked={parsed.mode === m}
              onChange={() => emit({ ...parsed, mode: m })}
              className="h-4 w-4"
            />
            {m === "recurring" && "Recurring"}
            {m === "onetime" && "One-time"}
            {m === "advanced" && "Advanced"}
          </label>
        ))}
      </div>

      {parsed.mode === "recurring" && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {DAY_LABELS.map((label, day) => (
              <button
                key={day}
                type="button"
                onClick={() => toggleDay(day)}
                className={`rounded-md border px-2.5 py-1 text-xs font-medium ${
                  parsed.days.includes(day)
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Start time
              </label>
              <input
                type="time"
                value={parsed.startTime}
                onChange={(e) => emit({ ...parsed, startTime: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Stop time
              </label>
              <input
                type="time"
                value={parsed.stopTime}
                onChange={(e) => emit({ ...parsed, stopTime: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              />
            </div>
          </div>
        </div>
      )}

      {parsed.mode === "onetime" && (
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Date
            </label>
            <input
              type="date"
              value={parsed.date}
              onChange={(e) => emit({ ...parsed, date: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Start time
            </label>
            <input
              type="time"
              value={parsed.startTime}
              onChange={(e) => emit({ ...parsed, startTime: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Stop time
            </label>
            <input
              type="time"
              value={parsed.stopTime}
              onChange={(e) => emit({ ...parsed, stopTime: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
          </div>
        </div>
      )}

      {parsed.mode === "advanced" && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Start cron
            </label>
            <input
              type="text"
              value={startCron}
              onChange={(e) => onChange(e.target.value, stopCron)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono focus:border-slate-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Stop cron
            </label>
            <input
              type="text"
              value={stopCron}
              onChange={(e) => onChange(startCron, e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono focus:border-slate-500 focus:outline-none"
            />
          </div>
        </div>
      )}
    </div>
  );
}
