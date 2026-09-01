"""InsightIDR router — cloud SIEM investigations and log search."""

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from rapid7_mcp.client import InsightIDRClient, get_idr_client
from rapid7_mcp.models import (
    IndicatorList,
    Investigation,
    InvestigationList,
    LogInfo,
    LogList,
    LogSearchRequest,
    LogSearchResults,
    LogSetRef,
)

router = APIRouter()


@router.get(
    "/investigations",
    response_model=InvestigationList,
    operation_id="list_investigations",
    summary="List InsightIDR investigations",
    description=(
        "Returns InsightIDR investigations (security incidents). Each investigation aggregates "
        "related alerts with an assigned priority, status, and optional assignee. "
        "Filter by status to focus on open incidents requiring attention. "
        "Use get_investigation for the full alert timeline."
    ),
)
async def list_investigations(
    status: str = Query("OPEN", description="Filter by status: OPEN, CLOSED, INVESTIGATING"),
    priority: str | None = Query(
        None, description="Filter by priority: CRITICAL, HIGH, MEDIUM, LOW"
    ),
    page_token: str | None = Query(None, description="Pagination cursor from previous response"),
    size: int = Query(20, ge=1, le=100),
    client: InsightIDRClient = Depends(get_idr_client),
) -> InvestigationList:
    params: dict = {"statuses": status, "size": size}
    if priority:
        params["priorities"] = priority
    if page_token:
        params["index"] = page_token
    data = await client.get("/idr/v2/investigations", params=params)
    return InvestigationList(**data)


@router.get(
    "/investigations/{investigation_id}",
    response_model=Investigation,
    operation_id="get_investigation",
    summary="Get an investigation by ID",
    description=(
        "Returns full details for a single InsightIDR investigation including all associated alerts, "
        "timeline, assignee, priority, and disposition. Use this to understand the full context "
        "of an active security incident."
    ),
)
async def get_investigation(
    investigation_id: str,
    client: InsightIDRClient = Depends(get_idr_client),
) -> Investigation:
    data = await client.get(f"/idr/v2/investigations/{investigation_id}")
    return Investigation(**data)


@router.get(
    "/logs/catalog",
    response_model=LogList,
    operation_id="list_logs",
    summary="List InsightIDR logs (name → ID lookup)",
    description=(
        "Returns every log configured in InsightIDR, with its ID and the log sets it belongs to. "
        "query_logs requires a log ID (UUID), not the friendly name shown in the Rapid7 console — "
        "use this first to resolve a name (e.g. 'prod-handler-pluggto') to the ID it needs. "
        "Optionally filter by a case-insensitive substring of the name."
    ),
)
async def list_logs(
    name_contains: str | None = Query(
        None, description="Case-insensitive substring to filter log names by"
    ),
    client: InsightIDRClient = Depends(get_idr_client),
) -> LogList:
    data = await client.get("/log_search/management/logs")
    logs = [
        LogInfo(
            id=log["id"],
            name=log["name"],
            logsets=[
                LogSetRef(id=ls["id"], name=ls["name"]) for ls in log.get("logsets_info", [])
            ],
        )
        for log in data.get("logs", [])
    ]
    if name_contains:
        needle = name_contains.lower()
        logs = [log for log in logs if needle in log.name.lower()]
    return LogList(logs=logs)


@router.post(
    "/logs",
    response_model=LogSearchResults,
    operation_id="query_logs",
    summary="Search logs with LEQL",
    description=(
        "Execute a LEQL (Log Entry Query Language) query against InsightIDR log sets. "
        "Use this to hunt for indicators of compromise — search for specific IPs, file hashes, "
        "domain names, or user activity across firewall, proxy, DNS, and endpoint logs. "
        "Example LEQL: 'where(destination_ip = \"1.2.3.4\")'. "
        "Time range is specified as Unix epoch milliseconds."
    ),
)
async def query_logs(
    body: LogSearchRequest,
    client: InsightIDRClient = Depends(get_idr_client),
) -> LogSearchResults:
    if not body.logs:
        raise HTTPException(
            status_code=400,
            detail="'logs' (lista de log set IDs) é obrigatório para query_logs.",
        )
    to_time = body.to_time or int(time.time() * 1000)
    from_time = body.from_time or (to_time - 24 * 3600 * 1000)
    payload: dict = {
        "leql": {"statement": body.query, "during": {"from": from_time, "to": to_time}},
        "logs": body.logs,
    }
    data = await client.post("/log_search/query/logs", body=payload)
    return LogSearchResults(**data)


@router.get(
    "/logs/query/{query_id:path}",
    response_model=LogSearchResults,
    operation_id="poll_log_query",
    summary="Poll a log search job for more results",
    description=(
        "query_logs starts an async search job and its first response usually comes back with "
        "progress=0 and no events yet, even when there are matches — the job keeps scanning in "
        "the background. Pass the 'id' from that response here (URL-encode it) to continue "
        "polling the same job. Keep calling this until 'progress' reaches 100; each call returns "
        "the events found so far, not just the newest increment — accumulate/dedupe by treating "
        "the last poll with progress=100 as the full result set."
    ),
)
async def poll_log_query(
    query_id: str,
    client: InsightIDRClient = Depends(get_idr_client),
) -> LogSearchResults:
    data = await client.get(f"/log_search/query/{query_id}")
    return LogSearchResults(**data)


@router.get(
    "/iocs",
    response_model=IndicatorList,
    operation_id="list_indicators",
    summary="List threat intelligence indicators (IOCs)",
    description=(
        "Returns active Indicators of Compromise (IOCs) being tracked in InsightIDR's threat "
        "intelligence feed. Indicators include malicious IPs, domains, file hashes, and URLs "
        "associated with known threat actors or malware families. "
        "Use this to check whether an IP or domain seen in logs is a known bad actor."
    ),
)
async def list_indicators(
    indicator_type: str | None = Query(
        None,
        description="Filter by type: IP_ADDRESS, DOMAIN, URL, FILE_HASH",
    ),
    client: InsightIDRClient = Depends(get_idr_client),
) -> IndicatorList:
    params: dict = {}
    if indicator_type:
        params["type"] = indicator_type
    data = await client.get("/idr/v2/iocs", params=params)
    return IndicatorList(**data)
