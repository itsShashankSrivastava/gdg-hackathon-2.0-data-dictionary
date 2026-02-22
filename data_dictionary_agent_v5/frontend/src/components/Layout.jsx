import React from 'react';
import { useApp } from '../App';
import {
  Database, LayoutDashboard, Table2, ShieldCheck, MessageSquare,
  Download, Sun, Moon, Plug, Unplug, BookOpen
} from 'lucide-react';
import { disconnectDb } from '../api/client';
import toast from 'react-hot-toast';

const navItems = [
  { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { key: 'tables',    label: 'Tables',    icon: Table2 },
  { key: 'quality',   label: 'Quality',   icon: ShieldCheck },
  { key: 'chat',      label: 'Chat',      icon: MessageSquare },
  { key: 'export',    label: 'Export',     icon: Download },
];

export default function Layout({ children }) {
  const { session, setSession, activeTab, setActiveTab, setShowConnect, darkMode, setDarkMode, setOverview, setQuality, setAiSummaries, setDbSummary } = useApp();

  const handleDisconnect = async () => {
    try {
      await disconnectDb(session.session_id);
    } catch { /* ignore */ }
    setSession(null);
    setOverview(null);
    setQuality({});
    setAiSummaries({});
    setDbSummary(null);
    toast.success('Disconnected');
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex">
      {/* ── Sidebar ── */}
      <aside className="w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col fixed h-full z-30">
        {/* Brand */}
        <div className="p-5 border-b border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 gradient-bg rounded-xl flex items-center justify-center text-white">
              <BookOpen size={22} />
            </div>
            <div>
              <h1 className="font-bold text-lg gradient-text">DataDict</h1>
              <p className="text-[10px] text-gray-400 uppercase tracking-widest">AI Agent</p>
            </div>
          </div>
        </div>

        {/* Connection status */}
        <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800">
          {session ? (
            <div className="flex items-center gap-2">
              <div className="pulse-dot"><span></span><span></span></div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-green-600 dark:text-green-400">Connected</p>
                <p className="text-[11px] text-gray-500 truncate">{session.database_name}</p>
              </div>
              <button onClick={handleDisconnect} className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-red-400 transition-colors" title="Disconnect">
                <Unplug size={16} />
              </button>
            </div>
          ) : (
            <button onClick={() => setShowConnect(true)} className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-brand-50 dark:bg-brand-900/20 text-brand-600 dark:text-brand-400 text-sm font-medium hover:bg-brand-100 dark:hover:bg-brand-900/40 transition-colors">
              <Plug size={16} /> Connect Database
            </button>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                activeTab === key
                  ? 'bg-brand-500 text-white shadow-md shadow-brand-500/25'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
              }`}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-gray-100 dark:border-gray-800">
          <button onClick={() => setDarkMode(!darkMode)} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            {darkMode ? <Sun size={18} /> : <Moon size={18} />}
            {darkMode ? 'Light Mode' : 'Dark Mode'}
          </button>
          <p className="text-center text-[10px] text-gray-400 mt-3">v2.0 • Read-Only • Secure</p>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 ml-64 p-6 min-h-screen">
        <div className="max-w-7xl mx-auto animate-fade-in">
          {children}
        </div>
      </main>
    </div>
  );
}
