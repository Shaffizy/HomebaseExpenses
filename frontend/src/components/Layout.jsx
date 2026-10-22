import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import { LayoutDashboard, Receipt, Settings, Users, Menu, X, LogOut, ChevronDown, LockKeyhole, PenLine, Tags, Mail } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

function SidebarGroup({ label, icon: Icon, path, items, onNavigate }) {
  const location = useLocation();
  const active = location.pathname === path;
  const [expanded, setExpanded] = useState(null);
  const open = expanded ?? active;
  const id = "sidebar-" + label.toLowerCase();
  return <div>
    <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setExpanded(!open)} className={`flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm font-semibold ${active ? "bg-red-50 text-[var(--color-rust)]" : "text-black/60 hover:bg-gray-50"}`}>
      <Icon size={18}/><span className="flex-1 text-left">{label}</span><ChevronDown size={16} className={open ? "rotate-180" : ""}/>
    </button>
    {open && <div id={id} className="ml-6 border-l border-[var(--color-line)] py-1 pl-2">{items.map(({ to, label: text, icon: ItemIcon, section }) => {
      const selected = active && (new URLSearchParams(location.search).get("section") || items[0].section) === section;
      return <Link key={to} to={to} onClick={onNavigate} aria-current={selected ? "page" : undefined} className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm ${selected ? "font-semibold text-[var(--color-rust)]" : "text-black/60 hover:bg-gray-50"}`}><ItemIcon size={16}/>{text}</Link>;
    })}</div>}
  </div>;
}

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const navigation = [
    { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/expenses", label: "Expenses", icon: Receipt },
  ];
  const signOut = () => { logout(); navigate("/login"); };
  return <div className="min-h-screen bg-[var(--color-paper)]">
    <header className="fixed inset-x-0 top-0 z-40 flex h-[76px] items-center justify-between gap-4 border-b border-[var(--color-line)] bg-white px-4 md:px-6">
      <div className="flex min-w-0 items-center gap-4">
        <button type="button" aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open} onClick={() => setOpen(!open)} className="p-2 md:hidden">{open ? <X size={20} /> : <Menu size={20} />}</button>
        <img src="/homebase-logo.png" alt="Homebase Mortgage Bank" className="h-11 w-[145px] shrink-0 object-contain" />
        <span className="hidden border-l border-[var(--color-line)] pl-4 text-sm font-semibold sm:block">Expenses</span>
      </div>
      <div className="min-w-0 text-right"><p className="max-w-[140px] truncate text-sm font-semibold">{user?.name}</p><p className="text-[11px] text-black/50">{user?.role}</p></div>
    </header>
    {open && <button type="button" aria-label="Close navigation" onClick={() => setOpen(false)} className="fixed inset-0 top-[76px] z-20 bg-black/30 md:hidden" />}
    <aside className={`fixed bottom-0 left-0 top-[76px] z-30 flex w-56 flex-col border-r border-[var(--color-line)] bg-white p-2 ${open ? "flex" : "hidden"} md:flex`}>
      <nav className="flex-1 space-y-1 overflow-y-auto">
        {navigation.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-semibold ${isActive ? "bg-red-50 text-[var(--color-rust)]" : "text-black/60 hover:bg-gray-50"}`}><Icon size={18}/>{label}</NavLink>)}
        <SidebarGroup label="Settings" icon={Settings} path="/settings" onNavigate={() => setOpen(false)} items={[
          { to: "/settings?section=password", section: "password", label: "Change Password", icon: LockKeyhole },
          ...(user?.role === "ADMIN" ? [{ to: "/settings?section=email", section: "email", label: "Email Notifications", icon: Mail }] : []),
          ...(user?.role === "APPROVER" ? [{ to: "/settings?section=signature", section: "signature", label: "Signature", icon: PenLine }] : []),
        ]}/>
        {user?.role === "ADMIN" && <SidebarGroup label="Users" icon={Users} path="/admin" onNavigate={() => setOpen(false)} items={[
          { to: "/admin?section=users", section: "users", label: "Manage Users", icon: Users },
          { to: "/admin?section=categories", section: "categories", label: "Categories", icon: Tags },
        ]}/>}
      </nav>
      <button type="button" onClick={signOut} className="flex items-center gap-3 border-t border-[var(--color-line)] px-4 py-4 text-sm font-semibold text-black/60"><LogOut size={18} />Sign out</button>
    </aside>
    <main className="pt-[76px] md:pl-56"><div className="mx-auto max-w-[1240px] px-4 py-6 sm:px-6 lg:px-8"><Outlet /></div></main>
  </div>;
}
