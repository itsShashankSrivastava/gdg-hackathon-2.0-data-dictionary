import React, { useState, createContext, useContext } from 'react';
import { Toaster } from 'react-hot-toast';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import TablesPage from './pages/TablesPage';
import QualityPage from './pages/QualityPage';
import ChatPage from './pages/ChatPage';
import ExportPage from './pages/ExportPage';
import ConnectionModal from './components/ConnectionModal';

// ── Global state context ──
export const AppContext = createContext(null);

export function useApp() {
  return useContext(AppContext);
}

export default function App() {
  const [session, setSession] = useState(null); // { session_id, database_name, database_type, schemas, table_count }
  const [overview, setOverview] = useState(null);
  const [quality, setQuality] = useState({});
  const [aiSummaries, setAiSummaries] = useState({});
  const [dbSummary, setDbSummary] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [showConnect, setShowConnect] = useState(false);
  const [darkMode, setDarkMode] = useState(false);

  // Clear session on expiration
  const handleSessionExpired = () => {
    setSession(null);
    setOverview(null);
    setQuality({});
    setAiSummaries({});
    setDbSummary(null);
    setActiveTab('dashboard');
    setShowConnect(true);
  };

  const ctx = {
    session, setSession,
    overview, setOverview,
    quality, setQuality,
    aiSummaries, setAiSummaries,
    dbSummary, setDbSummary,
    activeTab, setActiveTab,
    showConnect, setShowConnect,
    darkMode, setDarkMode,
    handleSessionExpired,
  };

  const pages = {
    dashboard: <Dashboard />,
    tables: <TablesPage />,
    quality: <QualityPage />,
    chat: <ChatPage />,
    export: <ExportPage />,
  };

  return (
    <AppContext.Provider value={ctx}>
      <div className={darkMode ? 'dark' : ''}>
        <Toaster position="top-right" toastOptions={{ duration: 3000 }} />
        <Layout>
          {pages[activeTab] || <Dashboard />}
        </Layout>
        {showConnect && <ConnectionModal />}
      </div>
    </AppContext.Provider>
  );
}
