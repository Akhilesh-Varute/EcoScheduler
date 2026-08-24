"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useAuth, setToken } from "@/lib/auth";
import { AccountVerifyResponse, ApiError, RefreshTokenResponse } from "@/lib/types";
import Spinner from "@/components/Spinner";

const MASTER_ACCOUNT_ID = "637423590778";

export default function ConnectAccountPage() {
  const router = useRouter();
  const { user, mergeUser } = useAuth();
  const [accountId, setAccountId] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [connectedCount, setConnectedCount] = useState<number | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const deployCommand = `aws cloudformation deploy \\
  --template-file customer-account-role.yml \\
  --stack-name ecoscheduler-access \\
  --parameter-overrides MasterAccountId=${MASTER_ACCOUNT_ID} \\
  --capabilities CAPABILITY_NAMED_IAM \\
  --profile <your-aws-profile>`;

  async function refreshSession(nextAccounts: string[]) {
    await apiFetch(`/users/${user!.userId}`, {
      method: "PUT",
      body: { awsAccounts: nextAccounts },
    });
    // Reissue the token with fresh awsAccounts baked in, instead of forcing
    // a logout/login cycle just to pick up the change.
    const refreshed = await apiFetch<RefreshTokenResponse>("/auth/refresh", {
      method: "POST",
    });
    setToken(refreshed.token);
    mergeUser({ awsAccounts: refreshed.user.awsAccounts });
  }

  async function handleConnect() {
    if (!user) return;
    setConnecting(true);
    setConnectError(null);
    setConnectedCount(null);
    try {
      const res = await apiFetch<AccountVerifyResponse>(
        `/accounts/verify?accountId=${encodeURIComponent(accountId)}`
      );

      const nextAccounts = Array.from(
        new Set([...(user.awsAccounts ?? []), accountId])
      );
      await refreshSession(nextAccounts);

      setConnectedCount(res.instanceCount);
      setAccountId("");
    } catch (err) {
      setConnectError(
        err instanceof ApiError ? err.message : "Failed to connect account"
      );
    } finally {
      setConnecting(false);
    }
  }

  async function handleRemove(accountToRemove: string) {
    if (!user) return;
    if (!confirm(`Remove ${accountToRemove}? Any schedules using it will stop working.`)) {
      return;
    }
    setRemovingId(accountToRemove);
    setRemoveError(null);
    try {
      const nextAccounts = (user.awsAccounts ?? []).filter(
        (a) => a !== accountToRemove
      );
      await refreshSession(nextAccounts);
    } catch (err) {
      setRemoveError(
        err instanceof ApiError ? err.message : "Failed to remove account"
      );
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">
          Connect an AWS account
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          EcoScheduler needs a cross-account IAM role deployed in each customer AWS
          account before it can see or schedule EC2 instances there.
        </p>
      </div>

      {(user?.awsAccounts ?? []).length > 0 && (
        <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-900">
            Connected accounts
          </h2>
          {removeError && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {removeError}
            </p>
          )}
          <ul className="divide-y divide-slate-100">
            {user!.awsAccounts.map((acc) => (
              <li key={acc} className="flex items-center justify-between py-2">
                <span className="font-mono text-sm text-slate-700">{acc}</span>
                <button
                  onClick={() => handleRemove(acc)}
                  disabled={removingId === acc}
                  className="inline-flex items-center gap-1.5 text-sm text-red-600 hover:text-red-800 hover:underline disabled:opacity-50"
                >
                  {removingId === acc && <Spinner className="h-3.5 w-3.5" />}
                  {removingId === acc ? "Removing…" : "Remove"}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-900">
          1. Deploy the access role in the target account
        </h2>
        <p className="text-sm text-slate-600">
          Download the template, then run this in a terminal authenticated
          against the <strong>target</strong> AWS account (not this one):
        </p>
        <a
          href="/customer-account-role.yml"
          download
          className="inline-block text-sm font-medium text-slate-900 underline"
        >
          Download customer-account-role.yml
        </a>
        <pre className="overflow-x-auto rounded-md bg-slate-900 px-4 py-3 text-xs text-slate-100">
          {deployCommand}
        </pre>
        <p className="text-xs text-slate-500">
          Master account ID (already filled in above):{" "}
          <span className="font-mono">{MASTER_ACCOUNT_ID}</span>
        </p>
      </section>

      <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-900">
          2. Connect the account
        </h2>
        <p className="text-sm text-slate-600">
          Verifies the role was deployed correctly and adds the account to your
          profile in one step — no logout needed, ready to use right away.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="123456789012"
            value={accountId}
            onChange={(e) => {
              setAccountId(e.target.value);
              setConnectedCount(null);
              setConnectError(null);
            }}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono focus:border-slate-500 focus:outline-none"
          />
          <button
            onClick={handleConnect}
            disabled={!accountId || connecting}
            className="inline-flex items-center gap-2 whitespace-nowrap rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {connecting && <Spinner className="h-4 w-4" />}
            {connecting ? "Connecting…" : "Connect account"}
          </button>
        </div>

        {connectError && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {connectError}
          </p>
        )}

        {connectedCount !== null && (
          <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
            Connected — found {connectedCount} instance
            {connectedCount === 1 ? "" : "s"}. Ready to use in the schedule
            picker now.
          </p>
        )}
      </section>

      <button
        onClick={() => router.push("/dashboard/schedules")}
        className="text-sm text-slate-500 underline"
      >
        Back to schedules
      </button>
    </div>
  );
}
