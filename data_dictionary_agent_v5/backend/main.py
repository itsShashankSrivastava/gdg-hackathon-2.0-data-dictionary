"""
Data Dictionary Agent – FastAPI Application.

Single entry point. All routes defined here (KISS).
Session management via in-memory store (swap for Redis in prod).
"""

from __future__ import annotations

import math
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import require_api_key
from .config import DatabaseConfig, SUPPORTED_DATABASES
from .database.connector import DatabaseConnector
from .database.extractor import SchemaExtractor, DatabaseMeta
from .analysis.quality import QualityAnalyzer
from .analysis.ai_summary import AISummaryGenerator
from .export.generator import DocumentationGenerator
from .exceptions import (
    DataDictionaryError,
    DatabaseConnectionError,
    DatabaseReadOnlyViolation,
    InvalidInputError,
)
from .logger import get_logger, set_trace_id
from .models import (
    ConnectRequest, ConnectResponse,
    ExtractSchemaRequest, SchemaResponse,
    AnalyzeQualityRequest, QualityResponse, QualityTableOut, QualityColumnOut,
    GenerateAISummaryRequest, AISummaryResponse,
    ChatRequest, ChatResponse,
    ExportRequest, ExportResponse,
    StatusResponse, TableOut, ColumnOut, ConstraintOut, IndexOut, RelationshipOut,
)

logger = get_logger("main")

# ---------------------------------------------------------------------------
# In-memory session store  (lightweight – KISS)
# ---------------------------------------------------------------------------

_sessions: Dict[str, Dict[str, Any]] = {}


def _get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found. Connect to a database first.")
    return _sessions[session_id]


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting")
    yield
    # Cleanup all sessions on shutdown
    for sid, s in list(_sessions.items()):
        conn = s.get("connector")
        if conn:
            conn.disconnect()
    _sessions.clear()
    logger.info("Application stopped, all sessions cleaned up")


app = FastAPI(
    title="Data Dictionary Agent API",
    description="Extract, analyze, and document database schemas with AI-powered insights. Read-only, secure, and scalable.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middleware – trace ID for every request
# ---------------------------------------------------------------------------

@app.middleware("http")
async def trace_id_middleware(request, call_next):
    tid = set_trace_id()
    response = await call_next(request)
    response.headers["X-Trace-Id"] = tid
    return response


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=StatusResponse, tags=["Health"])
async def health():
    return StatusResponse(status="ok", message="Service is running")


@app.get("/api/supported-databases", tags=["Info"])
async def supported_databases():
    return {"databases": SUPPORTED_DATABASES}


# ---------------------------------------------------------------------------
# Connect / Disconnect
# ---------------------------------------------------------------------------

@app.post("/api/connect", response_model=ConnectResponse, tags=["Connection"],
          dependencies=[Depends(require_api_key)])
async def connect(req: ConnectRequest):
    """Connect to a database (read-only). Returns a session_id."""
    trace = set_trace_id()
    try:
        config = DatabaseConfig(
            db_type=req.db_type,
            host=req.host,
            port=req.port,
            database=req.database,
            username=req.username,
            password=req.password,
            account=req.account,
            warehouse=req.warehouse,
            schema=req.schema_name,
            filepath=req.filepath,
        )
        connector = DatabaseConnector(config)
        connector.connect()

        # Extract schema
        extractor = SchemaExtractor(connector)
        db_meta = extractor.extract_all()

        session_id = uuid.uuid4().hex[:12]
        _sessions[session_id] = {
            "connector": connector,
            "config": config,
            "db_meta": db_meta,
            "quality": {},
            "ai_summaries": {},
            "db_summary": None,
            "ai_gen": AISummaryGenerator(),
        }

        logger.info("Session created", extra={"context": {"session": session_id, "tables": len(db_meta.tables)}})

        return ConnectResponse(
            status="connected",
            session_id=session_id,
            database_name=db_meta.database_name,
            database_type=db_meta.database_type,
            schemas=db_meta.schemas,
            table_count=len(db_meta.tables),
        )

    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Connect failed", exc_info=exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/connect-sample", response_model=ConnectResponse, tags=["Connection"],
          dependencies=[Depends(require_api_key)])
async def connect_sample():
    """Connect to a built-in sample SQLite database for demos."""
    db_path = _ensure_sample_db()
    req = ConnectRequest(db_type="sqlite", database=db_path, filepath=db_path)
    return await connect(req)


@app.post("/api/disconnect", response_model=StatusResponse, tags=["Connection"],
          dependencies=[Depends(require_api_key)])
async def disconnect(session_id: str):
    sess = _get_session(session_id)
    sess["connector"].disconnect()
    del _sessions[session_id]
    return StatusResponse(status="ok", message="Disconnected")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@app.get("/api/schema/{session_id}", response_model=SchemaResponse, tags=["Schema"],
         dependencies=[Depends(require_api_key)])
async def get_schema(session_id: str, page: int = 1, page_size: int = 50):
    """Return paginated schema info. Handles 10 000+ tables."""
    sess = _get_session(session_id)
    db: DatabaseMeta = sess["db_meta"]
    total = len(db.tables)
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    page_tables = db.tables[start : start + page_size]

    return SchemaResponse(
        database_name=db.database_name,
        database_type=db.database_type,
        schemas=db.schemas,
        tables=[_table_to_out(t) for t in page_tables],
        total_tables=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@app.get("/api/schema/{session_id}/table/{table_name}", tags=["Schema"],
         dependencies=[Depends(require_api_key)])
async def get_table_detail(session_id: str, table_name: str):
    sess = _get_session(session_id)
    db: DatabaseMeta = sess["db_meta"]
    table = next((t for t in db.tables if t.name == table_name or t.display_name == table_name), None)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return _table_to_out(table)


@app.get("/api/schema/{session_id}/overview", tags=["Schema"],
         dependencies=[Depends(require_api_key)])
async def get_overview(session_id: str):
    """Database overview with summary stats."""
    sess = _get_session(session_id)
    db: DatabaseMeta = sess["db_meta"]
    tables = [t for t in db.tables if t.table_type == "TABLE"]
    views = [t for t in db.tables if t.table_type == "VIEW"]
    return {
        "database_name": db.database_name,
        "database_type": db.database_type,
        "schemas": db.schemas,
        "total_tables": len(tables),
        "total_views": len(views),
        "total_columns": sum(len(t.columns) for t in db.tables),
        "total_rows": sum(t.row_count for t in db.tables if t.row_count > 0),
        "total_relationships": sum(len(t.relationships) for t in db.tables),
        "tables": [
            {
                "name": t.display_name,
                "type": t.table_type,
                "columns": len(t.columns),
                "rows": t.row_count,
                "pk": [c.name for c in t.columns if c.primary_key],
                "fk_count": sum(1 for c in t.columns if c.foreign_key),
                "indexes": len(t.indexes),
            }
            for t in db.tables
        ],
    }


# ---------------------------------------------------------------------------
# Quality Analysis
# ---------------------------------------------------------------------------

@app.post("/api/quality/analyze", response_model=QualityResponse, tags=["Quality"],
          dependencies=[Depends(require_api_key)])
async def analyze_quality(req: AnalyzeQualityRequest):
    sess = _get_session(req.session_id)
    analyzer = QualityAnalyzer(sess["connector"])
    db: DatabaseMeta = sess["db_meta"]

    if req.table_name:
        table = next((t for t in db.tables if t.name == req.table_name or t.display_name == req.table_name), None)
        if not table:
            raise HTTPException(404, f"Table '{req.table_name}' not found")
        q = analyzer.analyze_table(table)
        sess["quality"][table.display_name] = q
        result = {table.display_name: q}
    else:
        result = analyzer.analyze_all(db.tables)
        sess["quality"].update(result)

    tables_out = {}
    for k, v in result.items():
        tables_out[k] = QualityTableOut(
            table_name=v.table_name,
            schema_name=v.schema_name,
            row_count=v.row_count,
            column_count=v.column_count,
            overall_completeness=v.overall_completeness,
            primary_key_health=v.primary_key_health,
            duplicate_row_estimate=v.duplicate_row_estimate,
            data_freshness=v.data_freshness,
            latest_timestamp=v.latest_timestamp,
            freshness_column=v.freshness_column,
            quality_score=v.quality_score,
            issues=v.issues,
            recommendations=v.recommendations,
            columns=[QualityColumnOut(**c.to_dict()) for c in v.columns],
        )

    return QualityResponse(session_id=req.session_id, tables=tables_out)


# ---------------------------------------------------------------------------
# AI Summaries
# ---------------------------------------------------------------------------

@app.post("/api/ai/summary", response_model=AISummaryResponse, tags=["AI"],
          dependencies=[Depends(require_api_key)])
async def generate_ai_summary(req: GenerateAISummaryRequest):
    trace = set_trace_id()
    logger.info("AI summary generation started", extra={
        "context": {"session_id": req.session_id, "table_name": req.table_name}
    })
    sess = _get_session(req.session_id)
    db: DatabaseMeta = sess["db_meta"]
    ai: AISummaryGenerator = sess["ai_gen"]
    connector: DatabaseConnector = sess["connector"]

    table_summaries: Dict[str, Dict[str, Any]] = {}

    if req.table_name:
        table = next((t for t in db.tables if t.name == req.table_name or t.display_name == req.table_name), None)
        if not table:
            raise HTTPException(404, f"Table '{req.table_name}' not found")
        tables_to_process = [table]
    else:
        tables_to_process = [t for t in db.tables if t.table_type == "TABLE"]

    logger.info("Processing tables for AI summary", extra={
        "context": {"total_tables": len(tables_to_process)}
    })

    for table in tables_to_process:
        key = table.display_name
        logger.info("Generating AI summary for table", extra={"context": {"table": key}})
        q = sess["quality"].get(key)
        summary = ai.generate_table_summary(table, q)
        
        # Defensive: ensure summary is a dict with array fields
        if not isinstance(summary, dict):
            logger.warning("Table summary returned non-dict type", extra={"context": {"type": type(summary).__name__}})
            summary = {"business_description": "", "key_insights": [], "usage_recommendations": [], "potential_issues": []}
        
        # Ensure array fields are actually arrays
        if not isinstance(summary.get("key_insights"), list):
            summary["key_insights"] = []
        if not isinstance(summary.get("usage_recommendations"), list):
            summary["usage_recommendations"] = []
        if not isinstance(summary.get("potential_issues"), list):
            summary["potential_issues"] = []
        if not isinstance(summary.get("business_description"), str):
            summary["business_description"] = ""
        
        bctx = ai.generate_table_business_context(table, q)
        
        # Defensive: ensure bctx is a dict
        if isinstance(bctx, dict):
            summary["business_summary"] = bctx.get("business_summary", "")
            summary["analyst_recommendation"] = bctx.get("analyst_recommendation", "")
        else:
            logger.warning("Business context returned non-dict type", extra={"context": {"type": type(bctx).__name__}})
            summary["business_summary"] = ""
            summary["analyst_recommendation"] = ""

        # Column descriptions
        sample = connector.get_sample_data(table.name, table.schema, limit=5)
        sample_dict = {c: sample[c].tolist() for c in sample.columns} if not sample.empty else {}
        col_descs = ai.generate_column_descriptions(table, sample_dict)
        
        # Defensive: ensure col_descs is a dict
        if isinstance(col_descs, dict):
            summary["column_descriptions"] = col_descs
        else:
            logger.warning("Column descriptions returned non-dict type", extra={"context": {"type": type(col_descs).__name__}})
            summary["column_descriptions"] = {}

        table_summaries[key] = summary
        sess["ai_summaries"][key] = summary

    # Database summary
    db_summary = None
    if not req.table_name:
        db_summary = ai.generate_database_summary(db)
        # Defensive: ensure db_summary is a dict with array fields
        if not isinstance(db_summary, dict):
            logger.warning("Database summary returned non-dict type", extra={"context": {"type": type(db_summary).__name__}})
            db_summary = {"database_purpose": "Unknown", "domain_analysis": "Unknown", 
                         "architecture_observations": [], "data_model_type": "Unknown",
                         "key_entity_groups": [], "recommendations": []}
        
        # Ensure array fields are actually arrays
        if not isinstance(db_summary.get("architecture_observations"), list):
            db_summary["architecture_observations"] = []
        if not isinstance(db_summary.get("key_entity_groups"), list):
            db_summary["key_entity_groups"] = []
        if not isinstance(db_summary.get("recommendations"), list):
            db_summary["recommendations"] = []
        
        sess["db_summary"] = db_summary

    logger.info("AI summary generation completed", extra={
        "context": {"session_id": req.session_id, "tables_processed": len(table_summaries)}
    })
    
    return AISummaryResponse(
        session_id=req.session_id,
        database_summary=db_summary,
        table_summaries=table_summaries,
    )


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"],
          dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    sess = _get_session(req.session_id)
    ai: AISummaryGenerator = sess["ai_gen"]
    db: DatabaseMeta = sess["db_meta"]
    answer = ai.chat(req.question, db, sess.get("quality"), req.conversation_history)
    return ChatResponse(answer=answer)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@app.post("/api/export", response_model=ExportResponse, tags=["Export"],
          dependencies=[Depends(require_api_key)])
async def export_docs(req: ExportRequest):
    sess = _get_session(req.session_id)
    db: DatabaseMeta = sess["db_meta"]
    gen = DocumentationGenerator()

    fmt = req.format.lower()
    try:
        if fmt == "json":
            content = gen.generate_json(db, sess.get("quality"), sess.get("ai_summaries"))
        elif fmt == "markdown":
            content = gen.generate_markdown(db, sess.get("quality"), sess.get("ai_summaries"), sess.get("db_summary"))
        elif fmt == "html":
            content = gen.generate_html(db, sess.get("quality"), sess.get("ai_summaries"))
        elif fmt == "pdf":
            content = gen.generate_pdf(db, sess.get("quality"), sess.get("ai_summaries"), sess.get("db_summary"))
        else:
            raise HTTPException(400, f"Unsupported format: {fmt}. Use json, markdown, html, or pdf.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export generation error ({fmt}): {e}")
        raise HTTPException(500, f"Failed to generate {fmt}: {str(e)}")

    ext = {"json": "json", "markdown": "md", "html": "html", "pdf": "pdf"}.get(fmt, fmt)
    return ExportResponse(
        format=fmt,
        content=content,
        filename=f"{db.database_name}_data_dictionary.{ext}",
    )


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

@app.get("/api/sample-data/{session_id}/{table_name}", tags=["Data"],
         dependencies=[Depends(require_api_key)])
async def get_sample_data(session_id: str, table_name: str, limit: int = 100):
    sess = _get_session(session_id)
    connector: DatabaseConnector = sess["connector"]
    db: DatabaseMeta = sess["db_meta"]
    table = next((t for t in db.tables if t.name == table_name or t.display_name == table_name), None)
    if not table:
        raise HTTPException(404, f"Table '{table_name}' not found")
    df = connector.get_sample_data(table.name, table.schema, limit=min(limit, 500))
    return {"columns": list(df.columns), "rows": df.head(500).to_dict(orient="records")}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _table_to_out(t) -> TableOut:
    return TableOut(
        name=t.name,
        schema=t.schema,
        table_type=t.table_type,
        columns=[ColumnOut(
            name=c.name, data_type=c.data_type, nullable=c.nullable,
            default=c.default, primary_key=c.primary_key,
            foreign_key=c.foreign_key, unique=c.unique,
            comment=c.comment, description=c.description,
        ) for c in t.columns],
        constraints=[ConstraintOut(
            name=c.name, constraint_type=c.constraint_type,
            columns=c.columns, referenced_table=c.referenced_table,
            referenced_columns=c.referenced_columns,
        ) for c in t.constraints],
        indexes=[IndexOut(name=i.name, columns=i.columns, unique=i.unique) for i in t.indexes],
        row_count=t.row_count,
        comment=t.comment,
        relationships=[RelationshipOut(**r) for r in t.relationships],
    )


def _ensure_sample_db() -> str:
    """Create a sample SQLite DB for demos."""
    path = "sample_database.db"
    if os.path.exists(path):
        return path

    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL, last_name TEXT NOT NULL,
        email TEXT UNIQUE, phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'active')""")
    c.execute("""CREATE TABLE products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, description TEXT,
        price DECIMAL(10,2) NOT NULL, category TEXT,
        stock_quantity INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL, order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_amount DECIMAL(10,2), status TEXT DEFAULT 'pending',
        shipping_address TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id))""")
    c.execute("""CREATE TABLE order_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL, unit_price DECIMAL(10,2) NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id))""")
    c.execute("""CREATE VIEW customer_order_summary AS
        SELECT c.customer_id, c.first_name||' '||c.last_name AS customer_name,
               COUNT(o.order_id) AS total_orders, SUM(o.total_amount) AS total_spent
        FROM customers c LEFT JOIN orders o ON c.customer_id=o.customer_id
        GROUP BY c.customer_id""")

    customers = [('John','Doe','john@email.com','555-0101'),('Jane','Smith','jane@email.com','555-0102'),
                 ('Bob','Johnson','bob@email.com',None),('Alice','Williams','alice@email.com','555-0104'),
                 ('Charlie','Brown',None,'555-0105')]
    c.executemany("INSERT INTO customers (first_name,last_name,email,phone) VALUES (?,?,?,?)", customers)
    products = [('Laptop','High-performance laptop',999.99,'Electronics',50),
                ('Mouse','Wireless mouse',29.99,'Electronics',200),
                ('Keyboard','Mechanical keyboard',79.99,'Electronics',150),
                ('Monitor','27\" 4K monitor',399.99,'Electronics',30),
                ('Headphones','Noise-canceling',199.99,'Electronics',75)]
    c.executemany("INSERT INTO products (name,description,price,category,stock_quantity) VALUES (?,?,?,?,?)", products)
    orders = [(1,1029.98,'completed','123 Main St'),(1,79.99,'shipped','123 Main St'),
              (2,599.98,'completed','456 Oak Ave'),(3,29.99,'pending','789 Pine Rd'),
              (4,1399.97,'processing','321 Elm St')]
    c.executemany("INSERT INTO orders (customer_id,total_amount,status,shipping_address) VALUES (?,?,?,?)", orders)
    items = [(1,1,1,999.99),(1,2,1,29.99),(2,3,1,79.99),(3,4,1,399.99),
             (3,5,1,199.99),(4,2,1,29.99),(5,1,1,999.99),(5,4,1,399.99)]
    c.executemany("INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES (?,?,?,?)", items)
    conn.commit()
    conn.close()
    return path
