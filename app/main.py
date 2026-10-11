import hmac
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app import auth, library, transfers
from app.config import Settings
from app.db import make_engine, migrate, now, sessions
from app.filmaffinity import FilmAffinityAdapter, MetadataUnavailable, canonical_url, lookup_url, parse_url
from app.models import Admin, BrowserSession, Category, ImportPreview, MetadataCache, Work
from app.updates import BuildInfo, UpdateChecker

ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))
templates.env.filters["score"] = lambda x: "Sin nota" if x is None else f"{x:g}".replace(".", ",")
templates.env.filters["shortdate"] = lambda x: x[:10] if x else "Desconocida"


def safe_return(value):
    if value and value.startswith("/?") and len(value) < 4000 and not any(ord(c) < 32 for c in value):
        return value
    return "/"


def create_app(settings=None, adapter=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        os.umask(0o077)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        migrate(settings.db_path)
        app.state.engine = make_engine(settings.db_path)
        app.state.db = sessions(app.state.engine)
        with app.state.db() as db:
            auth.initialize(db, settings)
        # Remove bootstrap plaintext from the long-lived settings object after first use.
        settings.initial_password = ""
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="No lo vuelvas a ver", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.adapter = adapter or FilmAffinityAdapter(settings.filmaffinity_enabled)
    app.state.build = BuildInfo.from_env()
    app.state.updates = UpdateChecker(app.state.build, settings.update_check_enabled)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    def render(request, template, status=200, **context):
        return templates.TemplateResponse(
            request=request,
            name=template,
            context={
                "build": app.state.build,
                "update_check_enabled": settings.update_check_enabled,
                "csrf": request.state.session.csrf if getattr(request.state, "session", None) else "",
                "authenticated": bool(
                    getattr(request.state, "session", None) and request.state.session.authenticated
                ),
                **context,
            },
            status_code=status,
        )

    def redirect(path):
        return RedirectResponse(path, status_code=303)

    def set_cookie(response, token):
        response.set_cookie(
            "nlvav_session",
            token,
            max_age=settings.session_hours * 3600,
            httponly=True,
            samesite="lax",
            secure=settings.secure_cookies,
            path="/",
        )

    @app.middleware("http")
    async def access(request, call_next):
        request.state.session = None
        if not request.url.path.startswith("/static/") and request.url.path != "/healthz":
            if (
                request.headers.get("content-length", "0").isdigit()
                and int(request.headers.get("content-length", "0")) > transfers.MAX_IMPORT_BYTES + 500_000
            ):
                return Response("Petición demasiado grande", status_code=413)
            with app.state.db() as db:
                token = request.cookies.get("nlvav_session", "")
                session = db.get(BrowserSession, auth.token_hash(token)) if len(token) <= 100 else None
                if session and session.expires_at > int(time.time()):
                    request.state.session = session
            if request.url.path != "/login" and not (
                request.state.session and request.state.session.authenticated
            ):
                return redirect("/login")
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        )
        if not request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    async def form(request):
        # Bound streamed/chunked bodies before parsing, even when Content-Length is absent or incorrect.
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > transfers.MAX_IMPORT_BYTES + 500_000:
                raise HTTPException(413, "Petición demasiado grande")
            chunks.append(chunk)
        request._body = b"".join(chunks)
        data = await request.form(max_files=1, max_fields=200)
        session = request.state.session
        if not session or not hmac.compare_digest(str(data.get("csrf", "")), session.csrf):
            raise HTTPException(
                403, "La sesión del formulario ha caducado. Recarga la página y vuelve a intentarlo."
            )
        return data

    def form_values(data):
        values = dict(data)
        values["category_ids"] = data.getlist("category_ids")
        return values

    def get_work(db, work_id):
        work = db.get(Work, work_id)
        if not work:
            raise HTTPException(404, "La ficha no existe.")
        return work

    def cats(db):
        return list(db.scalars(select(Category).order_by(Category.name_key)))

    def error_message(exc):
        if isinstance(exc, ValidationError):
            return " · ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in exc.errors())[:2000]
        return str(exc)

    @app.get("/healthz")
    def health():
        with app.state.engine.connect() as db:
            db.execute(text("SELECT 1 FROM alembic_version"))
        return {"status": "ok"}

    @app.get("/login")
    def login_page(request: Request):
        if request.state.session and request.state.session.authenticated:
            return redirect("/")
        with app.state.db() as db:
            token, session = auth.new_session(db, 1)
        request.state.session = session
        response = render(request, "login.html")
        set_cookie(response, token)
        return response

    @app.get("/updates")
    async def updates():
        return await run_in_threadpool(app.state.updates.check)

    @app.post("/login")
    async def login(request: Request):
        data = await form(request)
        with app.state.db() as db:
            if not auth.consume_limit(db, "login-global", 10, 300):
                return render(
                    request, "login.html", status=429, error="Demasiados intentos. Espera cinco minutos."
                )
            admin = db.get(Admin, 1)
            correct = await run_in_threadpool(
                auth.verify_password, str(data.get("password", "")), admin.password_hash
            )
            if str(data.get("username", "")) != admin.username or not correct:
                return render(request, "login.html", status=401, error="Usuario o contraseña incorrectos.")
            db.execute(
                delete(BrowserSession).where(BrowserSession.token_hash == request.state.session.token_hash)
            )
            token, _ = auth.new_session(db, settings.session_hours, authenticated=True)
        response = redirect("/")
        set_cookie(response, token)
        return response

    @app.post("/logout")
    async def logout(request: Request):
        await form(request)
        with app.state.db() as db:
            db.execute(
                delete(BrowserSession).where(BrowserSession.token_hash == request.state.session.token_hash)
            )
            db.commit()
        response = redirect("/login")
        response.delete_cookie("nlvav_session", path="/")
        return response

    @app.get("/")
    def home(request: Request):
        params = request.query_params
        with app.state.db() as db:
            try:
                result = library.search(
                    db,
                    q=params.get("q", ""),
                    kind=params.get("kind", ""),
                    category_ids=[int(x) for x in params.getlist("category")],
                    recommended=params.get("recommended") == "1",
                    minimum=params.get("minimum"),
                    maximum=params.get("maximum"),
                    unrated=params.get("unrated") == "1",
                    sort=params.get("sort", "title"),
                    page=int(params.get("page", "1")),
                )
                error = None
            except ValueError as exc:
                result, error = library.search(db), str(exc)

            def page_url(page):
                values = [(k, v) for k, v in params.multi_items() if k != "page"] + [("page", str(page))]
                return "/?" + urlencode(values)

            def kind_url(kind):
                values = [(k, v) for k, v in params.multi_items() if k not in {"kind", "page"}]
                return "/?" + urlencode(values + ([("kind", kind)] if kind else []))

            return render(
                request,
                "library.html",
                **result,
                categories=cats(db),
                params=params,
                page_url=page_url,
                kind_url=kind_url,
                return_to="/?" + str(params),
                error=error,
            )

    @app.get("/works/new")
    def new(request: Request):
        with app.state.db() as db:
            query = request.query_params.get("q", "")[:500]
            values = {"title": query, "kind": "", "fa_url": ""}
            if query.startswith(("https://", "http://")):
                values.update(title="", fa_url=query)
            return render(
                request,
                "form.html",
                values=values,
                categories=cats(db),
                work=None,
                return_to=safe_return(request.query_params.get("return_to")),
            )

    @app.post("/metadata")
    async def metadata(request: Request):
        data = await form(request)
        values = form_values(data)
        return_to = safe_return(data.get("return_to"))
        reference_url = None
        with app.state.db() as db:
            try:
                fa_id = parse_url(str(data.get("fa_url", "")))
                source_url = lookup_url(fa_id, str(data.get("fa_url", "")))
                values["fa_url"] = canonical_url(fa_id)
                reference_url = values["fa_url"]
                existing = library.by_fa(db, fa_id)
                if existing:
                    return render(request, "duplicate.html", status=409, work=existing, return_to=return_to)
                cached = db.get(MetadataCache, fa_id)
                if cached and cached.expires_at > time.time():
                    payload = json.loads(cached.payload)
                else:
                    if not auth.consume_limit(db, "metadata-interval", 1, 15) or not auth.consume_limit(
                        db, "metadata-hour", 30, 3600
                    ):
                        raise MetadataUnavailable(
                            "Espera antes de consultar otra ficha. Puedes seguir con el formulario manual."
                        )
                    payload = await run_in_threadpool(app.state.adapter.fetch, fa_id, source_url=source_url)
                    cached = db.get(MetadataCache, fa_id) or MetadataCache(fa_id=fa_id)
                    cached.payload, cached.fetched_at = json.dumps(payload, ensure_ascii=False), now()
                    cached.expires_at = int(time.time()) + 7 * 86400
                    db.add(cached)
                    db.commit()
                for field in ("title", "original_title", "year", "kind"):
                    if payload.get(field) is not None:
                        values[field] = payload[field]
                return render(
                    request,
                    "form.html",
                    values=values,
                    categories=cats(db),
                    work=None,
                    return_to=return_to,
                    metadata=payload,
                    obtained_at=cached.fetched_at,
                    notice="Vista previa: revisa los datos obtenidos y completa los que faltan. Todavía no se ha guardado ninguna ficha.",
                )
            except (ValueError, MetadataUnavailable) as exc:
                return render(
                    request,
                    "form.html",
                    values=values,
                    categories=cats(db),
                    work=None,
                    return_to=return_to,
                    error=str(exc),
                    metadata_url=reference_url if isinstance(exc, MetadataUnavailable) else None,
                    status=422,
                )

    @app.post("/works")
    async def create(request: Request):
        return await save(request)

    @app.post("/works/{work_id}/edit")
    async def edit(request: Request, work_id: int):
        return await save(request, work_id)

    async def save(request, work_id=None):
        data = await form(request)
        return_to = safe_return(data.get("return_to"))
        with app.state.db() as db:
            work = get_work(db, work_id) if work_id else None
            categories = cats(db)
            try:
                validated = library.parse_form(data, categories)
                if not work and not validated.fa_id and data.get("allow_similar") != "on":
                    matches = library.possible_matches(db, validated)
                    if matches:
                        return render(
                            request,
                            "form.html",
                            status=409,
                            values=form_values(data),
                            categories=categories,
                            work=None,
                            similar=matches,
                            return_to=return_to,
                            error="Hay posibles coincidencias. Revisa sus fichas y confirma si quieres crear otra obra.",
                        )
                if not work and data.get("metadata_confirm") == "on" and validated.fa_id:
                    cached = db.get(MetadataCache, validated.fa_id)
                    if cached:
                        from datetime import datetime

                        validated.metadata_source = "FilmAffinity"
                        validated.metadata_fetched_at = datetime.fromisoformat(cached.fetched_at)
                        validated.metadata_snapshot = json.loads(cached.payload)
                work = library.save_work(db, validated, work)
                return redirect(f"/works/{work.id}?" + urlencode({"return_to": return_to, "saved": "1"}))
            except library.DuplicateWork as exc:
                return render(request, "duplicate.html", status=409, work=exc.existing, return_to=return_to)
            except (ValueError, ValidationError) as exc:
                return render(
                    request,
                    "form.html",
                    status=422,
                    values=form_values(data),
                    categories=categories,
                    work=work,
                    return_to=return_to,
                    error=error_message(exc),
                )

    @app.get("/works/{work_id}")
    def detail(request: Request, work_id: int):
        with app.state.db() as db:
            return render(
                request,
                "detail.html",
                work=get_work(db, work_id),
                return_to=safe_return(request.query_params.get("return_to")),
            )

    @app.get("/works/{work_id}/edit")
    def edit_page(request: Request, work_id: int):
        with app.state.db() as db:
            work = get_work(db, work_id)
            values = library.work_data(work)
            values["aliases"] = "\n".join(
                a.title + (" | " + a.language if a.language else "") for a in work.aliases
            )
            values["category_ids"] = [str(c.id) for c in work.categories]
            return render(
                request,
                "form.html",
                work=work,
                values=values,
                categories=cats(db),
                return_to=safe_return(request.query_params.get("return_to")),
            )

    @app.post("/works/{work_id}/recommend")
    async def recommend(request: Request, work_id: int):
        data = await form(request)
        with app.state.db() as db:
            work = get_work(db, work_id)
            work.review.recommended = not work.review.recommended
            work.updated_at = now()
            db.commit()
        return redirect(f"/works/{work_id}?" + urlencode({"return_to": safe_return(data.get("return_to"))}))

    @app.get("/works/{work_id}/delete")
    def delete_page(request: Request, work_id: int):
        with app.state.db() as db:
            return render(
                request,
                "delete.html",
                work=get_work(db, work_id),
                return_to=safe_return(request.query_params.get("return_to")),
            )

    @app.post("/works/{work_id}/delete")
    async def delete_work(request: Request, work_id: int):
        data = await form(request)
        if data.get("confirm") != "yes":
            raise HTTPException(422, "Confirma el borrado de la ficha.")
        with app.state.db() as db:
            db.delete(get_work(db, work_id))
            db.commit()
        return redirect(safe_return(data.get("return_to")))

    @app.get("/categories")
    def categories_page(request: Request):
        with app.state.db() as db:
            return render(
                request,
                "categories.html",
                categories=[(c, library.category_count(db, c.id)) for c in cats(db)],
            )

    @app.post("/categories")
    async def categories_change(request: Request):
        data = await form(request)
        with app.state.db() as db:
            try:
                category_id = int(data.get("id", "0"))
                item = db.get(Category, category_id) if category_id else None
                if category_id and not item:
                    raise ValueError("La categoría ya no existe.")
                if data.get("action") == "delete":
                    if data.get("confirm") != "yes":
                        return render(
                            request,
                            "category_delete.html",
                            category=item,
                            count=library.category_count(db, item.id),
                        )
                    db.delete(item)
                else:
                    name = " ".join(str(data.get("name", "")).split())
                    duplicate = library.category(db, name, create=False)
                    if duplicate and (not item or duplicate.id != item.id):
                        raise ValueError("Ya existe una categoría con ese nombre.")
                    if item:
                        item.name, item.name_key = name, library.normalize(name)
                    else:
                        library.category(db, name)
                db.commit()
                return redirect("/categories")
            except (ValueError, IntegrityError) as exc:
                db.rollback()
                return render(
                    request,
                    "categories.html",
                    status=422,
                    error=str(exc) if isinstance(exc, ValueError) else "La categoría ya existe.",
                    categories=[(c, library.category_count(db, c.id)) for c in cats(db)],
                )

    @app.get("/settings")
    def settings_page(request: Request):
        return render(request, "settings.html", fa_enabled=settings.filmaffinity_enabled)

    @app.post("/password")
    async def password(request: Request):
        data = await form(request)
        with app.state.db() as db:
            try:
                if not auth.consume_limit(db, "password-global", 10, 300):
                    raise ValueError("Demasiados intentos. Espera cinco minutos.")
                admin = db.get(Admin, 1)
                if not await run_in_threadpool(
                    auth.verify_password, str(data.get("current", "")), admin.password_hash
                ):
                    raise ValueError("La contraseña actual no es correcta.")
                if data.get("new") != data.get("repeat"):
                    raise ValueError("Las contraseñas nuevas no coinciden.")
                admin.password_hash = await run_in_threadpool(auth.password_hash, str(data.get("new", "")))
                db.execute(delete(BrowserSession))
                db.commit()
                response = redirect("/login")
                response.delete_cookie("nlvav_session", path="/")
                return response
            except ValueError as exc:
                return render(
                    request,
                    "settings.html",
                    status=422,
                    fa_enabled=settings.filmaffinity_enabled,
                    error=str(exc),
                )

    @app.get("/export/{format}")
    def export(request: Request, format: str):
        with app.state.db() as db:
            if format == "json":
                content, media = transfers.export_library(db).model_dump_json(indent=2), "application/json"
            elif format == "csv":
                content, media = transfers.export_csv(db), "text/csv; charset=utf-8"
            else:
                raise HTTPException(404)
        return Response(
            content,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="no-lo-vuelvas-a-ver.{format}"'},
        )

    @app.post("/import/preview")
    async def import_preview(request: Request):
        data = await form(request)
        with app.state.db() as db:
            try:
                upload = data.get("file")
                if not upload or not hasattr(upload, "read"):
                    raise ValueError("Selecciona una exportación JSON.")
                payload = transfers.read_import(await upload.read(transfers.MAX_IMPORT_BYTES + 1))
                rows = transfers.preview_import(db, payload)
                token = secrets.token_urlsafe(32)
                db.add(
                    ImportPreview(
                        token=token,
                        session_hash=request.state.session.token_hash,
                        payload=payload.model_dump_json(),
                        expires_at=int(time.time()) + 900,
                    )
                )
                db.commit()
                return render(
                    request,
                    "import.html",
                    token=token,
                    rows=rows[:100],
                    total=len(rows),
                    conflicts=sum(bool(x) for _, x in rows),
                    category_names=payload.categories,
                )
            except ValueError as exc:
                return render(
                    request,
                    "settings.html",
                    status=422,
                    fa_enabled=settings.filmaffinity_enabled,
                    error=str(exc),
                )

    @app.post("/import/confirm")
    async def import_confirm(request: Request):
        data = await form(request)
        with app.state.db() as db:
            item = db.get(ImportPreview, str(data.get("token", "")))
            if (
                not item
                or item.session_hash != request.state.session.token_hash
                or item.expires_at < time.time()
            ):
                raise HTTPException(422, "La vista previa ha caducado. Vuelve a cargar el archivo.")
            try:
                imported, skipped = transfers.import_library(
                    db, transfers.read_import(item.payload.encode()), str(data.get("mode", "skip"))
                )
                db.delete(item)
                db.commit()
                return render(
                    request,
                    "settings.html",
                    notice=f"Importación completada: {imported} nuevas, {skipped} omitidas.",
                    fa_enabled=settings.filmaffinity_enabled,
                )
            except ValueError as exc:
                return render(
                    request,
                    "settings.html",
                    status=409,
                    error=str(exc),
                    fa_enabled=settings.filmaffinity_enabled,
                )

    return app


app = create_app()
