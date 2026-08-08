"""Read/write Cursor Agent model settings via state.vscdb (no UI clicking).

Cursor stores the selected Agents/Composer model in:
  %APPDATA%/Cursor/User/globalStorage/state.vscdb
under reactive storage key applicationUser → aiSettings.modelConfig.composer
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REACTIVE_KEY = (
    "src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl"
    ".persistentStorage.applicationUser"
)


def cursor_state_db_path() -> Path:
    return Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


@dataclass
class ModelMatch:
    model_id: str
    display_name: str
    score: int
    parameter_ids: List[str]


@dataclass
class ComposerModelState:
    model_id: str
    display_name: str
    effort: Optional[str]
    max_mode: bool
    raw: Dict[str, Any]


def _connect(db: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
    else:
        con = sqlite3.connect(str(db), timeout=10)
    con.execute("PRAGMA busy_timeout = 8000")
    return con


def _load_reactive(con: sqlite3.Connection) -> Dict[str, Any]:
    row = con.execute(
        "SELECT value FROM ItemTable WHERE key = ?", (REACTIVE_KEY,)
    ).fetchone()
    if not row or row[0] is None:
        raise RuntimeError("Cursor reactive storage not found in state.vscdb")
    raw = row[0]
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def _save_reactive(con: sqlite3.Connection, data: Dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    con.execute(
        "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
        (REACTIVE_KEY, payload),
    )
    con.commit()


def list_available_models(db: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = db or cursor_state_db_path()
    con = _connect(path, readonly=True)
    try:
        data = _load_reactive(con)
        return list(data.get("availableDefaultModels2") or [])
    finally:
        con.close()


def get_composer_model(db: Optional[Path] = None) -> ComposerModelState:
    path = db or cursor_state_db_path()
    con = _connect(path, readonly=True)
    try:
        data = _load_reactive(con)
        composer = (
            (data.get("aiSettings") or {})
            .get("modelConfig", {})
            .get("composer", {})
        )
        model_id = str(composer.get("modelName") or "")
        display = model_id
        for m in data.get("availableDefaultModels2") or []:
            if m.get("name") == model_id:
                display = m.get("clientDisplayName") or m.get("inputboxShortModelName") or model_id
                break
        effort = None
        for sm in composer.get("selectedModels") or []:
            for p in sm.get("parameters") or []:
                if p.get("id") == "effort":
                    effort = str(p.get("value"))
        return ComposerModelState(
            model_id=model_id,
            display_name=display,
            effort=effort,
            max_mode=bool(composer.get("maxMode")),
            raw=composer,
        )
    finally:
        con.close()


def resolve_model(query: str, models: Optional[List[Dict[str, Any]]] = None) -> ModelMatch:
    models = models if models is not None else list_available_models()
    q = (query or "").strip()
    if not q:
        raise ValueError("Empty model query")
    qn = _normalize(q)
    scored: List[Tuple[int, Dict[str, Any]]] = []

    for m in models:
        name = str(m.get("name") or "")
        display = str(m.get("clientDisplayName") or "")
        short = str(m.get("inputboxShortModelName") or "")
        aliases = [str(a) for a in (m.get("idAliases") or [])]
        candidates = [name, display, short, *aliases]
        norms = [_normalize(c) for c in candidates if c]
        score = 0
        if any(n == qn for n in norms):
            score = 1000
        elif any(n.startswith(qn) for n in norms):
            score = 800
        elif any(qn in n for n in norms):
            score = 600
        else:
            # token-ish: "sonnet 5" vs "claudesonnet5"
            tokens = [t for t in re.split(r"[^a-z0-9]+", q.lower()) if t]
            if tokens and all(_normalize(t) in _normalize(name + display) for t in tokens):
                score = 500 + len(tokens) * 10
        if score:
            # Prefer newer / exact display matches slightly
            if _normalize(display) == qn:
                score += 50
            scored.append((score, m))

    if not scored:
        names = [
            f"{m.get('clientDisplayName') or m.get('name')} ({m.get('name')})"
            for m in models[:25]
        ]
        raise ValueError(
            f"No Cursor model matched '{query}'. Examples: " + ", ".join(names)
        )

    scored.sort(key=lambda x: (-x[0], str(x[1].get("name") or "")))
    best_score, best = scored[0]
    param_ids = [str(p.get("id")) for p in (best.get("parameterDefinitions") or []) if p.get("id")]
    return ModelMatch(
        model_id=str(best["name"]),
        display_name=str(best.get("clientDisplayName") or best["name"]),
        score=best_score,
        parameter_ids=param_ids,
    )


def _build_composer_config(
    model: ModelMatch,
    *,
    effort: Optional[str] = None,
    max_mode: bool = False,
    previous: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    prev = previous or {}
    params: List[Dict[str, str]] = []

    # Preserve previous effort/fast when the new model supports them
    prev_params: Dict[str, str] = {}
    for sm in prev.get("selectedModels") or []:
        for p in sm.get("parameters") or []:
            if p.get("id") is not None and p.get("value") is not None:
                prev_params[str(p["id"])] = str(p["value"])

    if effort:
        effort_val = effort.lower()
    else:
        effort_val = prev_params.get("effort", "medium")

    if "effort" in model.parameter_ids:
        params.append({"id": "effort", "value": effort_val})
    if "fast" in model.parameter_ids:
        params.append({"id": "fast", "value": prev_params.get("fast", "false")})

    return {
        "modelName": model.model_id,
        "maxMode": bool(max_mode if max_mode is not None else prev.get("maxMode", False)),
        "selectedModels": [
            {
                "modelId": model.model_id,
                "parameters": params,
            }
        ],
    }


def set_composer_model(
    query: str,
    *,
    effort: Optional[str] = None,
    max_mode: Optional[bool] = None,
    db: Optional[Path] = None,
    backup: bool = True,
) -> Dict[str, Any]:
    """Resolve model by name and write it into Cursor's global state DB."""
    path = db or cursor_state_db_path()
    if not path.exists():
        raise FileNotFoundError(f"Cursor state DB not found: {path}")

    if backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = path.with_name(f"state.vscdb.marianaos-bak-{stamp}")
        try:
            shutil.copy2(path, bak)
        except Exception:
            bak = None
    else:
        bak = None

    con = _connect(path, readonly=False)
    try:
        data = _load_reactive(con)
        models = list(data.get("availableDefaultModels2") or [])
        match = resolve_model(query, models)
        ai = data.setdefault("aiSettings", {})
        cfg = ai.setdefault("modelConfig", {})
        previous = dict(cfg.get("composer") or {})
        new_cfg = _build_composer_config(
            match,
            effort=effort,
            max_mode=bool(previous.get("maxMode")) if max_mode is None else max_mode,
            previous=previous,
        )
        cfg["composer"] = new_cfg
        _save_reactive(con, data)
        return {
            "ok": True,
            "query": query,
            "model_id": match.model_id,
            "display_name": match.display_name,
            "score": match.score,
            "composer": new_cfg,
            "previous": previous,
            "db": str(path),
            "backup": str(bak) if bak else None,
        }
    finally:
        con.close()


def set_composer_effort(
    effort: str,
    *,
    db: Optional[Path] = None,
    backup: bool = True,
) -> Dict[str, Any]:
    effort_val = effort.strip().lower()
    if effort_val not in {"low", "medium", "high", "xhigh", "max"}:
        raise ValueError("effort must be Low/Medium/High (or xhigh/max)")

    path = db or cursor_state_db_path()
    if backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            shutil.copy2(path, path.with_name(f"state.vscdb.marianaos-bak-{stamp}"))
        except Exception:
            pass

    con = _connect(path, readonly=False)
    try:
        data = _load_reactive(con)
        ai = data.setdefault("aiSettings", {})
        cfg = ai.setdefault("modelConfig", {})
        composer = dict(cfg.get("composer") or {})
        model_id = str(composer.get("modelName") or "default")
        selected = list(composer.get("selectedModels") or [])
        if not selected:
            selected = [{"modelId": model_id, "parameters": []}]
        sm = dict(selected[0])
        params = [dict(p) for p in (sm.get("parameters") or [])]
        found = False
        for p in params:
            if p.get("id") == "effort":
                p["value"] = effort_val
                found = True
        if not found:
            params.append({"id": "effort", "value": effort_val})
        sm["parameters"] = params
        sm["modelId"] = model_id
        composer["selectedModels"] = [sm]
        composer["modelName"] = model_id
        cfg["composer"] = composer
        _save_reactive(con, data)
        return {
            "ok": True,
            "effort": effort_val,
            "model_id": model_id,
            "composer": composer,
            "db": str(path),
        }
    finally:
        con.close()


def workspace_storage_dir() -> Path:
    return Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "workspaceStorage"


def list_models_brief() -> List[Dict[str, str]]:
    """Short list of models for the agent (id + display name)."""
    out: List[Dict[str, str]] = []
    for m in list_available_models():
        out.append(
            {
                "id": str(m.get("name") or ""),
                "name": str(m.get("clientDisplayName") or m.get("name") or ""),
                "short": str(m.get("inputboxShortModelName") or ""),
            }
        )
    return out


def list_chats(
    query: Optional[str] = None,
    *,
    limit: int = 30,
    include_archived: bool = False,
) -> List[Dict[str, Any]]:
    """List recent Cursor Agent/Composer chats from composer.composerHeaders."""
    path = cursor_state_db_path()
    con = _connect(path, readonly=True)
    try:
        row = con.execute(
            "SELECT value FROM ItemTable WHERE key = ?",
            ("composer.composerHeaders",),
        ).fetchone()
        if not row:
            return []
        raw = row[0] if isinstance(row[0], str) else row[0].decode("utf-8", "replace")
        data = json.loads(raw)
        composers = list(data.get("allComposers") or [])
    finally:
        con.close()

    qn = _normalize(query or "")
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for c in composers:
        if not isinstance(c, dict):
            continue
        if c.get("isDraft"):
            continue
        if not include_archived and c.get("isArchived"):
            continue
        # Skip spawned explore subagents unless searched specifically
        if c.get("subagentInfo") and not qn:
            continue
        name = str(c.get("name") or "")
        subtitle = str(c.get("subtitle") or "")
        cid = str(c.get("composerId") or "")
        ws = c.get("workspaceIdentifier") or {}
        ws_id = str(ws.get("id") or "") if isinstance(ws, dict) else ""
        ws_path = ""
        if isinstance(ws, dict):
            uri = ws.get("uri") or {}
            if isinstance(uri, dict):
                ws_path = str(uri.get("fsPath") or "")
        hay = f"{name} {subtitle} {cid}"
        score = 1
        if qn:
            hn = _normalize(hay)
            if qn == _normalize(name):
                score = 1000
            elif qn in hn:
                score = 500 + hn.count(qn)
            else:
                tokens = [t for t in re.split(r"[^a-z0-9]+", (query or "").lower()) if t]
                if tokens and all(_normalize(t) in hn for t in tokens):
                    score = 200
                else:
                    continue
        updated = int(c.get("conversationCheckpointLastUpdatedAt") or c.get("createdAt") or 0)
        scored.append(
            (
                score,
                {
                    "composer_id": cid,
                    "name": name,
                    "subtitle": subtitle[:160],
                    "mode": c.get("unifiedMode"),
                    "updated_at": updated,
                    "workspace_id": ws_id,
                    "workspace_path": ws_path,
                    "is_archived": bool(c.get("isArchived")),
                },
            )
        )

    # Sort by match score then recency
    scored.sort(key=lambda x: (-x[0], -int(x[1].get("updated_at") or 0)))
    return [item for _, item in scored[: max(1, min(limit, 100))]]


def open_chat_session(composer_id: str) -> Dict[str, Any]:
    """
    Focus a past chat by writing selectedComposerIds in that chat's workspace DB.
    Cursor usually needs a window reload to show it.
    """
    cid = (composer_id or "").strip()
    if not cid:
        raise ValueError("composer_id is required")

    chats = list_chats(cid, limit=5, include_archived=True)
    match = next((c for c in chats if c.get("composer_id") == cid), None)
    if not match:
        # fallback: scan headers without query filter for exact id
        all_hits = list_chats(None, limit=100, include_archived=True)
        # list_chats without query skips subagents and limits — do direct lookup
        path = cursor_state_db_path()
        con = _connect(path, readonly=True)
        try:
            row = con.execute(
                "SELECT value FROM ItemTable WHERE key = ?",
                ("composer.composerHeaders",),
            ).fetchone()
            raw = row[0] if isinstance(row[0], str) else row[0].decode("utf-8", "replace")
            composers = json.loads(raw).get("allComposers") or []
        finally:
            con.close()
        for c in composers:
            if isinstance(c, dict) and str(c.get("composerId")) == cid:
                ws = c.get("workspaceIdentifier") or {}
                uri = (ws.get("uri") or {}) if isinstance(ws, dict) else {}
                match = {
                    "composer_id": cid,
                    "name": c.get("name"),
                    "workspace_id": (ws.get("id") if isinstance(ws, dict) else ""),
                    "workspace_path": uri.get("fsPath") if isinstance(uri, dict) else "",
                }
                break
    if not match:
        raise ValueError(f"Chat not found: {cid}")

    ws_id = str(match.get("workspace_id") or "")
    if not ws_id:
        raise RuntimeError("Chat has no workspace_id; cannot open via DB")

    ws_db = workspace_storage_dir() / ws_id / "state.vscdb"
    if not ws_db.exists():
        raise FileNotFoundError(f"Workspace DB missing: {ws_db}")

    con = _connect(ws_db, readonly=False)
    try:
        row = con.execute(
            "SELECT value FROM ItemTable WHERE key = ?",
            ("composer.composerData",),
        ).fetchone()
        if row and row[0]:
            raw = row[0] if isinstance(row[0], str) else row[0].decode("utf-8", "replace")
            data = json.loads(raw)
        else:
            data = {}
        data["selectedComposerIds"] = [cid]
        focused = list(data.get("lastFocusedComposerIds") or [])
        data["lastFocusedComposerIds"] = [cid] + [x for x in focused if x != cid][:9]
        data["hasMigratedComposerData"] = True
        data["hasMigratedMultipleComposers"] = True
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        con.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
            ("composer.composerData", payload),
        )
        con.commit()
    finally:
        con.close()

    return {
        "ok": True,
        "composer_id": cid,
        "name": match.get("name"),
        "workspace_id": ws_id,
        "workspace_path": match.get("workspace_path"),
        "workspace_db": str(ws_db),
    }
