"""FastAPI entrypoint for the CATA admin portal."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.shared.config import get_settings
from src.shared.database import get_db_session
from src.workflow.polling import (
    ensure_default_mailbox,
    ensure_runtime_directories,
    get_message_detail,
    get_recent_poll_runs,
    list_mailboxes,
    list_queue_messages,
    mark_message_opened,
    parse_review_form,
    poll_mailbox,
    read_body_artifact,
    transition_message_status,
    update_message_review,
)


settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


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
    return templates.TemplateResponse(
        request,
        name="queue.html",
        context={
            "request": request,
            "messages": list_queue_messages(db),
            "mailboxes": list_mailboxes(db),
            "poll_runs": get_recent_poll_runs(db),
            "saved": request.query_params.get("saved") == "1",
            "polled": request.query_params.get("polled") == "1",
        },
    )


@app.get("/messages/{message_id}", response_class=HTMLResponse)
def message_detail_page(message_id: int, request: Request, db: Session = Depends(get_db_session)):
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

    form_data = parse_review_form(await request.body())
    update_message_review(db, message_id, **form_data)
    return RedirectResponse(url=f"/messages/{message_id}?saved=1", status_code=303)


@app.post("/messages/{message_id}/ignore")
def ignore_message_action(message_id: int, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")

    transition_message_status(db, message_id, "ignored")
    return RedirectResponse(url="/queue?saved=1", status_code=303)


@app.post("/messages/{message_id}/reopen")
def reopen_message_action(message_id: int, db: Session = Depends(get_db_session)):
    message = get_message_detail(db, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")

    transition_message_status(db, message_id, "new")
    return RedirectResponse(url=f"/messages/{message_id}?saved=1", status_code=303)


if __name__ == "__main__":
    uvicorn.run("src.admin_portal.main:app", host=settings.app_host, port=settings.app_port, reload=settings.app_debug)
