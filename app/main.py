import os
import random
import shutil
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from app.config import settings
from app.database import init_db, SessionLocal
from app.models import Lead, LeadMedia, Certificate
from app.data import SITE_DATA
from app.bot import bot, dp, scheduler, notify_new_lead

os.makedirs("app/static/uploads/leads", exist_ok=True)
os.makedirs("app/static/uploads/certs", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.start()
    polling_task = None
    if bot:
        polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    if polling_task:
        polling_task.cancel()
    scheduler.shutdown()


app = FastAPI(title="Чисто Екб", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            **SITE_DATA,
            "payment": {
                "phone": settings.payment_phone,
                "bank": settings.payment_bank,
                "recipient": settings.payment_recipient,
            }
        },
    )


@app.post("/api/lead")
async def create_lead(
    name: str = Form(...),
    contact_type: str = Form("phone"),
    contact_value: str = Form(...),
    district: str = Form(...),
    service: str = Form(...),
    desc: str = Form(""),
    media: list[UploadFile] = File(default=[]),
):
    async with SessionLocal() as session:
        lead = Lead(
            name=name.strip(),
            contact_type=contact_type,
            contact_value=contact_value.strip(),
            district=district,
            service=service,
            comment=desc.strip(),
        )
        session.add(lead)
        await session.flush()

        for file in media:
            if not file.filename:
                continue
            ext = os.path.splitext(file.filename)[1].lower()
            m_type = "video" if ext in [".mp4", ".mov", ".webm", ".avi"] else "photo"
            save_path = f"app/static/uploads/leads/lead_{lead.id}_{random.randint(1000, 9999)}{ext}"
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            session.add(LeadMedia(lead_id=lead.id, file_path=save_path, media_type=m_type))

        await session.commit()
        lead_id = lead.id

    asyncio.create_task(notify_new_lead(lead_id))
    return JSONResponse({"ok": True})


@app.post("/api/certificate")
async def order_certificate(
    buyer_name: str = Form(...),
    recipient_name: str = Form(""),
    email: str = Form(...),
    contact: str = Form(...),
    amount: int = Form(...),
):
    if amount < 1000:
        return JSONResponse({"ok": False, "error": "Минимальная сумма — 1000 ₽"}, status_code=400)

    code = f"CHISTO-{random.randint(1000, 9999)}"
    async with SessionLocal() as session:
        cert = Certificate(
            code=code,
            buyer_name=buyer_name.strip(),
            recipient_name=recipient_name.strip() or None,
            email=email.strip(),
            contact=contact.strip(),
            amount=amount,
            status="pending",
        )
        session.add(cert)
        await session.commit()

        if bot and settings.tg_admin_id:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, выпустить сертификат", callback_data=f"cert_approve:{cert.id}"),
                    InlineKeyboardButton(text="❌ Нет, отклонить", callback_data=f"cert_reject:{cert.id}"),
                ]
            ])
            await bot.send_message(
                chat_id=settings.tg_admin_id,
                text=(
                    f"💳 <b>Запрос на подарочный сертификат!</b>\n\n"
                    f"💰 <b>Сумма:</b> {cert.amount} ₽\n"
                    f"👤 <b>От кого:</b> {cert.buyer_name}\n"
                    f"🎁 <b>Кому:</b> {cert.recipient_name or 'Не указано'}\n"
                    f"📧 <b>Почта:</b> {cert.email}\n"
                    f"📱 <b>Связь:</b> {cert.contact}\n\n"
                    f"<b>Пришли ли деньги ({cert.amount} ₽) от {cert.buyer_name}?</b>"
                ),
                parse_mode="HTML",
                reply_markup=kb,
            )

    return JSONResponse({"ok": True})


@app.get("/rate/{token}", response_class=HTMLResponse)
async def rate_page(request: Request, token: str):
    async with SessionLocal() as session:
        res = await session.execute(select(Lead).where(Lead.review_token == token))
        lead = res.scalar_one_or_none()
        if not lead:
            return HTMLResponse("Ссылка недействительна", status_code=404)

        return templates.TemplateResponse(
            request=request,
            name="rate.html",
            context={
                "lead": lead,
                "links": {
                    "avito": settings.review_avito_url,
                    "dgis": settings.review_2gis_url,
                    "yandex": settings.review_yandex_url,
                },
            },
        )

@app.get("/services/{slug}", response_class=HTMLResponse)
async def service_detail(request: Request, slug: str):
    # Ищем услугу по slug в нашей коллекции
    service = next((s for s in SITE_DATA["services"] if s["slug"] == slug), None)
    if not service:
        return HTMLResponse("Услуга не найдена", status_code=404)
    
    return templates.TemplateResponse(
        request=request,
        name="service_detail.html",
        context={
            **SITE_DATA,
            "service": service,
        },
    )

@app.post("/api/rate/{token}")
async def submit_rating(token: str, rating: int = Form(...), feedback: str = Form("")):
    async with SessionLocal() as session:
        res = await session.execute(select(Lead).where(Lead.review_token == token))
        lead = res.scalar_one_or_none()
        if not lead:
            return JSONResponse({"ok": False}, status_code=404)

        lead.rating = rating
        if feedback:
            lead.negative_feedback = feedback.strip()
        await session.commit()

        if bot and settings.tg_admin_id:
            if rating <= 3:
                await bot.send_message(
                    chat_id=settings.tg_admin_id,
                    text=(
                        f"🚨 <b>ПЕРЕХВАЧЕН НЕГАТИВНЫЙ ОТЗЫВ ({rating} ★)</b>\n"
                        f"Заявка #{lead.id} — {lead.name} ({lead.contact_value})\n"
                        f"Услуга: {lead.service}\n\n"
                        f"💬 <b>Что не понравилось:</b>\n{lead.negative_feedback or 'Без комментария'}"
                    ),
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    chat_id=settings.tg_admin_id,
                    text=f"🌟 Клиент <b>{lead.name}</b> (заявка #{lead.id}) поставил <b>{rating} ★</b> и был перенаправлен на карты/Авито!",
                    parse_mode="HTML",
                )

    return JSONResponse({"ok": True})