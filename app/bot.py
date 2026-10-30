from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    Message, CallbackQuery, FSInputFile, InputMediaPhoto, InputMediaVideo,
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Lead, Certificate
from app.services.cert_generator import generate_certificate_image
from app.services.email_sender import send_certificate_email

bot = Bot(token=settings.tg_bot_token) if settings.tg_bot_token else None
dp = Dispatcher()
router = Router()
dp.include_router(router)
scheduler = AsyncIOScheduler()

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Новые заявки"), KeyboardButton(text="🗂 История заявок")],
        [KeyboardButton(text="🎁 Сертификаты")]
    ],
    resize_keyboard=True
)


def format_contact_link(c_type: str, c_val: str) -> tuple[str, str | None]:
    val = c_val.strip()
    if c_type == "phone":
        digits = "".join(filter(str.isdigit, val))
        if digits.startswith("8") and len(digits) == 11:
            digits = "7" + digits[1:]
        clean_phone = f"+{digits}" if not digits.startswith("+") else digits
        return f"{clean_phone} (нажми для звонка)", f"https://wa.me/{digits}"
    if c_type == "tg":
        username = val.lstrip("@").replace("https://t.me/", "")
        return f"@{username}", f"https://t.me/{username}"
    if c_type == "wa":
        digits = "".join(filter(str.isdigit, val))
        return val, f"https://wa.me/{digits}"
    if c_type == "vk":
        url = val if val.startswith("http") else f"https://vk.com/{val}"
        return val, url
    return val, val if val.startswith("http") else None


def lead_card_text(lead: Lead) -> str:
    status_map = {
        "new": "🆕 Новая",
        "in_work": "🛠 В работе",
        "completed": "✅ Выполнена",
        "canceled": "❌ Отменена"
    }
    contact_str, _ = format_contact_link(lead.contact_type, lead.contact_value)
    rating_str = f"\n⭐ <b>Оценка клиента:</b> {lead.rating}/5" if lead.rating else ""
    return (
        f"<b>Заявка #{lead.id}</b> ({status_map.get(lead.status, lead.status)})\n"
        f"📅 {lead.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"👤 <b>Имя:</b> {lead.name}\n"
        f"📱 <b>Связь ({lead.contact_type.upper()}):</b> {contact_str}\n"
        f"📍 <b>Район:</b> {lead.district}\n"
        f"🧹 <b>Услуга:</b> {lead.service}\n"
        f"💬 <b>Комментарий:</b> {lead.comment or '—'}"
        f"{rating_str}"
    )


def lead_inline_kb(lead: Lead) -> InlineKeyboardMarkup:
    _, url = format_contact_link(lead.contact_type, lead.contact_value)
    buttons = []
    if url:
        buttons.append([InlineKeyboardButton(text="💬 Открыть чат с клиентом", url=url)])
    buttons.append([
        InlineKeyboardButton(text="🛠 В работу", callback_data=f"lead_status:{lead.id}:in_work"),
        InlineKeyboardButton(text="🏁 Выполнено", callback_data=f"lead_status:{lead.id}:completed"),
    ])
    buttons.append([
        InlineKeyboardButton(text="📸 Показать медиа", callback_data=f"lead_media:{lead.id}"),
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"lead_status:{lead.id}:canceled"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def notify_new_lead(lead_id: int):
    if not bot or not settings.tg_admin_id:
        return
    async with SessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return

        if lead.media:
            media_group = []
            for m in lead.media[:10]:
                inp = FSInputFile(m.file_path)
                if m.media_type == "video":
                    media_group.append(InputMediaVideo(media=inp))
                else:
                    media_group.append(InputMediaPhoto(media=inp))
            msgs = await bot.send_media_group(chat_id=settings.tg_admin_id, media=media_group)
            for m_obj, sent_msg in zip(lead.media, msgs):
                if sent_msg.photo:
                    m_obj.tg_file_id = sent_msg.photo[-1].file_id
                elif sent_msg.video:
                    m_obj.tg_file_id = sent_msg.video.file_id
            await session.commit()

        await bot.send_message(
            chat_id=settings.tg_admin_id,
            text=lead_card_text(lead),
            parse_mode="HTML",
            reply_markup=lead_inline_kb(lead)
        )


async def send_review_prompt_to_admin(lead_id: int):
    if not bot or not settings.tg_admin_id:
        return
    async with SessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return
        rate_url = f"{settings.site_url}/rate/{lead.review_token}"
        msg_for_client = (
            f"Здравствуйте, {lead.name}! Спасибо, что выбрали «Чисто Екб». "
            f"Оцените, пожалуйста, нашу работу от 1 до 5 звёзд по ссылке: {rate_url}"
        )
        share_url = f"https://t.me/share/url?url={quote(rate_url)}&text={quote(msg_for_client)}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Переслать клиенту в Telegram", url=share_url)]
        ])
        await bot.send_message(
            chat_id=settings.tg_admin_id,
            text=(
                f"⭐ <b>Прошли сутки после заказа #{lead.id} ({lead.name})!</b>\n"
                f"Пора собрать отзыв.\n\n"
                f"Готовый текст для отправки клиенту:\n<code>{msg_for_client}</code>"
            ),
            parse_mode="HTML",
            reply_markup=kb
        )


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, command: CommandObject):
    if message.from_user.id != settings.tg_admin_id:
        await message.answer("Бот предназначен для проверки сертификатов мастером «Чисто Екб».")
        return

    args = command.args or ""
    if args.startswith("cert_"):
        token = args.replace("cert_", "")
        async with SessionLocal() as session:
            res = await session.execute(select(Certificate).where(Certificate.secret_token == token))
            cert = res.scalar_one_or_none()
            if not cert:
                await message.answer("❌ <b>ПОДДЕЛКА!</b> Сертификат с таким токеном не найден в базе.", parse_mode="HTML")
                return

            if cert.status == "active":
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔥 Погасить сертификат (Использован)", callback_data=f"cert_redeem:{cert.id}")]
                ])
                await message.answer(
                    f"✅ <b>Сертификат ПОДЛИННЫЙ и АКТИВЕН</b>\n\n"
                    f"🔢 <b>Код:</b> <code>{cert.code}</code>\n"
                    f"💰 <b>Номинал:</b> {cert.amount} ₽ (сгорает за 1 раз)\n"
                    f"👤 <b>Покупатель:</b> {cert.buyer_name}\n"
                    f"🎁 <b>Получатель:</b> {cert.recipient_name or '—'}",
                    parse_mode="HTML",
                    reply_markup=kb
                )
            elif cert.status == "redeemed":
                await message.answer(
                    f"⚠️ <b>Сертификат {cert.code} УЖЕ ИСПОЛЬЗОВАН!</b>\n"
                    f"Дата погашения: {cert.redeemed_at.strftime('%d.%m.%Y %H:%M')}",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"⚠️ Статус сертификата {cert.code}: <b>{cert.status}</b> (не оплачен или отклонён).",
                    parse_mode="HTML"
                )


@router.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id == settings.tg_admin_id:
        await message.answer("Добро пожаловать в панель управления «Чисто Екб»!", reply_markup=admin_kb)


@router.message(F.text == "📋 Новые заявки")
async def show_new_leads(message: Message):
    if message.from_user.id != settings.tg_admin_id:
        return
    async with SessionLocal() as session:
        res = await session.execute(
            select(Lead).where(Lead.status.in_(["new", "in_work"])).order_by(Lead.id.desc()).limit(10)
        )
        leads = res.scalars().all()
        if not leads:
            await message.answer("Активных заявок сейчас нет.")
            return
        for lead in leads:
            await message.answer(lead_card_text(lead), parse_mode="HTML", reply_markup=lead_inline_kb(lead))


@router.message(F.text == "🗂 История заявок")
async def show_history_leads(message: Message):
    if message.from_user.id != settings.tg_admin_id:
        return
    async with SessionLocal() as session:
        res = await session.execute(select(Lead).order_by(Lead.id.desc()).limit(15))
        leads = res.scalars().all()
        if not leads:
            await message.answer("История заявок пуста.")
            return
        for lead in leads:
            await message.answer(lead_card_text(lead), parse_mode="HTML", reply_markup=lead_inline_kb(lead))


@router.callback_query(F.data.startswith("lead_status:"))
async def cb_lead_status(call: CallbackQuery):
    _, lead_id_str, new_status = call.data.split(":")
    lead_id = int(lead_id_str)
    async with SessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            await call.answer("Заявка не найдена")
            return
        lead.status = new_status
        if new_status == "completed" and not lead.completed_at:
            lead.completed_at = datetime.now(timezone.utc)
            run_date = datetime.now() + timedelta(hours=24)
            scheduler.add_job(
                send_review_prompt_to_admin,
                "date",
                run_date=run_date,
                args=[lead.id],
                id=f"rev_{lead.id}",
                replace_existing=True
            )

        await session.commit()
        await call.message.edit_text(lead_card_text(lead), parse_mode="HTML", reply_markup=lead_inline_kb(lead))
        await call.answer(f"Статус изменён: {new_status}")


@router.callback_query(F.data.startswith("lead_media:"))
async def cb_lead_media(call: CallbackQuery):
    lead_id = int(call.data.split(":")[1])
    async with SessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead or not lead.media:
            await call.answer("К этой заявке нет прикреплённых фото/видео", show_alert=True)
            return
        media_group = []
        for m in lead.media[:10]:
            file_ref = m.tg_file_id or FSInputFile(m.file_path)
            if m.media_type == "video":
                media_group.append(InputMediaVideo(media=file_ref))
            else:
                media_group.append(InputMediaPhoto(media=file_ref))
        await call.message.answer_media_group(media=media_group)
        await call.answer()


@router.message(F.text == "🎁 Сертификаты")
async def list_certificates(message: Message):
    if message.from_user.id != settings.tg_admin_id:
        return
    async with SessionLocal() as session:
        res = await session.execute(select(Certificate).order_by(Certificate.id.desc()).limit(15))
        certs = res.scalars().all()
        if not certs:
            await message.answer("Сертификатов пока нет.")
            return
        for c in certs:
            kb = None
            if c.status == "active":
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔥 Погасить (Использован)", callback_data=f"cert_redeem:{c.id}")]
                ])
            elif c.status == "pending":
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Деньги пришли", callback_data=f"cert_approve:{c.id}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"cert_reject:{c.id}")
                    ]
                ])
            await message.answer(
                f"🎁 <b>Сертификат {c.code}</b>\n"
                f"Статус: <b>{c.status.upper()}</b>\n"
                f"Сумма: <b>{c.amount} ₽</b>\n"
                f"Покупатель: {c.buyer_name} ({c.contact}, {c.email})",
                parse_mode="HTML",
                reply_markup=kb
            )


@router.callback_query(F.data.startswith("cert_approve:"))
async def cb_cert_approve(call: CallbackQuery):
    cert_id = int(call.data.split(":")[1])
    async with SessionLocal() as session:
        cert = await session.get(Certificate, cert_id)
        if not cert:
            return
        cert.status = "active"
        file_path = generate_certificate_image(cert)
        cert.file_path = file_path
        await session.commit()

        email_sent = await send_certificate_email(cert, file_path)
        email_note = "📧 Отправлен клиенту на Email." if email_sent else "⚠️ SMTP не настроен — перешлите файл клиенту вручную."

        await call.message.edit_text(
            f"✅ <b>Оплата подтверждена! Сертификат {cert.code} на {cert.amount} ₽ выпущен.</b>\n"
            f"Покупатель: {cert.buyer_name} ({cert.contact} / {cert.email})\n"
            f"{email_note}",
            parse_mode="HTML"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Погасить при визите", callback_data=f"cert_redeem:{cert.id}")]
        ])
        await call.message.answer_photo(
            photo=FSInputFile(file_path),
            caption=f"🎁 Готовый сертификат <code>{cert.code}</code> для клиента ({cert.email} / {cert.contact}).",
            parse_mode="HTML",
            reply_markup=kb
        )
        await call.answer("Сертификат сгенерирован!")


@router.callback_query(F.data.startswith("cert_reject:"))
async def cb_cert_reject(call: CallbackQuery):
    cert_id = int(call.data.split(":")[1])
    async with SessionLocal() as session:
        cert = await session.get(Certificate, cert_id)
        if cert:
            cert.status = "rejected"
            await session.commit()
            await call.message.edit_text(f"❌ Запрос на сертификат #{cert.id} от {cert.buyer_name} отклонён.")
    await call.answer()


@router.callback_query(F.data.startswith("cert_redeem:"))
async def cb_cert_redeem(call: CallbackQuery):
    cert_id = int(call.data.split(":")[1])
    async with SessionLocal() as session:
        cert = await session.get(Certificate, cert_id)
        if not cert:
            return
        if cert.status == "redeemed":
            await call.answer("Уже погашен ранее!", show_alert=True)
            return
        cert.status = "redeemed"
        cert.redeemed_at = datetime.now(timezone.utc)
        await session.commit()
        await call.message.answer(
            f"🔥 <b>Сертификат {cert.code} ({cert.amount} ₽) официально ПОГАШЕН!</b>\n"
            f"Повторное использование заблокировано.",
            parse_mode="HTML"
        )
        await call.answer("Сертификат погашен!")