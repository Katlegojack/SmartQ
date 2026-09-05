import { useQuery } from "@tanstack/react-query";
import { api, clearCsrfToken } from "./api";
import type { Account, Role } from "./types";

export const roleRoutes: Record<Role, string> = {
  customer: "/app/customer/",
  receptionist: "/app/reception/",
  counter_staff: "/app/counter/",
  branch_manager: "/app/manager/",
  system_admin: "/app/admin/",
};


const roleReturnRoutes: Record<Role, readonly string[]> = {
  customer: ["/app/customer/", "/app/recovery/"],
  receptionist: ["/app/reception/"],
  counter_staff: ["/app/counter/"],
  branch_manager: ["/app/manager/", "/app/history/"],
  system_admin: ["/app/admin/", "/app/history/"],
};

export function safeNextRoute(role: Role, requested: string | null | undefined): string {
  if (!requested || requested.startsWith("//")) return roleRoutes[role];
  let normalized = requested;
  try {
    const parsed = new URL(requested, window.location.origin);
    if (parsed.origin !== window.location.origin) return roleRoutes[role];
    normalized = parsed.pathname.endsWith("/") ? parsed.pathname : `${parsed.pathname}/`;
  } catch {
    return roleRoutes[role];
  }
  return roleReturnRoutes[role].includes(normalized) ? normalized : roleRoutes[role];
}

export const roleLabels: Record<Role, string> = {
  customer: "Customer",
  receptionist: "Receptionist",
  counter_staff: "Counter Staff",
  branch_manager: "Branch Manager",
  system_admin: "System Admin",
};

export async function getCurrentAccount(): Promise<Account> {
  return api<Account>("/api/v1/accounts/me/");
}


export function useCurrentAccountQuery() {
  return useQuery({
    queryKey: ["account"],
    queryFn: getCurrentAccount,
    retry: false,
    staleTime: 30_000,
  });
}

export async function login(username: string, password: string, role: Role): Promise<Account> {
  const result = await api<{ user: Account }>("/api/v1/accounts/login/", {
    method: "POST",
    body: { username, password, role },
  });
  return result.user;
}

export async function logout(): Promise<void> {
  await api("/api/v1/accounts/logout/", { method: "POST" });
  clearCsrfToken();
}

export async function registerCustomer(payload: Record<string, unknown>): Promise<unknown> {
  return api("/api/v1/accounts/register/", { method: "POST", body: payload });
}
