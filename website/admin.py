"""EnPlans admin — описание моделей для движка eres-admin."""

from werkzeug.security import generate_password_hash

from eres_admin import AdminSite, Field as F
from common_models import (
    db, current_utc_time, count_online, get_current_application_id,
    org_accounts_cell, org_egr_state_display, org_egr_refresh,
    User, Application, UserAppActivity, UserAppDailyActivity, Organization, Region, Ministry, News,
    Plan, PlanApprovalPath, PlanColumnConfig, PlanTicket,
    Unit, Direction, Event, Indicator, IndicatorUsage,
    Notification, StatPlan, StatPlanValue, Chat, ChatMessage, Role, user_roles,
)

site = AdminSite(
    brand="EnPlans",
    db=db,
    code="enplans",
    site_endpoint="views.begin_page",
    login_endpoint="auth.login",
    logout_endpoint="auth.logout",
    now=current_utc_time,
)

site.link("Обращения «Другое»", "admin_support.list_view", group="Вспомогательные", icon="message")


def _scope_to_this_app(query):
    """Аккаунты теперь привязаны к конкретному приложению — админка enPlans
    должна видеть/создавать только свои (иначе тут же путается с
    erespondentN-аккаунтами того же человека)."""
    return query.filter(User.application_id == get_current_application_id())


def _user_app_activity_scope(query):
    return query.filter(UserAppActivity.app == "enplans")


def _user_on_save(obj, creating):
    """Новый аккаунт из админки всегда создаётся для ЭТОГО приложения —
    поле application_id нарочно не редактируется через форму (см. ниже,
    readonly), значение всегда берётся отсюда, а не из формы."""
    if creating:
        obj.application_id = get_current_application_id()
        # Без пароля в аккаунт нельзя войти — при создании он обязателен
        # (поле пароля в форме skip_if_blank: пустое значение не меняет пароль).
        if not obj.password:
            raise ValueError('Задайте пароль: без него пользователь не сможет войти')
    obj.email = (obj.email or '').strip() or None
    obj.login = (obj.login or '').strip().lower() or None

    # "Руководитель организации"/"Заместитель руководителя" — максимум один
    # сотрудник на организацию на каждую роль (та же проверка, что и в
    # views.invite_employee, но нужна и тут — org_role редактируется в
    # админке напрямую, в обход приглашения). dept_head/executor — без
    # ограничения по количеству, в пределах общего лимита ниже.
    if obj.org_role and obj.organization_id:
        if obj.org_role in ('org_head', 'org_head_deputy'):
            conflict = User.query.filter(
                User.organization_id == obj.organization_id,
                User.application_id == obj.application_id,
                User.org_role == obj.org_role,
                User.is_active.is_(True),
                User.id != obj.id,
            ).first()
            if conflict:
                raise ValueError(
                    f'Роль "{obj.org_role}" уже занята сотрудником {conflict.full_name or conflict.login} в этой организации'
                )

        if creating:
            employees_count = User.query.filter(
                User.organization_id == obj.organization_id,
                User.application_id == obj.application_id,
                User.is_active.is_(True),
            ).count()
            if employees_count >= 7:
                raise ValueError('В организации не может быть больше 7 сотрудников')


def _user_application_display(obj):
    return obj.application.name if obj.application else "—"




def _news_on_save(obj, creating):
    """Публикация новости на сайте EnPlans определяется полем published_at
    (см. /api/news). Держим его в синхроне с галочкой «Опубликовано»."""
    from common_models import current_utc_time
    if creating:
        obj.application_id = get_current_application_id()
    if getattr(obj, "is_published", False):
        if not obj.published_at:
            obj.published_at = current_utc_time()
    else:
        obj.published_at = None


def _news_scope_to_this_app(query):
    """Новость принадлежит одному приложению — админка видит только свои."""
    return query.filter(News.application_id == get_current_application_id())


def _support_chat_rows():
    """Превью обращений «Другое» для панели на главной странице админки —
    полная логика и отдельная страница со всеми обращениями теперь в
    routes/admin_support.py (list_view/dashboard_rows)."""
    from .routes.admin_support import dashboard_rows
    return dashboard_rows(limit=12)

# --------------------------------------------------------------------------- #
#  Основные
# --------------------------------------------------------------------------- #

site.register(
    User, name="Пользователи", group="Основные", stat_label="Пользователей",
    list_display=["id", "login", "email", "organization", "org_role", "begin_time"],
    list_badges=["is_admin", ("has_auditor_access", "Проверяющая организация"),
                 ("has_approver_access", "Утверждающая организация"), "is_reader", "is_verified"],
    search=["login", "email", "last_name", "first_name", "telephone"],
    scope_query=_scope_to_this_app,
    on_save=_user_on_save,
    fields=[
        F("login", "Логин"),
        F("email", "Email", type="email"),
        F("is_active", "Учётная запись активна", type="bool", default=True),
        F("is_cabinet_owner", "Ответственный за кабинет", type="bool"),
        F("last_name", "Фамилия"), F("first_name", "Имя"), F("patronymic_name", "Отчество"),
        F("telephone", "Телефон"), F("post", "Должность"),
        F("is_admin", "Администратор", type="bool"),
        F("is_reader", "Читатель", type="bool"),
        F("is_verified", "Верифицирован (ЭЦП)", type="bool",
          help="Прошёл проверку ЭЦП на регистрации (или приглашён уже верифицированным руководителем). Блокирует регистрацию новых аккаунтов на его организацию."),
        F("org_role", "Роль в организации", type="select", choices=[
            ("executor", "Исполнитель"),
            ("dept_head", "Руководитель структурного подразделения"),
            ("org_head", "Руководитель организации"),
            ("org_head_deputy", "Заместитель руководителя организации"),
        ], help="Кто этот сотрудник внутри своей организации (не путать с ролями выше — те про права в приложении)."),
        F("organization_id", "Организация", type="fk-search", target=Organization, target_label="full_name",
          help="Согласующая/утверждающая организация определяется флагами самой организации (is_coordinator/is_region_management/is_approver) — здесь достаточно привязать сотрудника к ней."),
        F("application_id", "Приложение", readonly=True, display=_user_application_display,
          help="Аккаунт создаётся только для текущего приложения (EnPlans) — не редактируется."),
        F("password", "Пароль", type="password", create_only=False, skip_if_blank=True,
          transform=generate_password_hash,
          help="Сохраняется в зашифрованном виде. При создании обязателен; при редактировании оставьте пустым, чтобы не менять."),
    ],
)

site.register(
    Organization, name="Организации", group="Основные", stat_label="Организаций",
    list_display=["id", "full_name", "okpo", "region", "ministry", ("accounts", "Пользователи")],
    list_badges=["is_active", "is_regular", "is_coordinator", "is_approver", "is_region_management", "is_energy_department"],
    list_format={"accounts": org_accounts_cell},
    search=["full_name", "short_name", "okpo", "ynp"],
    fields=[
        F("full_name", "Полное наименование", type="text", rows=2, required=True),
        F("short_name", "Сокращённое наименование"),
        F("okpo", "ОКПО"), F("ynp", "УНП"),
        F("legal_address", "Юридический адрес", type="text", rows=2),
        F("region_id", "Регион", type="fk", target=Region, target_label="name"),
        F("ministry_id", "Министерство", type="fk", target=Ministry, target_label="name"),
        F("is_active", "Активна", type="bool", section="Роль в системе"),
        F("is_regular", "Обычная", type="bool", section="Роль в системе"),
        F("is_coordinator", "Координатор", type="bool", section="Роль в системе"),
        F("is_approver", "Утверждающая", type="bool", section="Роль в системе"),
        F("is_region_management", "Региональное управление", type="bool", section="Роль в системе"),
        F("is_energy_department", "Департамент по энергоэффективности", type="bool", section="Роль в системе"),
        F("egr_status", "Статус в ЕГР", readonly=True, section="Данные ЕГР"),
        F("egr_status_kind", "Состояние", readonly=True, display=org_egr_state_display, section="Данные ЕГР"),
        F("egr_checked_at", "Последняя сверка с ЕГР", readonly=True, section="Данные ЕГР"),
        F("created_at", "Добавлена в систему", readonly=True, section="Данные ЕГР"),
    ],
    object_actions=[{
        "name": "egr-refresh", "label": "Обновить из ЕГР", "icon": "refresh", "handler": org_egr_refresh,
        "confirm": "Обновить наименования, юридический адрес, регион и статус организации по данным ЕГР?",
        "help": "По УНП: полное и сокращённое наименование, юридический адрес, регион и статус.",
    }],
)

# Добавление организации по УНП с подстановкой из ЕГР (routes/admin_org.py)
site.link("Добавить организацию по УНП", "admin_org.by_unp", group="Основные", icon="building")
# Тестовые пользователи маршрута согласования (routes/admin_test_users.py)
site.link("Тестовые пользователи", "admin_test_users.index", group="Вспомогательные", icon="users")

site.register(
    Region, name="Регионы", group="Основные",
    list_display=["id", "number", "name"], search=["name"], order_by="number",
    fields=[F("number", "Номер", type="int", required=True), F("name", "Название", required=True)],
)

site.register(
    Ministry, name="Министерства", group="Основные",
    list_display=["id", "name"], search=["name"], order_by="name",
    fields=[F("name", "Название", required=True)],
)

site.register(
    Application, name="Приложения", group="Основные",
    list_display=["id", "code", "name"], search=["code", "name"], order_by="code",
    fields=[
        F("code", "Код (APP_NAME)", required=True),
        F("name", "Название", required=True),
    ],
)

site.register(
    News, name="Новости", group="Основные", stat_label="Новостей",
    list_display=["id", "title", "created_time", "views_count"],
    list_badges=["is_published"],
    search=["title", "text"],
    scope_query=_news_scope_to_this_app,
    on_save=_news_on_save,
    fields=[
        F("title", "Заголовок", required=True),
        F("text", "Текст", type="text", rows=8),
        F("img_name", "Картинка (обложка)", type="file",
          upload_to="static/img/news", accept="image/*"),
        F("is_published", "Опубликовано", type="bool", default=True,
          help="Снимите галочку, чтобы скрыть новость с сайта"),
        F("application_id", "Приложение", readonly=True, display=_user_application_display,
          help="Новость создаётся только для текущего приложения (EnPlans) — не редактируется."),
        F("views_count", "Просмотры", type="int"),
    ],
)

# --------------------------------------------------------------------------- #
#  Планы
# --------------------------------------------------------------------------- #

site.register(
    Plan, name="Планы", group="Планы", stat_label="Планов",
    list_display=["id", "year", "organization", "user", "begin_time"],
    list_badges=["is_draft", "is_control", "is_sent", "is_error", "is_approved", "afch"],
    search=["plan_type"], order_by="-id",
    fields=[
        F("year", "Год", type="int", required=True),
        F("plan_type", "Тип плана"),
        F("org_id", "Организация", type="fk", target=Organization, target_label="full_name"),
        F("user_id", "Пользователь", type="fk", target=User, target_label="email"),
        F("energy_saving", "Экономия ТЭР", type="float"),
        F("share_fuel", "Доля топлива", type="float"),
        F("saving_fuel", "Экономия топлива", type="float"),
        F("share_energy", "Доля энергии", type="float"),
        F("usd_rate", "Курс USD", type="float"),
        F("cost_per_toe_usd", "Стоимость т.у.т., USD", type="float"),
        F("afch", "АФЧ", type="bool"),
        F("is_draft", "В редакции", type="bool"),
        F("is_control", "Контроль", type="bool"),
        F("is_sent", "Отправлен", type="bool"),
        F("is_error", "Есть ошибки", type="bool"),
        F("is_approved", "Утвержден", type="bool"),
        F("sent_time", "Отправлен в", type="datetime"),
        F("audit_time", "Проверен в", type="datetime"),
    ],
)

site.register(
    PlanApprovalPath, name="Пути согласования", group="Планы",
    list_display=["id", "plan_id", "step_order", "organization", "step_type"],
    list_badges=["is_viewed"], order_by="plan_id",
    fields=[
        F("plan_id", "План", type="fk", target=Plan, target_label="id", required=True),
        F("step_order", "Порядок", type="int", required=True),
        F("organization_id", "Организация", type="fk", target=Organization,
          target_label="full_name", required=True),
        F("step_type", "Тип шага", type="select",
          choices=[("region", "Региональное управление"),
                   ("coordinator", "Согласовывающая организация"),
                   ("approver", "Утверждающая организация")], blank=False),
        F("is_viewed", "Просмотрено", type="bool"),
        F("viewed_at", "Просмотрено в", type="datetime"),
    ],
)

site.register(
    PlanColumnConfig, name="Конфигурации колонок", group="Планы",
    list_display=["id", "plan_id", "year", "label"], order_by="-id",
    fields=[
        F("plan_id", "План", type="fk", target=Plan, target_label="id", required=True),
        F("year", "Год", type="int", required=True),
        F("label", "Подпись", required=True),
    ],
)

site.register(
    PlanTicket, name="Тикеты планов", group="Планы", stat_label="Тикетов",
    list_display=["id", "plan_id", "user", "begin_time", "note"],
    list_badges=["is_system"], order_by="-id",
    fields=[
        F("plan_id", "План", type="fk", target=Plan, target_label="id"),
        F("user_id", "Пользователь", type="fk", target=User, target_label="email"),
        F("note", "Текст", type="text", required=True),
        F("begin_time", "Время", type="datetime"),
        F("is_system", "Системный", type="bool"),
    ],
)

# --------------------------------------------------------------------------- #
#  Справочники
# --------------------------------------------------------------------------- #

site.register(
    Unit, name="Единицы измерения", group="Справочники",
    list_display=["id", "name"], search=["name"], order_by="name",
    fields=[F("name", "Название", required=True)],
)

site.register(
    Direction, name="Направления", group="Справочники",
    list_display=["id", "code", "name", "unit"], list_badges=["is_econom", "is_increase"],
    search=["code", "name"],
    fields=[
        F("code", "Код"), F("name", "Название"),
        F("id_unit", "Единица", type="fk", target=Unit, target_label="name"),
        F("is_econom", "Экономия", type="bool"),
        F("is_increase", "Прирост", type="bool"),
        F("DateStart", "Действует с", type="datetime"),
        F("DateEnd", "Действует по", type="datetime"),
    ],
)

site.register(
    Indicator, name="Показатели", group="Справочники",
    list_display=["id", "code", "name", "unit", "CoeffToTut"],
    list_badges=["is_local", "is_renewable", "IsMandatory", "is_computed", "is_custom"],
    search=["code", "name"],
    fields=[
        F("code", "Код"), F("name", "Название"),
        F("id_unit", "Единица", type="fk", target=Unit, target_label="name", required=True),
        F("CoeffToTut", "Коэфф. в т.у.т.", type="float"),
        F("Group", "Группа", type="float"),
        F("RowN", "№ строки", type="int"),
        F("is_local", "Местный", type="bool"),
        F("is_renewable", "ВИЭ", type="bool"),
        F("IsMandatory", "Обязательный", type="bool"),
        F("is_computed", "Считается автоматически", type="bool"),
        F("higher_is_better", "Рост — это хорошо", type="bool"),
        F("is_custom", "Прочие (свободный ввод)", type="bool"),
        F("DateStart", "Действует с", type="datetime"),
        F("DateEnd", "Действует по", type="datetime"),
    ],
)

# --------------------------------------------------------------------------- #
#  Данные
# --------------------------------------------------------------------------- #

site.register(
    Event, name="Мероприятия", group="Данные", stat_label="Мероприятий",
    list_display=["id", "display_code", "name", "id_plan", "ExpectedQuarter"],
    list_badges=["is_local", "is_corrected", "is_econom", "is_increase"],
    search=["name", "display_code"], order_by="-id", per_page=20,
    fields=[
        F("id_plan", "План", type="fk", target=Plan, target_label="id", required=True),
        F("id_direction", "Направление", type="fk", target=Direction, target_label="name", required=True),
        F("name", "Название", type="text", rows=3, required=True),
        F("display_code", "Код"),
        F("Volume", "Объём", type="int"),
        F("EffTut", "Эффект т.у.т.", type="float"),
        F("EffRub", "Эффект, руб.", type="int"),
        F("ExpectedQuarter", "Ожидаемый квартал"),
        F("Payback", "Окупаемость", type="float"),
        F("is_local", "Местный", type="bool"),
        F("is_corrected", "Скорректирован", type="bool"),
        F("is_econom", "Экономия", type="bool"),
        F("is_increase", "Прирост", type="bool"),
        F("order", "Порядок", type="int"),
    ],
)

site.register(
    IndicatorUsage, name="Использование показателей", group="Данные",
    list_display=["id", "indicator", "id_plan", "QYearCurrent"],
    list_badges=["is_local", "is_renewable"], order_by="-id",
    fields=[
        F("id_indicator", "Показатель", type="fk", target=Indicator, target_label="name", required=True),
        F("id_plan", "План", type="fk", target=Plan, target_label="id", required=True),
        F("note", "Примечание", type="text", rows=3),
        F("QYearBeforePrev", "Кол-во (позапрошлый год)", type="float"),
        F("QYearPrev", "Кол-во (прошлый год)", type="float"),
        F("QYearCurrent", "Кол-во (текущий год)", type="float"),
        F("coeff_before_prev", "Коэфф. (позапрошлый)", type="float"),
        F("coeff_prev", "Коэфф. (прошлый)", type="float"),
        F("coeff_current", "Коэфф. (текущий)", type="float"),
        F("is_local", "Местный", type="bool"),
        F("is_renewable", "ВИЭ", type="bool"),
    ],
)

# --------------------------------------------------------------------------- #
#  Статистика
# --------------------------------------------------------------------------- #

site.register(
    StatPlan, name="Статистические планы", group="Статистика",
    list_display=["id", "organization", "type", "year", "uploaded_by", "uploaded_at"],
    order_by="-id",
    fields=[
        F("organization_id", "Организация", type="fk", target=Organization,
          target_label="full_name", required=True),
        F("type", "Тип", type="select", choices=[("12-tek", "12-тек"), ("4-tek", "4-тек")], blank=False),
        F("year", "Год", type="int", required=True),
        F("uploaded_by_id", "Загрузил", type="fk", target=User, target_label="email"),
        F("uploaded_at", "Загружено", type="datetime"),
    ],
)

site.register(
    StatPlanValue, name="Значения статистики", group="Статистика",
    list_display=["id", "stat_plan_id", "row_code", "row_name", "column_code", "value"],
    search=["row_code", "row_name", "column_code"], order_by="-id", per_page=50,
    fields=[
        F("stat_plan_id", "Стат. план", type="fk", target=StatPlan, target_label="id", required=True),
        F("row_code", "Код строки", required=True),
        F("row_name", "Название строки"),
        F("column_code", "Код колонки", required=True),
        F("value", "Значение", type="float"),
    ],
)

# --------------------------------------------------------------------------- #
#  Вспомогательные / служебные
# --------------------------------------------------------------------------- #

site.register(
    Notification, name="Уведомления", group="Вспомогательные",
    list_display=["id", "user", "message", "created_at"], list_badges=["is_read"],
    search=["message"], order_by="-id", per_page=50,
    fields=[
        F("user_id", "Пользователь", type="fk", target=User, target_label="email", required=True),
        F("message", "Сообщение", required=True),
        F("is_read", "Прочитано", type="bool"),
        F("created_at", "Создано", type="datetime"),
    ],
)

site.register(
    Chat, name="Чаты", group="Вспомогательные",
    list_display=["id", "title", "created_by", "created_at", "updated_at"],
    search=["title"], order_by="-id",
    fields=[
        F("title", "Заголовок"),
        F("created_by_id", "Создатель", type="fk", target=User, target_label="email", required=True),
    ],
)

site.register(
    ChatMessage, name="Сообщения чатов", group="Вспомогательные",
    list_display=["id", "chat_id", "is_user", "content", "created_at"],
    search=["content"], order_by="-id", per_page=50,
    fields=[
        F("chat_id", "Чат", type="fk", target=Chat, target_label="id", required=True),
        F("is_user", "От пользователя", type="bool"),
        F("content", "Текст", type="text", required=True),
    ],
)

site.register(
    UserAppActivity, name="Активность по приложениям", group="Служебные",
    readonly=True, order_by="-last_active", per_page=50,
    list_display=["id", "user", "app", "first_seen", "last_active"],
    search=["app"],
    scope_query=_user_app_activity_scope,
)

# --------------------------------------------------------------------------- #


def _uploads_root():
    from flask import current_app
    return current_app.config["ATTACHMENTS_UPLOAD_FOLDER"]


def _describe_uploads(folder, names):
    """К какой записи привязан файл: ТЭО — к мероприятию плана, вложения
    замечаний — к тикету плана. Имена на диске — uuid, поэтому показываем
    и исходное имя файла."""
    from flask import url_for
    top = folder.split("/", 1)[0] if folder else ""
    out = {}
    if top == "teo" and folder == "teo":
        for ev in Event.query.filter(Event.teo_filename.in_(names)).all():
            out[ev.teo_filename] = {
                "label": ev.teo_original_name,
                "title": f"ТЭО мероприятия №{ev.id}, план №{ev.id_plan}",
                "url": url_for("eres_admin.edit_view", key="event", pk=ev.id),
                "in_use": True,
            }
    elif top == "tickets" and folder == "tickets":
        for t in PlanTicket.query.filter(PlanTicket.attachment_filename.in_(names)).all():
            out[t.attachment_filename] = {
                "label": t.attachment_original_name,
                "title": f"Замечание №{t.id}, план №{t.plan_id}",
                "url": url_for("eres_admin.edit_view", key="plan-ticket", pk=t.id),
                "in_use": True,
            }
    return out


site.files("uploads", root=_uploads_root, name="Файлы (uploads)", group="Служебные",
           describe=_describe_uploads, max_upload_mb=100)

ORG_ROLE_LABELS = {
    "org_head": "Руководитель организации",
    "org_head_deputy": "Заместитель руководителя",
    "dept_head": "Руководитель подразделения",
    "executor": "Исполнитель",
}


def _plan_status_rows():
    """Планы по текущему состоянию — так же, как статусы на сайте."""
    counts = {"Утверждены": 0, "Есть ошибки": 0, "На согласовании": 0, "Контроль пройден": 0, "В редакции": 0}
    rows = db.session.query(Plan.is_approved, Plan.is_error, Plan.is_sent, Plan.is_control).all()
    for approved, error, sent, control in rows:
        if approved:
            counts["Утверждены"] += 1
        elif error:
            counts["Есть ошибки"] += 1
        elif sent:
            counts["На согласовании"] += 1
        elif control:
            counts["Контроль пройден"] += 1
        else:
            counts["В редакции"] += 1
    return list(counts.items())


def _user_role_rows():
    rows = (
        db.session.query(Role.code, db.func.count(User.id))
        .join(user_roles, user_roles.c.role_id == Role.id)
        .join(User, User.id == user_roles.c.user_id)
        .filter(Role.is_org_role.is_(True), User.application_id == get_current_application_id())
        .group_by(Role.code)
        .all()
    )
    found = dict(rows)
    return [(label, found.get(code, 0)) for code, label in ORG_ROLE_LABELS.items()]


def _daily_activity_scope(query):
    return query.filter(UserAppDailyActivity.app == "enplans")


site.register(
    UserAppDailyActivity, name="Активность по дням", group="Служебные", key="user-app-daily-activity",
    readonly=True, order_by="-day", per_page=50,
    list_display=["day", "user", ("ticks", "Минут в приложении"), "first_at", "last_at"],
    scope_query=_daily_activity_scope,
)

site.dashboard(
    greeting_attr="first_name",
    stats=["news", "plan", "user", "organization"],
    online_count=lambda: count_online("enplans"),
    charts=[
        {"title": "Активные пользователи", "model": UserAppDailyActivity, "date_attr": "day",
         "distinct": "user_id", "scope": _daily_activity_scope},
        {"title": "Новые пользователи", "model": User, "date_attr": "begin_time", "scope": _scope_to_this_app},
        {"title": "Созданные планы", "model": Plan, "date_attr": "begin_time"},
        {"title": "Отправленные планы", "model": Plan, "date_attr": "sent_time"},
    ],
    breakdowns=[
        {"title": "Планы по статусам", "rows": _plan_status_rows, "icon": "clipboard"},
        {"title": "Пользователи по ролям", "rows": _user_role_rows, "icon": "users"},
    ],
    panels=[
        {
            "title": "Обращения «Другое»",
            "rows": _support_chat_rows,
            "empty": "Открытых обращений нет",
            "more_endpoint": "admin_support.list_view",
            "more_label": "Все обращения",
        },
    ],
    actions=[
        # {
        #     "label": "Заполнить базу данных",
        #     "endpoint": "db_bp.fill_database_route",
        #     "method": "post",
        #     "confirm": "Запустить заполнение всех справочных данных?",
        # },
        {
            "label": "Загрузить статистику",
            "endpoint": "db_bp.upload_statistics_route",
            "type": "upload",
            "field": "archive",
            "accept": ".zip",
            "confirm": "Загрузить архив со статистикой? Имена файлов внутри должны "
                       "соответствовать формату «окпо_..._год_...xlsx».",
        },
    ],
)


def init_admin(app):
    site.init_app(app)
