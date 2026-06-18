from flask_admin import AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView

from flask import flash, redirect, url_for, current_app
from flask_login import current_user

from website.models import (
    User, Organization, TimeByMinsk, Plan, Ticket, Unit, 
    Direction, Event, Indicator, IndicatorUsage, Notification
)

from sqlalchemy.exc import SQLAlchemyError

from functools import wraps
from datetime import datetime, timedelta

from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange
from wtforms import PasswordField

from werkzeug.security import generate_password_hash

from website import db
from flask_admin import Admin

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Необходимо авторизоваться', 'error')
            return redirect(url_for('auth.login'))
        
        is_admin = False
        if hasattr(current_user, 'is_admin'):
            is_admin = getattr(current_user, 'is_admin', False)
        
        if not is_admin:
            flash('Недостаточно прав для доступа к админ-панели', 'error')
            return redirect(url_for('views.begin_page'))
        
        return f(*args, **kwargs)
    return decorated_function


class AdminSetup:
    
    def __init__(self, app, db):
        self.app = app
        self.db = db
        self.admin = None
        
    def setup(self):  
         
        self.admin = Admin(
            self.app, 
            name='Админ-панель', 
            index_view=MyMainView(), 
            template_mode='bootstrap4'
        )
        
        views_config = {
            'user': (UserView, User, 'Пользователи', 'Основные'),
            'organization': (OrganizationView, Organization, 'Организации', 'Основные'),
            'plan': (PlanView, Plan, 'Планы', 'Основные'),
            'ticket': (TicketView, Ticket, 'Тикеты', 'Вспомогательные'),
            'unit': (UnitView, Unit, 'Единицы измерения', 'Справочники'),
            'direction': (DirectionView, Direction, 'Направления', 'Справочники'),
            'event': (EventView, Event, 'Исполнения мер', 'Данные'),
            'indicator': (IndicatorView, Indicator, 'Показатели', 'Справочники'),
            'indicator_usage': (IndicatorUsageView, IndicatorUsage, 'Использование показателей', 'Данные'),
            'notification': (NotificationView, Notification, 'Уведомления', 'Вспомогательные'),
        }
        
        for view_class, model, name, category in views_config.values():
            self.admin.add_view(view_class(model, self.db.session, name=name, category=category))
        return self.admin
    
    def get_admin(self):
        return self.admin

class MyMainView(AdminIndexView):
    @expose('/')
    @admin_required
    def index(self):
        try:
            user_data = User.query.count()
            organization_data = Organization.query.count()
            now = TimeByMinsk()
            threshold = now - timedelta(minutes=3)
            active_users = User.query.filter(User.last_active >= threshold).count()
            week_ago = now - timedelta(days=7)
            new_users = User.query.filter(User.begin_time >= week_ago).count()
            admins_count = User.query.filter_by(is_admin=True).count()
            auditors_count = User.query.filter_by(is_auditor=True).count()
            respondents_count = User.query.filter(
                User.is_admin == False,
                User.is_auditor == False
            ).count()
            orgs_with_users = db.session.query(Organization).join(User).distinct().count()
            plan_data = Plan.query.count()
            draft_plans = Plan.query.filter_by(is_draft=True).count()
            approved_plans = Plan.query.filter_by(is_approved=True).count()
            tickets_count = Ticket.query.count()
            units_count = Unit.query.count()
            directions_count = Direction.query.count()
            execs_count = Event.query.count()
            indicators_count = Indicator.query.count()
            usages_count = IndicatorUsage.query.count()
            notifications_count = Notification.query.count()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Database error in admin stats: {str(e)}")
            user_data = organization_data = active_users = new_users = 0
            admins_count = auditors_count = respondents_count = orgs_with_users = 0
            plan_data = draft_plans = approved_plans = 0
            tickets_count = units_count = directions_count = 0
            execs_count = indicators_count = usages_count = notifications_count = 0
            flash('Ошибка при получении статистики из базы данных', 'error')

        endpoints = {
            'users': 'user.index_view',  # UserView -> user
            'organizations': 'organization.index_view',  # OrganizationView -> organization
            'plans': 'plan.index_view',  # PlanView -> plan
            'tickets': 'ticket.index_view',  # TicketView -> ticket
            'units': 'unit.index_view',  # UnitView -> unit
            'directions': 'direction.index_view',  # DirectionView -> direction
            'econ_execs': 'Event.index_view',  # EventView -> Event
            'indicators': 'indicator.index_view',  # IndicatorView -> indicator
            'indicator_usages': 'indicatorusage.index_view',  # IndicatorUsageView -> indicatorusage
            'notifications': 'notification.index_view',  # NotificationView -> notification
        }

        return self.render('admin/stats.html',
                        user_data=user_data,
                        organization_data=organization_data,
                        active_users=active_users,
                        new_users=new_users,
                        admins_count=admins_count,
                        auditors_count=auditors_count,
                        respondents_count=respondents_count,
                        orgs_with_users=orgs_with_users,
                        plan_data=plan_data,
                        draft_plans=draft_plans,
                        approved_plans=approved_plans,
                        tickets_count=tickets_count,
                        units_count=units_count,
                        directions_count=directions_count,
                        execs_count=execs_count,
                        indicators_count=indicators_count,
                        usages_count=usages_count,
                        notifications_count=notifications_count,
                        profile_url=url_for('views.profile'),
                        current_time=datetime.utcnow(),
                        endpoints=endpoints
                        )

    def is_accessible(self):
        if not current_user.is_authenticated:
            return False

        if hasattr(current_user, 'is_admin'):
            return getattr(current_user, 'is_admin', False)
        return False

    def inaccessible_callback(self, name, **kwargs):
        if not current_user.is_authenticated:
            flash('Необходимо авторизоваться для доступа к админ-панели', 'error')
            return redirect(url_for('auth.login'))

        flash('Недостаточно прав для доступа к админ-панели', 'error')
        return redirect(url_for('views.begin_page'))

class SecureModelView(ModelView):
    def is_accessible(self):
        if not current_user.is_authenticated:
            return False

        if hasattr(current_user, 'is_admin'):
            return getattr(current_user, 'is_admin', False)
        return False

    def inaccessible_callback(self, name, **kwargs):
        if not current_user.is_authenticated:
            flash('Необходимо авторизоваться для доступа к админ-панели', 'error')
            return redirect(url_for('auth.login'))

        flash('Недостаточно прав для доступа к этому разделу', 'error')
        return redirect(url_for('views.begin_page'))

    page_size = 50
    can_view_details = True
    can_export = True
    export_max_rows = 1000
    export_types = ['csv', 'json']

    column_display_pk = False
    create_modal = False
    edit_modal = False
    details_modal = False

    def handle_view_exception(self, exc):
        if isinstance(exc, SQLAlchemyError):
            current_app.logger.error(f"Database error in admin: {str(exc)}")
            flash(f'Ошибка базы данных: {str(exc)}', 'error')
            return True
        return super().handle_view_exception(exc)

class UserView(SecureModelView):
    column_list = ['id', 'email', 'last_name', 'first_name', 'patronymic_name', 
                   'post', 'phone', 'organization', 'is_admin', 'is_auditor', 
                   'last_active', 'begin_time']
    column_default_sort = ('id', True)
    column_sortable_list = ('id', 'email', 'last_name', 'first_name', 'last_active', 'begin_time')

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True

    export_max_rows = 500
    export_types = ['csv']

    form_columns = ['email', 'last_name', 'first_name', 'patronymic_name', 
                    'post', 'phone', 'organization', 'password', 
                    'is_admin', 'is_auditor']

    form_args = {
        'email': {
            'label': 'Email',
            'validators': [DataRequired(), Email(), Length(max=255)],
            'description': 'Введите email пользователя'
        },
        'last_name': {
            'label': 'Фамилия',
            'validators': [DataRequired(), Length(max=100)],
            'description': 'Введите фамилию'
        },
        'first_name': {
            'label': 'Имя',
            'validators': [DataRequired(), Length(max=100)],
            'description': 'Введите имя'
        },
        'patronymic_name': {
            'label': 'Отчество',
            'validators': [Length(max=100)],
            'description': 'Введите отчество (необязательно)'
        },
        'post': {
            'label': 'Должность',
            'validators': [Length(max=100)],
            'description': 'Введите должность'
        },
        'phone': {
            'label': 'Телефон',
            'validators': [Length(max=20)],
            'description': 'Введите номер телефона'
        },
        'password': {
            'label': 'Пароль',
            'validators': [Length(min=4)],
            'description': 'Введите новый пароль (оставьте пустым, чтобы не менять)'
        }
    }

    form_widget_args = {
        'password': {
            'placeholder': 'Оставьте пустым, чтобы не менять пароль'
        }
    }
    form_extra_fields = {
        'confirm_password': PasswordField(
            'Подтверждение пароля',
            validators=[Length(min=4)],
            description='Повторите пароль для подтверждения'
        )
    }

    column_exclude_list = ['password', 'reset_password_token', 'reset_password_expires']
    column_searchable_list = ['email', 'last_name', 'first_name', 'patronymic_name', 'phone']
    column_filters = ['id', 'email', 'is_admin', 'is_auditor', 'organization_id']

    column_formatters = {
        'organization': lambda v, c, m, p: m.organization.name if m.organization else 'Не назначена',
        'is_admin': lambda v, c, m, p: '✅' if m.is_admin else '❌',
        'is_auditor': lambda v, c, m, p: '✅' if m.is_auditor else '❌',
        'last_active': lambda v, c, m, p: m.last_active.strftime('%d.%m.%Y %H:%M') if m.last_active else '',
        'begin_time': lambda v, c, m, p: m.begin_time.strftime('%d.%m.%Y %H:%M') if m.begin_time else ''
    }

    def on_model_change(self, form, model, is_created):
        password = form.password.data
        confirm_password = form.confirm_password.data if hasattr(form, 'confirm_password') else None
        if is_created:
            if not password:
                flash('При создании пользователя необходимо указать пароль!', 'error')
                raise ValueError('Пароль обязателен при создании пользователя')
            model.password = generate_password_hash(password)
        elif password:
            if confirm_password and password != confirm_password:
                flash('Пароли не совпадают!', 'error')
                raise ValueError('Пароли не совпадают')
            model.password = generate_password_hash(password)

        model.last_active = datetime.utcnow()
        if model.is_admin or model.is_auditor:
            model.organization_id = None

    def on_form_prefill(self, form, id):
        user = User.query.get(id)
        form.password.data = ''

        if hasattr(form, 'confirm_password'):
            form.confirm_password.data = ''
        form._old_password = user.password if user else ''

    def get_edit_form(self):
        form = super().get_edit_form()
        form.password.validators = [Length(min=6)]
        form.password.description = 'Введите новый пароль (оставьте пустым, чтобы не менять)'

        return form

    def get_create_form(self):
        form = super().get_create_form()
        form.password.validators = [DataRequired(), Length(min=6)]
        form.password.description = 'Введите пароль для нового пользователя'
        return form

class OrganizationView(SecureModelView):
    column_list = ['id', 'name', 'okpo', 'ynp', 'ministry_id', 'is_active', 'users']
    column_default_sort = ('id', True)
    column_sortable_list = ('id', 'name', 'okpo', 'is_active')
    can_delete = True
    can_create = True
    can_edit = True
    can_export = True
    form_columns = ['name', 'okpo', 'ynp', 'ministry_id', 'is_active']
    form_args = {
        'name': {
            'label': 'Полное наименование',
            'validators': [DataRequired(), Length(max=500)],
            'description': 'Полное название организации'
        },
        'okpo': {
            'label': 'ОКПО',
            'validators': [DataRequired(), Length(max=20)],
            'description': 'Код ОКПО организации'
        },
        'ynp': {
            'label': 'УНП',
            'validators': [Length(max=20)],
            'description': 'Учетный номер плательщика'
        },
        'ministry_id': {
            'label': 'Министерство',
            'validators': [Length(max=500)],
            'description': 'Вышестоящее министерство'
        },
        'is_active': {
            'label': 'Активна',
            'description': 'Активна ли организация'
        }
    }
    column_searchable_list = ['name', 'okpo', 'ynp', 'ministry_id']
    column_filters = ['id', 'is_active', 'ministry_id']
    column_formatters = {
        'is_active': lambda v, c, m, p: '✅' if m.is_active else '❌',
        'users': lambda v, c, m, p: f'{len(m.users)} пользователей' if m.users else 'Нет пользователей'
    }

class PlanView(SecureModelView):
    column_list = ['id',
                   'is_draft', 'is_control', 'is_sent', 'is_error', 'is_approved',
                   'begin_time', 'change_time', 'sent_time', 'audit_time', 'ministry_id', 'org_id', 'region_id']
    column_default_sort = ('id', True)
    column_sortable_list = ('id', 'year', 'begin_time', 'change_time', 'sent_time', 'audit_time')
    can_delete = True
    can_create = True
    can_edit = True
    can_export = True
    form_columns = ['year',
                    'organization', 'user', 'energy_saving', 'share_fuel',
                    'saving_fuel', 'share_energy', 'is_draft', 'is_control',
                    'is_sent', 'is_error', 'is_approved', 'afch']
    form_args = {
        'year': {
            'label': 'Год',
            'validators': [DataRequired(), NumberRange(min=2000, max=2100)],
            'description': 'Год плана'
        }
    }
    column_searchable_list = ['year']
    column_filters = ['id', 'year', 'is_draft', 'is_control', 'is_sent',
                      'is_error', 'is_approved', 'afch']
    column_formatters = {
        'is_draft': lambda v, c, m, p: '📝 Черновик' if m.is_draft else '',
        'is_control': lambda v, c, m, p: '👁 Контроль' if m.is_control else '',
        'is_sent': lambda v, c, m, p: '📤 Отправлен' if m.is_sent else '',
        'is_error': lambda v, c, m, p: '❌ Ошибка' if m.is_error else '',
        'is_approved': lambda v, c, m, p: '✅ Утвержден' if m.is_approved else '',
        'afch': lambda v, c, m, p: '🏭 АФЧ' if m.afch else '',
        'begin_time': lambda v, c, m, p: m.begin_time.strftime('%d.%m.%Y %H:%M') if m.begin_time else '',
        'change_time': lambda v, c, m, p: m.change_time.strftime('%d.%m.%Y %H:%M') if m.change_time else '',
        'sent_time': lambda v, c, m, p: m.sent_time.strftime('%d.%m.%Y %H:%M') if m.sent_time else '',
        'audit_time': lambda v, c, m, p: m.audit_time.strftime('%d.%m.%Y %H:%M') if m.audit_time else '',
        'organization': lambda v, c, m, p: m.organization.name if m.organization else '',
        'user': lambda v, c, m, p: f"{m.user.last_name} {m.user.first_name}" if m.user else ''
    }

class TicketView(SecureModelView):
    column_list = ['id', 'plan', 'begin_time', 'luck', 'is_owner', 'note']
    column_default_sort = ('begin_time', True)
    column_sortable_list = ('id', 'begin_time', 'luck', 'is_owner')

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True

    form_columns = ['plan', 'luck', 'is_owner', 'note']

    form_args = {
        'plan': {
            'label': 'План',
            'description': 'Связанный план'
        },
        'luck': {
            'label': 'Успешно',
            'description': 'Успешно ли выполнен тикет'
        },
        'is_owner': {
            'label': 'Владелец',
            'description': 'Является ли пользователь владельцем'
        },
        'note': {
            'label': 'Примечание',
            'validators': [DataRequired(), Length(max=500)],
            'description': 'Текст примечания'
        }
    }

    column_searchable_list = ['note']
    column_filters = ['id', 'luck', 'is_owner', 'plan_id']

    column_formatters = {
        'luck': lambda v, c, m, p: '✅' if m.luck else '❌',
        'is_owner': lambda v, c, m, p: '👤 Да' if m.is_owner else '👥 Нет',
        'begin_time': lambda v, c, m, p: m.begin_time.strftime('%d.%m.%Y %H:%M') if m.begin_time else '',
        'plan': lambda v, c, m, p: f"План #{m.plan.id} ({m.plan.organization.name})" if m.plan else ''
    }

class UnitView(SecureModelView):
    column_list = ['id', 'code', 'name']
    column_default_sort = ('id', True)
    column_sortable_list = ('id', 'name')

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True
    form_columns = ['name']
    form_args = {
        'name': {
            'label': 'Название',
            'validators': [DataRequired(), Length(max=400)],
            'description': 'Название единицы измерения'
        }
    }
    column_searchable_list = ['name']
    column_filters = ['id', 'name']

class DirectionView(SecureModelView):
    column_list = ['id', 'code', 'name', 'unit', 'DateStart', 'DateEnd']
    column_default_sort = ('id', True)
    column_sortable_list = ('id', 'code', 'name', 'DateStart', 'DateEnd')

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True

    form_columns = ['code', 'name', 'unit', 'is_econom', 'is_increase', 'DateStart', 'DateEnd']

    form_args = {
        'code': {
            'label': 'Код',
            'validators': [Length(max=400)],
            'description': 'Код направления'
        },
        'name': {
            'label': 'Название',
            'validators': [Length(max=400)],
            'description': 'Название направления'
        },
        'unit': {
            'label': 'Единица измерения',
            'description': 'Единица измерения'
        },
        'is_econom': {
            'label': 'Экономия',
            'description': 'Является ли экономией'
        },
        'is_increase': {
            'label': 'Увеличение',
            'description': 'Является ли увеличением'
        }
    }

    column_searchable_list = ['code', 'name']
    column_filters = ['id', 'is_econom', 'is_increase']

    column_formatters = {
        'is_econom': lambda v, c, m, p: '✅' if m.is_econom else '❌',
        'is_increase': lambda v, c, m, p: '✅' if m.is_increase else '❌',
        'DateStart': lambda v, c, m, p: m.DateStart.strftime('%d.%m.%Y') if m.DateStart else '',
        'DateEnd': lambda v, c, m, p: m.DateEnd.strftime('%d.%m.%Y') if m.DateEnd else '',
        'unit': lambda v, c, m, p: f"({m.unit.name})" if m.unit else ''
    }

class EventsView(SecureModelView):
    column_list = ['id', 'plan', 'direction', 'year_econ', 'estim_econ', 'order']
    column_default_sort = ('id', True)
    column_sortable_list = ('id', 'year_econ', 'estim_econ', 'order')

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True

    form_columns = ['plan', 'direction', 'year_econ', 'estim_econ', 'order']

    form_args = {
        'plan': {
            'label': 'План',
            'description': 'Связанный план'
        },
        'direction': {
            'label': 'Направление',
            'description': 'Направление меры'
        },
        'year_econ': {
            'label': 'Экономия в год',
            'validators': [Optional()],
            'description': 'Экономия в год'
        },
        'estim_econ': {
            'label': 'Расчетная экономия',
            'validators': [Optional()],
            'description': 'Расчетная экономия'
        },
        'order': {
            'label': 'Порядок',
            'validators': [Optional(), NumberRange(min=0)],
            'description': 'Порядок сортировки'
        }
    }

    column_searchable_list = []
    column_filters = ['id', 'order']

    column_formatters = {
        'plan': lambda v, c, m, p: f"План #{m.plan.id}" if m.plan else '',
        'direction': lambda v, c, m, p: f"{m.direction.code} - {m.direction.name}" if m.direction else ''
    }

class EventView(SecureModelView):
    column_list = ['id', 'plan', 'name', 'Volume', 'EffTut', 'EffRub',
                   'ExpectedQuarter', 'EffCurrYear', 'Payback', 'is_local', 'is_corrected']
    column_default_sort = ('id', True)

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True

    form_columns = ['plan', 'name', 'Volume', 'EffTut', 'EffRub',
                    'ExpectedQuarter', 'EffCurrYear', 'Payback', 'VolumeFinCurrentYear',
                    'BudgetState', 'BudgetRep', 'BudgetLoc', 'BudgetOther',
                    'MoneyOwn', 'MoneyLoan', 'MoneyOther', 'is_local', 'is_corrected', 'order']

    form_args = {
        'name': {
            'label': 'Название',
            'validators': [DataRequired(), Length(max=4000)],
            'description': 'Название исполнения'
        },
        'is_local': {
            'label': 'Локальный',
            'description': 'Является ли локальным'
        },
        'is_corrected': {
            'label': 'Корректированный',
            'description': 'Был ли скорректирован'
        },
        'order': {
            'label': 'Порядок',
            'validators': [Optional(), NumberRange(min=0)],
            'description': 'Порядок сортировки'
        }
    }

    column_searchable_list = ['name']
    column_filters = ['id', 'is_local', 'is_corrected']

    column_formatters = {
        'is_local': lambda v, c, m, p: '✅' if m.is_local else '❌',
        'is_corrected': lambda v, c, m, p: 'Да' if m.is_corrected else 'Нет',
        'plan': lambda v, c, m, p: f"План #{m.plan.id}" if m.plan else ''
    }

class IndicatorView(SecureModelView):
    column_list = ['id', 'code', 'name', 'unit', 'CoeffToTut', 'IsMandatory', 'Group', 'RowN', 'DateStart', 'DateEnd']
    column_default_sort = ('id', True)

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True

    form_columns = ['code', 'name', 'unit', 'CoeffToTut', 'IsMandatory', 'Group', 'RowN', 'DateStart', 'DateEnd']

    form_args = {
        'code': {
            'label': 'Код',
            'validators': [Length(max=400)],
            'description': 'Код показателя'
        },
        'name': {
            'label': 'Название',
            'validators': [Length(max=400)],
            'description': 'Название показателя'
        },
        'unit': {
            'label': 'Единица измерения',
            'description': 'Единица измерения'
        }
    }

    column_searchable_list = ['code', 'name']
    column_filters = ['id', 'IsMandatory', 'Group']

    column_formatters = {
        'IsMandatory': lambda v, c, m, p: '✅' if m.IsMandatory else '❌',
        # 'IsSummary': lambda v, c, m, p: '📊 Да' if m.IsSummary else '📈 Нет',
        # 'IsSendRealUnit': lambda v, c, m, p: '📤 Да' if m.IsSendRealUnit else '📥 Нет',
        # 'IsSelfProd': lambda v, c, m, p: '🏭 Да' if m.IsSelfProd else '🏢 Нет',
        # 'IsLocal': lambda v, c, m, p: '🏠 Да' if m.IsLocal else '🌍 Нет',
        # 'IsRenewable': lambda v, c, m, p: '♻️ Да' if m.IsRenewable else '⚡ Нет',
        'DateStart': lambda v, c, m, p: m.DateStart.strftime('%d.%m.%Y') if m.DateStart else '',
        'DateEnd': lambda v, c, m, p: m.DateEnd.strftime('%d.%m.%Y') if m.DateEnd else '',
        'unit': lambda v, c, m, p: f"({m.unit.name})" if m.unit else ''
    }

class IndicatorUsageView(SecureModelView):
    column_list = ['id', 'plan', 'indicator', 'QYearBeforePrev', 'QYearPrev', 'QYearCurrent']
    column_default_sort = ('id', True)

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True

    form_columns = ['plan', 'indicator', 'QYearBeforePrev', 'QYearPrev', 'QYearCurrent']

    form_args = {
        'plan': {
            'label': 'План',
            'description': 'Связанный план'
        },
        'indicator': {
            'label': 'Показатель',
            'description': 'Показатель'
        }
    }

    column_searchable_list = []
    column_filters = ['id']

    column_formatters = {
        'plan': lambda v, c, m, p: f"План #{m.plan.id}" if m.plan else '',
        'indicator': lambda v, c, m, p: f"{m.indicator.code} - {m.indicator.name}" if m.indicator else ''
    }

class NotificationView(SecureModelView):
    column_list = ['id', 'user', 'message', 'is_read', 'created_at']
    column_default_sort = ('created_at', True)
    column_sortable_list = ('id', 'created_at', 'is_read')

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True

    form_columns = ['user', 'message', 'is_read']
    form_args = {
        'user': {
            'label': 'Пользователь',
            'description': 'Пользователь'
        },
        'message': {
            'label': 'Сообщение',
            'validators': [DataRequired(), Length(max=140)],
            'description': 'Текст уведомления'
        },
        'is_read': {
            'label': 'Прочитано',
            'description': 'Прочитано ли уведомление'
        }
    }

    column_searchable_list = ['message']
    column_filters = ['id', 'is_read', 'user_id']
    column_formatters = {
        'is_read': lambda v, c, m, p: '✅' if m.is_read else '❌',
        'created_at': lambda v, c, m, p: m.created_at.strftime('%d.%m.%Y %H:%M') if m.created_at else '',
        'user': lambda v, c, m, p: f"{m.user.email}" if m.user else ''
    }