import React, { useState, useEffect } from 'react';
import { useApp } from '../App';
import { analyzeQuality, getSchema } from '../api/client';
import { ShieldCheck, Loader2, AlertTriangle, CheckCircle2, XCircle, ChevronDown, ChevronUp, BarChart3 } from 'lucide-react';
import toast from 'react-hot-toast';

export default function QualityPage() {
  const { session, quality, setQuality } = useApp();
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState('');
  const [expandedTable, setExpandedTable] = useState(null);

  useEffect(() => {
    if (!session) return;
    (async () => {
      try {
        const data = await getSchema(session.session_id, 1, 500);
        // Store tables with their full display name (schema.name format)
        setTables(data.tables.map(t => t.schema ? `${t.schema}.${t.name}` : t.name));
      } catch {}
    })();
  }, [session]);

  const analyzeAll = async () => {
    setLoading(true);
    let done = 0;
    for (const table of tables) {
      if (quality[table]) { done++; continue; }
      setAnalyzing(table);
      try {
        const data = await analyzeQuality(session.session_id, table);
        setQuality(prev => ({ ...prev, ...data.tables }));
      } catch { /* skip failed */ }
      done++;
    }
    setAnalyzing('');
    setLoading(false);
    toast.success(`Quality analysis complete (${done} tables)`);
  };

  const analyzeOne = async (table) => {
    setAnalyzing(table);
    try {
      const data = await analyzeQuality(session.session_id, table);
      setQuality(prev => ({ ...prev, ...data.tables }));
      toast.success(`Analyzed ${table}`);
    } catch { toast.error(`Failed to analyze ${table}`); }
    finally { setAnalyzing(''); }
  };

  if (!session) return (
    <div className="glass-card p-12 text-center animate-fade-in">
      <ShieldCheck size={40} className="mx-auto text-gray-300 dark:text-gray-600 mb-4" />
      <p className="text-gray-500">Connect to a database to analyze quality</p>
    </div>
  );

  const analyzed = Object.entries(quality);
  const avgScore = analyzed.length > 0 ? Math.round(analyzed.reduce((s, [, v]) => s + (v.quality_score || 0), 0) / analyzed.length) : 0;
  const totalIssues = analyzed.reduce((s, [, v]) => s + (v.issues?.length || 0), 0);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="glass-card p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold dark:text-white flex items-center gap-2">
              <ShieldCheck className="text-green-500" /> Data Quality Dashboard
            </h2>
            <p className="text-gray-500 text-sm mt-1">
              {analyzed.length} of {tables.length} tables analyzed
            </p>
          </div>
          <button onClick={analyzeAll} disabled={loading}
            className="flex items-center gap-2 px-6 py-3 rounded-xl font-medium text-white bg-gradient-to-r from-green-500 to-emerald-500 hover:shadow-lg hover:shadow-green-500/25 transition-all disabled:opacity-50">
            {loading ? <><Loader2 size={16} className="animate-spin" /> Analyzing {analyzing}...</> : <><BarChart3 size={16} /> Analyze All Tables</>}
          </button>
        </div>
      </div>

      {/* Summary stats */}
      {analyzed.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Avg Quality Score" value={`${avgScore}/100`} icon={<ScoreBadge score={avgScore} />} />
          <StatCard label="Tables Analyzed" value={analyzed.length} desc={`of ${tables.length}`} color="blue" />
          <StatCard label="Total Issues" value={totalIssues} color={totalIssues > 10 ? 'red' : 'green'} />
          <StatCard label="Best Score" value={`${analyzed.length > 0 ? Math.max(...analyzed.map(([, v]) => v.quality_score || 0)) : 0}/100`} color="purple" />
        </div>
      )}

      {/* Table results */}
      <div className="space-y-3">
        {tables.map(table => {
          const tq = quality[table];
          const expanded = expandedTable === table;
          return (
            <div key={table} className="glass-card overflow-hidden">
              <div className="flex items-center gap-3 p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                onClick={() => setExpandedTable(expanded ? null : table)}>
                <div className="flex-1 flex items-center gap-3 min-w-0">
                  {tq ? <ScoreBadge score={tq.quality_score} size="sm" /> : <div className="w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-800" />}
                  <span className="font-medium text-sm dark:text-white truncate">{table}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  {tq ? (
                    <>
                      <MiniStat label="Completeness" value={`${(tq.overall_completeness * 100).toFixed(0)}%`} />
                      <MiniStat label="PK Health" value={`${(tq.primary_key_health * 100).toFixed(0)}%`} />
                      {tq.issues?.length > 0 && (
                        <span className="flex items-center gap-1 text-xs text-yellow-600">
                          <AlertTriangle size={12} /> {tq.issues.length}
                        </span>
                      )}
                    </>
                  ) : (
                    <button onClick={e => { e.stopPropagation(); analyzeOne(table); }} disabled={analyzing === table}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg bg-green-50 dark:bg-green-900/20 text-green-600 hover:bg-green-100 transition-colors disabled:opacity-50">
                      {analyzing === table ? <Loader2 size={12} className="animate-spin" /> : 'Analyze'}
                    </button>
                  )}
                  {expanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
                </div>
              </div>

              {expanded && tq && (
                <div className="p-4 border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 animate-slide-up">
                  {/* Quality metrics grid */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                    <MetricCard label="Quality Score" value={tq.quality_score} max={100} color={scoreColor(tq.quality_score)} />
                    <MetricCard label="Completeness" value={(tq.overall_completeness * 100).toFixed(1)} suffix="%" color="blue" />
                    <MetricCard label="PK Health" value={(tq.primary_key_health * 100).toFixed(1)} suffix="%" color="purple" />
                    <MetricCard label="Avg Uniqueness" value={
                      Array.isArray(tq.columns) && tq.columns.length > 0 
                        ? ((tq.columns.reduce((sum, c) => sum + (c.uniqueness || 0), 0) / tq.columns.length) * 100).toFixed(1)
                        : '0.0'
                    } suffix="%" color="teal" />
                    <MetricCard label="Dup Estimate" value={(tq.duplicate_row_estimate * 100).toFixed(2)} suffix="%" color="amber" />
                  </div>

                  {/* Freshness */}
                  {tq.data_freshness && (
                    <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 mb-4">
                      <p className="text-sm font-semibold text-blue-700 dark:text-blue-400">📅 Freshness</p>
                      <p className="text-sm text-blue-600 dark:text-blue-300 mt-1">{tq.data_freshness}</p>
                    </div>
                  )}

                  {/* Issues */}
                  {Array.isArray(tq.issues) && tq.issues.length > 0 && (
                    <div className="p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 mb-4">
                      <p className="text-sm font-semibold text-yellow-700 dark:text-yellow-400 mb-2">⚠️ Issues</p>
                      {tq.issues.map((issue, i) => (
                        <p key={i} className="text-sm text-yellow-600 dark:text-yellow-300">• {issue}</p>
                      ))}
                    </div>
                  )}

                  {/* Column quality */}
                  {Array.isArray(tq.columns) && tq.columns.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="data-table w-full">
                        <thead><tr><th>Column</th><th>Type</th><th>Nulls %</th><th>Uniqueness %</th><th>Stats</th></tr></thead>
                        <tbody>
                          {tq.columns.map((col, idx) => {
                            const nullPct = col.total_count > 0 ? (col.null_count / col.total_count) * 100 : 0;
                            return (
                            <tr key={col.column_name || idx}>
                              <td className="font-mono text-xs font-medium">{col.column_name}</td>
                              <td className="text-xs text-gray-500">{col.data_type}</td>
                              <td>
                                <div className="flex items-center gap-2">
                                  <div className="w-16 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                    <div className={`h-full rounded-full ${nullPct > 50 ? 'bg-red-500' : nullPct > 10 ? 'bg-yellow-500' : 'bg-green-500'}`}
                                      style={{ width: `${Math.min(nullPct, 100)}%` }} />
                                  </div>
                                  <span className="text-xs">{nullPct.toFixed(1)}</span>
                                </div>
                              </td>
                              <td className="text-xs">{((col.uniqueness || 0) * 100).toFixed(1)}%</td>
                              <td className="text-xs text-gray-500">
                                {col.min_value != null && <span>Min: {String(col.min_value).slice(0, 20)} </span>}
                                {col.max_value != null && <span>Max: {String(col.max_value).slice(0, 20)}</span>}
                              </td>
                            </tr>
                          );})}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StatCard({ label, value, desc, icon, color = 'brand' }) {
  const colors = { brand: 'text-brand-600', blue: 'text-blue-600', green: 'text-green-600', red: 'text-red-600', purple: 'text-purple-600' };
  return (
    <div className="stat-card glass-card p-4 text-center">
      {icon || <p className={`text-2xl font-bold ${colors[color]}`}>{value}</p>}
      {desc && <p className="text-xs text-gray-400">{desc}</p>}
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="hidden md:block text-right">
      <p className="text-xs font-medium dark:text-white">{value}</p>
      <p className="text-[10px] text-gray-400">{label}</p>
    </div>
  );
}

function MetricCard({ label, value, suffix = '', color, max }) {
  const colors = { green: 'text-green-600', blue: 'text-blue-600', purple: 'text-purple-600', teal: 'text-teal-600', amber: 'text-amber-600', red: 'text-red-600' };
  return (
    <div className="p-3 rounded-xl bg-white dark:bg-gray-800/80 text-center">
      <p className={`text-lg font-bold ${colors[color]}`}>{value}{suffix}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}

function ScoreBadge({ score, size = 'md' }) {
  const dim = size === 'sm' ? 'w-8 h-8 text-xs' : 'w-12 h-12 text-sm';
  const bg = score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : score >= 40 ? 'bg-orange-500' : 'bg-red-500';
  return (
    <div className={`${dim} ${bg} rounded-full flex items-center justify-center text-white font-bold`}>
      {score}
    </div>
  );
}

function scoreColor(s) { return s >= 80 ? 'green' : s >= 60 ? 'amber' : 'red'; }
