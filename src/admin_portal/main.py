"""FastAPI entrypoint for the CATA admin portal."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from urllib.parse import parse_qs, urlencode, urlsplit

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from src.admin_portal.formatting import (
    format_portal_datetime,
    format_portal_datetime_compact,
    format_queue_received_datetime,
)
from src.shared.config import get_settings
from src.shared.database import get_db_session
from src.workflow.taxonomy import list_active_categories, list_active_subcategories, sync_taxonomy_catalog
from src.workflow.polling import (
    build_default_draft_html,
    get_default_reply_to_addresses,
    build_reply_subject,
    ensure_default_mailbox,
    ensure_runtime_directories,
    get_message_detail,
    get_message_detail_for_view,
    get_ignore_source,
    get_reply_cc_addresses,
    get_reply_to_addresses,
    get_self_identity_addresses,
    get_recent_poll_runs,
    has_prior_sent_reply,
    list_history_messages,
    list_mailboxes,
    list_queue_messages,
    mark_message_opened,
    normalize_history_tab,
    normalize_ignored_scope,
    parse_review_form,
    parse_draft_form,
    parse_send_form,
    parse_return_to,
    poll_mailbox,
    read_body_artifact,
    read_body_html_artifact,
    read_sent_reply_records,
    regenerate_message_draft,
    save_message_draft,
    send_reply_message,
    transition_message_status,
    update_message_review,
)


settings = get_settings()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.filters["portal_datetime"] = lambda value: format_portal_datetime(value, settings.display_timezone)
templates.env.filters["portal_datetime_compact"] = lambda value: format_portal_datetime_compact(
    value, settings.display_timezone
)
templates.env.filters["queue_received_datetime"] = lambda value: format_queue_received_datetime(
    value, settings.display_timezone
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_directories(settings)
    yield


app = FastAPI(title="CATA Email Assistant", lifespan=lifespan)
PAGE_ERROR_MESSAGES = {
    "history_load_failed": "History could not be fully loaded. The app stayed online, but some data could not be read.",
    "mailbox_poll_failed": "Polling did not complete. The app stayed online, but Gmail or stored data returned an unexpected error.",
    "message_action_failed": "The requested message action could not be completed. No partial change should be assumed.",
    "message_detail_failed": "The message detail view could not be loaded. The app stayed online, but some data could not be read.",
    "message_missing": "That message is no longer available in the current view.",
    "poll_runs_load_failed": "Recent poll runs could not be fully loaded.",
    "queue_load_failed": "The queue could not be fully loaded. The app stayed online, but some data could not be read.",
    "review_save_failed": "Review changes could not be saved.",
    "send_failed": "Send failed. No response was recorded. Please try again after checking Gmail authorization.",
}


def build_queue_return_path(selected_id: int | None, filter_query: str) -> str:
    parts: list[str] = []
    if selected_id:
        parts.append(f"selected_message_id={selected_id}")
    if filter_query:
        parts.append(filter_query)
    if not parts:
        return "/queue"
    return f"/queue?{'&'.join(parts)}"


def resolve_page_error(code: str | None) -> str:
    if not code:
        return ""
    return PAGE_ERROR_MESSAGES.get(code, "An unexpected application error occurred, but the app remained online.")


def rollback_session(session: Session) -> None:
    try:
        session.rollback()
    except Exception:
        logger.exception("Database rollback failed.")


def build_redirect_url(path: str, **params: str) -> str:
    query = urlencode({key: value for key, value in params.items() if value})
    if not query:
        return path
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}{query}"


def build_next_queue_return_path(db: Session, *, current_message_id: int, return_to: str) -> str:
    parsed_return = urlsplit(return_to or "/queue")
    if parsed_return.path != "/queue":
        return return_to or "/queue"

    parsed_params = parse_qs(parsed_return.query, keep_blank_values=False)
    search_text = (parsed_params.get("search") or [""])[0].strip()
    category_raw = (parsed_params.get("category_id") or [""])[0]
    category_id = int(category_raw) if category_raw.isdigit() else None
    priority = (parsed_params.get("priority") or [""])[0].strip().lower()
    reply_needed = (parsed_params.get("reply_needed") or [""])[0].strip().lower()

    messages = list_queue_messages(
        db,
        search_text=search_text,
        category_id=category_id,
        priority=priority,
        reply_needed=reply_needed,
    )
    ids = [message.id for message in messages]

    next_selected_id: int | None = None
    if ids:
        if current_message_id in ids:
            current_index = ids.index(current_message_id)
            if current_index + 1 < len(ids):
                next_selected_id = ids[current_index + 1]
            elif current_index > 0:
                next_selected_id = ids[current_index - 1]
        else:
            next_selected_id = ids[0]

    if next_selected_id is not None:
        parsed_params["selected_message_id"] = [str(next_selected_id)]
    else:
        parsed_params.pop("selected_message_id", None)

    ordered_pairs: list[tuple[str, str]] = []
    if parsed_params.get("selected_message_id"):
        ordered_pairs.append(("selected_message_id", parsed_params["selected_message_id"][0]))
    for key in ("search", "category_id", "priority", "reply_needed"):
        value = (parsed_params.get(key) or [""])[0]
        if value:
            ordered_pairs.append((key, value))

    query = urlencode(ordered_pairs)
    if not query:
        return "/queue"
    return f"/queue?{query}"


def build_queue_context(request: Request, **overrides):
    context = {
        "request": request,
        "messages": [],
        "mailboxes": [],
        "poll_runs": [],
        "saved": request.query_params.get("saved") == "1",
        "polled": request.query_params.get("polled") == "1",
        "sent": request.query_params.get("sent") == "1",
        "ignored": request.query_params.get("ignored") == "1",
        "regenerated": request.query_params.get("regenerated") == "1",
        "send_error": request.query_params.get("send_error") or "",
        "page_error": resolve_page_error(request.query_params.get("error")),
        "selected_message": None,
        "selected_message_id": None,
        "reply_to_addresses": "",
        "reply_cc_addresses": "",
        "reply_subject": "",
        "draft_html": "",
        "selected_sent_reply_records": [],
        "selected_has_prior_reply": False,
        "selected_body_text": "",
        "selected_body_html": "",
        "return_to_queue": "/queue",
        "categories": [],
        "subcategories": [],
        "focus_queue": request.query_params.get("sent") == "1" or request.query_params.get("ignored") == "1",
        "filters": {
            "search": "",
            "category_id": "",
            "priority": "",
            "reply_needed": "",
        },
        "filter_query": "",
    }
    context.update(overrides)
    return context


def _format_participant_display(participant) -> str:
    display_name = (participant.display_name or "").strip()
    email_address = (participant.email_address or "").strip()
    if display_name and email_address:
        return f"{display_name} <{email_address}>"
    return email_address or display_name or "Unknown"


def build_original_recipient_context(message) -> dict[str, list[str] | str]:
    if message is None:
        return {
            "original_other_recipients": [],
            "original_other_recipients_label": "Also included",
        }

    self_identity_addresses = get_self_identity_addresses(message)
    reply_target_addresses = {address.strip().lower() for address in get_default_reply_to_addresses(message)}
    sender_address = ((message.from_address or "") or "").strip().lower()
    sender_display = ((message.from_display or "") or "").strip().lower()
    recipients: list[str] = []
    seen: set[str] = set()

    for participant in sorted(message.participants, key=lambda item: (item.position_index, item.id)):
        normalized_email = (participant.email_address or "").strip().lower()
        normalized_name = (participant.display_name or "").strip().lower()
        if normalized_email in self_identity_addresses:
            continue
        if normalized_email and normalized_email in reply_target_addresses:
            continue
        if sender_address and normalized_email == sender_address:
            continue
        if sender_display and normalized_name and normalized_name == sender_display:
            continue
        label = _format_participant_display(participant)
        dedupe_key = normalized_email or label.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        recipients.append(label)

    return {
        "original_other_recipients": recipients,
        "original_other_recipients_label": "Also included",
    }


def build_queue_selection_context(
    db: Session,
    *,
    selected_message,
    selected_id: int | None,
    filter_query: str,
):
    return {
        "selected_message": selected_message,
        "selected_message_id": selected_id,
        "reply_to_addresses": get_reply_to_addresses(selected_message) if selected_message else "",
        "reply_cc_addresses": get_reply_cc_addresses(selected_message) if selected_message else "",
        "reply_subject": build_reply_subject(selected_message) if selected_message else "",
        "draft_html": build_default_draft_html(selected_message) if selected_message else "",
        "selected_sent_reply_records": read_sent_reply_records(selected_message) if selected_message else [],
        "selected_has_prior_reply": has_prior_sent_reply(selected_message) if selected_message else False,
        "selected_body_text": read_body_artifact(selected_message) if selected_message else "",
        "selected_body_html": read_body_html_artifact(selected_message) if selected_message else "",
        "return_to_queue": build_queue_return_path(selected_id, filter_query),
        "categories": list_active_categories(db),
        "subcategories": list_active_subcategories(db),
        **build_original_recipient_context(selected_message),
    }


def build_history_context(request: Request, **overrides):
    tab = normalize_history_tab(request.query_params.get("tab"))
    context = {
        "request": request,
        "tab": tab,
        "history_status_options": [
            ("all", "All"),
            ("responded", "Sent/Responded"),
            ("processed", "Processed"),
            ("ignored", "Ignored"),
            ("new", "New"),
        ],
        "messages": [],
        "selected_message": None,
        "selected_message_id": None,
        "search": "",
        "ignored_scope": normalize_ignored_scope(request.query_params.get("ignored_scope")),
        "saved": request.query_params.get("saved") == "1",
        "page_error": resolve_page_error(request.query_params.get("error")),
        "return_to_history": f"/history?tab={tab}",
        "history_filter_query": "",
        "sent_reply_records": [],
        "selected_body_text": "",
        "selected_body_html": "",
        "selected_ignore_source": "",
    }
    context.update(overrides)
    return context


def build_history_selection_context(selected_message):
    return {
        "sent_reply_records": read_sent_reply_records(selected_message) if selected_message else [],
        "selected_body_text": read_body_artifact(selected_message) if selected_message else "",
        "selected_body_html": read_body_html_artifact(selected_message) if selected_message else "",
        "selected_ignore_source": get_ignore_source(selected_message) if selected_message else "",
        **build_original_recipient_context(selected_message),
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error for %s %s", request.method, request.url.path, exc_info=exc)
    return templates.TemplateResponse(
        request,
        name="error.html",
        context={
            "request": request,
            "page_title": "Something went wrong",
            "error_message": "The application hit an unexpected error, but it stayed online. Please go back and try again.",
            "back_href": "/queue",
        },
        status_code=500,
    )


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok", "app_env": settings.app_env}


@app.get("/", response_class=RedirectResponse)
def root() -> RedirectResponse:
    return RedirectResponse(url="/queue", status_code=302)


@app.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, db: Session = Depends(get_db_session)):
    search_text = (request.query_params.get("search") or "").strip()
    category_raw = request.query_params.get("category_id") or ""
    category_id = int(category_raw) if category_raw.isdigit() else None
    priority = (request.query_params.get("priority") or "").strip().lower()
    reply_needed = (request.query_params.get("reply_needed") or "").strip().lower()
    filter_params = {
        "search": search_text,
        "category_id": category_raw,
        "priority": priority,
        "reply_needed": reply_needed,
    }
    filter_query = urlencode({key: value for key, value in filter_params.items() if value})
    selected_message_id = request.query_params.get("selected_message_id")
    selected_id = int(selected_message_id) if selected_message_id and selected_message_id.isdigit() else None
    try:
        ensure_default_mailbox(db, settings)
        sync_taxonomy_catalog(db, settings.taxonomy_catalog_path)
        messages = list_queue_messages(
            db,
            search_text=search_text,
            category_id=category_id,
            priority=priority,
            reply_needed=reply_needed,
        )
        selected_message = None
        if messages:
            available_ids = {message.id for message in messages}
            if selected_id not in available_ids:
                selected_id = messages[0].id
            selected_message = get_message_detail_for_view(db, selected_id, view="queue")
            if selected_message is not None:
                mark_message_opened(db, selected_message)
        selection_context = build_queue_selection_context(
            db,
            selected_message=selected_message,
            selected_id=selected_id,
            filter_query=filter_query,
        )
        return templates.TemplateResponse(
            request,
            name="queue.html",
            context=build_queue_context(
                request,
                messages=messages,
                mailboxes=list_mailboxes(db),
                poll_runs=get_recent_poll_runs(db),
                filters=filter_params,
                filter_query=filter_query,
                **selection_context,
            ),
        )
    except Exception:
        rollback_session(db)
        logger.exception("Queue page load failed.")
        return templates.TemplateResponse(
            request,
            name="queue.html",
            context=build_queue_context(
                request,
                page_error=resolve_page_error("queue_load_failed"),
                filters=filter_params,
                filter_query=filter_query,
            ),
        )


@app.get("/queue/selection", response_class=HTMLResponse)
def queue_selection_partial(request: Request, db: Session = Depends(get_db_session)):
    selected_message_id = request.query_params.get("selected_message_id")
    selected_id = int(selected_message_id) if selected_message_id and selected_message_id.isdigit() else None
    search_text = (request.query_params.get("search") or "").strip()
    category_raw = request.query_params.get("category_id") or ""
    priority = (request.query_params.get("priority") or "").strip().lower()
    reply_needed = (request.query_params.get("reply_needed") or "").strip().lower()
    filter_query = urlencode(
        {
            key: value
            for key, value in {
                "search": search_text,
                "category_id": category_raw,
                "priority": priority,
                "reply_needed": reply_needed,
            }.items()
            if value
        }
    )
    try:
        ensure_default_mailbox(db, settings)
        sync_taxonomy_catalog(db, settings.taxonomy_catalog_path)
        selected_message = None
        if selected_id is not None:
            selected_message = get_message_detail_for_view(db, selected_id, view="queue")
            if selected_message is not None and selected_message.status == "new":
                mark_message_opened(db, selected_message)
        return templates.TemplateResponse(
            request,
            name="partials/queue_workbench.html",
            context=build_queue_selection_context(
                db,
                selected_message=selected_message,
                selected_id=selected_id,
                filter_query=filter_query,
            ),
        )
    except Exception:
        rollback_session(db)
        logger.exception("Queue selection partial failed.")
        return templates.TemplateResponse(
            request,
            name="partials/queue_workbench.html",
            context=build_queue_selection_context(
                db,
                selected_message=None,
                selected_id=selected_id,
                filter_query=filter_query,
            ),
            status_code=200,
        )


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request, db: Session = Depends(get_db_session)):
    tab = normalize_history_tab(request.query_params.get("tab"))
    search_text = (request.query_params.get("search") or "").strip()
    ignored_scope = normalize_ignored_scope(request.query_params.get("ignored_scope"))
    filter_query = urlencode(
        {
            key: value
            for key, value in {
                "tab": tab,
                "search": search_text,
                "ignored_scope": ignored_scope if tab == "ignored" else "",
            }.items()
            if value
        }
    )
    selected_message_id = request.query_params.get("selected_message_id")
    selected_id = int(selected_message_id) if selected_message_id and selected_message_id.isdigit() else None
    try:
        ensure_default_mailbox(db, settings)
        sync_taxonomy_catalog(db, settings.taxonomy_catalog_path)
        messages = list_history_messages(db, tab=tab, search_text=search_text, ignored_scope=ignored_scope)
        selected_message = None
        if messages:
            available_ids = {message.id for message in messages}
            if selected_id not in available_ids:
                selected_id = messages[0].id
            selected_message = get_message_detail_for_view(db, selected_id, view="history")
        return templates.TemplateResponse(
            request,
            name="history.html",
            context=build_history_context(
                request,
                tab=tab,
                messages=messages,
                selected_message=selected_message,
                selected_message_id=selected_id,
                search=search_text,
                ignored_scope=ignored_scope,
                history_filter_query=filter_query,
                return_to_history=f"/history?{filter_query}" if filter_query else "/history",
                selected_history_status=selected_message.status if selected_message else "",
                **build_history_selection_context(selected_message),
            ),
        )
    except Exception:
        rollback_session(db)
        logger.exception("History page load failed.")
        return templates.TemplateResponse(
            request,
            name="history.html",
            context=build_history_context(
                request,
                tab=tab,
                search=search_text,
                ignored_scope=ignored_scope,
                history_filter_query=filter_query,
                page_error=resolve_page_error("history_load_failed"),
                return_to_history=f"/history?{filter_query}" if filter_query else "/history",
            ),
        )


@app.get("/history/selection", response_class=HTMLResponse)
def history_selection_partial(request: Request, db: Session = Depends(get_db_session)):
    selected_message_id = request.query_params.get("selected_message_id")
    selected_id = int(selected_message_id) if selected_message_id and selected_message_id.isdigit() else None
    try:
        ensure_default_mailbox(db, settings)
        sync_taxonomy_catalog(db, settings.taxonomy_catalog_path)
        selected_message = None
        if selected_id is not None:
            selected_message = get_message_detail_for_view(db, selected_id, view="history")
        return templates.TemplateResponse(
            request,
            name="partials/history_workbench.html",
            context={
                "selected_message": selected_message,
                "selected_message_id": selected_id,
                **build_history_selection_context(selected_message),
            },
        )
    except Exception:
        rollback_session(db)
        logger.exception("History selection partial failed.")
        return templates.TemplateResponse(
            request,
            name="partials/history_workbench.html",
            context={
                "selected_message": None,
                "selected_message_id": selected_id,
                **build_history_selection_context(None),
            },
            status_code=200,
        )


@app.get("/poll-runs", response_class=HTMLResponse)
def poll_runs_page(request: Request, db: Session = Depends(get_db_session)):
    try:
        ensure_default_mailbox(db, settings)
        return templates.TemplateResponse(
            request,
            name="poll_runs.html",
            context={
                "request": request,
                "poll_runs": get_recent_poll_runs(db, limit=50),
                "page_error": resolve_page_error(request.query_params.get("error")),
            },
        )
    except Exception:
        rollback_session(db)
        logger.exception("Poll-runs page load failed.")
        return templates.TemplateResponse(
            request,
            name="poll_runs.html",
            context={
                "request": request,
                "poll_runs": [],
                "page_error": resolve_page_error("poll_runs_load_failed"),
            },
        )


@app.get("/messages/{message_id}", response_class=HTMLResponse)
def message_detail_page(message_id: int, request: Request, db: Session = Depends(get_db_session)):
    try:
        sync_taxonomy_catalog(db, settings.taxonomy_catalog_path)
        message = get_message_detail(db, message_id)
        if message is None:
            raise HTTPException(status_code=404, detail="Message not found.")
        mark_message_opened(db, message)
        return templates.TemplateResponse(
            request,
            name="message_detail.html",
            context={
                "request": request,
                "message": message,
                "body_text": read_body_artifact(message),
                "body_html": read_body_html_artifact(message),
                "saved": request.query_params.get("saved") == "1",
                "page_error": resolve_page_error(request.query_params.get("error")),
                "categories": list_active_categories(db),
                "subcategories": list_active_subcategories(db),
                "sent_reply_records": read_sent_reply_records(message),
                **build_original_recipient_context(message),
            },
        )
    except HTTPException:
        raise
    except Exception:
        rollback_session(db)
        logger.exception("Message detail page failed for message %s.", message_id)
        return RedirectResponse(url=build_redirect_url("/queue", error="message_detail_failed"), status_code=303)


@app.post("/mailboxes/{mailbox_id}/poll")
def poll_mailbox_action(
    mailbox_id: int,
    db: Session = Depends(get_db_session),
):
    try:
        poll_mailbox(db, settings, mailbox_id=mailbox_id, trigger_source="portal")
        return RedirectResponse(url="/queue?polled=1", status_code=303)
    except Exception:
        rollback_session(db)
        logger.exception("Mailbox poll action failed for mailbox %s.", mailbox_id)
        return RedirectResponse(url=build_redirect_url("/queue", error="mailbox_poll_failed"), status_code=303)


@app.post("/messages/{message_id}/review")
async def update_message_review_action(
    message_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
):
    message = get_message_detail(db, message_id)
    if message is None:
        return RedirectResponse(url=build_redirect_url("/queue", error="message_missing"), status_code=303)

    body = await request.body()
    return_to = parse_return_to(body, f"/messages/{message_id}")
    try:
        form_data = parse_review_form(body)
        update_message_review(db, message_id, **form_data)
        return RedirectResponse(url=build_redirect_url(return_to, saved="1"), status_code=303)
    except Exception:
        rollback_session(db)
        logger.exception("Review update failed for message %s.", message_id)
        return RedirectResponse(url=build_redirect_url(return_to, error="review_save_failed"), status_code=303)


@app.post("/messages/{message_id}/draft")
async def save_message_draft_action(message_id: int, request: Request, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        return RedirectResponse(url=build_redirect_url("/queue", error="message_missing"), status_code=303)

    body = await request.body()
    return_to = parse_return_to(body, "/queue")
    try:
        draft_data = parse_draft_form(body)
        save_message_draft(db, settings, message_id, **draft_data)
        return RedirectResponse(url=build_redirect_url(return_to, saved="1"), status_code=303)
    except Exception:
        rollback_session(db)
        logger.exception("Draft save failed for message %s.", message_id)
        return RedirectResponse(url=build_redirect_url(return_to, error="review_save_failed"), status_code=303)


@app.post("/messages/{message_id}/regenerate")
async def regenerate_message_draft_action(message_id: int, request: Request, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        return RedirectResponse(url=build_redirect_url("/queue", error="message_missing"), status_code=303)

    body = await request.body()
    return_to = parse_return_to(body, "/queue")
    try:
        regenerate_message_draft(db, settings, message_id)
        return RedirectResponse(url=build_redirect_url(return_to, regenerated="1"), status_code=303)
    except Exception:
        rollback_session(db)
        logger.exception("Draft regenerate failed for message %s.", message_id)
        return RedirectResponse(url=build_redirect_url(return_to, error="review_save_failed"), status_code=303)


@app.post("/messages/{message_id}/send")
async def send_message_action(message_id: int, request: Request, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        return RedirectResponse(url=build_redirect_url("/queue", error="message_missing"), status_code=303)

    body = await request.body()
    return_to = parse_return_to(body, "/queue")
    try:
        next_return_to = build_next_queue_return_path(db, current_message_id=message_id, return_to=return_to)
        review_data = parse_review_form(body)
        send_data = parse_send_form(body)
        update_message_review(db, message_id, **review_data)
        send_reply_message(db, settings, message_id, **send_data)
    except HttpError as exc:
        rollback_session(db)
        if exc.resp is not None and exc.resp.status == 403:
            return RedirectResponse(url=build_redirect_url(return_to, send_error="permissions"), status_code=303)
        logger.exception("Gmail send failed for message %s.", message_id)
        return RedirectResponse(url=build_redirect_url(return_to, send_error="failed"), status_code=303)
    except Exception:
        rollback_session(db)
        logger.exception("Portal send action failed for message %s.", message_id)
        return RedirectResponse(url=build_redirect_url(return_to, send_error="failed"), status_code=303)

    return RedirectResponse(url=build_redirect_url(next_return_to, sent="1"), status_code=303)


@app.post("/messages/{message_id}/ignore")
async def ignore_message_action(message_id: int, request: Request, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        return RedirectResponse(url=build_redirect_url("/queue", error="message_missing"), status_code=303)

    body = await request.body()
    return_to = parse_return_to(body, "/queue")
    try:
        next_return_to = build_next_queue_return_path(db, current_message_id=message_id, return_to=return_to)
        transition_message_status(db, message_id, "ignored")
        return RedirectResponse(url=build_redirect_url(next_return_to, ignored="1"), status_code=303)
    except Exception:
        rollback_session(db)
        logger.exception("Ignore action failed for message %s.", message_id)
        return RedirectResponse(url=build_redirect_url(return_to, error="message_action_failed"), status_code=303)


@app.post("/messages/{message_id}/reopen")
async def reopen_message_action(message_id: int, request: Request, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        return RedirectResponse(url=build_redirect_url("/queue", error="message_missing"), status_code=303)

    body = await request.body()
    return_to = parse_return_to(body, f"/messages/{message_id}")
    try:
        transition_message_status(db, message_id, "new")
        return RedirectResponse(url=build_redirect_url(return_to, saved="1"), status_code=303)
    except Exception:
        rollback_session(db)
        logger.exception("Reopen action failed for message %s.", message_id)
        return RedirectResponse(url=build_redirect_url(return_to, error="message_action_failed"), status_code=303)


@app.post("/messages/{message_id}/responded")
async def responded_message_action(message_id: int, request: Request, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        return RedirectResponse(url=build_redirect_url("/history", tab="all", error="message_missing"), status_code=303)

    body = await request.body()
    return_to = parse_return_to(body, "/history?tab=all")
    try:
        transition_message_status(db, message_id, "responded")
        return RedirectResponse(url=build_redirect_url(return_to, saved="1"), status_code=303)
    except Exception:
        rollback_session(db)
        logger.exception("Return-to-responded action failed for message %s.", message_id)
        return RedirectResponse(url=build_redirect_url(return_to, error="message_action_failed"), status_code=303)


if __name__ == "__main__":
    uvicorn.run("src.admin_portal.main:app", host=settings.app_host, port=settings.app_port, reload=settings.app_debug)
