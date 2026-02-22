"""
AI-powered summary generator using AWS Bedrock (boto3 converse).
DRY: one retry helper, one JSON-parse helper, reused everywhere.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from ..config import BEDROCK_MODEL_ID, BEDROCK_REGION
from ..database.extractor import DatabaseMeta, TableMeta
from ..analysis.quality import TableQuality
from ..exceptions import AIServiceError, AIRateLimitError, AITimeoutError
from ..logger import get_logger

logger = get_logger("analysis.ai_summary")


class AISummaryGenerator:
    """Generates business-friendly summaries via AWS Bedrock LLM calls."""

    def __init__(self, model_id: str = "", region: str = ""):
        self.model_id = model_id or BEDROCK_MODEL_ID
        self.region = region or BEDROCK_REGION
        
        # Initialize Bedrock Runtime client
        try:
            self.client = boto3.client(
                "bedrock-runtime",
                region_name=self.region
            )
        except Exception as exc:
            raise AIServiceError(
                f"Failed to initialize AWS Bedrock client: {exc}. "
                "Please check your AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)."
            )

    # ── LLM call with retry (DRY) ────────────────────────────────────

    def _call(self, messages: List[Dict[str, str]], temperature: float = 0.3,
              max_tokens: int = 1000, retries: int = 3) -> str:
        last_err = None
        
        # Convert messages to Bedrock converse format
        converse_messages = []
        system_prompt = None
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_prompt = content
            elif role == "assistant":
                converse_messages.append({"role": "assistant", "content": [{"text": content}]})
            else:  # user
                converse_messages.append({"role": "user", "content": [{"text": content}]})
        
        # Build request kwargs
        request_kwargs = {
            "modelId": self.model_id,
            "messages": converse_messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            }
        }
        
        if system_prompt:
            request_kwargs["system"] = [{"text": system_prompt}]
        
        logger.info("Starting LLM call", extra={
            "context": {"model": self.model_id, "max_tokens": max_tokens}
        })
        start_time = time.time()
        
        for attempt in range(retries):
            try:
                response = self.client.converse(**request_kwargs)
                
                elapsed = time.time() - start_time
                logger.info("LLM call completed", extra={
                    "context": {"elapsed_seconds": round(elapsed, 2), "model": self.model_id}
                })
                
                # Extract text from Bedrock response
                output = response.get("output", {})
                message = output.get("message", {})
                content_blocks = message.get("content", [])
                
                if content_blocks:
                    return content_blocks[0].get("text", "").strip()
                
                raise AIServiceError("Empty response from AWS Bedrock")
                
            except ClientError as exc:
                last_err = exc
                error_code = exc.response.get("Error", {}).get("Code", "")
                
                # Don't retry on authentication errors (won't succeed)
                if error_code in ["AccessDeniedException", "UnauthorizedAccessException", "InvalidSignatureException"]:
                    logger.error("AWS Bedrock authentication error", extra={
                        "context": {"error": str(exc), "hint": "Check your AWS credentials"}
                    })
                    raise AIServiceError(
                        f"AWS Bedrock error: {exc}. Please check your AWS credentials."
                    )
                
                logger.warning("LLM call failed, retrying", extra={
                    "context": {"attempt": attempt + 1, "error": str(exc)}
                })
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
            except Exception as exc:
                last_err = exc
                logger.warning("LLM call failed, retrying", extra={
                    "context": {"attempt": attempt + 1, "error": str(exc)}
                })
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        
        raise AIServiceError(f"LLM failed after {retries} attempts: {last_err}")

    def _parse_json(self, text: str) -> Any:
        """Extract JSON from LLM response (handles markdown fences and unwraps single-item arrays)."""
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            for fence in ("```json", "```"):
                if fence in text:
                    text = text.split(fence, 1)[1].split("```", 1)[0].strip()
                    break
            result = json.loads(text)
        
        # Unwrap single-item arrays (common LLM mistake)
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
            logger.info("Unwrapped single-item array returned by LLM")
            return result[0]
        
        return result

    @staticmethod
    def _safe(obj: Any) -> Any:
        """Make any value JSON-safe."""
        if obj is None:
            return None
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, (list, tuple)):
            return [AISummaryGenerator._safe(i) for i in obj]
        if isinstance(obj, dict):
            return {k: AISummaryGenerator._safe(v) for k, v in obj.items()}
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)

    # ── public methods ────────────────────────────────────────────────

    def generate_column_descriptions(self, table: TableMeta,
                                     sample_data: Optional[Dict[str, List]] = None) -> Dict[str, str]:
        cols_info = []
        for c in table.columns:
            info: Dict[str, Any] = {
                "name": c.name, "type": c.data_type, "nullable": c.nullable,
                "is_pk": c.primary_key, "is_fk": c.foreign_key is not None,
                "fk_ref": c.foreign_key.get("referred_table") if c.foreign_key else None,
            }
            if sample_data and c.name in sample_data:
                info["samples"] = self._safe(sample_data[c.name][:3])
            cols_info.append(info)

        rel = ""
        if table.relationships:
            refs = [r["to_table"] for r in table.relationships if r["type"] == "references"]
            rby = [r["from_table"] for r in table.relationships if r["type"] == "referenced_by"]
            if refs:
                rel += f"References: {', '.join(refs)}. "
            if rby:
                rel += f"Referenced by: {', '.join(rby)}."

        prompt = (
            f"Analyze the following table columns and provide clear, user-friendly descriptions that anyone can understand.\n\n"
            f"Table: {table.name} ({table.row_count:,} rows). {rel}\n"
            f"Columns:\n{json.dumps(self._safe(cols_info), indent=2)}\n\n"
            f"IMPORTANT: Write descriptions for NON-TECHNICAL business users who may not understand databases.\n"
            f"- Explain WHAT the data represents in plain English\n"
            f"- Explain WHY this data matters for the business\n"
            f"- Use everyday language, avoid technical jargon\n"
            f"- Be specific about the purpose of each column\n\n"
            f"Return ONLY a JSON object (not an array) where keys are column names and values are descriptions.\n"
            f"Example format:\n"
            f'{{\n'
            f'  "customer_id": "A unique number assigned to each customer to track their purchases and account history.",\n'
            f'  "order_date": "The date when the customer placed their order, used for tracking delivery timelines and sales reports."\n'
            f'}}\n\n'
            f"Each description should be 1-2 sentences. Focus on business meaning, not technical details.\n"
            f"Return ONLY the JSON object. Do not wrap in an array."
        )
        try:
            raw = self._call([
                {"role": "system", "content": "You are a data documentation expert. Always return JSON objects (not arrays). Map each column name to its description."},
                {"role": "user", "content": prompt},
            ], temperature=0.2, max_tokens=2000)
            result = self._parse_json(raw)
            # Validate return type
            if not isinstance(result, dict):
                logger.warning("Column descriptions returned non-dict, using fallback", extra={"context": {"type": type(result).__name__}})
                raise ValueError(f"Expected dict, got {type(result).__name__}")
            return result
        except Exception as exc:
            logger.warning("Column description generation failed", extra={"context": {"error": str(exc)}})
            return {}

    def generate_table_summary(self, table: TableMeta,
                               quality: Optional[TableQuality] = None) -> Dict[str, Any]:
        cols_desc = "\n".join(
            f"- {c.name} ({c.data_type})"
            + (" [PRIMARY KEY]" if c.primary_key else "")
            + (f" [FK -> {c.foreign_key.get('referred_table')}]" if c.foreign_key else "")
            + ("" if c.nullable else " [NOT NULL]")
            for c in table.columns
        )
        
        relationships_info = ""
        if table.relationships:
            refs = [r for r in table.relationships if r.get('type') == 'references']
            ref_by = [r for r in table.relationships if r.get('type') == 'referenced_by']
            if refs:
                relationships_info += f"\nReferences: {', '.join(r.get('to_table', '') for r in refs)}"
            if ref_by:
                relationships_info += f"\nReferenced by: {', '.join(r.get('from_table', '') for r in ref_by)}"
        
        qual = ""
        if quality:
            issues_str = ', '.join(quality.issues) if quality.issues else 'None'
            qual = f"\n\nData Quality Metrics:\n- Row count: {table.row_count:,}\n- Completeness: {quality.overall_completeness:.1%}\n- Quality Score: {quality.quality_score}/100\n- Issues: {issues_str}"

        prompt = f"""Analyze this database table and provide a business-friendly summary.

Table: {table.name}
Type: {table.table_type}
Row Count: {table.row_count:,}

Columns:
{cols_desc}{relationships_info}{qual}

CRITICAL: You MUST provide ALL fields below. Do NOT skip any field. Each field is REQUIRED.

Provide a JSON response with EXACTLY this structure (all fields are MANDATORY):
{{
    "business_description": "A clear, non-technical description of what this table stores and its business purpose (2-3 sentences). Be specific about what business entity this represents.",
    "key_insights": ["Insight 1 about the table structure", "Insight 2 about data relationships", "Insight 3 about column purposes"],
    "usage_recommendations": ["Recommendation 1 for how analysts should use this table", "Recommendation 2 for joining with other tables"],
    "potential_issues": ["Any data quality or design concerns to be aware of"]
}}

MANDATORY REQUIREMENTS:
1. "business_description" - REQUIRED: 2-3 sentences explaining the business purpose
2. "key_insights" - REQUIRED: Provide EXACTLY 3 insights about the table
3. "usage_recommendations" - REQUIRED: Provide EXACTLY 2-3 specific recommendations
4. "potential_issues" - REQUIRED: Provide at least 1 issue or "None identified" if no issues

Return ONLY the JSON object, no additional text. Do not wrap in an array."""
        try:
            raw = self._call([
                {"role": "system", "content": "You are a data analyst expert who provides clear, business-friendly descriptions of database tables. You MUST include ALL required fields in your response: business_description, key_insights (exactly 3), usage_recommendations (2-3), and potential_issues (at least 1). Always respond with valid JSON objects, never arrays."},
                {"role": "user", "content": prompt},
            ], max_tokens=1500)
            result = self._parse_json(raw)
            # Validate return type
            if not isinstance(result, dict):
                logger.warning("Table summary returned non-dict, using fallback", extra={"context": {"type": type(result).__name__}})
                raise ValueError(f"Expected dict, got {type(result).__name__}")
            return result
        except Exception as exc:
            logger.warning("Table summary generation failed", extra={"context": {"error": str(exc)}})
            return {"business_description": f"Table {table.name} with {len(table.columns)} columns.",
                    "key_insights": [], "usage_recommendations": [], "potential_issues": [str(exc)]}

    def generate_table_business_context(self, table: TableMeta,
                                        quality: Optional[TableQuality] = None) -> Dict[str, Any]:
        cols_info = []
        for col in table.columns[:15]:
            col_desc = f"{col.name} ({col.data_type})"
            if col.primary_key:
                col_desc += " [PK]"
            if col.foreign_key:
                col_desc += f" [FK→{col.foreign_key.get('referred_table')}]"
            cols_info.append(col_desc)
        
        relationships_info = ""
        if table.relationships:
            refs = [r for r in table.relationships if r.get('type') == 'references']
            ref_by = [r for r in table.relationships if r.get('type') == 'referenced_by']
            if refs:
                relationships_info += f"\nReferences: {', '.join(r.get('to_table', '') for r in refs)}. "
            if ref_by:
                relationships_info += f"\nReferenced by: {', '.join(r.get('from_table', '') for r in ref_by)}."

        prompt = f"""You are a business analyst documenting a database for non-technical stakeholders.

Table: {table.name}
Columns: {', '.join(cols_info)}
Row Count: {table.row_count:,}{relationships_info}

CRITICAL: You MUST provide BOTH fields below. Do NOT skip any field. Both are REQUIRED.

Provide a JSON response with EXACTLY this structure:
{{
    "business_summary": "A 2-sentence summary explaining: 1) What business entity/concept this table represents 2) What critical business data it stores. Be specific and reference actual column names.",
    "analyst_recommendation": "One specific, actionable recommendation for how business analysts should use this table (e.g., 'Join with X table to analyze Y', 'Use for calculating Z metrics'). Be concrete and actionable."
}}

MANDATORY REQUIREMENTS:
1. "business_summary" - REQUIRED: Must be exactly 2 sentences. First sentence: what entity this represents. Second sentence: what data it stores.
2. "analyst_recommendation" - REQUIRED: Must be a specific, actionable recommendation mentioning table names or metrics.

Return ONLY the JSON object, no additional text. Do not wrap in an array."""
        try:
            raw = self._call([
                {"role": "system", "content": "You are a business intelligence expert. You MUST provide BOTH fields: business_summary (exactly 2 sentences) AND analyst_recommendation (specific, actionable). Never skip any field. Always respond with valid JSON objects, never arrays."},
                {"role": "user", "content": prompt},
            ], temperature=0.3, max_tokens=500)
            result = self._parse_json(raw)
            # Validate return type
            if not isinstance(result, dict):
                logger.warning("Business context returned non-dict, using fallback", extra={"context": {"type": type(result).__name__}})
                raise ValueError(f"Expected dict, got {type(result).__name__}")
            return result
        except Exception as exc:
            logger.warning("Business context generation failed", extra={"context": {"error": str(exc)}})
            return {
                "business_summary": f"Stores {table.name.replace('_', ' ')} data.",
                "analyst_recommendation": "Review structure for analysis opportunities.",
            }

#     def generate_database_summary(self, db: DatabaseMeta) -> Dict[str, Any]:
#         """Generate a high-level summary of the entire database."""
        
#         tables_overview = []
#         for table in db.tables[:20]:  # Limit to first 20 tables
#             tables_overview.append(f"- {table.name}: {len(table.columns)} columns, {table.row_count:,} rows")
        
#         # Count relationships
#         total_relationships = sum(len(t.relationships) for t in db.tables)
        
#         prompt = f"""Analyze this database schema and provide a high-level summary.

# Database: {db.database_name}
# Type: {db.database_type}
# Total Tables: {db.summary['total_tables']}
# Total Views: {db.summary['total_views']}
# Total Relationships: {total_relationships}

# Tables Overview:
# {chr(10).join(tables_overview)}

# Provide a JSON response with the following structure:
# {{
#     "database_purpose": "A clear description of what this database appears to be used for (2-3 sentences)",
#     "domain_analysis": "What business domain or industry this database appears to serve",
#     "architecture_observations": ["List of 3-5 observations about the database design"],
#     "data_model_type": "Identify if this appears to be OLTP, OLAP, data warehouse, etc.",
#     "key_entity_groups": ["List the main entity groups/domains in the database"],
#     "recommendations": ["List 2-3 high-level recommendations"]
# }}

# Return ONLY the JSON, no additional text."""

#         try:
#             raw = self._call([
#                 {"role": "system", "content": "You are a database architect who provides clear, insightful analysis of database schemas. Always respond with valid JSON."},
#                 {"role": "user", "content": prompt},
#             ], temperature=0.3, max_tokens=1000)
#             result = self._parse_json(raw)
#             # Validate return type
#             if not isinstance(result, dict):
#                 logger.warning("Database summary returned non-dict, using fallback", extra={"context": {"type": type(result).__name__}})
#                 raise ValueError(f"Expected dict, got {type(result).__name__}")
#             return result
#         except Exception as exc:
#             logger.warning("Database summary generation failed", extra={"context": {"error": str(exc)}})
#             return {"database_purpose": "Unknown", "domain_analysis": "Unknown",
#                     "architecture_observations": [], "data_model_type": "Unknown",
#                     "key_entity_groups": [], "recommendations": [str(exc)]}


    def generate_database_summary(self, db: DatabaseMeta) -> Dict[str, Any]:
        """Generate a high-level summary of the entire database."""

        tables_overview = []
        for table in db.tables[:20]:
            tables_overview.append(
                f"- {table.name}: {len(table.columns)} columns, {table.row_count:,} rows"
            )

        total_relationships = sum(len(t.relationships) for t in db.tables)

        prompt = f"""Analyze this database schema and provide a high-level summary.

    Database: {db.database_name}
    Type: {db.database_type}
    Total Tables: {db.summary['total_tables']}
    Total Views: {db.summary['total_views']}
    Total Relationships: {total_relationships}

    Tables Overview:
    {chr(10).join(tables_overview)}

    Provide a JSON response with the following structure:
    {{
        "database_purpose": "A clear description of what this database appears to be used for (2-3 sentences)",
        "domain_analysis": "What business domain or industry this database appears to serve",
        "architecture_observations": ["List of 3-5 observations about the database design"],
        "data_model_type": "Identify if this appears to be OLTP, OLAP, data warehouse, etc.",
        "key_entity_groups": ["List the main entity groups/domains in the database"],
        "recommendations": ["List 2-3 high-level recommendations"]
    }}

    IMPORTANT: Return ONLY valid JSON. No markdown, no code fences, no comments, no trailing commas."""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a database architect who provides clear, insightful analysis "
                    "of database schemas. You MUST respond with ONLY valid JSON — no markdown "
                    "formatting, no code fences, no explanatory text before or after the JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        fallback = {
            "database_purpose": "Unknown",
            "domain_analysis": "Unknown",
            "architecture_observations": [],
            "data_model_type": "Unknown",
            "key_entity_groups": [],
            "recommendations": [],
        }

        # Attempt with retry
        max_attempts = 2
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                raw = self._call(messages, temperature=0.3, max_tokens=1000)
                result = self._parse_json(raw)

                if not isinstance(result, dict):
                    raise ValueError(f"Expected dict, got {type(result).__name__}")

                # Validate expected keys exist, fill missing ones with defaults
                for key, default_value in fallback.items():
                    if key not in result:
                        result[key] = default_value

                return result

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Database summary generation failed (attempt %d/%d)",
                    attempt,
                    max_attempts,
                    extra={"context": {"error": str(exc)}},
                )

                if attempt < max_attempts:
                    # On retry, add a correction message to the conversation
                    messages.append({"role": "assistant", "content": raw if 'raw' in dir() else ""})
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your previous response was not valid JSON. "
                            "Please respond with ONLY the raw JSON object, nothing else."
                        ),
                    })

        fallback["recommendations"] = [f"Analysis failed: {str(last_error)}"]
        return fallback


    def chat(self, question: str, db: DatabaseMeta,
             quality: Optional[Dict[str, TableQuality]] = None,
             history: Optional[List[Dict[str, str]]] = None) -> str:
        """Answer free-form questions about the schema / data."""
        # Build concise schema context
        ctx_parts = [f"Database: {db.database_name} ({db.database_type})", ""]
        for t in db.tables[:50]:  # cap to keep prompt manageable
            line = f"TABLE {t.display_name} ({t.row_count:,} rows): "
            cols = ", ".join(
                c.name + (" [PK]" if c.primary_key else "")
                + (f" [FK→{c.foreign_key.get('referred_table')}]" if c.foreign_key else "")
                for c in t.columns
            )
            ctx_parts.append(line + cols)

        schema_ctx = "\n".join(ctx_parts)
        messages = [
            {"role": "system", "content": (
                "You are a helpful database assistant.\n\n"
                f"SCHEMA:\n{schema_ctx}\n\n"
                "Answer questions about tables, columns, relationships. "
                "Generate SQL when asked. Be concise."
            )},
        ]
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": question})

        try:
            return self._call(messages, temperature=0.3, max_tokens=1500)
        except Exception as exc:
            return f"Sorry, I couldn't process that: {exc}"
