"""EnPlans admin — model registry for the shared engine (common_models.admin)."""

from werkzeug.security import generate_password_hash

from common_models.admin import AdminSite, Field as F
from common_models import (
    count_online, get_current_application_id,
    User, Application, UserAppActivity, Organization, Region, Ministry, News,
    Plan, PlanApprovalPath, PlanColumnConfig, PlanTicket,
    Unit, Direction, Event, Indicator, IndicatorUsage,
    Notification, StatPlan, StatPlanValue, Chat, ChatMessage,
)

site = AdminSite(
    brand="EnPlans",
    accent="#00798f",
    accent_2="#009bb6",
    site_endpoint="views.begin_page",
    login_endpoint="auth.login",
    logout_endpoint="auth.logout",
)

site.link("Обращения «Другое»", "admin_support.list_view", group="Вспомогательные")


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


def _user_application_display(obj):
    return obj.application.name if obj.application else "—"


def _org_account_emails(org):
    """Email аккаунтов, привязанных к организации — только из ЭТОГО
    приложения (у организации вполне может быть отдельный аккаунт и в
    erespondentN, его сюда не подмешиваем)."""
    app_id = get_current_application_id()
    emails = [u.email for u in org.users if u.application_id == app_id and u.email]
    return ", ".join(emails) if emails else "—"


def _news_on_save(obj, creating):
    """Публикация новости на сайте EnPlans определяется полем published_at
    (см. /api/news). Держим его в синхроне с галочкой «Опубликовано»."""
    from common_models import current_utc_time
    if getattr(obj, "is_published", False):
        if not obj.published_at:
            obj.published_at = current_utc_time()
    else:
        obj.published_at = None


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
    list_display=["id", "email", "organization", "begin_time"],
    list_badges=["is_admin", "is_auditor", "is_approver", "is_reader"],
    search=["email", "last_name", "first_name", "telephone"],
    scope_query=_scope_to_this_app,
    on_save=_user_on_save,
    fields=[
        F("email", "Email", type="email", required=True),
        F("last_name", "Фамилия"), F("first_name", "Имя"), F("patronymic_name", "Отчество"),
        F("telephone", "Телефон"), F("post", "Должность"),
        F("is_admin", "Администратор", type="bool"),
        F("is_auditor", "Согласовывающая организация", type="bool"),
        F("is_approver", "Утверждающая организация", type="bool"),
        F("is_reader", "Читатель", type="bool"),
        F("organization_id", "Организация", type="fk-search", target=Organization, target_label="full_name"),
        F("application_id", "Приложение", readonly=True, display=_user_application_display,
          help="Аккаунт создаётся только для текущего приложения (EnPlans) — не редактируется."),
        F("password", "Пароль", type="password", create_only=False, skip_if_blank=True,
          transform=generate_password_hash, help="Оставьте пустым, чтобы не менять"),
    ],
)

site.register(
    Organization, name="Организации", group="Основные", stat_label="Организаций",
    list_display=["id", "full_name", "okpo", "region", "ministry", ("accounts", "Email аккаунта")],
    list_badges=["is_active", "is_regular", "is_coordinator", "is_approver", "is_region_management"],
    list_format={"accounts": _org_account_emails},
    search=["full_name", "okpo", "ynp"],
    fields=[
        F("full_name", "Полное название", required=True),
        F("okpo", "ОКПО"), F("ynp", "УНП"),
        F("region_id", "Регион", type="fk", target=Region, target_label="name"),
        F("ministry_id", "Министерство", type="fk", target=Ministry, target_label="name"),
        F("is_active", "Активна", type="bool"),
        F("is_regular", "Обычная", type="bool"),
        F("is_coordinator", "Координатор", type="bool"),
        F("is_approver", "Утверждающая", type="bool"),
        F("is_region_management", "Региональное управление", type="bool"),
    ],
)

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
    list_badges=["is_published", "is_enplans", "is_erespondentn"],
    search=["title", "text"],
    on_save=_news_on_save,
    fields=[
        F("title", "Заголовок", required=True),
        F("text", "Текст", type="text", rows=8),
        F("img_name", "Картинка (обложка)", type="file",
          upload_to="static/img/news", accept="image/*"),
        F("is_published", "Опубликовано", type="bool", default=True,
          help="Снимите галочку, чтобы скрыть новость с сайта"),
        F("is_enplans", "Показывать в EnPlans", type="bool", default=True),
        F("is_erespondentn", "Показывать в ErespondentN", type="bool"),
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
        F("is_approved", "Одобрен", type="bool"),
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
    list_badges=["luck", "is_system"], order_by="-id",
    fields=[
        F("plan_id", "План", type="fk", target=Plan, target_label="id"),
        F("user_id", "Пользователь", type="fk", target=User, target_label="email"),
        F("note", "Текст", type="text", required=True),
        F("begin_time", "Время", type="datetime"),
        F("luck", "Успех", type="bool"),
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

site.dashboard(
    greeting_attr="first_name",
    stats=["news", "plan", "user", "organization"],
    online_count=lambda: count_online("enplans"),
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
        {
            "label": "Создать тестовых проверяющих",
            "endpoint": "db_bp.create_test_auditors_route",
            "method": "post",
            "confirm": "Удалить все ранее созданные тестовые аккаунты проверяющих и "
                       "создать заново — по одному на каждое региональное управление "
                       "(пароль у всех: 12345678)?",
        },
        {
            "label": "Создать тестовых согласующих/утверждающих",
            "endpoint": "db_bp.create_test_approvers_route",
            "method": "post",
            "confirm": "Удалить ранее созданные тестовые аккаунты согласующей/"
                       "утверждающей организации и создать заново — по одной на "
                       "организацию с УНП 200100489 (согласовывающая) и "
                       "УНП 500022116 (утверждающая). Пароль у обеих: 12345678?",
        },
        # {
        #     "label": "Синхронизировать направления энергосбережения",
        #     "endpoint": "db_bp.sync_directions_route",
        #     "method": "post",
        #     "confirm": "Полностью привести справочник «Направления» к официальному "
        #                "перечню (приложение 1 к Указаниям по форме 4-энергосбережение)? "
        #                "Недостающие коды будут добавлены, расхождения в названии/единице "
        #                "измерения — исправлены, а коды, которых нет в перечне, — удалены "
        #                "(или помечены неактуальными, если уже используются в мероприятиях).",
        # },
    ],
)


def init_admin(app):
    site.init_app(app)
