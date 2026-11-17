"""Раздел «Сотрудники»: учётные записи сотрудников личного кабинета.

Управляет ими только «Ответственный за кабинет» своей организации:
создаёт учётные записи (логин и пароль выдаёт сам, писем нет),
редактирует, сбрасывает пароль, деактивирует (вместо удаления — история
планов и подписей остаётся), назначает других ответственных и ведёт
справочник структурных подразделений.
"""
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from common_models import Department, Plan, PlanApprovalPath, current_utc_time, db, get_current_application_id
from common_models.logins import PASSWORD_MIN, generate_password, normalize_login, validate_login

from ..models import User
from ..sessions import session_required
from ..user import login_taken, parse_and_validate_phones, suggest_login
from .auth import user_with_all_params

cabinet_bp = Blueprint('cabinet', __name__)

ORG_ROLE_LABELS = {
    'org_head': 'Руководитель организации',
    'org_head_deputy': 'Заместитель руководителя организации',
    'dept_head': 'Руководитель структурного подразделения',
    'executor': 'Исполнитель',
}
SINGLE_SLOT_ROLES = ('org_head', 'org_head_deputy')
ORG_EMPLOYEES_MAX = 7
NAME_MAX = 100
DEPARTMENT_NAME_MAX = 255


def _fail(message, status=400):
    return jsonify({'success': False, 'error': message}), status


def cabinet_owner_required(f):
    @wraps(f)
    @user_with_all_params()
    @login_required
    @session_required
    def decorated(*args, **kwargs):
        if not (current_user.is_cabinet_owner and current_user.is_active and current_user.organization_id):
            return _fail('Раздел доступен только ответственному за кабинет', 403)
        return f(*args, **kwargs)
    return decorated


def org_members_query():
    return User.query.filter(
        User.organization_id == current_user.organization_id,
        User.application_id == get_current_application_id(),
        User.org_role.isnot(None),
    )


def org_members():
    return org_members_query().order_by(User.is_active.desc(), User.begin_time.desc()).all()


def org_departments(org_id=None):
    return Department.query.filter_by(organization_id=org_id or current_user.organization_id) \
        .order_by(func.lower(Department.name)).all()


def _get_member(user_id):
    return org_members_query().filter(User.id == user_id).first()


def _active_count(exclude_id=None):
    query = org_members_query().filter(User.is_active.is_(True))
    if exclude_id:
        query = query.filter(User.id != exclude_id)
    return query.count()


def _role_holder(role, exclude_id=None):
    query = org_members_query().filter(User.is_active.is_(True), User.org_role == role)
    if exclude_id:
        query = query.filter(User.id != exclude_id)
    return query.first()


def _active_owners_count(exclude_id=None):
    query = org_members_query().filter(User.is_active.is_(True), User.is_cabinet_owner.is_(True))
    if exclude_id:
        query = query.filter(User.id != exclude_id)
    return query.count()


def _awaits_signature(user_id):
    """Сотрудник сейчас указан подписантом плана — менять ему роль или
    деактивировать нельзя, пока план не подписан или не возвращён."""
    if Plan.query.filter(Plan.pending_signer_user_id == user_id).first():
        return True
    return bool(PlanApprovalPath.query.filter(PlanApprovalPath.pending_signer_user_id == user_id).first())


def _payload():
    return request.get_json(silent=True) or request.form


def _clean(data, key, limit=NAME_MAX):
    return (data.get(key) or '').strip()[:limit]


def _read_profile(data, user_id=None):
    """Общие поля создания и редактирования. (values, error)."""
    values = {
        'last_name': _clean(data, 'last_name'),
        'first_name': _clean(data, 'first_name'),
        'patronymic_name': _clean(data, 'patronymic_name'),
        'post': _clean(data, 'post', 255),
    }
    if not values['last_name'] or not values['first_name']:
        return None, 'Укажите фамилию и имя'
    if not values['post']:
        return None, 'Укажите должность'

    phone, phone_error = parse_and_validate_phones(data.get('telephone'))
    if phone_error:
        return None, phone_error
    values['telephone'] = phone

    role = data.get('org_role')
    if role not in ORG_ROLE_LABELS:
        return None, 'Выберите роль'
    values['org_role'] = role

    department_id = data.get('department_id')
    values['department_id'] = None
    if department_id not in (None, '', 'null'):
        try:
            department = Department.query.filter_by(
                id=int(department_id), organization_id=current_user.organization_id).first()
        except (TypeError, ValueError):
            department = None
        if not department:
            return None, 'Подразделение не найдено'
        values['department_id'] = department.id

    login = normalize_login(data.get('login'))
    if not login:
        login = suggest_login(values['first_name'], values['last_name'], user_id)
    login_error = validate_login(login)
    if login_error:
        return None, login_error
    if login_taken(login, user_id):
        return None, f'Логин «{login}» уже занят'
    values['login'] = login
    return values, None


def _read_password(data):
    if data.get('password_mode') == 'manual':
        password = data.get('password') or ''
        if len(password) < PASSWORD_MIN:
            return None, f'Пароль не короче {PASSWORD_MIN} символов'
        if len(password) > 64:
            return None, 'Пароль не длиннее 64 символов'
        return password, None
    return generate_password(), None


def serialize(user):
    return {
        'id': user.id,
        'full_name': user.full_name,
        'last_name': user.last_name or '',
        'first_name': user.first_name or '',
        'patronymic_name': user.patronymic_name or '',
        'post': user.post or '',
        'telephone': user.telephone or '',
        'login': user.login or '',
        'org_role': user.org_role,
        'department_id': user.department_id,
        'is_active': bool(user.is_active),
        'is_cabinet_owner': bool(user.is_cabinet_owner),
    }


@cabinet_bp.route('/employees/login-suggest', methods=['GET'])
@cabinet_owner_required
def login_suggest():
    exclude = request.args.get('user_id', type=int)
    wanted = normalize_login(request.args.get('login'))
    if wanted:
        error = validate_login(wanted)
        if not error and login_taken(wanted, exclude):
            error = 'Логин уже занят'
        return jsonify({'login': wanted, 'available': error is None, 'error': error})
    first = (request.args.get('first_name') or '').strip()
    last = (request.args.get('last_name') or '').strip()
    if not first or not last:
        return jsonify({'login': '', 'available': False})
    return jsonify({'login': suggest_login(first, last, exclude), 'available': True})


@cabinet_bp.route('/employees', methods=['POST'])
@cabinet_owner_required
def create_employee():
    data = _payload()
    values, error = _read_profile(data)
    if error:
        return _fail(error)
    password, error = _read_password(data)
    if error:
        return _fail(error)

    if _active_count() >= ORG_EMPLOYEES_MAX:
        return _fail(f'В организации не может быть больше {ORG_EMPLOYEES_MAX} активных сотрудников')
    if values['org_role'] in SINGLE_SLOT_ROLES and _role_holder(values['org_role']):
        return _fail(f'Роль «{ORG_ROLE_LABELS[values["org_role"]]}» уже занята')

    employee = User(
        organization_id=current_user.organization_id,
        application_id=get_current_application_id(),
        password=generate_password_hash(password),
        is_verified=True,
        is_active=True,
    )
    org_role = values.pop('org_role')
    for key, value in values.items():
        setattr(employee, key, value)
    employee.org_role = org_role
    db.session.add(employee)
    db.session.commit()
    return jsonify({'success': True, 'employee': serialize(employee),
                    'credentials': {'login': employee.login, 'password': password}})


@cabinet_bp.route('/employees/<int:user_id>', methods=['POST'])
@cabinet_owner_required
def update_employee(user_id):
    employee = _get_member(user_id)
    if not employee:
        return _fail('Сотрудник не найден', 404)
    values, error = _read_profile(_payload(), employee.id)
    if error:
        return _fail(error)

    new_role = values.pop('org_role')
    if new_role != employee.org_role:
        if employee.is_active and new_role in SINGLE_SLOT_ROLES and _role_holder(new_role, employee.id):
            return _fail(f'Роль «{ORG_ROLE_LABELS[new_role]}» уже занята')
        if _awaits_signature(employee.id):
            return _fail('Сотруднику направлен план на подпись — роль можно сменить после подписания или возврата плана')

    for key, value in values.items():
        setattr(employee, key, value)
    if new_role != employee.org_role:
        employee.org_role = new_role
    db.session.commit()
    return jsonify({'success': True, 'employee': serialize(employee)})


@cabinet_bp.route('/employees/<int:user_id>/password', methods=['POST'])
@cabinet_owner_required
def reset_employee_password(user_id):
    employee = _get_member(user_id)
    if not employee:
        return _fail('Сотрудник не найден', 404)
    password, error = _read_password(_payload())
    if error:
        return _fail(error)
    employee.password = generate_password_hash(password)
    employee.reset_password_token = None
    employee.reset_password_expires = None
    db.session.commit()
    return jsonify({'success': True, 'credentials': {'login': employee.login, 'password': password}})


@cabinet_bp.route('/employees/<int:user_id>/status', methods=['POST'])
@cabinet_owner_required
def set_employee_status(user_id):
    employee = _get_member(user_id)
    if not employee:
        return _fail('Сотрудник не найден', 404)
    active = str(_payload().get('active')).lower() in ('1', 'true', 'yes')

    if active == bool(employee.is_active):
        return jsonify({'success': True, 'employee': serialize(employee)})

    if not active:
        if employee.id == current_user.id:
            return _fail('Нельзя деактивировать собственную учётную запись')
        if employee.is_cabinet_owner and _active_owners_count(employee.id) == 0:
            return _fail('Это последний ответственный за кабинет — сначала назначьте другого')
        if _awaits_signature(employee.id):
            return _fail('Сотруднику направлен план на подпись — деактивировать можно после подписания или возврата плана')
        employee.is_active = False
        employee.is_cabinet_owner = False
        employee.deactivated_at = current_utc_time()
    else:
        if _active_count() >= ORG_EMPLOYEES_MAX:
            return _fail(f'В организации не может быть больше {ORG_EMPLOYEES_MAX} активных сотрудников')
        if employee.org_role in SINGLE_SLOT_ROLES and _role_holder(employee.org_role, employee.id):
            return _fail(f'Роль «{ORG_ROLE_LABELS[employee.org_role]}» уже занята — смените сотруднику роль перед активацией')
        employee.is_active = True
        employee.deactivated_at = None
    db.session.commit()
    return jsonify({'success': True, 'employee': serialize(employee)})


@cabinet_bp.route('/employees/<int:user_id>/owner', methods=['POST'])
@cabinet_owner_required
def set_cabinet_owner(user_id):
    employee = _get_member(user_id)
    if not employee:
        return _fail('Сотрудник не найден', 404)
    owner = str(_payload().get('owner')).lower() in ('1', 'true', 'yes')

    if owner:
        if not employee.is_active:
            return _fail('Назначить ответственным можно только активного сотрудника')
        employee.is_cabinet_owner = True
    else:
        if _active_owners_count(employee.id) == 0:
            return _fail('Это последний ответственный за кабинет — сначала назначьте другого')
        employee.is_cabinet_owner = False
    db.session.commit()
    return jsonify({'success': True, 'employee': serialize(employee),
                    'self_revoked': employee.id == current_user.id and not owner})


def _read_department_name():
    name = ' '.join((_payload().get('name') or '').split())
    if not name:
        return None, 'Укажите название подразделения'
    if len(name) > DEPARTMENT_NAME_MAX:
        return None, f'Название не длиннее {DEPARTMENT_NAME_MAX} символов'
    return name, None


def _department_exists(name, exclude_id=None):
    query = Department.query.filter(
        Department.organization_id == current_user.organization_id,
        func.lower(Department.name) == name.lower(),
    )
    if exclude_id:
        query = query.filter(Department.id != exclude_id)
    return query.first() is not None


@cabinet_bp.route('/departments', methods=['POST'])
@cabinet_owner_required
def create_department():
    name, error = _read_department_name()
    if error:
        return _fail(error)
    if _department_exists(name):
        return _fail('Такое подразделение уже есть')
    department = Department(organization_id=current_user.organization_id, name=name)
    db.session.add(department)
    db.session.commit()
    return jsonify({'success': True, 'department': {'id': department.id, 'name': department.name}})


@cabinet_bp.route('/departments/<int:department_id>', methods=['POST'])
@cabinet_owner_required
def rename_department(department_id):
    department = Department.query.filter_by(id=department_id, organization_id=current_user.organization_id).first()
    if not department:
        return _fail('Подразделение не найдено', 404)
    name, error = _read_department_name()
    if error:
        return _fail(error)
    if _department_exists(name, department.id):
        return _fail('Такое подразделение уже есть')
    department.name = name
    db.session.commit()
    return jsonify({'success': True, 'department': {'id': department.id, 'name': department.name}})


@cabinet_bp.route('/departments/<int:department_id>/delete', methods=['POST'])
@cabinet_owner_required
def delete_department(department_id):
    department = Department.query.filter_by(id=department_id, organization_id=current_user.organization_id).first()
    if not department:
        return _fail('Подразделение не найдено', 404)
    if User.query.filter(User.department_id == department.id).first():
        return _fail('В подразделении есть сотрудники — сначала переведите их в другое подразделение')
    db.session.delete(department)
    db.session.commit()
    return jsonify({'success': True})
