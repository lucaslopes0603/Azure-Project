# function_app.py  (Azure Functions - Python v2 programming model)
import os
import re
import json
import base64
import logging
from typing import Dict, Any, Set, Iterable
from datetime import datetime, timezone

import requests
import azure.functions as func
from urllib.parse import quote
from azure.data.tables import TableServiceClient

# -----------------------------
# App setup (HTTP auth: Anonymous para facilitar webhook/CLI)
# -----------------------------
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# -----------------------------
# Config (env)
# -----------------------------
ADO_ORG     = os.getenv("ADO_ORG", "")
ADO_PROJECT = os.getenv("ADO_PROJECT", "")
ADO_PAT     = os.getenv("ADO_PAT", "")
API_VERSION = "7.1"  # estável

DEFAULT_ESTIMATE_HOURS = float(os.getenv("DEFAULT_ESTIMATE_HOURS", "6.0"))
HOURS_PER_PUSH         = float(os.getenv("HOURS_PER_PUSH", "0.5"))

WORK_REMAINING_FIELD = "/fields/Microsoft.VSTS.Scheduling.RemainingWork"
WORK_COMPLETED_FIELD = "/fields/Microsoft.VSTS.Scheduling.CompletedWork"
STATE_FIELD          = "/fields/System.State"

# Ajuste se seu fluxo usa outro rótulo de estado
STATE_IN_PROGRESS_VALUES = {"in progress", "em andamento", "doing"}  # para comparação
STATE_NEW_VALUES         = {"new", "to do", "todo", "backlog", "a fazer"}

# Tabela de tracking de relógio
TABLE_NAME = "Tracking"

# AB#123 detector
RE_AB_ID = re.compile(r"AB#(\d+)", re.IGNORECASE)

# -----------------------------
# Helpers gerais
# -----------------------------
def _auth_header() -> Dict[str, str]:
    token = ":" + ADO_PAT
    b64 = base64.b64encode(token.encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {b64}"}

def _ado_url(path: str) -> str:
    # URL-encode para nomes com espaço/acentos
    org = quote(ADO_ORG or "", safe="")
    proj = quote(ADO_PROJECT or "", safe="")
    return f"https://dev.azure.com/{org}/{proj}/_apis/{path}?api-version={API_VERSION}"

def _get_work_item(id_: str) -> Dict[str, Any]:
    url = _ado_url(f"wit/workitems/{id_}")
    logging.info(f"GET {url}")
    r = requests.get(url, headers=_auth_header(), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"GET {url} -> {r.status_code} {r.text}")
    return r.json()

def _patch_work_item(id_: str, ops: Iterable[Dict[str, Any]]):
    url = _ado_url(f"wit/workitems/{id_}")
    headers = _auth_header()
    headers["Content-Type"] = "application/json-patch+json"
    body = json.dumps(list(ops))
    logging.info(f"PATCH {url} body={body}")
    r = requests.patch(url, headers=headers, data=body, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"PATCH {url} -> {r.status_code} {r.text}")
    return r.json()

def _safe_get_field(wi: Dict[str, Any], refname: str, default=None):
    return (wi.get("fields") or {}).get(refname, default)

def _extract_ids_from_text(text: str, out: Set[str]):
    if not text:
        return
    for m in RE_AB_ID.finditer(text):
        out.add(m.group(1))

def _extract_work_item_ids(payload: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    resource = payload.get("resource") or {}

    # git.push
    for ru in resource.get("refUpdates") or []:
        _extract_ids_from_text(ru.get("name", ""), ids)
    for c in resource.get("commits") or []:
        _extract_ids_from_text(c.get("comment", ""), ids)

    # git.refUpdateCreated (branch criada)
    ref = resource.get("ref")
    if isinstance(ref, dict):
        _extract_ids_from_text(ref.get("name", ""), ids)

    # (futuro) PR title/description
    _extract_ids_from_text(resource.get("title", ""), ids)
    _extract_ids_from_text(resource.get("description", ""), ids)

    return ids

def _utcnow():
    return datetime.now(timezone.utc)

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

# -----------------------------
# Storage (Azure Table Storage) helpers
# -----------------------------
def _table_client():
    conn = os.getenv("AzureWebJobsStorage")
    if not conn:
        raise RuntimeError("AzureWebJobsStorage não configurado.")
    svc = TableServiceClient.from_connection_string(conn)
    try:
        svc.create_table(TABLE_NAME)
    except Exception:
        pass
    return svc.get_table_client(TABLE_NAME)

def _start_tracking(wid: str, branch_name: str | None = None):
    tc = _table_client()
    ent = {
        "PartitionKey": "WI",
        "RowKey": str(wid),
        "running": True,
        "last_updated": _iso(_utcnow()),
        "accumulated_minutes": 0
    }
    if branch_name:
        ent["branch_name"] = branch_name
    tc.upsert_entity(mode="merge", entity=ent)

def _set_running_many(wi_ids: Iterable[str], running: bool):
    tc = _table_client()
    now = _iso(_utcnow())
    updated = []
    for wid in wi_ids:
        try:
            ent = tc.get_entity("WI", str(wid))
        except Exception:
            ent = {"PartitionKey": "WI", "RowKey": str(wid), "accumulated_minutes": 0}
        ent["running"] = running
        ent["last_updated"] = now
        tc.upsert_entity(mode="merge", entity=ent)
        updated.append(str(wid))
    return updated

# -----------------------------
# Inicialização/ativação do WI
# -----------------------------
def _first_time_initialize_and_activate(wi: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    ops = []
    remaining = _safe_get_field(wi, "Microsoft.VSTS.Scheduling.RemainingWork")
    completed = _safe_get_field(wi, "Microsoft.VSTS.Scheduling.CompletedWork")
    state     = (_safe_get_field(wi, "System.State", "") or "").strip()

    if remaining is None and completed is None:
        ops.append({"op": "add", "path": WORK_REMAINING_FIELD, "value": DEFAULT_ESTIMATE_HOURS})
        ops.append({"op": "add", "path": WORK_COMPLETED_FIELD, "value": 0.0})

    # mover para In Progress se estiver "New/To do/..." e não já em doing
    if state.lower() in STATE_NEW_VALUES:
        ops.append({"op": "add", "path": STATE_FIELD, "value": "Active"})
    return ops

def _apply_push_heuristic(wi: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    ops = []
    remaining = float(_safe_get_field(wi, "Microsoft.VSTS.Scheduling.RemainingWork", 0.0) or 0.0)
    completed = float(_safe_get_field(wi, "Microsoft.VSTS.Scheduling.CompletedWork", 0.0) or 0.0)
    new_completed = round(completed + HOURS_PER_PUSH, 2)
    new_remaining = round(max(0.0, remaining - HOURS_PER_PUSH), 2)
    ops.append({"op": "add", "path": WORK_COMPLETED_FIELD, "value": new_completed})
    ops.append({"op": "add", "path": WORK_REMAINING_FIELD, "value": new_remaining})
    return ops

# -----------------------------
# /devops-webhook
# -----------------------------
@app.route(route="devops-webhook", methods=["POST"])
def devops_webhook(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Azure DevOps webhook recebido (Python v2).")
    logging.info(f"ENV ADO_ORG={ADO_ORG} ADO_PROJECT={ADO_PROJECT}")

    if not (ADO_ORG and ADO_PROJECT and ADO_PAT):
        return func.HttpResponse("Faltam configs ADO_ORG/ADO_PROJECT/ADO_PAT.", status_code=500)

    try:
        payload = req.get_json()
    except ValueError:
        return func.HttpResponse("JSON inválido", status_code=400)

    event_type = payload.get("eventType", "")
    ids = _extract_work_item_ids(payload)
    logging.info("eventType=%s | workItems=%s", event_type, list(ids))

    processed, errors = [], []

    # branch name (se vier)
    resource = payload.get("resource") or {}
    ref_name = None
    if isinstance(resource.get("ref"), dict):
        ref_name = resource["ref"].get("name")

    for wid in ids:
        try:
            wi = _get_work_item(str(wid))
            ops: list[Dict[str, Any]] = []

            if event_type == "git.refUpdateCreated":
                # branch criada -> iniciar tracking e ativar
                _start_tracking(str(wid), branch_name=ref_name)
                ops.extend(_first_time_initialize_and_activate(wi))

            if event_type == "git.push":
                # se nunca inicializado, inicializa + ativa
                if _safe_get_field(wi, "Microsoft.VSTS.Scheduling.RemainingWork") is None and \
                   _safe_get_field(wi, "Microsoft.VSTS.Scheduling.CompletedWork") is None:
                    ops.extend(_first_time_initialize_and_activate(wi))
                # heurística por push (opcional)
                ops.extend(_apply_push_heuristic(wi))

            if not ops:
                # fallback: ao menos ativa/inicializa
                ops.extend(_first_time_initialize_and_activate(wi))

            if ops:
                _patch_work_item(str(wid), ops)

            processed.append(str(wid))
        except Exception as e:
            logging.exception("Erro processando WI %s", wid)
            errors.append({"id": str(wid), "error": str(e)})

    status = 207 if errors else 200
    body = {"eventType": event_type, "processed": processed, "processedCount": len(processed), "errors": errors}
    return func.HttpResponse(json.dumps(body), mimetype="application/json", status_code=status)

# -----------------------------
# /connect  (inicia contagem para 1..n WIs)
# -----------------------------
@app.route(route="connect", methods=["POST"])
def connect(req: func.HttpRequest) -> func.HttpResponse:
    if not (ADO_ORG and ADO_PROJECT and ADO_PAT):
        return func.HttpResponse("Faltam configs ADO_ORG/ADO_PROJECT/ADO_PAT.", status_code=500)

    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("JSON inválido", status_code=400)

    wi_ids = data.get("wi_ids") or []
    if not wi_ids:
        return func.HttpResponse("Informe wi_ids: [..]", status_code=400)

    processed = []
    for wid in wi_ids:
        wid = str(wid)
        try:
            _start_tracking(wid)
            wi = _get_work_item(wid)
            ops = _first_time_initialize_and_activate(wi)
            if ops:
                _patch_work_item(wid, ops)
            processed.append(wid)
        except Exception as e:
            logging.exception("Falha ao conectar WI %s", wid)

    return func.HttpResponse(json.dumps({"connected": processed}), mimetype="application/json")

# -----------------------------
# /pause e /resume (pausa/retoma tracking)
# -----------------------------
@app.route(route="pause", methods=["POST"])
def pause(req: func.HttpRequest) -> func.HttpResponse:
    return _set_running_endpoint(req, False)

@app.route(route="resume", methods=["POST"])
def resume(req: func.HttpRequest) -> func.HttpResponse:
    return _set_running_endpoint(req, True)

def _set_running_endpoint(req: func.HttpRequest, running: bool) -> func.HttpResponse:
    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("JSON inválido", status_code=400)

    wi_ids = data.get("wi_ids") or []
    if not wi_ids:
        return func.HttpResponse("Informe wi_ids: [..]", status_code=400)

    updated = _set_running_many([str(x) for x in wi_ids], running)
    return func.HttpResponse(json.dumps({"updated": updated, "running": running}), mimetype="application/json")

@app.route(route="focus", methods=["POST"])
def focus(req: func.HttpRequest) -> func.HttpResponse:
    """Define um único WI como ativo (pausa os outros)."""
    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("JSON inválido", status_code=400)

    wi_id = str(data.get("wi_id", "")).strip()
    if not wi_id:
        return func.HttpResponse("Informe wi_id", status_code=400)

    tc = _table_client()
    now = _iso(_utcnow())
    updated = []

    # Pausa todos
    entities = list(tc.list_entities())
    for ent in entities:
        if ent.get("PartitionKey") == "WI":
            ent["running"] = False
            ent["last_updated"] = now
            tc.update_entity(ent, mode="merge")

    # Ativa o escolhido
    try:
        ent = tc.get_entity("WI", wi_id)
    except Exception:
        # se não existir ainda no tracking, cria
        ent = {"PartitionKey": "WI", "RowKey": wi_id, "accumulated_minutes": 0}
    ent["running"] = True
    ent["last_updated"] = now
    tc.upsert_entity(mode="merge", entity=ent)

    updated.append(wi_id)

    return func.HttpResponse(
        json.dumps({"focused": wi_id}),
        mimetype="application/json"
    )


# -----------------------------
# Timer (a cada 5 minutos) acumula e aplica horas inteiras
# -----------------------------
@app.schedule(schedule="0 */5 * * * *", arg_name="myTimer", run_on_startup=False, use_monitor=True)
def hourly_counter(myTimer: func.TimerRequest) -> None:
    logging.info("Timer tick - acumulando minutos...")
    try:
        tc = _table_client()
    except Exception:
        logging.exception("Sem Table Storage configurado.")
        return

    now = _utcnow()
    try:
        entities = list(tc.list_entities())
    except Exception:
        logging.exception("Falha ao listar entidades do Tracking.")
        return

    for ent in entities:
        try:
            wid = ent["RowKey"]
            running = bool(ent.get("running", False))
            last_updated = ent.get("last_updated")
            acc = int(ent.get("accumulated_minutes", 0))

            last = datetime.fromisoformat(last_updated) if last_updated else now

            if not running:
                # pausado: apenas atualiza last_updated para manter referência
                ent["last_updated"] = _iso(now)
                tc.update_entity(ent, mode="merge")
                continue

            delta_min = int((now - last).total_seconds() // 60)
            if delta_min <= 0:
                ent["last_updated"] = _iso(now)
                tc.update_entity(ent, mode="merge")
                continue

            acc += delta_min
            hours_to_apply = acc // 5
            acc = acc % 60

            if hours_to_apply > 0:
                try:
                    wi = _get_work_item(wid)
                    remaining = float(_safe_get_field(wi, "Microsoft.VSTS.Scheduling.RemainingWork", 0.0) or 0.0)
                    completed = float(_safe_get_field(wi, "Microsoft.VSTS.Scheduling.CompletedWork", 0.0) or 0.0)
                    new_completed = round(completed + float(hours_to_apply), 2)
                    new_remaining = round(max(0.0, remaining - float(hours_to_apply)), 2)
                    ops = [
                        {"op": "add", "path": WORK_COMPLETED_FIELD, "value": new_completed},
                        {"op": "add", "path": WORK_REMAINING_FIELD, "value": new_remaining},
                    ]
                    _patch_work_item(wid, ops)
                except Exception:
                    logging.exception("Falha ao aplicar horas no WI %s", wid)

            ent["accumulated_minutes"] = acc
            ent["last_updated"] = _iso(now)
            tc.update_entity(ent, mode="merge")

        except Exception:
            logging.exception("Erro no tick para entidade %s", ent.get("RowKey"))
