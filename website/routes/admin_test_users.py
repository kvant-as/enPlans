"""Админ-панель: тестовые пользователи для проверки маршрута согласования.

Одна кнопка создаёт (или приводит к эталону, если уже есть) 9 аккаунтов —
по три роли (исполнитель, руководитель структурного подразделения,
руководитель организации) в трёх организациях маршрута:
  - Беларуськалий — разработчик (и утверждающая для своих планов);
  - Минское областное управление по надзору — согласующая (региональное);
  - Лидское пиво — утверждающая.
Пароль у всех — TEST_USERS_PASSWORD. Существующие аккаунты не
пересоздаются (их id остаются — на них могут ссылаться тестовые планы),
обновляются только ФИО, должность, телефон, организация, роль и пароль.
"""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from common_models import db, get_current_application_id

from ..models import Organization, Region, User

admin_test_users_bp = Blueprint('admin_test_users', __name__, url_prefix='/admin/test-users')

TEST_USERS_PASSWORD = 'Test12345!'

# Организации ищутся не по id (на другой базе они другие), а по признакам.
# По одному УНП в базе бывает несколько записей (старые импортированные —
# без ролей), поэтому дополнительно требуется роль в маршруте (role):
# иначе пользователи попали бы в «пустую» запись-дубль.
TEST_ORGS = {
    'belarus_kali': {'label': 'Беларуськалий (разработчик)', 'ynp': '600122610', 'role': 'is_regular'},
    'minsk_obl': {'label': 'Минское областное (согласующая)', 'region_management_of': 6},
    'lidskoe_pivo': {'label': 'Лидское пиво (утверждающая)', 'ynp': '500022116', 'role': 'is_approver'},
}

ROLE_LABELS = {
    'executor': 'Исполнитель',
    'dept_head': 'Руководитель структурного подразделения',
    'org_head': 'Руководитель организации',
}

# (префикс email, роль, фамилия, имя, отчество, должность, телефон)
TEST_USERS = [
    ('belarus_kali', 'executor', 'Ковалёва', 'Ольга', 'Николаевна', 'Инженер по энергосбережению', '+375291000001'),
    ('belarus_kali', 'dept_head', 'Лапицкий', 'Андрей', 'Викторович', 'Главный энергетик', '+375291000002'),
    ('belarus_kali', 'org_head', 'Шевчук', 'Дмитрий', 'Сергеевич', 'Генеральный директор', '+375291000003'),
    ('minsk_obl', 'executor', 'Жук', 'Наталья', 'Петровна', 'Главный специалист', '+375291000004'),
    ('minsk_obl', 'dept_head', 'Мельник', 'Игорь', 'Владимирович', 'Начальник отдела надзора', '+375291000005'),
    ('minsk_obl', 'org_head', 'Кравченко', 'Виктор', 'Иванович', 'Начальник управления', '+375291000006'),
    ('lidskoe_pivo', 'executor', 'Новик', 'Елена', 'Александровна', 'Инженер-энергетик', '+375291000007'),
    ('lidskoe_pivo', 'dept_head', 'Ткачук', 'Павел', 'Михайлович', 'Главный инженер', '+375291000008'),
    ('lidskoe_pivo', 'org_head', 'Савицкий', 'Алексей', 'Геннадьевич', 'Генеральный директор', '+375291000009'),
]


@admin_test_users_bp.before_request
def _guard():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


def _site_ctx():
    site = current_app.extensions.get('cm_admin')
    return site.nav_context() if site else {}


def _find_org(key):
    spec = TEST_ORGS[key]
    if spec.get('ynp'):
        return Organization.query.filter(
            Organization.ynp == spec['ynp'],
            getattr(Organization, spec['role']) == True,
            Organization.is_active == True,
        ).order_by(Organization.id).first()
    region = Region.query.filter_by(number=spec['region_management_of']).first()
    if not region:
        return None
    return Organization.query.filter(
        Organization.is_region_management == True,
        Organization.region_id == region.id,
    ).first()


def _email(prefix, role):
    return f'{prefix}.{role}@test.local'


def _find_user(email):
    return User.query.filter(
        func.lower(User.email) == email.lower(),
        User.application_id == get_current_application_id(),
    ).first()


def _rows():
    orgs = {key: _find_org(key) for key in TEST_ORGS}
    rows = []
    for prefix, role, last, first, patr, post, phone in TEST_USERS:
        email = _email(prefix, role)
        rows.append({
            'email': email,
            'org_label': TEST_ORGS[prefix]['label'],
            'org': orgs[prefix],
            'role_label': ROLE_LABELS[role],
            'fio': f'{last} {first} {patr}',
            'post': post,
            'user': _find_user(email),
        })
    return rows, orgs


@admin_test_users_bp.route('/', methods=['GET'])
def index():
    rows, orgs = _rows()
    missing_orgs = [TEST_ORGS[k]['label'] for k, o in orgs.items() if not o]
    return render_template('admin/test_users.html', rows=rows, missing_orgs=missing_orgs,
                           password=TEST_USERS_PASSWORD, **_site_ctx())


@admin_test_users_bp.route('/', methods=['POST'])
def create():
    orgs = {key: _find_org(key) for key in TEST_ORGS}
    missing = [TEST_ORGS[k]['label'] for k, o in orgs.items() if not o]
    if missing:
        flash('Не найдены организации: ' + ', '.join(missing) + '. Добавьте их и повторите.', 'error')
        return redirect(url_for('admin_test_users.index'))

    app_id = get_current_application_id()
    created = updated = 0
    for prefix, role, last, first, patr, post, phone in TEST_USERS:
        email = _email(prefix, role)
        user = _find_user(email)
        if user is None:
            user = User(email=email, application_id=app_id)
            db.session.add(user)
            created += 1
        else:
            updated += 1
        user.last_name, user.first_name, user.patronymic_name = last, first, patr
        user.post = post
        user.telephone = phone
        user.organization_id = orgs[prefix].id
        user.org_role = role
        user.password = generate_password_hash(TEST_USERS_PASSWORD)
        user.is_verified = True
        user.reset_password_token = None
        user.reset_password_expires = None
    db.session.commit()

    current_app.logger.info(f'Admin {current_user.id}: test users created={created} updated={updated}')
    flash(f'Тестовые пользователи готовы: создано {created}, обновлено {updated}. Пароль у всех — {TEST_USERS_PASSWORD}', 'success')
    return redirect(url_for('admin_test_users.index'))
