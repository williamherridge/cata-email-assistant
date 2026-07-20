"""FastAPI entrypoint for the CATA admin portal."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
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
    build_reply_subject,
    ensure_default_mailbox,
    ensure_runtime_directories,
    get_message_detail,
    get_reply_cc_addresses,
    get_reply_to_addresses,
    get_recent_poll_runs,
    list_mailboxes,
    list_queue_messages,
    mark_message_opened,
    parse_review_form,
    parse_return_to,
    poll_mailbox,
    read_body_artifact,
    transition_message_status,
    update_message_review,
)


settings = get_settings()
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


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok", "app_env": settings.app_env}


@app.get("/", response_class=RedirectResponse)
def root() -> RedirectResponse:
    return RedirectResponse(url="/queue", status_code=302)


@app.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, db: Session = Depends(get_db_session)):
    ensure_default_mailbox(db, settings)
    sync_taxonomy_catalog(db, settings.taxonomy_catalog_path)
    messages = list_queue_messages(db)
    selected_message = None
    selected_message_id = request.query_params.get("selected_message_id")
    selected_id = int(selected_message_id) if selected_message_id and selected_message_id.isdigit() else None
    if messages:
        available_ids = {message.id for message in messages}
        if selected_id not in available_ids:
            selected_id = messages[0].id
        selected_message = get_message_detail(db, selected_id)
        if selected_message is not None:
            mark_message_opened(db, selected_message)

    return templates.TemplateResponse(
        request,
        name="queue.html",
        context={
            "request": request,
            "messages": messages,
            "mailboxes": list_mailboxes(db),
            "poll_runs": get_recent_poll_runs(db),
            "saved": request.query_params.get("saved") == "1",
            "polled": request.query_params.get("polled") == "1",
            "selected_message": selected_message,
            "selected_message_id": selected_id,
            "reply_to_addresses": get_reply_to_addresses(selected_message) if selected_message else "",
            "reply_cc_addresses": get_reply_cc_addresses(selected_message) if selected_message else "",
            "reply_subject": build_reply_subject(selected_message) if selected_message else "",
            "draft_html": build_default_draft_html(selected_message) if selected_message else "",
            "selected_body_text": read_body_artifact(selected_message) if selected_message else "",
            "return_to_queue": f"/queue?selected_message_id={selected_id}" if selected_id else "/queue",
            "categories": list_active_categories(db),
            "subcategories": list_active_subcategories(db),
        },
    )


@app.get("/poll-runs", response_class=HTMLResponse)
def poll_runs_page(request: Request, db: Session = Depends(get_db_session)):
    ensure_default_mailbox(db, settings)
    return templates.TemplateResponse(
        request,
        name="poll_runs.html",
        context={
            "request": request,
            "poll_runs": get_recent_poll_runs(db, limit=50),
        },
    )


@app.get("/messages/{message_id}", response_class=HTMLResponse)
def message_detail_page(message_id: int, request: Request, db: Session = Depends(get_db_session)):
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
            "saved": request.query_params.get("saved") == "1",
            "categories": list_active_categories(db),
            "subcategories": list_active_subcategories(db),
        },
    )


@app.post("/mailboxes/{mailbox_id}/poll")
def poll_mailbox_action(
    mailbox_id: int,
    db: Session = Depends(get_db_session),
):
    poll_mailbox(db, settings, mailbox_id=mailbox_id, trigger_source="portal")
    return RedirectResponse(url="/queue?polled=1", status_code=303)


@app.post("/messages/{message_id}/review")
async def update_message_review_action(
    message_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
):
    message = get_message_detail(db, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")

    body = await request.body()
    form_data = parse_review_form(body)
    return_to = parse_return_to(body, f"/messages/{message_id}?saved=1")
    update_message_review(db, message_id, **form_data)
    separator = "&" if "?" in return_to else "?"
    return RedirectResponse(url=f"{return_to}{separator}saved=1", status_code=303)


@app.post("/messages/{message_id}/ignore")
async def ignore_message_action(message_id: int, request: Request, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")

    body = await request.body()
    return_to = parse_return_to(body, "/queue")
    transition_message_status(db, message_id, "ignored")
    separator = "&" if "?" in return_to else "?"
    return RedirectResponse(url=f"{return_to}{separator}saved=1", status_code=303)


@app.post("/messages/{message_id}/reopen")
async def reopen_message_action(message_id: int, request: Request, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")

    body = await request.body()
    return_to = parse_return_to(body, f"/messages/{message_id}")
    transition_message_status(db, message_id, "new")
    separator = "&" if "?" in return_to else "?"
    return RedirectResponse(url=f"{return_to}{separator}saved=1", status_code=303)


if __name__ == "__main__":
    uvicorn.run("src.admin_portal.main:app", host=settings.app_host, port=settings.app_port, reload=settings.app_debug)
