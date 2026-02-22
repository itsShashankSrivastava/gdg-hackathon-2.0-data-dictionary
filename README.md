<div align="center">

# 📚 Data Dictionary Agent v4

### AI-Powered Database Documentation & Analysis Platform

*Connect to any database, extract its schema, analyze data quality, chat with AI,
and export professional documentation — all from a beautiful web interface.*

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Groq](https://img.shields.io/badge/Groq_AI-Powered-00D4AA?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

</div>

---

## 🎯 What This Does

Data Dictionary Agent automatically **documents databases** that nobody has time to
document manually. Point it at any supported database and it will:

1. **Extract** every table, column, key, index, and relationship
2. **Analyze** data quality — nulls, duplicates, freshness, uniqueness
3. **Summarize** using AI — business-friendly descriptions for every table and column
4. **Let you chat** — ask plain-English questions about your schema
5. **Export** a polished data dictionary document in JSON, Markdown, or HTML

It was built for teams who inherit databases with zero documentation, and for
data engineers who need to onboard new teammates fast.

---

## 🖼️ Screenshots

| Dashboard | Table Explorer | Data Quality |
|-----------|----------------|--------------|
| Stats overview, AI database summary | Column details, relationships, sample data | Per-table scores, column-level metrics |

| Chat Assistant | Export |
|---------------|--------|
| Ask questions in plain English | Download JSON / Markdown / HTML |

---

## 🏗️ Architecture

```
┌─────────────── React Frontend (Port 3000) ──────────────────┐
│  Dashboard  │  Tables  │  Quality  │  Chat  │  Export       │
└──────────────────────────┬──────────────────────────────────┘
                           │ Axios + API Key
┌──────────────────────────▼──────────────────────────────────┐
│              FastAPI Backend (Port 8000)                      │
│                                                              │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │ Auth    │  │ Trace-ID     │  │ Structured JSON      │    │
│  │ (API Key│  │ Middleware   │  │ Logging              │    │
│  └────┬────┘  └──────┬───────┘  └──────────────────────┘    │
│       │              │                                       │
│  ┌────▼──────────────▼───────────────────────────────────┐  │
│  │                   Session Store                        │  │
│  │    DatabaseConnector · SchemaExtractor                  │  │
│  │    QualityAnalyzer · AISummaryGenerator                 │  │
│  │    DocumentationGenerator                              │  │
│  └────────────────────────────────────────────────────────┘  │
│       │                                                      │
│  ┌────▼──────────┐  ┌──────────────┐  ┌────────────┐       │
│  │ SQLAlchemy    │  │ Groq API     │  │ File I/O   │       │
│  │ + Pool (R/O)  │  │ (LLM)        │  │ (exports)  │       │
│  └───────────────┘  └──────────────┘  └────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Principle | Implementation |
|-----------|---------------|
| **Read-only access** | `before_cursor_execute` event blocks INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE / CREATE |
| **Connection pooling** | SQLAlchemy `QueuePool` with configurable size, overflow, timeout, recycle |
| **Scalable to 10 000+ tables** | Batched extraction (`TABLE_BATCH_SIZE`), paginated API, lazy loading |
| **Structured logging** | JSON lines with `trace_id`, `timestamp`, `severity`, `component`, `context` |
| **Custom exceptions** | Typed hierarchy — `DatabaseConnectionError`, `AIRateLimitError`, etc. |
| **DRY / Open-Closed** | Shared helpers, one-place configs, extension via new analyzers or exporters |
| **Security** | API key auth (`X-API-Key` header), CORS whitelist, env-only secrets |

---

## ⚙️ Requirements

- **Python 3.10+**
- **Node.js 18+** & npm
- A **Groq API key** (free tier works) — [https://console.groq.com](https://console.groq.com)

---

## 🚀 Quick Start

### 1. Clone & enter the project

```bash
cd data_dictionary_agent_v4
```

### 2. Create a Python virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

Edit `.env` and set at minimum:

```
GROQ_API_KEY=gsk_your_key_here
DD_API_KEY=any-secret-string
```

### 5. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 6. Start both servers

**Option A — one command (Windows):**

```bash
start.bat
```

**Option B — two terminals:**

```bash
# Terminal 1 – Backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 – Frontend
cd frontend && npm run dev
```

### 7. Open your browser

Go to **http://localhost:3000** and click **Connect** in the sidebar.

> 💡 **No database handy?** Click **"Try with Sample Database"** in the
> connection dialog — the backend will create a demo SQLite DB automatically.

---

## 📡 API Reference

All endpoints require the `X-API-Key` header (value = your `DD_API_KEY`).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/supported-databases` | List supported DB types |
| `POST` | `/api/connect` | Connect to a database |
| `POST` | `/api/connect-sample` | Connect to built-in sample DB |
| `POST` | `/api/disconnect` | Close connection & pool |
| `GET` | `/api/schema/{sid}?page=1&per_page=100` | Paginated table list |
| `GET` | `/api/schema/{sid}/table/{name}` | Full table detail |
| `GET` | `/api/schema/{sid}/overview` | DB stats summary |
| `POST` | `/api/quality/analyze` | Analyze table quality |
| `POST` | `/api/ai/summary` | Generate AI summary |
| `POST` | `/api/chat` | Chat with AI about the DB |
| `POST` | `/api/export` | Export documentation |
| `GET` | `/api/sample-data/{sid}/{table}` | Sample rows |

Interactive Swagger docs at **http://localhost:8000/docs**.

---

## 🗂️ Project Structure

```
data_dictionary_agent_v4/
├── backend/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application & routes
│   ├── config.py                # Environment-based settings
│   ├── logger.py                # Structured JSON logging
│   ├── exceptions.py            # Custom typed exception hierarchy
│   ├── models.py                # Pydantic request / response models
│   ├── auth.py                  # API key authentication dependency
│   ├── database/
│   │   ├── connector.py         # Connection pool, read-only enforcement
│   │   └── extractor.py         # Schema extraction with batching
│   ├── analysis/
│   │   ├── quality.py           # Data quality analyzer
│   │   └── ai_summary.py       # Groq AI summary generator
│   └── export/
│       └── generator.py         # JSON / Markdown / HTML exporter
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx              # Root component + context
│       ├── index.css            # Tailwind + custom styles
│       ├── api/
│       │   └── client.js        # Axios API client
│       ├── components/
│       │   ├── Layout.jsx       # Sidebar, nav, dark mode
│       │   └── ConnectionModal.jsx
│       └── pages/
│           ├── Dashboard.jsx    # Overview & stats
│           ├── TablesPage.jsx   # Table browser + detail
│           ├── QualityPage.jsx  # Quality dashboard
│           ├── ChatPage.jsx     # AI chat interface
│           └── ExportPage.jsx   # Documentation export
├── .env.example
├── requirements.txt
├── start.bat
└── README.md
```

---

## 🔒 Security

- **No hard-coded secrets** — all API keys read from environment variables
- **Read-only DB access** — write SQL statements are blocked at the engine level
- **API key authentication** — every request must include `X-API-Key`
- **CORS whitelist** — configurable allowed origins
- **Connection pooling** — prevents connection exhaustion attacks


---

## 🗄️ Supported Databases

| Database | Driver | Connection String |
|----------|--------|-------------------|
| PostgreSQL | `psycopg2` | `postgresql://user:pass@host:5432/db` |
| MySQL | `pymysql` | `mysql+pymysql://user:pass@host:3306/db` |
| SQLite | built-in | `sqlite:///path/to/file.db` |
| SQL Server | `pyodbc` | `mssql+pyodbc://user:pass@host/db?driver=...` |
| Oracle | `cx_Oracle` | `oracle+cx_oracle://user:pass@host:1521/sid` |

---

## 🧪 Try the Sample Database

Click **"Try with Sample Database"** in the connection dialog. The backend
will create an in-memory SQLite database with realistic e-commerce tables:

- `customers`, `products`, `categories`
- `orders`, `order_items`
- `reviews`, `inventory`

This is great for demos and for testing all features without needing a real
database.

---

## 📝 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Groq API key (required for AI features) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | LLM model name |
| `DD_API_KEY` | `dev-key` | API authentication key |
| `DB_POOL_SIZE` | `5` | SQLAlchemy pool size |
| `DB_MAX_OVERFLOW` | `10` | Extra connections above pool size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for a connection |
| `DB_POOL_RECYCLE` | `1800` | Recycle connections after N seconds |
| `TABLE_BATCH_SIZE` | `200` | Tables per extraction batch |
| `SAMPLE_ROW_LIMIT` | `10000` | Max rows for column stats |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m "Add my feature"`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <strong>Built with ❤️ for the GDG Hackfest 2.0</strong>
</div>
