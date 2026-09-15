"""FastAPI application with MCP mount for Rapid7 InsightVM, InsightIDR, and Metasploit Pro."""

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi_mcp import FastApiMCP

from rapid7_mcp.routers import (
    asset_groups,
    assets,
    idr,
    metasploit,
    remediation,
    reports,
    scans,
    sites,
    vulnerabilities,
)

app = FastAPI(
    title="Rapid7 MCP Server",
    description=(
        "Unified MCP server exposing Rapid7 vulnerability and threat management tools to LLM clients. "
        "Covers InsightVM (vulnerability management), InsightIDR (SIEM/investigations), "
        "and Metasploit Pro (pentest telemetry, read-only). "
        "Set DEMO_MODE=true to explore all tools without live credentials."
    ),
    version="0.1.0",
    contact={"name": "Tim Hollingsworth"},
    license_info={"name": "MIT"},
)

# InsightVM — vulnerability management
app.include_router(sites.router, prefix="/sites", tags=["InsightVM · Sites"])
app.include_router(assets.router, prefix="/assets", tags=["InsightVM · Assets"])
app.include_router(asset_groups.router, prefix="/asset_groups", tags=["InsightVM · Asset Groups"])
app.include_router(
    vulnerabilities.router, prefix="/vulnerabilities", tags=["InsightVM · Vulnerabilities"]
)
app.include_router(scans.router, prefix="/scans", tags=["InsightVM · Scans"])
app.include_router(
    remediation.router, prefix="/remediation_projects", tags=["InsightVM · Remediation"]
)
app.include_router(reports.router, prefix="/reports", tags=["InsightVM · Reports"])

# InsightIDR — cloud SIEM
app.include_router(idr.router, prefix="/idr", tags=["InsightIDR"])

# Metasploit Pro — read-only pentest telemetry
app.include_router(metasploit.router, prefix="/metasploit", tags=["Metasploit Pro (read-only)"])

@app.exception_handler(httpx.HTTPStatusError)
async def httpx_status_error_handler(
    request: Request, exc: httpx.HTTPStatusError
) -> JSONResponse:
    """Surface the upstream Rapid7 API's real status/body instead of a generic 500.

    All product clients call ``raise_for_status()`` on the raw httpx response, so
    upstream errors (401 bad/expired key, 403 missing scope, 404, 429, ...) would
    otherwise reach the MCP client as an opaque ``500 Internal Server Error``.
    """
    upstream = exc.response
    try:
        detail = upstream.json()
    except ValueError:
        detail = upstream.text
    return JSONResponse(status_code=upstream.status_code, content={"detail": detail})


mcp = FastApiMCP(app)
mcp.mount_http()  # Streamable HTTP MCP endpoint at /mcp
