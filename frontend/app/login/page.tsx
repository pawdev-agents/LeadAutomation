"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { login } from "@/lib/auth";
import { ApiError } from "@/lib/api";

const schema = z.object({
  email: z.string().min(1, "Enter your email").email("Enter a valid email"),
  password: z.string().min(1, "Enter your password"),
});
type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  async function onSubmit(values: Values) {
    setError(null);
    try {
      await login(values.email, values.password);
      router.replace("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    }
  }

  const input =
    "mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]";

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm"
      >
        <h1 className="text-xl font-semibold">Sign in</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">Welcome back to LeadAutomation.</p>

        <label className="mt-5 block text-sm font-medium">
          Email
          <input type="email" autoComplete="email" className={input} {...register("email")} />
          {errors.email && <span className="mt-1 block text-xs text-[var(--danger)]">{errors.email.message}</span>}
        </label>

        <label className="mt-4 block text-sm font-medium">
          Password
          <input type="password" autoComplete="current-password" className={input} {...register("password")} />
          {errors.password && (
            <span className="mt-1 block text-xs text-[var(--danger)]">{errors.password.message}</span>
          )}
        </label>

        {error && (
          <p role="alert" className="mt-4 rounded-lg border border-[var(--danger)] px-3 py-2 text-sm text-[var(--danger)]">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-5 w-full rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-[var(--accent-text)] disabled:opacity-60"
        >
          {isSubmitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </main>
  );
}
