"""
Documentation generator – JSON, Markdown, HTML, PDF.
Single class, multiple methods, no duplication.
"""

from __future__ import annotations

import base64
import io
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..database.extractor import DatabaseMeta, TableMeta
from ..analysis.quality import TableQuality
from ..logger import get_logger

logger = get_logger("export.generator")


class DocumentationGenerator:
    """Generates data-dictionary documents in multiple formats."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    @staticmethod
    def _display(table: TableMeta) -> str:
        return table.display_name

    # ── JSON ──────────────────────────────────────────────────────────

    def generate_json(self, db: DatabaseMeta,
                      quality: Optional[Dict[str, TableQuality]] = None,
                      ai: Optional[Dict[str, Dict]] = None) -> str:
        doc: Dict[str, Any] = {
            "metadata": {"generated_at": datetime.now().isoformat(), "generator": "Data Dictionary Agent", "version": "2.0.0"},
            "database": db.to_dict(),
        }
        if quality:
            doc["quality_analysis"] = {k: v.to_dict() for k, v in quality.items()}
        if ai:
            doc["ai_summaries"] = ai
        content = json.dumps(doc, indent=2, default=str)
        path = os.path.join(self.output_dir, f"{db.database_name}_data_dictionary.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return content

    # ── Markdown ──────────────────────────────────────────────────────

    def generate_markdown(self, db: DatabaseMeta,
                          quality: Optional[Dict[str, TableQuality]] = None,
                          ai: Optional[Dict[str, Dict]] = None,
                          db_summary: Optional[Dict[str, Any]] = None) -> str:
        L: List[str] = []
        L.append(f"# Data Dictionary: {db.database_name}\n")
        L.append(f"**Type:** {db.database_type}  ")
        L.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        s = db.summary
        L.append("## Overview\n")
        L.append("| Metric | Value |\n|---|---:|")
        L.append(f"| Tables | {s['total_tables']} |")
        L.append(f"| Views | {s['total_views']} |")
        L.append(f"| Columns | {s['total_columns']} |")
        L.append(f"| Relationships | {s['total_relationships']} |\n")

        if db_summary:
            L.append("## AI Analysis\n")
            for key in ("database_purpose", "domain_analysis", "data_model_type"):
                if db_summary.get(key):
                    L.append(f"**{key.replace('_', ' ').title()}:** {db_summary[key]}\n")

        L.append("## Tables\n")
        for t in db.tables:
            L.extend(self._md_table(t, quality, ai))

        content = "\n".join(L)
        path = os.path.join(self.output_dir, f"{db.database_name}_data_dictionary.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return content

    def _md_table(self, t: TableMeta, quality: Optional[Dict[str, TableQuality]],
                  ai: Optional[Dict[str, Dict]]) -> List[str]:
        key = self._display(t)
        L = [f"### {'📊' if t.table_type == 'TABLE' else '👁️'} {key}\n"]

        # Business context
        if ai and key in ai:
            bs = ai[key].get("business_summary") or ai[key].get("business_description", "")
            if bs:
                L.append(f"> {bs}\n")

        L.append(f"**Type:** {t.table_type} | **Rows:** {t.row_count:,}\n")

        ai_desc = (ai or {}).get(key, {}).get("column_descriptions", {})
        L.append("| Column | Type | Null | Key | Description |")
        L.append("|---|---|---|---|---|")
        for c in t.columns:
            keys = []
            if c.primary_key:
                keys.append("🔑PK")
            if c.foreign_key:
                keys.append(f"🔗FK→{c.foreign_key.get('referred_table')}")
            desc = ai_desc.get(c.name) or c.description or c.comment or "-"
            L.append(f"| `{c.name}` | {c.data_type} | {'✓' if c.nullable else '✗'} | {' '.join(keys) or '-'} | {desc} |")
        L.append("")

        if quality and key in quality:
            q = quality[key]
            L.append(f"**Quality Score:** {q.quality_score}/100 | **Completeness:** {q.overall_completeness:.0%}\n")

        L.append("---\n")
        return L

    # ── HTML ──────────────────────────────────────────────────────────

    def generate_html(self, db: DatabaseMeta,
                      quality: Optional[Dict[str, TableQuality]] = None,
                      ai: Optional[Dict[str, Dict]] = None) -> str:
        tables_html = ""
        toc_items = ""
        for t in db.tables:
            key = self._display(t)
            toc_items += f'<li><a href="#{t.name}">📊 {key}</a></li>'
            
            ai_data = (ai or {}).get(key, {})
            ai_desc = ai_data.get("column_descriptions", {})
            
            # Business Context block
            business_ctx_html = ""
            business_summary = ai_data.get("business_summary") or ai_data.get("business_description", "")
            analyst_rec = ai_data.get("analyst_recommendation", "")
            if business_summary or analyst_rec:
                business_ctx_html = f'''
                <div style="background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; margin: 15px 0; border-radius: 4px;">
                    <h4 style="margin-top: 0; color: #2e7d32;">💼 Business Context</h4>
                    <p style="margin-bottom: 10px;">{business_summary}</p>
                    {"<p><strong>📋 Analyst Recommendation:</strong> " + analyst_rec + "</p>" if analyst_rec else ""}
                </div>
                '''
            
            rows = ""
            for c in t.columns:
                k = []
                if c.primary_key:
                    k.append('<span class="pk">🔑 PK</span>')
                if c.foreign_key:
                    k.append(f'<span class="fk">🔗 FK→{c.foreign_key.get("referred_table")}</span>')
                desc = ai_desc.get(c.name) or c.description or c.comment or "-"
                rows += f"<tr><td><code>{c.name}</code></td><td>{c.data_type}</td><td>{'✓' if c.nullable else '✗'}</td><td>{' '.join(k) or '-'}</td><td>{desc}</td></tr>\n"

            q_html = ""
            if quality and key in quality:
                q = quality[key]
                colour = "#27ae60" if q.quality_score >= 75 else "#e67e22" if q.quality_score >= 50 else "#e74c3c"
                q_html = f'<p><b>Quality:</b> <span style="color:{colour}">{q.quality_score}/100</span> | Completeness: {q.overall_completeness:.0%}</p>'

            tables_html += f"""
            <h2 id="{t.name}">{'📊' if t.table_type == 'TABLE' else '👁️'} {key}</h2>
            {business_ctx_html}
            <p><b>Type:</b> {t.table_type} | <b>Rows:</b> {t.row_count:,}</p>
            {q_html}
            <h3>Columns</h3>
            <table><tr><th>Column</th><th>Type</th><th>Nullable</th><th>Keys</th><th>Description</th></tr>{rows}</table>
            <hr>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data Dictionary: {db.database_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; line-height: 1.6; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 40px; }}
        h3 {{ color: #2980b9; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #3498db; color: white; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        tr:hover {{ background-color: #f1f1f1; }}
        code {{ background: #e8e8e8; padding: 2px 6px; border-radius: 3px; font-family: 'Consolas', monospace; }}
        .pk {{ color: #e74c3c; font-weight: bold; }}
        .fk {{ color: #9b59b6; }}
        blockquote {{ background: #ecf0f1; border-left: 4px solid #3498db; padding: 15px; margin: 20px 0; }}
        .quality-good {{ color: #27ae60; }}
        .quality-bad {{ color: #e74c3c; }}
        .toc {{ background: #ecf0f1; padding: 20px; border-radius: 5px; }}
        .toc a {{ color: #2980b9; text-decoration: none; }}
        .toc a:hover {{ text-decoration: underline; }}
        hr {{ border: none; border-top: 1px solid #ddd; margin: 30px 0; }}
    </style>
</head>
<body>
<div class="container">
    <h1>📚 Data Dictionary: {db.database_name}</h1>
    <p><strong>Database Type:</strong> {db.database_type}</p>
    <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>Overview</h2>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Total Tables</td><td>{db.summary['total_tables']}</td></tr>
        <tr><td>Total Views</td><td>{db.summary['total_views']}</td></tr>
        <tr><td>Total Columns</td><td>{db.summary['total_columns']}</td></tr>
    </table>
    
    <div class="toc">
        <h2>📋 Table of Contents</h2>
        <ul>
            {toc_items}
        </ul>
    </div>
    
    <hr>
    
    {tables_html}
    
</div>
</body>
</html>"""

        content = html
        path = os.path.join(self.output_dir, f"{db.database_name}_data_dictionary.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return content

    # ── PDF ───────────────────────────────────────────────────────────

    def generate_pdf(self, db: DatabaseMeta,
                     quality: Optional[Dict[str, TableQuality]] = None,
                     ai: Optional[Dict[str, Dict]] = None,
                     db_summary: Optional[Dict[str, Any]] = None) -> str:
        """Generate a professional PDF document. Returns base64-encoded PDF."""
        try:
            from xhtml2pdf import pisa
        except ImportError:
            logger.warning("xhtml2pdf not installed, falling back to HTML")
            return self.generate_html(db, quality, ai)

        # Build executive summary section
        exec_summary = ""
        if db_summary:
            purpose = db_summary.get("database_purpose", "")
            domain = db_summary.get("domain_analysis", "")
            model_type = db_summary.get("data_model_type", "")
            if purpose or domain:
                exec_summary = f"""
                <div class="exec-summary">
                    <h2>Executive Summary</h2>
                    {f'<p><strong>Purpose:</strong> {purpose}</p>' if purpose else ''}
                    {f'<p><strong>Domain:</strong> {domain}</p>' if domain else ''}
                    {f'<p><strong>Data Model:</strong> {model_type}</p>' if model_type else ''}
                </div>
                """

        # Build tables content
        tables_html = ""
        for idx, t in enumerate(db.tables):
            key = self._display(t)
            ai_data = (ai or {}).get(key, {})
            ai_desc = ai_data.get("column_descriptions", {})
            
            # Business context
            business_html = ""
            bs = ai_data.get("business_summary") or ai_data.get("business_description", "")
            ar = ai_data.get("analyst_recommendation", "")
            if bs or ar:
                business_html = f"""
                <div class="business-context">
                    <h4>Business Context</h4>
                    {f'<p>{bs}</p>' if bs else ''}
                    {f'<p><em>Recommendation: {ar}</em></p>' if ar else ''}
                </div>
                """
            
            # Quality info
            quality_html = ""
            if quality and key in quality:
                q = quality[key]
                score_class = "good" if q.quality_score >= 75 else "warning" if q.quality_score >= 50 else "poor"
                quality_html = f"""
                <div class="quality-badge {score_class}">
                    Quality Score: {q.quality_score}/100 | Completeness: {q.overall_completeness:.0%}
                </div>
                """
            
            # Column rows
            col_rows = ""
            for c in t.columns:
                keys = []
                if c.primary_key:
                    keys.append("PK")
                if c.foreign_key:
                    keys.append(f"FK->{c.foreign_key.get('referred_table', '?')}")
                desc = ai_desc.get(c.name) or c.description or c.comment or "-"
                col_rows += f"""
                <tr>
                    <td class="col-name">{c.name}</td>
                    <td class="col-type">{c.data_type}</td>
                    <td class="col-null">{'Yes' if c.nullable else 'No'}</td>
                    <td class="col-key">{', '.join(keys) if keys else '-'}</td>
                    <td class="col-desc">{desc}</td>
                </tr>
                """
            
            # Page break every 3 tables (except first)
            page_break = 'style="page-break-before: always;"' if idx > 0 and idx % 3 == 0 else ''
            
            tables_html += f"""
            <div class="table-section" {page_break}>
                <h3>{t.table_type}: {key}</h3>
                <p class="table-meta">Rows: {t.row_count:,} | Columns: {len(t.columns)}</p>
                {business_html}
                {quality_html}
                <table class="columns-table">
                    <thead>
                        <tr>
                            <th>Column Name</th>
                            <th>Data Type</th>
                            <th>Nullable</th>
                            <th>Keys</th>
                            <th>Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        {col_rows}
                    </tbody>
                </table>
            </div>
            """

        # Full HTML for PDF (no emojis - xhtml2pdf doesn't support them)
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        
        body {{
            font-family: Helvetica, Arial, sans-serif;
            font-size: 11px;
            line-height: 1.5;
            color: #333;
        }}
        
        .cover {{
            text-align: center;
            padding: 100px 0;
            page-break-after: always;
        }}
        
        .cover h1 {{
            font-size: 32px;
            color: #2c3e50;
            margin-bottom: 20px;
        }}
        
        .cover .subtitle {{
            font-size: 18px;
            color: #7f8c8d;
            margin-bottom: 40px;
        }}
        
        .cover .meta {{
            font-size: 12px;
            color: #95a5a6;
        }}
        
        .cover .logo {{
            font-size: 48px;
            margin-bottom: 30px;
            color: #3498db;
        }}
        
        h2 {{
            font-size: 18px;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
            margin-top: 30px;
        }}
        
        h3 {{
            font-size: 14px;
            color: #34495e;
            margin-top: 25px;
            margin-bottom: 10px;
            background: #ecf0f1;
            padding: 8px 12px;
            border-left: 4px solid #3498db;
        }}
        
        h4 {{
            font-size: 12px;
            color: #2980b9;
            margin: 10px 0 5px 0;
        }}
        
        .exec-summary {{
            background: #f8f9fa;
            padding: 15px;
            margin: 20px 0;
            border-left: 4px solid #27ae60;
        }}
        
        .overview-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        
        .overview-table th, .overview-table td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }}
        
        .overview-table th {{
            background: #3498db;
            color: white;
            font-weight: bold;
        }}
        
        .table-section {{
            margin: 20px 0;
        }}
        
        .table-meta {{
            font-size: 10px;
            color: #7f8c8d;
            margin: 5px 0 10px 0;
        }}
        
        .business-context {{
            background: #e8f5e9;
            padding: 10px;
            margin: 10px 0;
            border-left: 3px solid #4caf50;
        }}
        
        .business-context h4 {{
            color: #2e7d32;
            margin: 0 0 5px 0;
        }}
        
        .business-context p {{
            margin: 5px 0;
            font-size: 10px;
        }}
        
        .quality-badge {{
            padding: 5px 10px;
            font-size: 10px;
            font-weight: bold;
            margin: 5px 0;
        }}
        
        .quality-badge.good {{
            background: #d4edda;
            color: #155724;
        }}
        
        .quality-badge.warning {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .quality-badge.poor {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .columns-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 9px;
        }}
        
        .columns-table th {{
            background: #34495e;
            color: white;
            padding: 8px 5px;
            text-align: left;
            font-weight: bold;
        }}
        
        .columns-table td {{
            border: 1px solid #ddd;
            padding: 6px 5px;
            vertical-align: top;
        }}
        
        .col-name {{
            font-weight: bold;
            color: #2c3e50;
        }}
        
        .col-type {{
            color: #8e44ad;
            font-size: 8px;
        }}
        
        .col-null {{
            text-align: center;
        }}
        
        .col-key {{
            font-size: 8px;
            color: #e74c3c;
            font-weight: bold;
        }}
        
        .col-desc {{
            color: #555;
        }}
        
        .toc {{
            page-break-after: always;
        }}
        
        .toc ul {{
            list-style: none;
            padding: 0;
        }}
        
        .toc li {{
            padding: 5px 0;
            border-bottom: 1px dotted #ddd;
        }}
        
        .footer {{
            margin-top: 50px;
            text-align: center;
            font-size: 9px;
            color: #95a5a6;
        }}
    </style>
</head>
<body>
    <div class="cover">
        <div class="logo">[DATA DICTIONARY]</div>
        <h1>Data Dictionary</h1>
        <div class="subtitle">{db.database_name}</div>
        <p class="meta">
            Database Type: {db.database_type}<br/>
            Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}<br/>
            Tables: {db.summary['total_tables']} | Views: {db.summary['total_views']} | Columns: {db.summary['total_columns']}
        </p>
    </div>
    
    <div class="toc">
        <h2>Database Overview</h2>
        <table class="overview-table">
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Database Name</td><td>{db.database_name}</td></tr>
            <tr><td>Database Type</td><td>{db.database_type}</td></tr>
            <tr><td>Total Tables</td><td>{db.summary['total_tables']}</td></tr>
            <tr><td>Total Views</td><td>{db.summary['total_views']}</td></tr>
            <tr><td>Total Columns</td><td>{db.summary['total_columns']}</td></tr>
            <tr><td>Total Relationships</td><td>{db.summary['total_relationships']}</td></tr>
        </table>
        
        {exec_summary}
        
        <h2>Table of Contents</h2>
        <ul>
            {''.join(f'<li>{t.table_type}: {self._display(t)} ({len(t.columns)} columns)</li>' for t in db.tables)}
        </ul>
    </div>
    
    <h2>Table Definitions</h2>
    {tables_html}
    
    <div class="footer">
        Generated by Data Dictionary Agent | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>"""

        # Convert HTML to PDF
        pdf_buffer = io.BytesIO()
        try:
            pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer, encoding='utf-8')
        except Exception as e:
            logger.error(f"PDF generation exception: {e}")
            raise Exception(f"Failed to generate PDF: {e}")
        
        if pisa_status.err:
            logger.error(f"PDF generation returned {pisa_status.err} errors")
            raise Exception(f"PDF generation had {pisa_status.err} errors")
        
        # Get PDF bytes and encode as base64
        pdf_bytes = pdf_buffer.getvalue()
        
        if not pdf_bytes or len(pdf_bytes) < 100:
            logger.error("PDF generation produced empty or invalid output")
            raise Exception("PDF generation produced empty output")
        
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # Also save to file
        path = os.path.join(self.output_dir, f"{db.database_name}_data_dictionary.pdf")
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        
        logger.info(f"PDF generated successfully: {path} ({len(pdf_bytes)} bytes)")
        return pdf_base64
