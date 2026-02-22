import React, { useState } from 'react';
import { useApp } from '../App';
import { connectDb, connectSample, getOverview } from '../api/client';
import { X, Database, Loader2, Zap } from 'lucide-react';
import toast from 'react-hot-toast';

const DB_TYPES = [
  { value: 'postgresql', label: 'PostgreSQL', port: 5432 },
  { value: 'mysql', label: 'MySQL', port: 3306 },
  { value: 'sqlite', label: 'SQLite', port: null },
  { value: 'sqlserver', label: 'SQL Server', port: 1433 },
  { value: 'snowflake', label: 'Snowflake', port: null },
  { value: 'oracle', label: 'Oracle', port: 1521 },
];

export default function ConnectionModal() {
  const { setSession, setShowConnect, setOverview } = useApp();
  const [dbType, setDbType] = useState('postgresql');
  const [form, setForm] = useState({ host: 'localhost', port: '5432', database: '', username: '', password: '', filepath: '', account: '', warehouse: '', schema: '' });
  const [loading, setLoading] = useState(false);

  const update = (key, val) => setForm(prev => ({ ...prev, [key]: val }));

  const handleConnect = async () => {
    setLoading(true);
    try {
      const payload = { db_type: dbType, ...form, port: form.port ? parseInt(form.port) : null };
      const data = await connectDb(payload);
      setSession(data);
      const ov = await getOverview(data.session_id);
      setOverview(ov);
      setShowConnect(false);
      toast.success(`Connected to ${data.database_name}!`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Connection failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSample = async () => {
    setLoading(true);
    try {
      const data = await connectSample();
      setSession(data);
      const ov = await getOverview(data.session_id);
      setOverview(ov);
      setShowConnect(false);
      toast.success('Connected to sample database!');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    } finally {
      setLoading(false);
    }
  };

  const dbTypeInfo = DB_TYPES.find(d => d.value === dbType);
  const isSqlite = dbType === 'sqlite';
  const isSnowflake = dbType === 'snowflake';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in">
      <div className="glass-card w-full max-w-lg p-6 m-4 animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 gradient-bg rounded-xl flex items-center justify-center text-white">
              <Database size={20} />
            </div>
            <div>
              <h2 className="text-lg font-bold dark:text-white">Connect Database</h2>
              <p className="text-xs text-gray-500">Read-only access • Secure connection</p>
            </div>
          </div>
          <button onClick={() => setShowConnect(false)} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
            <X size={18} className="text-gray-400" />
          </button>
        </div>

        {/* Quick connect */}
        <button onClick={handleSample} disabled={loading} className="w-full mb-5 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-brand-500 to-purple-500 text-white font-medium text-sm hover:shadow-lg hover:shadow-brand-500/25 transition-all disabled:opacity-50">
          <Zap size={16} /> Try with Sample Database
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
          <span className="text-xs text-gray-400 uppercase">or connect your own</span>
          <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
        </div>

        {/* DB type selector */}
        <div className="grid grid-cols-3 gap-2 mb-5">
          {DB_TYPES.map(dt => (
            <button
              key={dt.value}
              onClick={() => { setDbType(dt.value); if (dt.port) update('port', String(dt.port)); }}
              className={`py-2 rounded-xl text-xs font-medium transition-all ${
                dbType === dt.value
                  ? 'bg-brand-500 text-white shadow-md'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {dt.label}
            </button>
          ))}
        </div>

        {/* Form fields */}
        <div className="space-y-3 max-h-60 overflow-y-auto pr-1">
          {isSqlite ? (
            <Input label="Database File Path" value={form.filepath} onChange={v => update('filepath', v)} placeholder="/path/to/database.db" />
          ) : isSnowflake ? (
            <>
              <Input label="Account" value={form.account} onChange={v => update('account', v)} placeholder="your_account" />
              <Input label="Warehouse" value={form.warehouse} onChange={v => update('warehouse', v)} placeholder="your_warehouse" />
              <Input label="Database" value={form.database} onChange={v => update('database', v)} placeholder="your_database" />
              <Input label="Schema" value={form.schema} onChange={v => update('schema', v)} placeholder="your_schema" />
              <Input label="Username" value={form.username} onChange={v => update('username', v)} />
              <Input label="Password" value={form.password} onChange={v => update('password', v)} type="password" />
            </>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2"><Input label="Host" value={form.host} onChange={v => update('host', v)} /></div>
                <Input label="Port" value={form.port} onChange={v => update('port', v)} />
              </div>
              <Input label="Database" value={form.database} onChange={v => update('database', v)} placeholder="your_database" />
              <Input label="Username" value={form.username} onChange={v => update('username', v)} />
              <Input label="Password" value={form.password} onChange={v => update('password', v)} type="password" />
            </>
          )}
        </div>

        {/* Connect button */}
        <button onClick={handleConnect} disabled={loading} className="w-full mt-5 py-3 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
          {loading ? 'Connecting...' : 'Connect'}
        </button>
      </div>
    </div>
  );
}

function Input({ label, value, onChange, type = 'text', placeholder = '' }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none transition-all dark:text-white"
      />
    </div>
  );
}
