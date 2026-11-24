"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Compass,
  Database,
  FileSearch,
  Info,
  MapPinned,
  MessageSquareText,
  Waves,
} from "lucide-react";
import type { ReactNode } from "react";

const navigation = [
  { href: "/", label: "Overview", icon: BarChart3 },
  { href: "/explorer", label: "AI Explorer", icon: MessageSquareText },
  { href: "/map", label: "Ocean Map", icon: MapPinned },
  { href: "/profiles", label: "Profile Explorer", icon: FileSearch },
  { href: "/compare", label: "Profile Comparison", icon: Compass },
  { href: "/about", label: "About OceanIQ", icon: Info },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col bg-[#071b32] px-4 py-6 text-slate-200 lg:flex">
        <Link href="/" className="flex items-center gap-3 px-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400 text-slate-950">
            <Waves size={22} />
          </div>
          <div>
            <div className="text-lg font-semibold tracking-wide text-white">OceanIQ</div>
            <div className="text-xs text-slate-400">ARGO data explorer</div>
          </div>
        </Link>
        <nav className="mt-10 space-y-1">
          {navigation.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm transition ${
                  active
                    ? "bg-cyan-400/15 font-medium text-cyan-200"
                    : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon size={18} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-white">
            <Database size={16} className="text-cyan-300" />
            Local dataset
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-400">
            Read-only DuckDB and Chroma services. Metrics reflect the available processed archive.
          </p>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-5 py-3 backdrop-blur lg:hidden">
          <div className="flex items-center gap-2 font-semibold text-slate-900">
            <Waves size={19} className="text-cyan-700" />
            OceanIQ
          </div>
          <nav className="mt-3 flex gap-2 overflow-x-auto pb-1">
            {navigation.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`shrink-0 rounded-full px-3 py-1.5 text-xs ${
                  pathname === href ? "bg-cyan-700 text-white" : "bg-slate-100 text-slate-600"
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-7 lg:px-9 lg:py-9">{children}</main>
      </div>
    </div>
  );
}
