import logging
from email.message import EmailMessage
import aiosmtplib
from app.config import settings
from app.models import Certificate

logger = logging.getLogger("uvicorn.error")


async def send_certificate_email(cert: Certificate, file_path: str) -> bool:
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        logger.info("SMTP не настроен, пропуск отправки сертификата %s на почту.", cert.code)
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_user
    msg["To"] = cert.email
    msg["Subject"] = f"Ваш подарочный сертификат «Чисто Екб» на {cert.amount} ₽"

    msg.set_content(
        f"Здравствуйте, {cert.buyer_name}!\n\n"
        f"Оплата успешно подтверждена. Во вложении — ваш именной подарочный сертификат «Чисто Екб».\n"
        f"• Код сертификата: {cert.code}\n"
        f"• Номинал: {cert.amount} ₽ (действует единовременно на любые услуги)\n\n"
        f"Для записи на уборку, мытьё окон или химчистку просто назовите этот код или покажите QR-код мастеру.\n"
        f"Телефон: {settings.payment_phone}\n"
        f"Сайт: {settings.site_url}\n"
    )

    with open(file_path, "rb") as f:
        file_data = f.read()
    msg.add_attachment(file_data, maintype="image", subtype="png", filename=f"{cert.code}.png")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            use_tls=True,
            username=settings.smtp_user,
            password=settings.smtp_password,
        )
        return True
    except Exception as exc:
        logger.error("Ошибка отправки письма с сертификатом: %s", exc)
        return False