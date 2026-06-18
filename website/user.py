import random
import string
from flask import current_app, flash, redirect, request, session, url_for
from sqlalchemy import func
from website import db
from website.email import send_email
from website.models import User

from flask import request, flash, redirect, session, url_for

import re

from flask_login import (
    login_user, current_user,
)

from sqlalchemy import func
from werkzeug.security import generate_password_hash

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
            flash('Пользователь с таким email уже существует.', 'error')
            return redirect(url_for('auth.sign'))
        elif not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            flash('Некорректный адрес электронной почты.', 'error')
            return redirect(url_for('auth.sign'))
        elif password1 != password2:
            flash('Ошибка в подтверждении пароля.', 'error')
            return redirect(url_for('auth.sign'))
        else:
            session['temp_user'] = {
                'email': email,
                'password': generate_password_hash(password1)
            }
            session.permanent = True
            send_activation_email(email) 
            flash('Проверьте свою почту для активации аккаунта.', 'success')
            return redirect(url_for('auth.code'))
    else:
        flash('Введите данные для регистрации.', 'error')
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
        flash('Некорректный код активации.', 'error')
        return redirect(url_for('auth.code')) 
         
def add_param(first_name, last_name, patronymic_name, phone, organization_id=None, ministry_id=None, region_id=None, post=None):
    required_fields = {
        'first_name': first_name,
        'last_name': last_name,
        'phone': phone
    }
    
    for field_name, value in required_fields.items():
        if not value or not str(value).strip():
            flash(f'Поле "{field_name}" обязательно для заполнения!', 'error')
            return redirect(url_for('auth.param'))
    
    if not phone or len(phone.strip()) < 5:
        flash('Номер телефона должен содержать не менее 5 символов!', 'error')
        return redirect(url_for('views.profile'))
    
    def parse_id(id_value):
        if not id_value or not str(id_value).strip():
            return None
        try:
            return int(id_value)
        except (ValueError, TypeError):
            return None
    
    org_id = parse_id(organization_id)
    min_id = parse_id(ministry_id)
    reg_id = parse_id(region_id)
    
    filled_ids = [id for id in [org_id, min_id, reg_id] if id is not None]
    
    if len(filled_ids) > 1:
        flash('Можно выбрать только одну принадлежность: организацию, министерство или регион!', 'error')
        return redirect(url_for('auth.param'))
    
    if len(filled_ids) == 0:
        flash('Необходимо выбрать принадлежность: организацию, министерство или регион!', 'error')
        return redirect(url_for('auth.param'))
    
    normalized_phone = phone.strip()
    # if normalized_phone.startswith('+'):
    #     plus = '+'
    #     digits = ''.join(filter(str.isdigit, normalized_phone[1:]))
    #     normalized_phone = plus + digits
    # else:
    #     normalized_phone = ''.join(filter(str.isdigit, normalized_phone))
    
    # existing_user = User.query.filter_by(phone=normalized_phone).first()
    # if existing_user and existing_user.id != current_user.id:
    #     flash('Пользователь с таким номером телефона уже зарегистрирован!', 'error')
    #     return redirect(url_for('auth.param'))
    
    current_user.first_name = first_name.strip()
    current_user.last_name = last_name.strip()
    current_user.patronymic_name = patronymic_name.strip() if patronymic_name else None
    current_user.phone = normalized_phone
    current_user.post = post.strip() if post else ''
    
    current_user.organization_id = org_id
    current_user.ministry_id = min_id
    current_user.region_id = reg_id

    if min_id:
        current_user.plan_type = 'ministry'
    elif reg_id:
        current_user.plan_type = 'region'

    try:
        db.session.commit()
        flash('Данные успешно сохранены!', 'success')
        send_email(
            recipient_email=current_user.email,
            message=current_user.first_name or "Пользователь",
            email_type="registration"
        )
        return redirect(url_for('views.profile'))
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при сохранении данных: {str(e)}', 'error')
        return redirect(url_for('auth.param'))