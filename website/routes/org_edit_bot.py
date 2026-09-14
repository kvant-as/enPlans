"""Обращение «Изменить данные организации» в виджете виртуального помощника.

В отличие от 'dif' (уходит живому администратору) и ИИ-типов, этот сценарий
ведёт полностью автоматический диалог: бот сам спрашивает, что менять,
подсказывает текущее значение из БД и, получив корректный новый вариант,
сразу применяет изменение к организации пользователя (без участия ИИ и без
подтверждения администратором). Логика (какие поля можно менять, проверка
формата ОКПО/УНП, блокировка при уже отправленном/утверждённом плане за
текущий год) перенесена из ErespondentN (website/organization.py, форма
редактирования организации на главной странице) — там она уже год работает
как проверенный первоисточник этих правил.

Состояние диалога хранится в Chat.flow_state (JSON-строка) — шаг сценария
плюс, для режима «все поля», очередь оставшихся полей и уже введённые
пользователем значения.
"""
import json
from datetime import datetime

from common_models import current_utc_time, db, validate_okpo, validate_ynp

from ..models import Notification, Organization, Plan, Region

ORG_EDIT_CHAT_TYPE = 'org-edit'

FIELD_ORDER = ["full_name", "okpo", "ynp", "region_id"]
FIELD_LABELS = {
    "full_name": "Наименование",
    "okpo": "ОКПО",
    "ynp": "УНП",
    "region_id": "Регион",
}
# варианты ответа пользователя на вопрос "что менять" -> ключ поля, либо 'all'
_SCOPE_SYNONYMS = {
    "все": "all", "всё": "all", "все данные": "all", "всё данные": "all",
    "наименование": "full_name", "название": "full_name",
    "полное название": "full_name", "полное наименование": "full_name",
    "окпо": "okpo",
    "унп": "ynp",
    "регион": "region_id",
}
_SKIP_WORDS = {"-", "—", "пропустить", "оставить", "без изменений"}
_CONFIRM_YES = {"да", "да.", "yes", "ок", "окей", "хорошо", "конечно"}
_CONFIRM_NO = {"нет", "нет.", "no", "отмена", "не хочу", "не надо"}


def _with_quick_replies(text, options):
    """Добавляет к тексту сообщения бота служебный маркер с вариантами
    быстрого ответа — chat.js вырезает его перед отображением и рисует
    вместо него кнопки-чипы (см. _extractQuickReplies в chat.js)."""
    return text + "\n[[QUICK_REPLIES:" + "|".join(options) + "]]"


def _current_field_value(org, field):
    if field == "region_id":
        return org.region.name if org.region else "не указан"
    value = getattr(org, field, None)
    return value if value else "не указано"


def _display_value(field, value):
    if field == "region_id":
        region = Region.query.get(value)
        return region.name if region else str(value)
    return value


def _check_plan_lock(org):
    """Блокируем редактирование, если по организации уже отправлен или
    утверждён план за текущий год — по аналогии с блокировкой в
    ErespondentN на уже отправленные за квартал отчёты."""
    current_year = datetime.utcnow().year
    plan = Plan.query.filter(
        Plan.org_id == org.id,
        Plan.year == current_year,
        db.or_(Plan.is_sent.is_(True), Plan.is_approved.is_(True)),
    ).first()
    if plan:
        return True, (
            f"Изменение данных организации «{org.full_name}» сейчас недоступно: "
            f"по ней уже отправлен или утверждён план за {current_year} год. "
            "Обратитесь к администратору (обращение «Другое»)."
        )
    return False, None


def _ask_field(org, field, allow_skip):
    label = FIELD_LABELS[field]
    current = _current_field_value(org, field)

    if field == "region_id":
        # регион выбирается из списка кнопками — не набирается вручную,
        # чтобы не ловить опечатки/несовпадения с названием в БД
        text = f"Текущее значение поля «{label}»: {current}. Выберите новый регион из списка ниже."
        options = [r.name for r in Region.query.order_by(Region.number).all()]
        if allow_skip:
            options.append("Пропустить")
        return _with_quick_replies(text, options)

    hint = ""
    if field == "okpo":
        hint = " (12 цифр)"
    elif field == "ynp":
        hint = " (9 цифр)"
    text = f"Текущее значение поля «{label}»: {current}. Введите новое значение{hint}."
    if allow_skip:
        text += " Чтобы оставить без изменений, отправьте «-»."
    return text


def _validate_field(org, field, text):
    """Возвращает (True, новое_значение_для_записи) либо (False, текст_ошибки)."""
    if field == "full_name":
        if len(text) < 3:
            return False, "Название слишком короткое."
        return True, text

    if field == "okpo":
        digits = text.strip()
        ok, err = validate_okpo(digits)
        if not ok:
            return False, err + "."
        dup = Organization.query.filter(
            Organization.okpo == digits, Organization.id != org.id,
        ).first()
        if dup:
            return False, "Организация с таким ОКПО уже существует."
        return True, digits

    if field == "ynp":
        digits = text.strip()
        ok, err = validate_ynp(digits)
        if not ok:
            return False, err + "."
        return True, digits

    if field == "region_id":
        name = text.strip().lower()
        region = Region.query.filter(db.func.lower(Region.name) == name).first()
        if not region and name.isdigit():
            region = Region.query.filter_by(number=int(name)).first()
        if not region:
            return False, "Регион не найден — введите название точно как в списке."
        return True, region.id

    return False, "Неизвестное поле."


def _truncate(text, limit=140):
    text = text.strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def _apply_changes(org, changes):
    for field, value in changes.items():
        setattr(org, field, value)
    db.session.commit()


def _notify_change_applied(user_id, summary):
    """Итоговое сообщение сценария («было → стало») дублируем в колокольчик
    уведомлений (Notification) — так же, как это делают статусы планов
    (см. utils/status_plan.py) — на случай, если пользователь закроет чат
    и не увидит финальный ответ бота."""
    db.session.add(Notification(
        user_id=user_id,
        message=_truncate(f'Данные вашей организации изменены: {summary}'),
        created_at=current_utc_time(),
    ))
    db.session.commit()


def _start_flow(chat, user):
    org = user.organization
    if not org:
        chat.flow_state = json.dumps({"step": "done"})
        return (
            "У вас не указана организация в профиле. Обратитесь к "
            "администратору, чтобы привязать организацию к вашей учётной записи."
        )

    blocked, reason = _check_plan_lock(org)
    if blocked:
        chat.flow_state = json.dumps({"step": "done"})
        return reason

    chat.flow_state = json.dumps({"step": "await_confirm"})
    return _with_quick_replies(
        f"Здравствуйте! Вы обратились по вопросу изменения данных организации "
        f"«{org.full_name}» (ОКПО {org.okpo or '—'}).\n\n"
        "Перейти к изменению данных?",
        ["Да", "Нет"],
    )


def _handle_confirm_answer(chat, content):
    key = content.strip().lower().strip('«»"\'.')

    if key in _CONFIRM_NO:
        chat.flow_state = json.dumps({"step": "done"})
        return "Хорошо, обращение отменено. Если передумаете — начните новый чат."

    if key not in _CONFIRM_YES:
        return _with_quick_replies(
            "Не поняла ваш ответ. Перейти к изменению данных организации?",
            ["Да", "Нет"],
        )

    chat.flow_state = json.dumps({"step": "await_scope"})
    return _with_quick_replies(
        "Вы хотите изменить все данные организации или только определённые?",
        ["Все данные", "Наименование", "ОКПО", "УНП", "Регион"],
    )


def _handle_scope_answer(chat, org, content):
    key = content.strip().lower().strip('«»"\'.')
    choice = _SCOPE_SYNONYMS.get(key)

    if choice is None:
        return _with_quick_replies(
            "Не поняла ваш выбор. Пожалуйста, выберите один из вариантов ниже.",
            ["Все данные", "Наименование", "ОКПО", "УНП", "Регион"],
        )

    if choice == "all":
        state = {"step": "await_value", "mode": "all", "queue": FIELD_ORDER, "idx": 0, "collected": {}}
        chat.flow_state = json.dumps(state)
        return _ask_field(org, FIELD_ORDER[0], allow_skip=True)

    chat.flow_state = json.dumps({"step": "await_value", "mode": "single", "field": choice})
    return _ask_field(org, choice, allow_skip=False)


def _handle_value_answer(chat, org, state, content, user_id):
    mode = state.get("mode")
    text = content.strip()

    if mode == "single":
        field = state["field"]
        if text.lower() in _SKIP_WORDS:
            chat.flow_state = json.dumps({"step": "done"})
            return "Хорошо, изменения не внесены."

        ok, result = _validate_field(org, field, text)
        if not ok:
            return result + " " + _ask_field(org, field, allow_skip=False)

        old_value = _current_field_value(org, field)
        _apply_changes(org, {field: result})
        chat.flow_state = json.dumps({"step": "done"})
        summary = f"«{FIELD_LABELS[field]}»: «{old_value}» → «{_display_value(field, result)}»"
        _notify_change_applied(user_id, summary)
        return f"Готово! Поле {summary}."

    # mode == "all" — идём по очереди полей, собираем изменения и
    # применяем всё разом, когда очередь закончится
    queue = state["queue"]
    idx = state["idx"]
    field = queue[idx]
    collected = state.get("collected", {})

    if text.lower() not in _SKIP_WORDS:
        ok, result = _validate_field(org, field, text)
        if not ok:
            return result + " " + _ask_field(org, field, allow_skip=True)
        collected[field] = result

    idx += 1
    if idx < len(queue):
        state["idx"] = idx
        state["collected"] = collected
        chat.flow_state = json.dumps(state)
        return _ask_field(org, queue[idx], allow_skip=True)

    chat.flow_state = json.dumps({"step": "done"})
    if not collected:
        return "Изменений не внесено — данные организации остались прежними."

    old_values = {f: _current_field_value(org, f) for f in collected}
    _apply_changes(org, collected)
    lines = [
        f"«{FIELD_LABELS[f]}»: «{old_values[f]}» → «{_display_value(f, v)}»"
        for f, v in collected.items()
    ]
    summary = "; ".join(lines)
    _notify_change_applied(user_id, summary)
    return "Данные организации обновлены:\n" + "\n".join(lines)


def handle_org_edit_message(chat, content, user):
    """Точка входа из chat_bp.send_message — обрабатывает очередное сообщение
    пользователя в сценарии 'org-edit' и возвращает текст ответа бота."""
    state = json.loads(chat.flow_state) if chat.flow_state else {}
    step = state.get("step")

    if not step:
        return _start_flow(chat, user)

    org = user.organization
    if not org:
        chat.flow_state = json.dumps({"step": "done"})
        return "Организация не найдена. Обратитесь к администратору."

    if step == "await_confirm":
        return _handle_confirm_answer(chat, content)

    if step == "await_scope":
        return _handle_scope_answer(chat, org, content)

    if step == "await_value":
        blocked, reason = _check_plan_lock(org)
        if blocked:
            chat.flow_state = json.dumps({"step": "done"})
            return reason
        return _handle_value_answer(chat, org, state, content, user.id)

    if step == "done":
        return (
            "Обращение по изменению данных организации завершено. Чтобы "
            "задать новый вопрос, нажмите «Завершить чат» и выберите тему заново."
        )

    chat.flow_state = None
    return _start_flow(chat, user)
