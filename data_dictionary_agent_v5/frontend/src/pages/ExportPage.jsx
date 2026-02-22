import React, { useState, useRef } from 'react';
import { useApp } from '../App';
import { exportDocs, generateAISummary, getSchema } from '../api/client';
import { Download, FileJson, FileText, Globe, Loader2, Check, Eye, Sparkles, FileOutput } from 'lucide-react';
import toast from 'react-hot-toast';

const FORMATS = [
  { id: 'json', label: 'JSON', desc: 'Machine-readable format, great for integrations and further processing', icon: FileJson, color: 'amber', ext: '.json' },
  { id: 'markdown', label: 'Markdown', desc: 'Clean text format, perfect for README files and wikis', icon: FileText, color: 'blue', ext: '.md' },
  { id: 'html', label: 'HTML', desc: 'Rich formatted document, ideal for sharing and embedding', icon: Globe, color: 'green', ext: '.html' },
  { id: 'pdf', label: 'PDF', desc: 'Professional document format, perfect for sharing with stakeholders', icon: FileOutput, color: 'red', ext: '.pdf' },
];

export default function ExportPage() {
  const { session, setAiSummaries, setDbSummary, handleSessionExpired } = useApp();
  const [selectedFormat, setSelectedFormat] = useState('html');
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [downloadReady, setDownloadReady] = useState(false);
  const [aiGenerated, setAiGenerated] = useState(false);
  
  // Local AI generation state - doesn't affect other pages
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiProgressText, setAiProgressText] = useState('');
  const cancelledRef = useRef(false);

  const handleGenerateAllAI = async () => {
    if (!session || aiGenerating) return;
    cancelledRef.current = false;
    setAiGenerating(true);
    setAiProgressText('Fetching tables...');
    try {
      // Get all tables
      const schemaData = await getSchema(session.session_id, 1, 500);
      const tables = schemaData.tables.map(t => t.schema ? `${t.schema}.${t.name}` : t.name);
      setAiProgressText('Generating database summary...');
      
      // Generate database summary first
      const dbResp = await generateAISummary(session.session_id);
      if (dbResp.database_summary) setDbSummary(dbResp.database_summary);
      
      // Generate for each table
      for (let i = 0; i < tables.length; i++) {
        if (cancelledRef.current) break;
        const table = tables[i];
        setAiProgressText(`Analyzing ${table}... (${i + 1}/${tables.length})`);
        try {
          const data = await generateAISummary(session.session_id, table);
          if (data.table_summaries) {
            setAiSummaries(prev => ({ ...prev, ...data.table_summaries }));
          }
        } catch (err) {
          if (err?.response?.status === 404) {
            toast.error('Session expired. Please reconnect.');
            handleSessionExpired();
            return;
          }
          console.warn(`Failed to generate AI for ${table}:`, err);
        }
      }
      if (!cancelledRef.current) {
        setAiGenerated(true);
        toast.success('All AI summaries generated! Now export your documentation.');
      }
    } catch (err) {
      console.error('AI generation error:', err);
      if (err?.response?.status === 404) {
        toast.error('Session expired. Please reconnect.');
        handleSessionExpired();
        return;
      }
      toast.error('AI generation failed');
    } finally {
      setAiGenerating(false);
      setAiProgressText('');
    }
  };

  const handleExport = async (preview_only = false) => {
    if (!session) return;
    // PDF doesn't support preview - just trigger download instead
    if (preview_only && selectedFormat === 'pdf') {
      toast('PDF preview not available. Starting download...', { icon: 'ℹ️' });
      return handleExport(false); // Trigger download instead
    }
    setLoading(true);
    setDownloadReady(false);
    try {
      const data = await exportDocs(session.session_id, selectedFormat);
      if (data.content) {
        if (preview_only) {
          setPreview(data.content);
        } else {
          downloadFile(data.content, `data_dictionary${FORMATS.find(f => f.id === selectedFormat).ext}`, selectedFormat);
          setDownloadReady(true);
          toast.success('Documentation exported successfully!');
        }
      } else {
        toast.success('Documentation saved to output folder');
      }
    } catch (error) { 
      console.error('Export error:', error);
      const errMsg = error?.response?.data?.detail || error?.message || 'Export failed';
      toast.error(errMsg); 
    }
    finally { setLoading(false); }
  };

  const downloadFile = (content, filename, format) => {
    let blob;
    if (format === 'pdf') {
      // PDF content is base64 encoded
      const binaryString = atob(content);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      blob = new Blob([bytes], { type: 'application/pdf' });
    } else {
      const mime = format === 'json' ? 'application/json' : format === 'html' ? 'text/html' : 'text/markdown';
      blob = new Blob([content], { type: `${mime};charset=utf-8` });
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  if (!session) return (
    <div className="glass-card p-12 text-center animate-fade-in">
      <Download size={40} className="mx-auto text-gray-300 dark:text-gray-600 mb-4" />
      <p className="text-gray-500">Connect to a database to export documentation</p>
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="glass-card p-6">
        <h2 className="text-2xl font-bold dark:text-white flex items-center gap-2 mb-2">
          <Download className="text-brand-500" /> Export Documentation
        </h2>
        <p className="text-gray-500 text-sm">
          Generate comprehensive data dictionary documentation from your database schema.
          Choose a format below and download your documentation.
        </p>
      </div>

      {/* Format selection */}
      <div className="grid md:grid-cols-4 gap-4">
        {FORMATS.map(fmt => {
          const Icon = fmt.icon;
          const active = selectedFormat === fmt.id;
          const colors = {
            amber: { bg: 'bg-amber-50 dark:bg-amber-900/20', border: 'border-amber-400', icon: 'text-amber-500', ring: 'ring-amber-400' },
            blue:  { bg: 'bg-blue-50 dark:bg-blue-900/20',   border: 'border-blue-400',  icon: 'text-blue-500',  ring: 'ring-blue-400' },
            green: { bg: 'bg-green-50 dark:bg-green-900/20', border: 'border-green-400', icon: 'text-green-500', ring: 'ring-green-400' },
            red:   { bg: 'bg-red-50 dark:bg-red-900/20',     border: 'border-red-400',   icon: 'text-red-500',   ring: 'ring-red-400' },
          }[fmt.color];

          return (
            <button key={fmt.id} onClick={() => { setSelectedFormat(fmt.id); setPreview(null); }}
              className={`glass-card p-5 text-left transition-all ${active
                ? `${colors.bg} border-2 ${colors.border} ring-2 ${colors.ring} ring-opacity-30`
                : 'border-2 border-transparent hover:border-gray-200 dark:hover:border-gray-700'}`}>
              <div className="flex items-center gap-3 mb-3">
                <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center`}>
                  <Icon size={20} className={colors.icon} />
                </div>
                <div>
                  <h3 className="font-bold dark:text-white">{fmt.label}</h3>
                  <span className="text-xs text-gray-400">{fmt.ext}</span>
                </div>
                {active && <Check size={18} className={`ml-auto ${colors.icon}`} />}
              </div>
              <p className="text-xs text-gray-500">{fmt.desc}</p>
            </button>
          );
        })}
      </div>

      {/* AI Generation */}
      <div className="glass-card p-6">
        <h3 className="font-bold dark:text-white mb-3 flex items-center gap-2">
          <Sparkles size={18} className="text-purple-500" /> AI-Powered Documentation
        </h3>
        <p className="text-sm text-gray-500 mb-4">
          Generate comprehensive AI summaries for all tables before exporting. This adds business context, 
          column descriptions, and analyst recommendations to your documentation.
        </p>
        <button onClick={handleGenerateAllAI} disabled={aiGenerating || loading}
          className={`w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-medium transition-all disabled:opacity-50 ${
            aiGenerated 
              ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-2 border-green-400'
              : 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:shadow-lg hover:shadow-purple-500/25'
          }`}>
          {aiGenerating ? (
            <><Loader2 size={16} className="animate-spin" /> {aiProgressText || 'Generating...'}</>
          ) : aiGenerated ? (
            <><Check size={16} /> AI Summaries Generated</>
          ) : (
            <><Sparkles size={16} /> Generate All AI Summaries</>
          )}
        </button>
        {aiGenerating && (
          <p className="text-xs text-gray-400 mt-2 text-center">
            You can navigate to other pages while this runs in the background
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="glass-card p-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <button onClick={() => handleExport(false)} disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-medium text-white bg-gradient-to-r from-brand-500 to-purple-500 hover:shadow-lg hover:shadow-brand-500/25 transition-all disabled:opacity-50">
            {loading ? <><Loader2 size={16} className="animate-spin" /> Generating...</> : <><Download size={16} /> Download {selectedFormat.toUpperCase()}</>}
          </button>
          <button onClick={() => handleExport(true)} disabled={loading}
            className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-all disabled:opacity-50">
            <Eye size={16} /> Preview
          </button>
        </div>

        {downloadReady && (
          <div className="mt-4 p-3 rounded-xl bg-green-50 dark:bg-green-900/20 flex items-center gap-2 animate-slide-up">
            <Check size={16} className="text-green-500" />
            <span className="text-sm text-green-700 dark:text-green-400">Download started! Check your downloads folder.</span>
          </div>
        )}
      </div>

      {/* Preview panel */}
      {preview && (
        <div className="glass-card overflow-hidden animate-slide-up">
          <div className="p-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
            <h3 className="font-bold dark:text-white flex items-center gap-2"><Eye size={16} /> Preview</h3>
            <button onClick={() => setPreview(null)} className="text-xs text-gray-400 hover:text-gray-600">Close</button>
          </div>
          <div className="p-4 max-h-[60vh] overflow-auto">
            {selectedFormat === 'html' ? (
              <iframe srcDoc={preview} className="w-full h-[55vh] border-0 rounded-lg" title="preview" />
            ) : (
              <pre className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">{preview.slice(0, 50000)}</pre>
            )}
          </div>
        </div>
      )}

      {/* Info cards */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="glass-card p-5">
          <h3 className="font-bold dark:text-white mb-3">📦 What's Included</h3>
          <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
            <li className="flex items-center gap-2"><Check size={14} className="text-green-500" /> Database overview & statistics</li>
            <li className="flex items-center gap-2"><Check size={14} className="text-green-500" /> Complete table & column metadata</li>
            <li className="flex items-center gap-2"><Check size={14} className="text-green-500" /> Primary keys, foreign keys, indexes</li>
            <li className="flex items-center gap-2"><Check size={14} className="text-green-500" /> Relationships between tables</li>
            <li className="flex items-center gap-2"><Check size={14} className="text-green-500" /> Data quality insights (if analyzed)</li>
            <li className="flex items-center gap-2"><Check size={14} className="text-green-500" /> AI-generated descriptions (if generated)</li>
          </ul>
        </div>
        <div className="glass-card p-5">
          <h3 className="font-bold dark:text-white mb-3">💡 Tips</h3>
          <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
            <li>• Run AI Summary on tables before exporting for richer documentation</li>
            <li>• Run Quality Analysis for data health insights in your export</li>
            <li>• HTML format includes interactive navigation</li>
            <li>• JSON format is ideal for automated documentation pipelines</li>
            <li>• Markdown works great with GitHub wikis and Confluence</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
