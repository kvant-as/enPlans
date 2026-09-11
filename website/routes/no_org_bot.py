"""Обращение «Нет организации» в виджете виртуального помощника.

Раньше тип 'no-org' уходил во внешний ИИ-бэкенд и был доступен только
администраторам (см. chat_bp.py, комментарий "ИИ-помощник пока доступен
только администраторам"). Переведён на собственный скриптованный сценарий —
по аналогии с 'dif' и 'org-edit' (org_edit_bot.py).

Сценарий не смотрит на то, какая организация сейчас указана в профиле
пользователя — сразу идёт по порядку и просит заполнить данные организации
(наименование → ОКПО → УНП → регион), как при регистрации новой. Но по
ходу дела, как только введён ОКПО или УНП, бот проверяет базу: если такая
организация уже существует, он останавливает сбор данных, переспрашивает
«это ваша организация?» и, если да, не создаёт дубль — просто привязывает
найденную организацию к профилю и сразу переходит к вопросу о роли в
цепочке согласования (Organization.is_regular/is_coordinator/is_approver/
is_region_management — самая частая причина, по которой часть функционала
выглядит так, будто организации нет вовсе, хотя она есть).

Полностью автоматический — без ИИ и без администратора, изменения
применяются сразу. Состояние диалога — в Chat.flow_state (JSON), как и у
'org-edit'.
"""
import json

from common_models import current_utc_time, db, validate_okpo, validate_ynp

from ..models import Notification, Organization, Region

NO_ORG_CHAT_TYPE = 'no-org'

# "Региональное управление" в список для самостоятельного выбора не входит —
# эта роль присваивается администратором отдельно, не через чат
ROLE_ORDER = ["is_regular", "is_coordinator", "is_approver"]
ROLE_LABELS = {
    "is_regular": "Обычная организация — подаёт свои планы",
    "is_coordinator": "Согласовывающая организация",
    "is_approver": "Утверждающая организация",
}

NEW_ORG_FIELD_ORDER = ["full_name", "okpo", "ynp", "region_id"]
NEW_ORG_FIELD_LABELS = {
    "full_name": "наименование организации",
    "okpo": "ОКПО",
    "ynp": "УНП",
    "region_id": "регион",
}
# поля, по которым при вводе проверяем совпадение с уже существующей
# организацией в базе — см. _handle_new_field_answer
_DUP_CHECK_FIELDS = {"okpo", "ynp"}

_CONFIRM_YES = {"да", "да.", "yes", "ок", "окей", "хорошо", "конечно"}
_CONFIRM_NO = {"нет", "нет.", "no", "отмена", "не хочу", "не надо"}
_BAIL_PHRASES = {"ничего из этого", "другое", "не то", "не мой вопрос"}


def _with_quick_replies(text, options):
    """См. одноимённый приём в org_edit_bot.py — chat.js вырезает маркер
    перед отображением и рисует вместо него кнопки-чипы."""
    return text + "\n[[QUICK_REPLIES:" + "|".join(options) + "]]"


def _truncate(text, limit=140):
    text = text.strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def _notify(user_id, message):
    db.session.add(Notification(
        user_id=user_id, message=_truncate(message), created_at=current_utc_time(),
    ))
    db.session.commit()


# --------------------------------------------------------------- роль ----

def _missing_roles(org):
    return [r for r in ROLE_ORDER if not getattr(org, r, False)]


def _ask_role(org):
    """None, если у организации уже отмечены все роли."""
    missing = _missing_roles(org)
    if not missing:
        return None
    text = (
        f"У организации «{org.full_name}» не отмечена роль в цепочке "
        "согласования. Какая роль ей подходит?"
    )
    options = [ROLE_LABELS[r] for r in missing]
    return _with_quick_replies(text, options)


def _match_role(text):
    key = text.strip().lower().strip('«»"\'.')
    if key in _BAIL_PHRASES:
        return "bail"
    for role, label in ROLE_LABELS.items():
        if key == label.lower() or key == label.split(" —")[0].strip().lower():
            return role
    return None


def _handle_role_answer(chat, org, content, user_id):
    match = _match_role(content)

    if match == "bail":
        chat.flow_state = json.dumps({"step": "done"})
        return (
            "Хорошо, если дело не в роли организации — опишите вопрос "
            "подробнее через обращение «Другое», его увидит администратор."
        )

    if match is None:
        return "Не поняла ваш выбор. " + (_ask_role(org) or "")

    setattr(org, match, True)
    db.session.commit()
    _notify(user_id, f'Организации «{org.full_name}» присвоена роль «{ROLE_LABELS[match]}»')

    reask = _ask_role(org)
    if reask is None:
        chat.flow_state = json.dumps({"step": "done"})
        return f"Готово! Организации «{org.full_name}» присвоена роль «{ROLE_LABELS[match]}»."

    chat.flow_state = json.dumps({"step": "await_role_more", "org_id": org.id})
    return _with_quick_replies(
        f"Готово! Организации «{org.full_name}» присвоена роль «{ROLE_LABELS[match]}». "
        "Нужно добавить ещё одну роль?",
        ["Да", "Нет"],
    )


def _handle_role_more_answer(chat, org, content, user_id):
    key = content.strip().lower()
    if key in _CONFIRM_NO:
        chat.flow_state = json.dumps({"step": "done"})
        return "Хорошо, обращение завершено."
    if key not in _CONFIRM_YES:
        return _with_quick_replies("Не поняла ваш ответ. Добавить ещё одну роль?", ["Да", "Нет"])

    reask = _ask_role(org)
    if reask is None:
        chat.flow_state = json.dumps({"step": "done"})
        return "У организации уже отмечены все роли."
    chat.flow_state = json.dumps({"step": "await_role", "org_id": org.id})
    return reask


def _link_and_ask_role(chat, org, user):
    if user.organization_id != org.id:
        user.organization_id = org.id
        db.session.commit()

    reask = _ask_role(org)
    if reask is None:
        chat.flow_state = json.dumps({"step": "done"})
        return (
            f"Организация «{org.full_name}» привязана к вашему профилю. У неё уже "
            "отмечены все роли — если дело не в этом, опишите вопрос через «Другое»."
        )
    chat.flow_state = json.dumps({"step": "await_role", "org_id": org.id})
    return f"Организация «{org.full_name}» привязана к вашему профилю.\n\n" + reask


# ------------------------------------------------------- заполнение данных

def _ask_new_field(field):
    if field == "region_id":
        options = [r.name for r in Region.query.order_by(Region.number).all()]
        return _with_quick_replies("Выберите регион организации из списка.", options)

    hint = ""
    if field == "okpo":
        hint = " (12 цифр)"
    elif field == "ynp":
        hint = " (9 цифр)"
    return f"Введите {NEW_ORG_FIELD_LABELS[field]}{hint}."


def _validate_new_field(field, text):
    """Возвращает (True, значение_для_записи) либо (False, текст_ошибки) —
    только проверка формата; совпадение с уже существующей организацией по
    ОКПО/УНП проверяется отдельно в _handle_new_field_answer, потому что это
    не ошибка, а повод переспросить пользователя, а не отклонить ввод."""
    if field == "full_name":
        if len(text.strip()) < 3:
            return False, "Название слишком короткое."
        return True, text.strip()

    if field == "okpo":
        digits = text.strip()
        ok, err = validate_okpo(digits)
        return (True, digits) if ok else (False, err + ".")

    if field == "ynp":
        digits = text.strip()
        ok, err = validate_ynp(digits)
        return (True, digits) if ok else (False, err + ".")

    if field == "region_id":
        name = text.strip().lower()
        region = Region.query.filter(db.func.lower(Region.name) == name).first()
        if not region:
            return False, "Регион не найден — выберите точно из списка."
        return True, region.id

    return False, "Неизвестное поле."


def _find_existing_org(field, value):
    if field == "okpo":
        return Organization.query.filter_by(okpo=value).first()
    if field == "ynp":
        return Organization.query.filter_by(ynp=value).first()
    return None


def _handle_new_field_answer(chat, state, content, user):
    idx = state["field_idx"]
    field = NEW_ORG_FIELD_ORDER[idx]
    collected = state.get("collected", {})

    ok, result = _validate_new_field(field, content)
    if not ok:
        return result + " " + _ask_new_field(field)

    if field in _DUP_CHECK_FIELDS:
        existing = _find_existing_org(field, result)
        if existing:
            chat.flow_state = json.dumps({
                "step": "await_dup_confirm",
                "org_id": existing.id,
                "field_idx": idx,
                "collected": collected,
            })
            return _with_quick_replies(
                f"Организация с таким {NEW_ORG_FIELD_LABELS[field]} уже есть в базе: "
                f"«{existing.full_name}» (ОКПО {existing.okpo or '—'}). Это ваша организация?",
                ["Да", "Нет"],
            )

    collected[field] = result
    idx += 1
    if idx < len(NEW_ORG_FIELD_ORDER):
        chat.flow_state = json.dumps({"step": "await_new_field", "field_idx": idx, "collected": collected})
        return _ask_new_field(NEW_ORG_FIELD_ORDER[idx])

    # При регистрации новой организации роль "Обычная" выставляется сразу
    # автоматически — не нужно об этом спрашивать; дальше только предлагаем
    # (необязательно) добавить согласовывающую/утверждающую роль
    org = Organization(
        full_name=collected["full_name"],
        okpo=collected["okpo"],
        ynp=collected["ynp"],
        region_id=collected["region_id"],
        is_regular=True,
    )
    db.session.add(org)
    db.session.flush()
    user.organization_id = org.id
    db.session.commit()
    _notify(user.id, f'Организация «{org.full_name}» зарегистрирована и привязана к вашему профилю')

    intro = f"Организация «{org.full_name}» зарегистрирована и привязана к вашему профилю."
    if not _missing_roles(org):
        chat.flow_state = json.dumps({"step": "done"})
        return intro

    chat.flow_state = json.dumps({"step": "await_role_more", "org_id": org.id})
    return _with_quick_replies(
        intro + " Нужна ли ей ещё и согласовывающая или утверждающая роль?",
        ["Да", "Нет"],
    )


def _handle_dup_confirm(chat, state, content, user):
    key = content.strip().lower()
    org = Organization.query.get(state.get("org_id"))
    field_idx = state.get("field_idx", 0)
    collected = state.get("collected", {})

    if key in _CONFIRM_YES and org:
        return _link_and_ask_role(chat, org, user)

    # "Нет" (или запись успела пропасть) — возвращаемся к тому же полю,
    # уже собранные данные (например, наименование) не теряем
    chat.flow_state = json.dumps({"step": "await_new_field", "field_idx": field_idx, "collected": collected})
    field = NEW_ORG_FIELD_ORDER[field_idx]
    hint = "Хорошо, попробуйте ещё раз. " if key in _CONFIRM_NO else "Не поняла ваш ответ. "
    return hint + _ask_new_field(field)


# ----------------------------------------------------------- точка входа -

def _start_flow(chat, user):
    chat.flow_state = json.dumps({"step": "await_new_field", "field_idx": 0, "collected": {}})
    return (
        "Здравствуйте! Давайте по порядку заполним данные вашей организации.\n\n"
        + _ask_new_field(NEW_ORG_FIELD_ORDER[0])
    )


def handle_no_org_message(chat, content, user):
    """Точка входа из chat_bp.send_message — обрабатывает очередное
    сообщение пользователя в сценарии 'no-org' и возвращает ответ бота."""
    state = json.loads(chat.flow_state) if chat.flow_state else {}
    step = state.get("step")

    if not step:
        return _start_flow(chat, user)

    if step == "await_new_field":
        return _handle_new_field_answer(chat, state, content, user)

    if step == "await_dup_confirm":
        return _handle_dup_confirm(chat, state, content, user)

    if step in ("await_role", "await_role_more"):
        org = Organization.query.get(state.get("org_id"))
        if not org:
            chat.flow_state = json.dumps({"step": "done"})
            return "Организация не найдена. Обратитесь к администратору."
        if step == "await_role":
            return _handle_role_answer(chat, org, content, user.id)
        return _handle_role_more_answer(chat, org, content, user.id)

    if step == "done":
        return (
            "Обращение по организации завершено. Чтобы задать новый вопрос, "
            "нажмите «Завершить чат» и выберите тему заново."
        )

    chat.flow_state = None
    return _start_flow(chat, user)
