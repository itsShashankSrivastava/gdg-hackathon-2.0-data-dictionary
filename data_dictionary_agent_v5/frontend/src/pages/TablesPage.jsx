import React, { useState, useEffect } from 'react';
import { useApp } from '../App';
import { getSchema, getTableDetail, analyzeQuality, generateAISummary, getSampleData } from '../api/client';
import { Search, Loader2, Key, Link2, Sparkles, ShieldCheck, Eye, ChevronDown, ChevronRight, Table2, RefreshCw, AlertCircle } from 'lucide-react';
import toast from 'react-hot-toast';

export default function TablesPage() {
  const { session, overview, quality, setQuality, aiSummaries, setAiSummaries, handleSessionExpired } = useApp();
  const [tables, setTables] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [actionLoading, setActionLoading] = useState('');
  const [sampleData, setSampleData] = useState(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    if (!session) return;
    loadTables(1);
  }, [session]);

  const loadTables = async (p, retryCount = 0) => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getSchema(session.session_id, p, 100);
      setTables(data.tables);
      setTotalPages(data.total_pages);
      setPage(p);
    } catch (err) {
      console.error('Load tables error:', err);
      // Check if session expired (404)
      if (err?.response?.status === 404) {
        toast.error('Session expired. Please reconnect.');
        handleSessionExpired();
        return;
      }
      // Retry up to 2 times for network errors
      if (retryCount < 2 && (!err?.response || err?.response?.status >= 500)) {
        await new Promise(r => setTimeout(r, 1000 * (retryCount + 1)));
        return loadTables(p, retryCount + 1);
      }
      setLoadError('Failed to load tables. Check your connection.');
      toast.error('Failed to load tables');
    } finally {
      setLoading(false);
    }
  };

  const selectTable = async (tableName) => {
    setSelected(tableName);
    setSampleData(null);
    try {
      const d = await getTableDetail(session.session_id, tableName);
      setDetail(d);
    } catch (err) {
      if (err?.response?.status === 404) {
        toast.error('Session expired. Please reconnect.');
        handleSessionExpired();
        return;
      }
      toast.error('Failed to load table details');
    }
  };

  const handleAI = async () => {
    if (!selected || !detail) return;
    setActionLoading('ai');
    try {
      // Use the full table key (with schema if present) to match backend storage
      const tableNameForAPI = detail.schema ? `${detail.schema}.${detail.name}` : detail.name;
      console.log('Requesting AI summary for:', tableNameForAPI);
      const data = await generateAISummary(session.session_id, tableNameForAPI);
      console.log('AI Summary Response:', data);
      setAiSummaries(prev => ({ ...prev, ...data.table_summaries }));
      toast.success('AI summary generated');
    } catch (err) {
      console.error('AI Summary Error:', err);
      if (err?.response?.status === 404) {
        toast.error('Session expired. Please reconnect.');
        handleSessionExpired();
        return;
      }
      toast.error('AI summary failed');
    }
    finally { setActionLoading(''); }
  };

  const handleSample = async () => {
    if (!selected) return;
    setActionLoading('sample');
    try {
      const data = await getSampleData(session.session_id, selected);
      setSampleData(data);
    } catch (err) {
      if (err?.response?.status === 404) {
        toast.error('Session expired. Please reconnect.');
        handleSessionExpired();
        return;
      }
      toast.error('Failed to load sample data');
    }
    finally { setActionLoading(''); }
  };

  const handleQuality = async () => {
    if (!selected) return;
    setActionLoading('quality');
    try {
      const data = await analyzeQuality(session.session_id, selected);
      setQuality(prev => ({ ...prev, ...data.tables }));
      toast.success('Quality analysis complete');
    } catch (err) {
      if (err?.response?.status === 404) {
        toast.error('Session expired. Please reconnect.');
        handleSessionExpired();
        return;
      }
      toast.error('Quality analysis failed');
    }
    finally { setActionLoading(''); }
  };

  if (!session) return <EmptyState />;

  const filtered = tables.filter(t => t.name.toLowerCase().includes(search.toLowerCase()));
  
  // Build consistent key for looking up quality and AI data (use 'schema' not 'schema_name')
  const tableKey = detail ? (detail.schema ? `${detail.schema}.${detail.name}` : detail.name) : selected;
  const tq = quality[tableKey];
  const tAI = aiSummaries[tableKey];
  
  console.log('DEBUG - Looking for AI summary with key:', tableKey, '| Available keys:', Object.keys(aiSummaries));

  return (
    <div className="flex gap-6 animate-fade-in" style={{ minHeight: 'calc(100vh - 6rem)' }}>
      {/* Sidebar – table list */}
      <div className="w-72 shrink-0">
        <div className="glass-card overflow-hidden sticky top-6">
          <div className="p-3 border-b border-gray-100 dark:border-gray-800">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search tables..."
                className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent focus:ring-2 focus:ring-brand-500 outline-none dark:text-white"
              />
            </div>
          </div>
          <div className="max-h-[65vh] overflow-y-auto">
            {loading ? (
              <div className="flex justify-center py-8"><Loader2 className="animate-spin text-brand-500" size={24} /></div>
            ) : loadError ? (
              <div className="p-6 text-center">
                <AlertCircle size={32} className="mx-auto text-red-400 mb-3" />
                <p className="text-sm text-red-500 mb-3">{loadError}</p>
                <button 
                  onClick={() => loadTables(page)} 
                  className="flex items-center gap-2 mx-auto px-4 py-2 text-sm rounded-lg bg-brand-500 text-white hover:bg-brand-600 transition-colors"
                >
                  <RefreshCw size={14} /> Retry
                </button>
              </div>
            ) : filtered.length === 0 ? (
              <div className="p-6 text-center text-gray-400 text-sm">
                {search ? 'No tables match your search' : 'No tables found'}
              </div>
            ) : (
              filtered.map(t => (
                <button
                  key={t.name}
                  onClick={() => selectTable(t.name)}
                  className={`w-full text-left px-4 py-3 text-sm border-b border-gray-50 dark:border-gray-800 transition-colors flex items-center gap-2 ${
                    selected === t.name ? 'bg-brand-50 dark:bg-brand-900/20 text-brand-600 dark:text-brand-400 font-medium' : 'hover:bg-gray-50 dark:hover:bg-gray-800/50 text-gray-700 dark:text-gray-300'
                  }`}
                >
                  {t.table_type === 'VIEW' ? <Eye size={14} className="text-purple-500" /> : <Table2 size={14} className="text-brand-500" />}
                  <span className="truncate flex-1">{t.name}</span>
                  <span className="text-[10px] text-gray-400">{t.columns?.length || 0} cols</span>
                </button>
              ))
            )}
          </div>
          {totalPages > 1 && (
            <div className="p-3 flex gap-2 justify-center border-t border-gray-100 dark:border-gray-800">
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => (
                <button key={i} onClick={() => loadTables(i + 1)}
                  className={`w-8 h-8 rounded-lg text-xs font-medium ${page === i + 1 ? 'bg-brand-500 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600'}`}>
                  {i + 1}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detail panel */}
      <div className="flex-1 min-w-0">
        {!detail ? (
          <div className="glass-card p-12 text-center">
            <Table2 size={40} className="mx-auto text-gray-300 dark:text-gray-600 mb-4" />
            <p className="text-gray-500 text-sm">Select a table from the list to view details</p>
          </div>
        ) : (
          <div className="space-y-5 animate-slide-up">
            {/* Header + actions */}
            <div className="glass-card p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-xl font-bold dark:text-white">{tableKey}</h2>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`badge ${detail.table_type === 'TABLE' ? 'badge-success' : 'badge-warning'}`}>{detail.table_type}</span>
                    <span className="text-xs text-gray-500">{(detail.row_count || 0).toLocaleString()} rows • {detail.columns?.length || 0} columns</span>
                  </div>
                </div>
              </div>
              <div className="flex gap-2 flex-wrap">
                <ActionBtn icon={ShieldCheck} label="Analyze Quality" loading={actionLoading === 'quality'} onClick={handleQuality} />
                <ActionBtn icon={Sparkles} label="AI Summary" loading={actionLoading === 'ai'} onClick={handleAI} gradient />
                <ActionBtn icon={Eye} label="Sample Data" loading={actionLoading === 'sample'} onClick={handleSample} />
              </div>
            </div>

            {/* AI summary */}
            {tAI && (
              <div className="glass-card p-5 animate-slide-up">
                <h3 className="font-bold dark:text-white flex items-center gap-2 mb-3"><Sparkles size={16} className="text-brand-500" /> AI Analysis</h3>
                {tAI.business_summary && (
                  <div className="p-4 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 mb-4">
                    <p className="text-sm font-semibold text-green-700 dark:text-green-400 mb-1">💼 Business Context</p>
                    <p className="text-sm text-green-800 dark:text-green-300">{tAI.business_summary}</p>
                    {tAI.analyst_recommendation && <p className="text-xs text-green-600 dark:text-green-400 mt-2">📋 {tAI.analyst_recommendation}</p>}
                  </div>
                )}
                <div className="grid md:grid-cols-2 gap-4">
                  {Array.isArray(tAI.key_insights) && tAI.key_insights.length > 0 && (
                    <div><p className="text-sm font-semibold mb-2 dark:text-white">💡 Key Insights</p>
                      <ul className="space-y-1">{tAI.key_insights.map((s, i) => <li key={i} className="text-sm text-gray-600 dark:text-gray-400">• {s}</li>)}</ul>
                    </div>
                  )}
                  {Array.isArray(tAI.usage_recommendations) && tAI.usage_recommendations.length > 0 && (
                    <div><p className="text-sm font-semibold mb-2 dark:text-white">🎯 Recommendations</p>
                      <ul className="space-y-1">{tAI.usage_recommendations.map((s, i) => <li key={i} className="text-sm text-gray-600 dark:text-gray-400">• {s}</li>)}</ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Quality */}
            {tq && (
              <div className="glass-card p-5 animate-slide-up">
                <h3 className="font-bold dark:text-white flex items-center gap-2 mb-3"><ShieldCheck size={16} className="text-green-500" /> Data Quality</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <QStat label="Quality Score" value={`${tq.quality_score}/100`} color={tq.quality_score >= 75 ? 'green' : tq.quality_score >= 50 ? 'yellow' : 'red'} />
                  <QStat label="Completeness" value={`${(tq.overall_completeness * 100).toFixed(0)}%`} color="blue" />
                  <QStat label="PK Health" value={`${(tq.primary_key_health * 100).toFixed(0)}%`} color="purple" />
                  <QStat label="Duplicates" value={`${(tq.duplicate_row_estimate * 100).toFixed(1)}%`} color="amber" />
                </div>
                {Array.isArray(tq.issues) && tq.issues.length > 0 && (
                  <div className="p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 text-sm space-y-1 mb-2">
                    {tq.issues.map((i, idx) => <p key={idx} className="text-yellow-700 dark:text-yellow-400">⚠️ {i}</p>)}
                  </div>
                )}
              </div>
            )}

            {/* Columns table */}
            <div className="glass-card overflow-hidden">
              <div className="p-4 border-b border-gray-100 dark:border-gray-800">
                <h3 className="font-bold dark:text-white">📋 Columns</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="data-table w-full">
                  <thead><tr><th>Name</th><th>Type</th><th>Nullable</th><th>Keys</th><th>Description</th></tr></thead>
                  <tbody>
                    {(detail.columns || []).map(col => {
                      const aiDesc = tAI?.column_descriptions?.[col.name];
                      return (
                        <tr key={col.name}>
                          <td className="font-medium font-mono text-xs dark:text-gray-100">{col.name}</td>
                          <td className="text-xs text-gray-500 dark:text-gray-400">{col.data_type}</td>
                          <td>{col.nullable ? <span className="text-green-500">✓</span> : <span className="text-red-400">✗</span>}</td>
                          <td className="space-x-1">
                            {col.primary_key && <span className="badge badge-pk">🔑 PK</span>}
                            {col.foreign_key && <span className="badge badge-fk">🔗 FK→{col.foreign_key.referred_table}</span>}
                            {col.unique && <span className="badge badge-unique">✨ U</span>}
                          </td>
                          <td className="text-xs text-gray-600 dark:text-gray-400 max-w-xs">{aiDesc || col.description || col.comment || '-'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Relationships */}
            {Array.isArray(detail.relationships) && detail.relationships.length > 0 && (
              <div className="glass-card p-5">
                <h3 className="font-bold dark:text-white flex items-center gap-2 mb-3"><Link2 size={16} className="text-purple-500" /> Relationships</h3>
                <div className="grid md:grid-cols-2 gap-3">
                  {detail.relationships.filter(r => r.type === 'references').map((r, i) => (
                    <div key={i} className="p-3 rounded-lg bg-purple-50 dark:bg-purple-900/20 text-sm flex items-center gap-2">
                      <span className="badge badge-fk">→</span>
                      <span className="text-gray-700 dark:text-gray-300">{r.from_columns.join(', ')} → <strong>{r.to_table}</strong></span>
                    </div>
                  ))}
                  {detail.relationships.filter(r => r.type === 'referenced_by').map((r, i) => (
                    <div key={i} className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 text-sm flex items-center gap-2">
                      <span className="badge badge-pk">←</span>
                      <span className="text-gray-700 dark:text-gray-300"><strong>{r.from_table}</strong> → {r.from_columns.join(', ')}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Sample data */}
            {sampleData && (
              <div className="glass-card overflow-hidden">
                <div className="p-4 border-b border-gray-100 dark:border-gray-800">
                  <h3 className="font-bold dark:text-white">📝 Sample Data ({sampleData.rows?.length || 0} rows)</h3>
                </div>
                <div className="overflow-x-auto max-h-96">
                  <table className="data-table w-full">
                    <thead><tr>{(sampleData.columns || []).map(c => <th key={c}>{c}</th>)}</tr></thead>
                    <tbody>
                      {(sampleData.rows || []).slice(0, 50).map((row, ri) => (
                        <tr key={ri}>{(sampleData.columns || []).map(c => <td key={c} className="text-xs max-w-[200px] truncate">{String(row[c] ?? '')}</td>)}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ActionBtn({ icon: Icon, label, loading, onClick, gradient }) {
  return (
    <button onClick={onClick} disabled={loading}
      className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all disabled:opacity-50 ${
        gradient
          ? 'bg-gradient-to-r from-brand-500 to-purple-500 text-white hover:shadow-lg hover:shadow-brand-500/25'
          : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
      }`}>
      {loading ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />} {label}
    </button>
  );
}

function QStat({ label, value, color }) {
  const colors = { green: 'text-green-600', blue: 'text-blue-600', purple: 'text-purple-600', amber: 'text-amber-600', yellow: 'text-yellow-600', red: 'text-red-600' };
  return (
    <div className="text-center p-3 rounded-xl bg-gray-50 dark:bg-gray-800/50">
      <p className={`text-xl font-bold ${colors[color]}`}>{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="glass-card p-12 text-center">
      <Table2 size={40} className="mx-auto text-gray-300 dark:text-gray-600 mb-4" />
      <p className="text-gray-500">Connect to a database to explore tables</p>
    </div>
  );
}
