"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect } from "react";
import { LayoutDashboard, LogOut, UsersRound, Columns3, CalendarDays, RadioTower, BarChart3, Settings } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { getToken } from "@/lib/api";
import { logout } from "@/lib/auth";
import { useMe } from "@/lib/hooks";

const NAV = [{ href: "/", label: "Dashboard", icon: LayoutDashboard },{href:"/leads",label:"Leads",icon:UsersRound},{href:"/pipeline",label:"Pipeline",icon:Columns3},{href:"/appointments",label:"Appointments",icon:CalendarDays},{href:"/team",label:"Team",icon:UsersRound},{href:"/sources",label:"Sources",icon:RadioTower},{href:"/reports",label:"Reports",icon:BarChart3},{href:"/settings",label:"Settings",icon:Settings}];

function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const token = getToken();

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [router, token]);

  const me = useMe();

  if (!token || me.isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-[var(--muted)]">Loading...</div>;
  }
  if (me.isError || !me.data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-sm">
        <p className="text-[var(--danger)]">{me.error?.message ?? "Could not load your account."}</p>
        <button onClick={logout} className="rounded-lg border border-[var(--border)] px-3 py-1.5">
          Back to sign in
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] p-4 md:flex">
        <div className="text-base font-semibold">LeadAutomation</div>
        <div className="mt-1 text-xs text-[var(--muted)]">{me.data.team.name}</div>
        <nav className="mt-6 flex flex-col gap-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm " +
                  (active ? "bg-[var(--bg)] font-medium" : "text-[var(--muted)] hover:bg-[var(--bg)]")
                }
              >
                <Icon size={16} /> {label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto border-t border-[var(--border)] pt-3 text-xs">
          <ThemeToggle />
          <div className="font-medium">{me.data.user.name}</div>
          <div className="text-[var(--muted)]">{me.data.user.role}</div>
          <button onClick={logout} className="mt-2 flex items-center gap-1 text-[var(--muted)] hover:text-[var(--text)]">
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-8">{children}</main>
      <nav className="mobile-nav">{NAV.map(({href,label,icon:Icon})=><Link key={href} href={href} aria-label={label} className={pathname===href?"active":""}><Icon size={18}/><span>{label}</span></Link>)}<ThemeToggle /></nav>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="min-h-screen" />}><AppShell>{children}</AppShell></Suspense>;
}
