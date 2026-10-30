const METRIKA_ID = Number(document.body.dataset.metrikaId || 0);
function goal(name) {
  if (METRIKA_ID && typeof ym === 'function') {
    ym(METRIKA_ID, 'reachGoal', name);
  }
}
document.querySelectorAll('.js-phone').forEach(a => a.addEventListener('click', () => goal('phone_click')));
document.querySelectorAll('.js-telegram').forEach(a => a.addEventListener('click', () => goal('telegram_click')));

const siteHeader = document.getElementById('siteHeader');
function onScroll() {
  if (siteHeader) siteHeader.classList.toggle('scrolled', window.scrollY > 8);
}
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

function initWipeCard(card) {
  const clean = card.querySelector('.clean');
  const handle = card.querySelector('.wipe-handle');
  if (!clean || !handle) return;

  let dragging = false;
  let current = 50;

  handle.setAttribute('role', 'slider');
  handle.setAttribute('tabindex', '0');
  handle.setAttribute('aria-label', 'Сравнить «до» и «после»');
  handle.setAttribute('aria-valuemin', '0');
  handle.setAttribute('aria-valuemax', '100');

  function setWipe(percent) {
    percent = Math.max(4, Math.min(96, percent));
    current = percent;
    clean.style.clipPath = `inset(0 0 0 ${percent}%)`;
    handle.style.left = percent + '%';
    handle.setAttribute('aria-valuenow', Math.round(percent));
  }
  function posFromEvent(e) {
    const rect = card.getBoundingClientRect();
    const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
    return (x / rect.width) * 100;
  }
  handle.addEventListener('pointerdown', (e) => { dragging = true; e.stopPropagation(); });
  window.addEventListener('pointerup', () => dragging = false);
  window.addEventListener('pointercancel', () => dragging = false);
  window.addEventListener('pointermove', (e) => { if (dragging) setWipe(posFromEvent(e)); });
  card.addEventListener('click', (e) => setWipe(posFromEvent(e)));
  handle.addEventListener('keydown', (e) => {
    const step = e.shiftKey ? 15 : 5;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { setWipe(current - step); e.preventDefault(); }
    else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { setWipe(current + step); e.preventDefault(); }
    else if (e.key === 'Home') { setWipe(0); e.preventDefault(); }
    else if (e.key === 'End') { setWipe(100); e.preventDefault(); }
  });
  setWipe(50);
}
document.querySelectorAll('.wipe-card').forEach(initWipeCard);

const burgerBtn = document.getElementById('burgerBtn');
const mobileMenu = document.getElementById('mobileMenu');
function closeMenu() {
  if (!mobileMenu || !burgerBtn) return;
  mobileMenu.classList.remove('open');
  burgerBtn.setAttribute('aria-expanded', 'false');
  burgerBtn.setAttribute('aria-label', 'Открыть меню');
  burgerBtn.textContent = '☰';
}
if (burgerBtn && mobileMenu) {
  burgerBtn.addEventListener('click', () => {
    const isOpen = mobileMenu.classList.toggle('open');
    burgerBtn.setAttribute('aria-expanded', isOpen);
    burgerBtn.setAttribute('aria-label', isOpen ? 'Закрыть меню' : 'Открыть меню');
    burgerBtn.textContent = isOpen ? '✕' : '☰';
  });
  mobileMenu.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && mobileMenu.classList.contains('open')) {
      closeMenu();
      burgerBtn.focus();
    }
  });
}

const contactTypeSelect = document.getElementById('contact_type');
const contactValueInput = document.getElementById('contact_value');
const contactLabel = document.getElementById('contactLabel');

const contactConfig = {
  phone: { label: 'Номер телефона', placeholder: '+7 (___) ___-__-__', type: 'tel' },
  tg:    { label: 'Ник или номер в Telegram', placeholder: '@username или +7...', type: 'text' },
  wa:    { label: 'Номер в WhatsApp', placeholder: '+7 (___) ___-__-__', type: 'tel' },
  max:   { label: 'Контакт в MAX', placeholder: 'Номер телефона или ссылка', type: 'text' },
  vk:    { label: 'Ссылка на ВКонтакте', placeholder: 'vk.com/id...', type: 'text' },
  inst:  { label: 'Ник в Instagram', placeholder: '@username', type: 'text' },
};

if (contactTypeSelect && contactValueInput && contactLabel) {
  contactTypeSelect.addEventListener('change', () => {
    const cfg = contactConfig[contactTypeSelect.value] || contactConfig.phone;
    contactLabel.textContent = cfg.label;
    contactValueInput.placeholder = cfg.placeholder;
    contactValueInput.type = cfg.type;
  });
}

const form = document.getElementById('leadForm');
const msg = document.getElementById('formMsg');

function markField(input, errEl, isError) {
  if (!input || !errEl) return;
  errEl.classList.toggle('show', isError);
  input.setAttribute('aria-invalid', isError ? 'true' : 'false');
}

function validateContact(type, val) {
  const trimmed = val.trim();
  if (type === 'phone' || type === 'wa') {
    const digits = trimmed.replace(/\D/g, '');
    return digits.length >= 10;
  }
  return trimmed.length >= 2;
}

if (form) {
  [['name', 'err-name'], ['contact_value', 'err-contact']].forEach(([id, errId]) => {
    const input = document.getElementById(id);
    const errEl = document.getElementById(errId);
    if (input && errEl) {
      input.addEventListener('input', () => {
        if (errEl.classList.contains('show')) markField(input, errEl, false);
      });
    }
  });

  const consentInput = document.getElementById('consent');
  if (consentInput) {
    consentInput.addEventListener('change', (e) => {
      if (e.target.checked) markField(e.target, document.getElementById('err-consent'), false);
    });
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const name = document.getElementById('name');
    const cType = document.getElementById('contact_type');
    const cVal = document.getElementById('contact_value');
    const consent = document.getElementById('consent');

    const errName = document.getElementById('err-name');
    const errContact = document.getElementById('err-contact');
    const errConsent = document.getElementById('err-consent');

    let valid = true;
    let firstInvalid = null;

    if (name.value.trim().length < 2) {
      markField(name, errName, true); valid = false; firstInvalid = firstInvalid || name;
    } else {
      markField(name, errName, false);
    }

    if (!validateContact(cType.value, cVal.value)) {
      markField(cVal, errContact, true); valid = false; firstInvalid = firstInvalid || cVal;
    } else {
      markField(cVal, errContact, false);
    }

    if (!consent.checked) {
      markField(consent, errConsent, true); valid = false; firstInvalid = firstInvalid || consent;
    } else {
      markField(consent, errConsent, false);
    }

    if (!valid) {
      if (firstInvalid) firstInvalid.focus();
      return;
    }

    const submitBtn = form.querySelector('.submit-btn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Отправляю заявку и медиа...';

    try {
      const res = await fetch('/api/lead', { method: 'POST', body: new FormData(form) });
      const data = await res.json();
      if (data.ok) {
        goal('lead_form');
        msg.classList.add('show');
        form.reset();
        setTimeout(() => msg.classList.remove('show'), 7000);
      } else {
        alert('Не получилось отправить заявку. Позвоните, пожалуйста: +7 (904) 886-31-41');
      }
    } catch {
      alert('Ошибка сети при отправке заявки. Позвоните, пожалуйста: +7 (904) 886-31-41');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Отправить заявку';
    }
  });
}

const certForm = document.getElementById('certForm');
const certMsg = document.getElementById('certMsg');
const certModal = document.getElementById('certModal');

if (certForm) {
  certForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = certForm.querySelector('.submit-btn');
    btn.disabled = true;
    btn.textContent = 'Отправляю...';

    try {
      const res = await fetch('/api/certificate', { method: 'POST', body: new FormData(certForm) });
      const data = await res.json();
      if (data.ok) {
        goal('lead_form');
        certMsg.classList.add('show');
        certForm.reset();
        setTimeout(() => {
          certMsg.classList.remove('show');
          if (certModal) certModal.close();
        }, 4000);
      } else {
        alert(data.error || 'Ошибка при оформлении сертификата');
      }
    } catch {
      alert('Ошибка сети. Попробуйте ещё раз.');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Я перевёл(а) — получить сертификат';
    }
  });
}