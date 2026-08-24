"use client";

import { createContext, useContext } from "react";
import type { User } from "./types";

const TOKEN_KEY = "ecoscheduler_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

interface TokenPayload {
  sub: string;
  email: string;
  role: User["role"];
  permissions: string[];
  aws_accounts: string[];
  exp: number;
  iat: number;
}

function decodeToken(token: string): TokenPayload | null {
  try {
    const payload = token.split(".")[1];
    const padded = payload + "=".repeat((4 - (payload.length % 4)) % 4);
    const json = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as TokenPayload;
  } catch {
    return null;
  }
}

export function getCurrentUserFromToken(): (User & { permissions: string[] }) | null {
  const token = getToken();
  if (!token) return null;

  const payload = decodeToken(token);
  if (!payload) return null;

  if (payload.exp * 1000 < Date.now()) {
    clearToken();
    return null;
  }

  return {
    userId: payload.sub,
    email: payload.email,
    role: payload.role,
    awsAccounts: payload.aws_accounts ?? [],
    permissions: payload.permissions ?? [],
    createdAt: 0,
    updatedAt: 0,
  };
}

interface AuthContextValue {
  user: (User & { permissions: string[] }) | null;
  loading: boolean;
  refresh: () => void;
  logout: () => void;
  mergeUser: (partial: Partial<User>) => void;
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  refresh: () => {},
  logout: () => {},
  mergeUser: () => {},
});

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
