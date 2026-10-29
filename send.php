<?php
/**
 * Приём заявок с формы сайта "Чисто Екб♥".
 * Работает на любом российском хостинге с поддержкой PHP (Beget, Timeweb и т.п.),
 * не требует внешних сервисов вроде Formspree.
 *
 * ЧТО НУЖНО НАСТРОИТЬ ПЕРЕД ЗАГРУЗКОЙ НА ХОСТИНГ:
 * 1. Впишите вашу почту в переменную $to (лучше — почтовый ящик на вашем домене,
 *    его создают в панели управления хостингом бесплатно).
 * 2. Загрузите этот файл send.php в ту же папку, что и index.html.
 * 3. В index.html в JS-коде формы укажите fetch('send.php', ...) — это уже сделано.
 */

header('Content-Type: application/json; charset=utf-8');

// ---- НАСТРОЙКИ ----
$to = 'chistoekb196@mail.ru';
$subject = 'Новая заявка с сайта Чисто Екб';

// ---- Разрешаем запрос только методом POST ----
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'method_not_allowed']);
    exit;
}

// ---- Получаем и очищаем данные ----
function clean($value) {
    return htmlspecialchars(trim($value ?? ''), ENT_QUOTES, 'UTF-8');
}

$name    = clean($_POST['name'] ?? '');
$phone   = clean($_POST['phone'] ?? '');
$service = clean($_POST['service'] ?? '');
$desc    = clean($_POST['desc'] ?? '');
$consent = isset($_POST['consent']) ? 'да' : 'нет';

// ---- Простая защита от пустых/спам-заявок ----
if (mb_strlen($name) < 2 || mb_strlen(preg_replace('/\D/', '', $phone)) < 10) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'invalid_data']);
    exit;
}

// ---- Собираем письмо ----
$body = "Новая заявка с сайта chisto-ekb\n\n"
      . "Имя: $name\n"
      . "Телефон: $phone\n"
      . "Услуга: $service\n"
      . "Описание: $desc\n"
      . "Согласие на обработку ПД: $consent\n"
      . "Дата: " . date('d.m.Y H:i') . "\n";

$headers = "From: Заявки с сайта <noreply@" . $_SERVER['HTTP_HOST'] . ">\r\n"
         . "Reply-To: noreply@" . $_SERVER['HTTP_HOST'] . "\r\n"
         . "Content-Type: text/plain; charset=UTF-8\r\n";

$sent = mail($to, $subject, $body, $headers);

if ($sent) {
    echo json_encode(['ok' => true]);
} else {
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'mail_failed']);
}
