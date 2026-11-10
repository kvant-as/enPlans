import random
import string
from flask import current_app, flash, redirect, request, session, url_for
from sqlalchemy import func
from website import db
from website.email import send_email
from website.models import User, Organization
from common_models import get_current_application_id
from flask import request, flash, redirect, session, url_for
import logging
import re

from flask_login import (
    login_user, current_user,
)

from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

from common_models import current_utc_time

logger = logging.getLogger(__name__)

# Черновик регистрации живёт в сессии (session['temp_user']) — аккаунт в
# базе создаётся только на последнем шаге, после ЭЦП (add_param). Сессия
# Flask — подписанная cookie (подделать нельзя), но НЕ зашифрованная
# (клиент может прочитать) — поэтому код подтверждения хранится только
# хэшем, а отметку «почта подтверждена» подделать нельзя из-за подписи.
REGISTRATION_TTL_SECONDS = 24 * 3600


def pending_registration():
    """Черновик регистрации с ПОДТВЕРЖДЁННОЙ почтой (или None): шаг /param
    доступен такому посетителю без аккаунта и входа."""
    temp = session.get('temp_user') or {}
    if not temp.get('email_verified') or not temp.get('email') or not temp.get('password'):
        return None
    started = temp.get('started_at') or 0
    if current_utc_time().timestamp() - started > REGISTRATION_TTL_SECONDS:
        session.pop('temp_user', None)
        return None
    return temp

PHONE_PREFIX = '+375'
PHONE_TOTAL_DIGITS = 12
PHONE_MAX_COUNT = 2

FIELD_LABELS = {
    'first_name': 'Имя',
    'last_name': 'Фамилия',
    'patronymic_name': 'Отчество',
    'post': 'Должность',
}

def parse_and_validate_phones(raw_telephone):
    """Разбирает один или несколько номеров (разделённых ';' или ','),
    проверяет, что каждый начинается с +375 (международный формат хранения)
    и содержит ровно PHONE_TOTAL_DIGITS цифр вместе с кодом, и что номеров
    не больше PHONE_MAX_COUNT. Возвращает (строка_для_сохранения, ошибка)."""
    if not raw_telephone or not str(raw_telephone).strip():
        return None, 'Поле "Телефон" обязательно для заполнения!'

    raw_numbers = [n.strip() for n in re.split(r'[;,]', raw_telephone) if n.strip()]
    if not raw_numbers:
        return None, 'Поле "Телефон" обязательно для заполнения!'

    if len(raw_numbers) > PHONE_MAX_COUNT:
        return None, f'Можно указать не более {PHONE_MAX_COUNT} номеров телефона!'

    validated = []
    for number in raw_numbers:
        if not number.startswith(PHONE_PREFIX):
            return None, f'Номер телефона "{number}" должен начинаться с {PHONE_PREFIX}!'
        digits_only = re.sub(r'\D', '', number)
        if len(digits_only) != PHONE_TOTAL_DIGITS:
            return None, f'Номер телефона "{number}" должен содержать {PHONE_TOTAL_DIGITS} цифр вместе с кодом!'
        validated.append(number)

    return '; '.join(validated), None

def gener_password():
    length=5
    characters = string.digits
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

def send_activation_email(email):
    activation_code = gener_password()
    # Только хэш: сессия — читаемая клиентом cookie, раньше код лежал в ней
    # открытым текстом и подтверждение почты можно было обойти.
    session.pop('activation_code', None)
    session['activation_code_hash'] = generate_password_hash(activation_code)
    send_email(activation_code, email, 'code')

def sign_def(email, password1, password2):
    if email and password1:
        # Аккаунт теперь привязан к конкретному приложению (Application) —
        # тот же email может быть отдельно зарегистрирован в erespondentN и
        # в enPlans, поэтому проверка на дубль ограничена только текущим
        # приложением.
        existing = User.query.filter(
            func.lower(User.email) == func.lower(email),
            User.application_id == get_current_application_id()
        ).first()
        if existing:
            flash('Пользователь с таким email уже существует', 'error')
            return redirect(url_for('auth.sign'))
        elif not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            flash('Некорректный адрес электронной почты', 'error')
            return redirect(url_for('auth.sign'))
        elif len(password1) < 5:
            flash('Пароль должен содержать не менее 5 символов', 'error')
            return redirect(url_for('auth.sign'))
        elif password1 != password2:
            flash('Ошибка в подтверждении пароля', 'error')
            return redirect(url_for('auth.sign'))
        else:
            session['temp_user'] = {
                'email': email,
                'password': generate_password_hash(password1),
                'email_verified': False,
                'started_at': current_utc_time().timestamp(),
            }
            session.permanent = True
            send_activation_email(email) 
            flash('Проверьте свою почту для активации аккаунта', 'success')
            return redirect(url_for('auth.code'))
    else:
        flash('Введите данные для регистрации', 'error')
        return redirect(url_for('auth.sign'))

def activate_account():
    """Подтверждение почты кодом из письма. Аккаунт в базе НЕ создаётся —
    только отмечаем в черновике регистрации (сессии), что почта
    подтверждена; аккаунт появится после последнего шага (ЭЦП, add_param)."""
    input_code = ''.join([
            request.form.get(f'activation_code_{i}', '') for i in range(5)
        ])
    temp = session.get('temp_user')
    code_hash = session.get('activation_code_hash')
    if not temp or not code_hash:
        flash('Сессия регистрации истекла — зарегистрируйтесь заново', 'error')
        return redirect(url_for('auth.sign'))

    if not (input_code and check_password_hash(code_hash, input_code)):
        flash('Некорректный код активации', 'error')
        return redirect(url_for('auth.code'))

    temp['email_verified'] = True
    session['temp_user'] = temp
    session.pop('activation_code_hash', None)
    session.modified = True
    flash('Почта подтверждена, заполните необходимые данные для продолжения!', 'success')
    return redirect(url_for('auth.param'))
         
def add_param(first_name, last_name, patronymic_name, telephone, organization_id=None, user_type='respondent', post=None):
    required_fields = {
        'first_name': first_name,
        'last_name': last_name,
        'patronymic_name': patronymic_name,
        'post': post,
    }

    for field_name, value in required_fields.items():
        if not value or not str(value).strip():
            flash(f'Поле "{FIELD_LABELS.get(field_name, field_name)}" обязательно для заполнения!', 'error')
            return redirect(url_for('auth.param'))

    normalized_telephone, phone_error = parse_and_validate_phones(telephone)
    if phone_error:
        flash(phone_error, 'error')
        return redirect(url_for('auth.param'))

    def parse_id(id_value):
        if not id_value or not str(id_value).strip():
            return None
        try:
            return int(id_value)
        except (ValueError, TypeError):
            return None
    
    org_id = parse_id(organization_id)
    
    filled_ids = [id for id in [org_id] if id is not None]
    
    if len(filled_ids) > 1:
        flash('Можно выбрать только одну принадлежность: организацию, министерство или регион!', 'error')
        return redirect(url_for('auth.param'))
    
    if len(filled_ids) == 0:
        flash('Необходимо выбрать принадлежность: организацию, министерство или регион!', 'error')
        return redirect(url_for('auth.param'))

    # Поиск организации (auth.param, /api/organizations) уже показывает
    # только is_active=True — эта проверка на то, если id организации
    # пришёл напрямую через форму в обход поиска.
    org = Organization.query.filter_by(id=org_id, is_active=True).first()
    if not org:
        flash('Организация не найдена или недоступна для регистрации', 'error')
        return redirect(url_for('auth.param'))

    # Организация считается занятой только если на ней уже есть
    # ВЕРИФИЦИРОВАННЫЙ аккаунт (прошедший проверку ЭЦП — финальный шаг
    # регистрации, см. auth.param/param.html). Если организация занята
    # только неверифицированными "самозванцами" — регистрация разрешена, а
    # при успешном прохождении ЭЦП (ниже, после коммита) все их аккаунты
    # удаляются. Фронт прячет уже верифицированные организации из поиска
    # (см. /api/organizations?exclude_registered=true), но это единственная
    # настоящая защита от дублей — обходится напрямую через форму.
    #
    # Исключение — сотрудник, приглашённый руководителем организации
    # (views.invite_employee): у него organization_id уже проставлен ЗАРАНЕЕ
    # и совпадает с org_id, который он сейчас "выбирает" на этой же форме —
    # это не повторная привязка нового аккаунта к занятой организации, а
    # просто то же самое значение, с которым его создали.
    # Новый регистрант (аккаунта ещё нет — черновик в сессии, почта
    # подтверждена) или вошедший пользователь со старым незавершённым
    # аккаунтом (созданным ещё по прежнему порядку регистрации).
    pending = None if current_user.is_authenticated else pending_registration()
    if not current_user.is_authenticated and not pending:
        flash('Сессия регистрации истекла — зарегистрируйтесь заново', 'error')
        return redirect(url_for('auth.sign'))

    if pending:
        # Email мог успеть занять кто-то другой, пока шла регистрация.
        if User.query.filter(func.lower(User.email) == func.lower(pending['email']),
                             User.application_id == get_current_application_id()).first():
            session.pop('temp_user', None)
            flash('Пользователь с таким email уже существует — войдите в систему', 'error')
            return redirect(url_for('auth.login'))
        user = User(
            email=pending['email'],
            password=pending['password'],
            application_id=get_current_application_id(),
        )
    else:
        user = current_user

    if user.organization_id != org_id:
        verified_q = User.query.filter(
            User.organization_id == org_id,
            User.application_id == get_current_application_id(),
            User.is_verified == True,
        )
        # У ещё не созданного пользователя id нет — условие id != NULL в SQL
        # отсекло бы ВСЕ строки и проверка молча перестала бы работать.
        if user.id is not None:
            verified_q = verified_q.filter(User.id != user.id)
        if verified_q.first():
            flash('Для этой организации уже зарегистрирован аккаунт. Один УНП — один аккаунт в системе.', 'error')
            return redirect(url_for('auth.param'))

    if user_type in ('respondent', 'auditor', 'approver'):
        # is_auditor/is_approver больше не проставляются на пользователе —
        # согласующая/утверждающая принадлежность организации читается
        # прямо из Organization.is_coordinator/is_region_management/
        # is_approver (см. User.has_auditor_access/has_approver_access),
        # сам user_type с формы регистрации сейчас используется только
        # чтобы определить, что текущий аккаунт становится руководителем
        # организации (а не приглашённым сотрудником — у тех org_role уже
        # проставлен заранее через invite_employee).
        if not user.org_role:
            user.org_role = 'org_head'
    else:
        current_app.logger.warning(f'Unknown user_type: {user_type} for user {user.id or pending and pending["email"]}')
        flash('Такого типа пользователя не существует', 'error')
        return redirect(url_for('auth.param'))

    user.first_name = first_name.strip()
    user.last_name = last_name.strip()
    user.patronymic_name = patronymic_name.strip() if patronymic_name else None
    user.telephone = normalized_telephone
    user.post = post.strip() if post else ''
    user.organization_id = org_id

    # Эта точка достигается только после успешной проверки ЭЦП на клиенте
    # (см. param.html/base.js::MultiStepForm — шаг 4 вызывает реальную
    # отправку формы лишь в onSuccess ЭЦП-модалки), поэтому сохранение
    # данных = подтверждение личности: аккаунт сразу верифицированный.
    user.is_verified = True

    try:
        if pending:
            db.session.add(user)
        db.session.flush()

        # Прежние НЕверифицированные аккаунты этой же организации (остатки
        # старого порядка регистрации, когда аккаунт создавался сразу после
        # подтверждения почты) удаляются вместе с данными — каскад
        # User.plans удалит и их планы.
        old_accounts = User.query.filter(
            User.organization_id == org_id,
            User.application_id == get_current_application_id(),
            User.id != user.id,
            User.is_verified.isnot(True),
        ).all()
        for old_user in old_accounts:
            db.session.delete(old_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Registration save failed: {e}', exc_info=True)
        flash('Ошибка при сохранении данных — попробуйте ещё раз', 'error')
        return redirect(url_for('auth.param'))

    flash('Добро пожаловать в EnPlans!', 'success')
    if pending:
        # Регистрация завершена: аккаунт создан — входим в него и чистим
        # черновик из сессии.
        session.pop('temp_user', None)
        session.pop('activation_code_hash', None)
        login_user(user)
        from website.sessions import create_session_token, set_session_cookie
        current_app.logger.info(f'User {user.id} registered (org {org_id}) after EDS')
        return set_session_cookie(redirect(url_for('views.profile')), create_session_token(user))
    return redirect(url_for('views.profile'))