"use client";

import { useEffect, useMemo, useRef, useState } from "react";

interface Props {
  value: string;
  onChange: (timezone: string) => void;
}

const FALLBACK_TIMEZONES = [
  "UTC",
  "Asia/Kolkata",
  "America/New_York",
  "America/Los_Angeles",
  "Europe/London",
  "Asia/Tokyo",
];

function listAllTimezones(): string[] {
  const supportedValuesOf = (
    Intl as unknown as { supportedValuesOf?: (key: string) => string[] }
  ).supportedValuesOf;

  if (typeof supportedValuesOf === "function") {
    try {
      return supportedValuesOf("timeZone");
    } catch {
      return FALLBACK_TIMEZONES;
    }
  }
  return FALLBACK_TIMEZONES;
}

function offsetLabel(timezone: string): string {
  try {
    const part = new Intl.DateTimeFormat("en-US", {
      timeZone: timezone,
      timeZoneName: "shortOffset",
    })
      .formatToParts(new Date())
      .find((p) => p.type === "timeZoneName");
    return part?.value ?? "";
  } catch {
    return "";
  }
}

export default function TimezoneSelect({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const allTimezones = useMemo(() => listAllTimezones(), []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matches = q
      ? allTimezones.filter((z) => z.toLowerCase().includes(q))
      : allTimezones;
    return matches.slice(0, 200); // keep the DOM light even mid-search
  }, [allTimezones, query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function selectZone(zone: string) {
    onChange(zone);
    setOpen(false);
    setQuery("");
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-md border border-slate-300 px-3 py-2 text-left text-sm focus:border-slate-500 focus:outline-none"
      >
        <span>
          {value}
          {offsetLabel(value) ? ` (${offsetLabel(value)})` : ""}
        </span>
        <span className="text-slate-400">▾</span>
      </button>

      {open && (
        <div className="absolute z-10 mt-1 w-full rounded-md border border-slate-200 bg-white shadow-lg">
          <input
            autoFocus
            type="text"
            placeholder="Search timezones…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full border-b border-slate-200 px-3 py-2 text-sm focus:outline-none"
          />
          <div className="max-h-56 overflow-y-auto">
            {filtered.length === 0 && (
              <p className="px-3 py-3 text-sm text-slate-400">No matches</p>
            )}
            {filtered.map((zone) => (
              <button
                key={zone}
                type="button"
                onClick={() => selectZone(zone)}
                className={`block w-full px-3 py-1.5 text-left text-sm hover:bg-slate-50 ${
                  zone === value ? "bg-slate-50 font-medium" : ""
                }`}
              >
                {zone}
                <span className="ml-2 text-xs text-slate-400">
                  {offsetLabel(zone)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
