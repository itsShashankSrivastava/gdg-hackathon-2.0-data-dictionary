import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../App';
import { chatWithDb } from '../api/client';
import { MessageSquare, Send, Loader2, Bot, User, Trash2, Sparkles, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import toast from 'react-hot-toast';

const SUGGESTIONS = [
  "What are the main entities in this database?",
  "Describe the relationships between tables",
  "What columns have data quality issues?",
  "Summarize the database schema for a new team member",
  "Which tables store customer information?",
  "What indexes exist and are they optimal?",
];

export default function ChatPage() {
  const { session } = useApp();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async (text) => {
    const q = text || input.trim();
    if (!q || !session) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setLoading(true);
    try {
      const data = await chatWithDb(session.session_id, q);
      setMessages(prev => [...prev, { role: 'assistant', content: data.answer }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Sorry, I encountered an error processing your request. Please try again.' }]);
    } finally { setLoading(false); }
  };

  const clear = () => { setMessages([]); toast.success('Chat cleared'); };

  if (!session) return (
    <div className="glass-card p-12 text-center animate-fade-in">
      <MessageSquare size={40} className="mx-auto text-gray-300 dark:text-gray-600 mb-4" />
      <p className="text-gray-500">Connect to a database to start chatting</p>
    </div>
  );

  return (
    <div className="flex flex-col animate-fade-in" style={{ height: 'calc(100vh - 6rem)' }}>
      {/* Header */}
      <div className="glass-card p-4 mb-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-purple-500 flex items-center justify-center">
            <Bot size={20} className="text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold dark:text-white">Database Assistant</h2>
            <p className="text-xs text-gray-500">Ask anything about your database schema, relationships, or data quality</p>
          </div>
        </div>
        {messages.length > 0 && (
          <button onClick={clear} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 transition-colors">
            <Trash2 size={16} />
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto min-h-0 space-y-4 pb-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center px-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-purple-500 flex items-center justify-center mb-6 animate-pulse-slow">
              <Sparkles size={28} className="text-white" />
            </div>
            <h3 className="text-xl font-bold mb-2 dark:text-white">How can I help?</h3>
            <p className="text-gray-500 text-sm mb-8 text-center max-w-md">
              Ask me about your database schema, relationships, data quality, or anything else. I have context about all your tables and columns.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-xl">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} onClick={() => send(s)}
                  className="text-left p-3 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-all text-sm text-gray-600 dark:text-gray-400 hover:text-brand-600">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => <ChatBubble key={i} message={msg} />)
        )}
        {loading && (
          <div className="flex gap-3 items-start px-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-purple-500 flex items-center justify-center shrink-0">
              <Bot size={14} className="text-white" />
            </div>
            <div className="glass-card p-4 max-w-2xl">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 bg-brand-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-brand-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-brand-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="glass-card p-4 shrink-0">
        <form onSubmit={e => { e.preventDefault(); send(); }} className="flex gap-3">
          <input
            value={input} onChange={e => setInput(e.target.value)}
            placeholder="Ask about your database..."
            className="flex-1 px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-transparent focus:ring-2 focus:ring-brand-500 outline-none dark:text-white text-sm"
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}
            className="px-5 py-3 rounded-xl bg-gradient-to-r from-brand-500 to-purple-500 text-white font-medium hover:shadow-lg hover:shadow-brand-500/25 transition-all disabled:opacity-50 flex items-center gap-2">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </form>
      </div>
    </div>
  );
}

function ChatBubble({ message }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const copyText = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`flex gap-3 items-start px-2 animate-slide-up ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
        isUser ? 'bg-gray-200 dark:bg-gray-700' : 'bg-gradient-to-br from-brand-500 to-purple-500'
      }`}>
        {isUser ? <User size={14} className="text-gray-600 dark:text-gray-300" /> : <Bot size={14} className="text-white" />}
      </div>
      <div className={`group relative max-w-2xl ${isUser ? 'chat-bubble-user' : 'chat-bubble-bot'}`}>
        {isUser ? (
          <p className="text-sm">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
            <ReactMarkdown
              components={{
                code({ node, inline, className, children, ...props }) {
                  if (inline) return <code className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-xs font-mono" {...props}>{children}</code>;
                  return (
                    <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 overflow-x-auto text-xs my-2">
                      <code {...props}>{children}</code>
                    </pre>
                  );
                },
                table({ children }) { return <div className="overflow-x-auto my-2"><table className="data-table w-full text-xs">{children}</table></div>; },
              }}
            >{message.content}</ReactMarkdown>
          </div>
        )}
        {!isUser && (
          <button onClick={copyText}
            className="absolute -bottom-3 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg bg-white dark:bg-gray-800 shadow-md border border-gray-200 dark:border-gray-700">
            {copied ? <Check size={12} className="text-green-500" /> : <Copy size={12} className="text-gray-400" />}
          </button>
        )}
      </div>
    </div>
  );
}
