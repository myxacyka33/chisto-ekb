import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from app.config import settings
from app.models import Certificate

os.makedirs("app/static/uploads/certs", exist_ok=True)

def generate_certificate_image(cert: Certificate) -> str:
    width, height = 1200, 675
    img = Image.new("RGB", (width, height), "#123A5C")
    draw = ImageDraw.Draw(img)

    # Внутренняя светлая карточка
    draw.rounded_rectangle([40, 40, width - 40, height - 40], radius=28, fill="#F3F8FD", outline="#3FA9F5", width=4)

    # Загружаем шрифты
    try:
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44) # Чуть уменьшили для длинных названий
        font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        font_lg = font_md = font_sm = ImageFont.load_default()

    # Текстовый блок (аккуратные вертикальные отступы)
    draw.text((80, 70), "ЧИСТО ЕКБ ♥", fill="#3FA9F5", font=font_md)
    draw.text((80, 125), "ПОДАРОЧНЫЙ СЕРТИФИКАТ", fill="#123A5C", font=font_lg)
    draw.text((80, 205), f"Номинал: {cert.amount} ₽", fill="#1B4B7A", font=font_md)

    current_y = 265
    if cert.recipient_name:
        draw.text((80, current_y), f"Для кого: {cert.recipient_name}", fill="#152233", font=font_md)
        current_y += 55

    draw.text((80, current_y), f"Код сертификата: {cert.code}", fill="#123A5C", font=font_md)
    
    # Нижний информационный блок
    draw.text((80, 470), "Действует на мытьё окон, химчистку и уборку в Екатеринбурге.", fill="#5A7288", font=font_sm)
    draw.text((80, 505), "Сертификат используется единовременно на всю сумму.", fill="#5A7288", font=font_sm)
    draw.text((80, 540), f"Запись по тел.: {settings.payment_phone} | chisto-ekb96.ru", fill="#123A5C", font=font_sm)

    # Уменьшаем QR-код до 200x200 и смещаем правее/ниже, чтобы он свободно умещался в правой части
    verify_url = f"https://t.me/{settings.tg_bot_username}?start=cert_{cert.secret_token}"
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#123A5C", back_color="#FFFFFF").convert("RGB")
    qr_img = qr_img.resize((200, 200))

    # Координаты вставки QR-кода (теперь он правее текста и не перекрывает его)
    qr_x = width - 300
    qr_y = 140
    img.paste(qr_img, (qr_x, qr_y))
    
    # Подпись под QR-кодом
    draw.text((qr_x - 15, qr_y + 215), "Проверка подлинности", fill="#5A7288", font=font_sm)

    file_path = f"app/static/uploads/certs/{cert.code}.png"
    img.save(file_path)
    return file_path