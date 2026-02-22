import React from 'react';
import { useApp } from '../App';
import { getOverview, generateAISummary } from '../api/client';
import { Database, Table2, Columns3, Rows3, Link, Eye, Sparkles, Loader2, ArrowRight } from 'lucide-react';
import toast from 'react-hot-toast';

export default function Dashboard() {
  const { session, overview, setOverview, setShowConnect, dbSummary, setDbSummary, setActiveTab } = useApp();
  const [loadingAI, setLoadingAI] = React.useState(false);

  if (!session) {
    return <HeroSection onConnect={() => setShowConnect(true)} />;
  }

  const handleAISummary = async () => {
    setLoadingAI(true);
    try {
      const data = await generateAISummary(session.session_id);
      console.log('AI Summary Response:', data);
      if (data.database_summary) {
        console.log('Database Summary:', data.database_summary);
        setDbSummary(data.database_summary);
      } else {
        console.warn('No database_summary in response');
      }
      toast.success('AI analysis complete!');
    } catch (err) {
      console.error('AI analysis error:', err);
      toast.error('AI analysis failed');
    } finally {
      setLoadingAI(false);
    }
  };

  const o = overview;
  if (!o) return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-brand-500" size={32} /></div>;

  const stats = [
    { label: 'Tables', value: o.total_tables, icon: Table2, color: 'from-blue-500 to-cyan-500' },
    { label: 'Views', value: o.total_views, icon: Eye, color: 'from-purple-500 to-pink-500' },
    { label: 'Columns', value: o.total_columns, icon: Columns3, color: 'from-amber-500 to-orange-500' },
    { label: 'Rows', value: (o.total_rows || 0).toLocaleString(), icon: Rows3, color: 'from-green-500 to-emerald-500' },
    { label: 'Relationships', value: o.total_relationships, icon: Link, color: 'from-rose-500 to-red-500' },
  ];

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold dark:text-white">Database Overview</h1>
          <p className="text-sm text-gray-500 mt-1 flex items-center gap-2">
            <Database size={14} /> {o.database_name} <span className="badge badge-success">{o.database_type}</span>
          </p>
        </div>
        <button onClick={handleAISummary} disabled={loadingAI} className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-brand-500 to-purple-500 text-white text-sm font-medium hover:shadow-lg hover:shadow-brand-500/25 transition-all disabled:opacity-50">
          {loadingAI ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
          {loadingAI ? 'Analyzing...' : 'AI Analysis'}
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {stats.map(s => (
          <div key={s.label} className="stat-card group cursor-pointer" onClick={() => s.label === 'Tables' && setActiveTab('tables')}>
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${s.color} flex items-center justify-center text-white mb-3 group-hover:scale-110 transition-transform`}>
              <s.icon size={20} />
            </div>
            <p className="text-2xl font-bold dark:text-white">{s.value}</p>
            <p className="text-xs text-gray-500 mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* AI Summary */}
      {dbSummary && (
        <div className="glass-card p-6 animate-slide-up">
          <h2 className="text-lg font-bold dark:text-white flex items-center gap-2 mb-4">
            <Sparkles size={20} className="text-brand-500" /> AI Database Analysis
          </h2>
          {console.log('Rendering dbSummary:', dbSummary)}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Left column - Purpose, Domain, Model Type */}
            <div className="space-y-4">
              {dbSummary.database_purpose && (
                <InfoBlock label="Purpose" value={dbSummary.database_purpose} color="blue" />
              )}
              {dbSummary.domain_analysis && (
                <InfoBlock label="Domain" value={dbSummary.domain_analysis} color="green" />
              )}
              {dbSummary.data_model_type && (
                <InfoBlock label="Model Type" value={dbSummary.data_model_type} color="amber" />
              )}
            </div>
            
            {/* Right column - Architecture & Entity Groups */}
            <div className="space-y-4">
              {/* Architecture Observations */}
              <div className="p-4 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                <p className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-3">Architecture Observations</p>
                {Array.isArray(dbSummary.architecture_observations) && dbSummary.architecture_observations.length > 0 ? (
                  <ul className="space-y-2">
                    {dbSummary.architecture_observations.map((obs, i) => (
                      <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                        <span className="text-brand-500 mt-0.5">•</span> {obs}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-400 italic">No observations generated</p>
                )}
              </div>
              
              {/* Key Entity Groups */}
              <div className="p-4 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                <p className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-3">Key Entity Groups</p>
                {Array.isArray(dbSummary.key_entity_groups) && dbSummary.key_entity_groups.length > 0 ? (
                  <ul className="space-y-2">
                    {dbSummary.key_entity_groups.map((g, i) => (
                      <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                        <span className="text-purple-500 mt-0.5">•</span> {g}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-400 italic">No entity groups generated</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tables list */}
      <div className="glass-card overflow-hidden">
        <div className="p-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <h2 className="font-bold dark:text-white">Tables Overview</h2>
          <button onClick={() => setActiveTab('tables')} className="text-xs text-brand-500 hover:underline">View All →</button>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table w-full">
            <thead><tr>
              <th>Name</th><th>Type</th><th>Columns</th><th>Rows</th><th>Primary Key</th><th>FKs</th><th>Indexes</th>
            </tr></thead>
            <tbody>
              {(o.tables || []).slice(0, 20).map(t => (
                <tr key={t.name} className="cursor-pointer" onClick={() => setActiveTab('tables')}>
                  <td className="font-medium text-brand-600 dark:text-brand-400">{t.name}</td>
                  <td><span className={`badge ${t.type === 'TABLE' ? 'badge-success' : 'badge-warning'}`}>{t.type}</span></td>
                  <td>{t.columns}</td>
                  <td>{(t.rows || 0).toLocaleString()}</td>
                  <td className="text-xs">{(t.pk || []).join(', ') || '-'}</td>
                  <td>{t.fk_count}</td>
                  <td>{t.indexes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(o.tables || []).length > 20 && (
          <div className="p-3 text-center text-xs text-gray-400">
            Showing 20 of {o.tables.length} tables
          </div>
        )}
      </div>
    </div>
  );
}

function HeroSection({ onConnect }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] text-center animate-fade-in">
      <div className="w-20 h-20 gradient-bg rounded-3xl flex items-center justify-center text-white mb-6 animate-pulse-slow">
        <Database size={40} />
      </div>
      <h1 className="text-4xl font-extrabold gradient-text mb-3">Data Dictionary Agent</h1>
      <p className="text-gray-500 dark:text-gray-400 max-w-lg mb-8 text-lg">
        Extract, analyze, and document your database schema with AI-powered insights.
        Secure, read-only, and enterprise-ready.
      </p>
      <div className="flex gap-4">
        <button onClick={onConnect} className="px-6 py-3 rounded-xl bg-gradient-to-r from-brand-500 to-purple-500 text-white font-semibold hover:shadow-xl hover:shadow-brand-500/25 transition-all hover:-translate-y-0.5">
          Connect Database
        </button>
      </div>
      <div className="mt-12 grid grid-cols-3 gap-8 max-w-2xl">
        {[
          { icon: '🔒', title: 'Read-Only', desc: 'Your data is never modified' },
          { icon: '🤖', title: 'AI-Powered', desc: 'Smart column descriptions & insights' },
          { icon: '🚀', title: 'Enterprise Scale', desc: 'Handles 10,000+ tables seamlessly' },
        ].map(f => (
          <div key={f.title} className="text-center">
            <div className="text-3xl mb-2">{f.icon}</div>
            <p className="font-semibold dark:text-white">{f.title}</p>
            <p className="text-xs text-gray-500">{f.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function InfoBlock({ label, value, color }) {
  const colors = {
    blue: 'bg-blue-50 dark:bg-blue-900/30 border-l-4 border-blue-500 text-blue-800 dark:text-blue-300',
    green: 'bg-green-50 dark:bg-green-900/30 border-l-4 border-green-500 text-green-800 dark:text-green-300',
    amber: 'bg-amber-50 dark:bg-amber-900/30 border-l-4 border-amber-500 text-amber-800 dark:text-amber-300',
  };
  return (
    <div className={`p-4 rounded-lg ${colors[color]}`}>
      <p className="text-xs font-bold uppercase mb-2 opacity-70">{label}</p>
      <p className="text-sm leading-relaxed">{value}</p>
    </div>
  );
}
