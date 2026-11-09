"""Данные организации из ЕГР (Единый государственный регистр юридических
лиц и ИП, egr.gov.by) по УНП.

Используемые методы API (см. спецификацию egr.gov.by/api, v2):
  getJurNamesByRegNum/{УНП}  → наименование (EGR0332Dto: vnaim — полное,
                                vn — сокращённое, vfn — фирменное);
  getBaseInfoByRegNum/{УНП}  → состояние субъекта (EGR01Dto.nsi00219.vnsostk:
                                «Действующий», «Ликвидирован», «В процессе
                                ликвидации», …), дата регистрации;
  getAddressByRegNum/{УНП}   → юридический адрес (EGR0321Dto) и код СОАТО
                                населённого пункта (nsi00202.nksoato) —
                                первая цифра СОАТО = область (1 Брестская …
                                5 г. Минск, 6 Минская, 7 Могилёвская), что
                                совпадает с Region.number.

ФИО руководителя юридического лица этот API НЕ отдаёт (есть только ФИО
индивидуального предпринимателя — getIPFIOByRegNum) — не импортируется.

Каждый метод возвращает МАССИВ записей с историей (dfrom/dto) — берётся
текущая: без dto (действует сейчас), иначе самая поздняя по dfrom.
"""
import re

import requests
from flask import current_app

from common_models.timeutils import current_utc_time


class EgrError(Exception):
    """Понятная пользователю ошибка обращения к ЕГР."""


UNP_RE = re.compile(r'^\d{9}$')

STATUS_LABELS = {
    'active': 'Действующая',
    'liquidating': 'В процессе ликвидации',
    'liquidated': 'Ликвидирована',
    'bankrupt': 'Банкротство',
    'unknown': 'Состояние не определено',
}


# Не действующая по ЕГР организация — её сотрудники в программе только
# просматривают (см. block_inactive_organization в website/__init__.py).
# 'unknown'/None (не сверялась или ЕГР вернул незнакомое состояние) — НЕ
# блокирует: блокировка только по подтверждённому состоянию из ЕГР.
INACTIVE_KINDS = {'liquidating', 'liquidated', 'bankrupt'}


def org_is_inactive(org):
    return bool(org and org.egr_status_kind in INACTIVE_KINDS)


def inactive_notice(org):
    """Текст для пользователя: почему доступен только просмотр."""
    label = STATUS_LABELS.get(org.egr_status_kind, org.egr_status or '')
    return (f'По данным ЕГР организация «{org.full_name}» — {label.lower()}. '
            f'Работа в программе недоступна, только просмотр.')


def normalize_unp(value):
    unp = re.sub(r'\D', '', str(value or ''))
    if not UNP_RE.match(unp):
        raise EgrError('УНП должен состоять из 9 цифр')
    return unp


def _get(method, unp, timeout=None):
    base = current_app.config.get('EGR_API_BASE', 'https://egr.gov.by/api/v2/egr').rstrip('/')
    headers = {'Accept': 'application/json'}
    api_key = current_app.config.get('EGR_API_KEY')
    if api_key:
        headers['Authorization'] = api_key
    try:
        resp = requests.get(f'{base}/{method}/{unp}', headers=headers,
                            timeout=timeout or current_app.config.get('EGR_TIMEOUT', 15))
    except requests.RequestException as exc:
        current_app.logger.warning(f'EGR {method}/{unp}: {exc}')
        raise EgrError('ЕГР сейчас недоступен — попробуйте позже')

    if resp.status_code == 404:
        return []
    if resp.status_code in (401, 403):
        raise EgrError('ЕГР отклонил запрос: нет доступа (нужен ключ API ЕГР — EGR_API_KEY)')
    if resp.status_code != 200:
        current_app.logger.warning(f'EGR {method}/{unp}: HTTP {resp.status_code}')
        raise EgrError(f'ЕГР вернул ошибку (HTTP {resp.status_code})')
    if not resp.content or not resp.content.strip():
        return []
    try:
        data = resp.json()
    except ValueError:
        raise EgrError('ЕГР вернул ответ в неожиданном формате')
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


def _current(records):
    """Текущая запись из истории: без dto (действует), иначе последняя по dfrom."""
    if not records:
        return None
    open_ended = [r for r in records if not r.get('dto')]
    pool = open_ended or records
    return max(pool, key=lambda r: r.get('dfrom') or '')


def classify_status(text):
    s = (text or '').lower()
    if not s:
        return 'unknown'
    if 'банкрот' in s or 'несостоятельн' in s:
        return 'bankrupt'
    if 'ликвидац' in s and ('процесс' in s or 'стади' in s):
        return 'liquidating'
    if 'ликвидир' in s or 'исключ' in s or 'прекращ' in s:
        return 'liquidated'
    if 'действ' in s:
        return 'active'
    return 'unknown'


def _address(rec):
    if not rec:
        return None
    parts = []
    if rec.get('nindex'):
        parts.append(str(rec['nindex']))
    settlement = (rec.get('nsi00202') or {}).get('vnsfull') or rec.get('vnp')
    street_type = (rec.get('nsi00226') or {}).get('vntulk')
    street = ' '.join(p for p in (street_type, rec.get('vulitsa')) if p)
    for value in (rec.get('vregion'), rec.get('vdistrict'), settlement, street):
        if value and value not in parts:
            parts.append(value)
    if rec.get('vdom'):
        parts.append(f"д. {rec['vdom']}")
    if rec.get('vkorp'):
        parts.append(f"корп. {rec['vkorp']}")
    if rec.get('vpom'):
        room_type = (rec.get('nsi00227') or {}).get('vntpomk') or 'пом.'
        parts.append(f"{room_type} {rec['vpom']}")
    return ', '.join(str(p).strip() for p in parts if str(p).strip()) or None


def _region_number(rec):
    soato = (rec or {}).get('nsi00202') or {}
    code = soato.get('nksoato')
    if code is None:
        return None
    digits = re.sub(r'\D', '', str(code).split('.')[0])
    return int(digits[0]) if digits and digits[0] in '1234567' else None


def fetch_organization(unp, timeout=None):
    """Данные организации из ЕГР по УНП (dict) или EgrError. timeout — на
    каждый запрос (по умолчанию EGR_TIMEOUT); первый же сбой прерывает."""
    unp = normalize_unp(unp)

    names = _current(_get('getJurNamesByRegNum', unp, timeout))
    base = _current(_get('getBaseInfoByRegNum', unp, timeout))
    if not names and not base:
        raise EgrError(f'Организация с УНП {unp} в ЕГР не найдена')
    address = _current(_get('getAddressByRegNum', unp, timeout))

    status_text = ((base or {}).get('nsi00219') or {}).get('vnsostk')
    return {
        'unp': unp,
        'full_name': (names or {}).get('vnaim') or None,
        'short_name': (names or {}).get('vn') or None,
        'status': status_text,
        'status_kind': classify_status(status_text),
        'registered_at': (base or {}).get('dfrom'),
        'legal_address': _address(address),
        'region_number': _region_number(address),
    }


def refresh_before_send(org):
    """Сверка организации-разработчика с ЕГР прямо перед «Подписать и
    отправить» (plan_bp.internal_sign), до смены статуса на «На
    согласовании». Без успешной сверки план НЕ отправляется. Возвращает
    None (можно отправлять) или текст причины отказа:
      - у организации нет УНП;
      - ЕГР недоступен / вернул ошибку / не нашёл организацию по УНП;
      - по ЕГР организация не действующая (обновлённые данные ЕГР
        вызывающий сохраняет — дальше действует блокировка «только просмотр»).
    Отключается целиком EGR_CHECK_ON_SEND=false; таймаут — EGR_SEND_TIMEOUT."""
    if not current_app.config.get('EGR_CHECK_ON_SEND', True) or not org:
        return None
    if not org.ynp:
        return ('Отправка невозможна: у организации не указан УНП — сверка с ЕГР '
                'не выполнена. Обратитесь к администратору, чтобы указать УНП.')
    try:
        data = fetch_organization(org.ynp, timeout=current_app.config.get('EGR_SEND_TIMEOUT', 5))
    except EgrError as exc:
        current_app.logger.warning(f'EGR check before send, org {org.id}: {exc}')
        return f'Отправка невозможна: сверка с ЕГР не выполнена — {exc}. План остаётся у вас на подписи, попробуйте отправить позже.'
    apply_to_organization(org, data)
    if org_is_inactive(org):
        return f'Отправка невозможна: {inactive_notice(org)}'
    return None


def apply_to_organization(org, data):
    """Записывает данные ЕГР в организацию. Возвращает список изменений
    [(поле, было, стало)] для показа пользователю. Коммит — на вызывающем."""
    from common_models.models import Region

    changes = []

    def _set(attr, label, value):
        if value in (None, ''):
            return
        old = getattr(org, attr)
        if (old or None) != value:
            setattr(org, attr, value)
            changes.append((label, old, value))

    _set('full_name', 'Полное наименование', data.get('full_name'))
    _set('short_name', 'Сокращённое наименование', data.get('short_name'))
    _set('legal_address', 'Юридический адрес', data.get('legal_address'))
    _set('egr_status', 'Состояние в ЕГР', data.get('status'))
    org.egr_status_kind = data.get('status_kind') or 'unknown'

    if data.get('region_number'):
        region = Region.query.filter_by(number=data['region_number']).first() or \
            Region.query.get(data['region_number'])
        if region and org.region_id != region.id:
            changes.append(('Регион', org.region.name if org.region else None, region.name))
            org.region_id = region.id

    org.egr_checked_at = current_utc_time()
    return changes
