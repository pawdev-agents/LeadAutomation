import { api, setToken } from "./api";
/* eslint-disable @next/next/no-location-assign-relative-destination */

export async function login(email: string, password: string) {
  const data = await api<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: { email, password },
    auth: false,
  });
  setToken(data.access_token);
  return data;
}

export function logout() {
  setToken(null);
  window.location.href = "/login";
}
