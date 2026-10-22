import random
import string
from flask import current_app, flash, redirect, request, session, url_for
from sqlalchemy import func
from website import db
from website.email import send_email
from website.models import User
from flask import request, flash, redirect, session, url_for
import logging
import re

from flask_login import (
    login_user, current_user,
)

from sqlalchemy import func
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

PHONE_PREFIX = '+375'
PHONE_TOTAL_DIGITS = 12
PHONE_MAX_COUNT = 2

FIELD_LABELS = {
    'first_name': 'Имя',
    'last_name': 'Фамилия',
    'patronymic_name': 'Отчество',
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
    session['activation_code'] = activation_code
    send_email(activation_code, email, 'code')

def sign_def(email, password1, password2):
    if email and password1:
        if User.query.filter(func.lower(User.email) == func.lower(email)).first():
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
                'password': generate_password_hash(password1)
            }
            session.permanent = True
            send_activation_email(email) 
            flash('Проверьте свою почту для активации аккаунта', 'success')
            return redirect(url_for('auth.code'))
    else:
        flash('Введите данные для регистрации', 'error')
        return redirect(url_for('auth.sign'))

def activate_account():
    input_code = ''.join([
            request.form.get(f'activation_code_{i}', '') for i in range(5)
        ])
    if input_code == session.get('activation_code'):
        new_user = User(
            email=session['temp_user']['email'],
            password=session['temp_user']['password']
        )
        db.session.add(new_user)
        db.session.commit()
        session.pop('temp_user', None)
        session.pop('activation_code', None)

        login_user(new_user)
        flash('Почта подтверждена, заполните необходимые данные для продолжения!', 'success')
        return redirect(url_for('auth.param'))        
    else:
        flash('Некорректный код активации', 'error')
        return redirect(url_for('auth.code')) 
         
def add_param(first_name, last_name, patronymic_name, telephone, organization_id=None, user_type='respondent', post=None):
    required_fields = {
        'first_name': first_name,
        'last_name': last_name,
        'patronymic_name': patronymic_name,
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

    # Один УНП — один аккаунт: для каждой организации в системе может быть
    # зарегистрирован строго один аккаунт. Фронт уже прячет такие
    # организации из результатов поиска (см. /api/organizations?exclude_registered=true),
    # но это единственная настоящая защита от дублей — обходится напрямую
    # через форму.
    existing_user = User.query.filter(
        User.organization_id == org_id,
        User.id != current_user.id
    ).first()
    if existing_user:
        flash('Для этой организации уже зарегистрирован аккаунт. Один УНП — один аккаунт в системе.', 'error')
        return redirect(url_for('auth.param'))

    if user_type == 'respondent':
        current_user.is_auditor = False
        current_user.is_approver = False
        current_app.logger.info(f'User {current_user.id} set as respondent')
    elif user_type == 'auditor':
        current_user.is_auditor = True
        current_user.is_approver = False
        current_app.logger.info(f'User {current_user.id} set as auditor')
    elif user_type == 'approver':
        current_user.is_auditor = False
        current_user.is_approver = True
        current_app.logger.info(f'User {current_user.id} set as approver')
    else:
        current_app.logger.warning(f'Unknown user_type: {user_type} for user {current_user.id}')
        flash(f'Такого типа пользователя не существует: {str(e)}', 'error')
        return redirect(url_for('auth.param'))
        
        
    current_user.first_name = first_name.strip()
    current_user.last_name = last_name.strip()
    current_user.patronymic_name = patronymic_name.strip() if patronymic_name else None
    current_user.telephone = normalized_telephone
    current_user.post = post.strip() if post else ''
    
    current_user.organization_id = org_id

    try:
        db.session.commit()
        flash('Данные успешно сохранены!', 'success')
        # send_email(
        #     recipient_email=current_user.email,
        #     message=current_user.first_name or "Пользователь",
        #     email_type="registration"
        # )
        return redirect(url_for('views.profile'))
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при сохранении данных: {str(e)}', 'error')
        return redirect(url_for('auth.param'))