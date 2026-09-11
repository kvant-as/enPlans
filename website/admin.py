"""EnPlans admin — model registry for the shared engine (common_models.admin)."""

from flask import url_for
from werkzeug.security import generate_password_hash

from common_models.admin import AdminSite, Field as F
from common_models import (
    count_online,
    User, UserAppActivity, Organization, Region, Ministry, News,
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
    """Открытые обращения «Другое» из виджета виртуального помощника —
    уходят живому администратору, минуя ИИ (см. routes/chat_bp.py и
    routes/admin_support.py). Показываем последние на главной странице
    админки, чтобы можно было сразу перейти и ответить."""
    from .routes.chat_bp import SUPPORT_CHAT_TYPE

    rows = []
    chats = (
        Chat.query.filter_by(chat_type=SUPPORT_CHAT_TYPE)
        .order_by(Chat.updated_at.desc())
        .limit(12)
        .all()
    )
    for c in chats:
        last = (
            ChatMessage.query.filter_by(chat_id=c.id)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        preview = (last.content or "") if last else ""
        if len(preview) > 90:
            preview = preview[:90].rstrip() + "…"
        author = c.created_by
        if author:
            full = f"{author.last_name or ''} {author.first_name or ''}".strip()
            name = author.fio or full or author.email or f"Чат №{c.id}"
        else:
            name = f"Чат №{c.id}"
        rows.append({
            "title": name,
            "subtitle": preview,
            "meta": c.updated_at.strftime("%d.%m %H:%M") if c.updated_at else "",
            "url": url_for("admin_support.thread", chat_id=c.id),
        })
    return rows

# --------------------------------------------------------------------------- #
#  Основные
# --------------------------------------------------------------------------- #

site.register(
    User, name="Пользователи", group="Основные", stat_label="Пользователей",
    list_display=["id", "email", "fio", "organization", "begin_time"],
    list_badges=["is_admin", "is_auditor", "is_approver", "is_reader"],
    search=["email", "fio", "last_name", "first_name", "telephone"],
    fields=[
        F("email", "Email", type="email", required=True),
        F("fio", "ФИО"),
        F("last_name", "Фамилия"), F("first_name", "Имя"), F("patronymic_name", "Отчество"),
        F("telephone", "Телефон"), F("post", "Должность"),
        F("is_admin", "Администратор", type="bool"),
        F("is_auditor", "Аудитор", type="bool"),
        F("is_approver", "Утверждающий", type="bool"),
        F("is_reader", "Читатель", type="bool"),
        F("organization_id", "Организация", type="fk", target=Organization, target_label="full_name"),
        F("password", "Пароль", type="password", create_only=False, skip_if_blank=True,
          transform=generate_password_hash, help="Оставьте пустым, чтобы не менять"),
    ],
)

site.register(
    Organization, name="Организации", group="Основные", stat_label="Организаций",
    list_display=["id", "full_name", "okpo", "region", "ministry"],
    list_badges=["is_active", "is_regular", "is_coordinator", "is_approver", "is_region_management"],
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
        F("is_draft", "Черновик", type="bool"),
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
        },
    ],
    actions=[
        {
            "label": "Заполнить базу данных",
            "endpoint": "db_bp.fill_database_route",
            "method": "post",
            "confirm": "Запустить заполнение всех справочных данных?",
        },
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
