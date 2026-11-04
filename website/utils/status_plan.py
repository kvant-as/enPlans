from flask import current_app
from flask_login import current_user
from ..models import PlanTicket, Notification, PlanApprovalPath, User

from common_models.timeutils import current_utc_time
from website import db


CANCEL_SEND_NOTE_PREFIX = 'Отправка отменена'


def _latest_cycle(plan_id):
    """Номер последнего (текущего) цикла отправки плана — старые циклы
    (отменённые/замещённые повторной отправкой) больше не удаляются из
    PlanApprovalPath, поэтому любой запрос "текущего этапа" обязан
    фильтроваться по этому циклу, иначе найдёт брошенный этап из
    прошлого, отменённого цикла."""
    cycle = db.session.query(db.func.max(PlanApprovalPath.cycle)).filter(
        PlanApprovalPath.plan_id == plan_id
    ).scalar()
    return cycle or 1


def _unlink_stale_remark_tickets(path):
    """Отмена подтверждения этапа (is_viewed сбрасывается на ТОМ ЖЕ
    path.id — в отличие от повторной отправки, новый цикл/новые строки
    тут не создаются) не трогает PlanTicket.approval_path_id старых
    сообщений, написанных ДО подтверждения — has_pending_review_message
    видел бы их как "уже есть сообщение по этому этапу" и не давал бы
    написать новое. Отвязываем все НЕ системные сообщения, привязанные к
    этому этапу: они относятся к состоянию, которое только что отменили,
    и теперь не должны считаться актуальным замечанием по новой попытке.
    Заодно сбрасываем path.ticket_id — "то самое" замечание шага
    (см. PlanApprovalPath.ticket) тоже относится к отменённому состоянию."""
    PlanTicket.query.filter_by(approval_path_id=path.id, is_system=False).update(
        {'approval_path_id': None}
    )
    path.ticket_id = None


def handle_draft_status(plan, reason=None, attachment_file=None):
    """«Отменить отправку» (доступна только первые 5 минут после реальной
    внешней отправки, см. api_change_plan_status) — возвращает план не в
    «В редакции» с нуля, а на тот же этап внутреннего подписания, на
    котором он был прямо перед отправкой: тому же человеку (последнему
    внутреннему подписанту, plan.internal_signed_by_user_id —
    handle_sent_status его больше не очищает) снова нужно подписать и
    отправить, по тому же маршруту (pending_coordinator_ids/pending_approver_id
    — тоже не очищаются при отправке) — заново выбирать организации не
    нужно. is_control тоже восстанавливаем в True — handle_sent_status
    сбрасывает его в False при реальной отправке, а до этого момента (с
    "Пройти контроль" и до самой отправки) он был True."""
    try:
        was_sent = plan.is_sent

        plan.is_sent = False
        plan.is_error = False
        plan.is_approved = False
        plan.sent_time = None

        if was_sent:
            plan.pending_signer_user_id = plan.internal_signed_by_user_id
            plan.is_signed = False
            plan.is_control = True

        plan.change_time = current_utc_time()

        if was_sent and reason and reason.strip():
            ticket = PlanTicket(
                note=f'{CANCEL_SEND_NOTE_PREFIX}. Причина: {reason.strip()}',
                is_system=True,
                user_id=current_user.id if current_user.is_authenticated else None,
                plan_id=plan.id,
                begin_time=current_utc_time(),
            )
            db.session.add(ticket)
            if attachment_file and attachment_file.filename:
                from website.utils.ticket_attachment import save_ticket_attachment
                db.session.flush()
                save_ticket_attachment(ticket, attachment_file)

        db.session.commit()

        return {'message': 'Отправка отменена, план возвращён на этап внутреннего подписания'}

    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при отмене отправки: {str(e)}'}

def handle_control_status(plan):
    errors = []

    try:
        from website.utils.teo import find_directions_missing_teo

        missing_teo = find_directions_missing_teo(plan)
        if missing_teo:
            code, _name = missing_teo[0]
            errors.append(
                f'План не может пройти контроль. Отсутствует обязательное ТЭО по направлению '
                f'энергосбережению с кодом: {code}. Необходимо прикрепить файл ТЭО в графу 20 '
                f'хотя бы к одному мероприятию с этим кодом.'
            )

        indicator_9999 = next(
            (iu for iu in plan.indicators_usage if iu.indicator.code == '9999'), 
            None
        )
        indicator_9900 = next(
            (iu for iu in plan.indicators_usage if iu.indicator.code == '9900'), 
            None
        )
        indicator_9911 = next(
            (iu for iu in plan.indicators_usage if iu.indicator.code == '9911'), 
            None
        )
        indicator_9912 = next(
            (iu for iu in plan.indicators_usage if iu.indicator.code == '9912'), 
            None
        )
        indicator_9913 = next(
            (iu for iu in plan.indicators_usage if iu.indicator.code == '9913'), 
            None
        )
        indicator_9914 = next(
            (iu for iu in plan.indicators_usage if iu.indicator.code == '9914'), 
            None
        )
        indicator_9915 = next(
            (iu for iu in plan.indicators_usage if iu.indicator.code == '9915'), 
            None
        )
        indicator_9916 = next(
            (iu for iu in plan.indicators_usage if iu.indicator.code == '9916'), 
            None
        )
        indicator_9917 = next(
            (iu for iu in plan.indicators_usage if iu.indicator.code == '9917'), 
            None
        )
        
        # Проверка 1: Годовая экономия ТЭР
        # Сравнение 9999 (считается автоматически) с 9900 исключено — эти
        # значения не обязаны совпадать, это было неверное утверждение.
        if indicator_9999 and indicator_9900:
            try:
                if indicator_9999.QYearCurrent < (indicator_9914.QYearCurrent if indicator_9914 else 0):
                    errors.append("Годовая экономия ТЭР от энергосберегающих мероприятий всего должна быть больше или равна экономии ТЭР от мероприятий предыдущего года внедрения (январь-декабрь).")
            except AttributeError as e:
                current_app.logger.error(f"Ошибка при проверке индикаторов 9999/9900: {e}")
                errors.append("Ошибка при проверке годовой экономии ТЭР")
        
        # Проверка 2: Экономия ТЭР по периодам
        if indicator_9911 and indicator_9912 and indicator_9913 and indicator_9914:
            try:
                if indicator_9914.QYearCurrent < indicator_9913.QYearCurrent:
                    errors.append("Экономия ТЭР за январь-декабрь должна быть больше или равна экономии за январь-сентябрь.")
                
                if indicator_9913.QYearCurrent < indicator_9912.QYearCurrent:
                    errors.append("Экономия ТЭР за январь-сентябрь должна быть больше или равна экономии за январь-июнь.")
                
                if indicator_9912.QYearCurrent < indicator_9911.QYearCurrent:
                    errors.append("Экономия ТЭР за январь-июнь должна быть больше или равна экономии за январь-март.")
            except AttributeError as e:
                current_app.logger.error(f"Ошибка при проверке индикаторов 9911-9914: {e}")
                errors.append("Ошибка при проверке экономии ТЭР по периодам")
        
        # Проверка 3: Целевой показатель энергосбережения
        if indicator_9915 and plan.energy_saving:
            try:
                if indicator_9915.QYearCurrent > plan.energy_saving:
                    errors.append(f"Целевой показатель энергосбережения ({indicator_9915.QYearCurrent}%) не должен превышать задание ({plan.energy_saving}%).")
            except AttributeError as e:
                current_app.logger.error(f"Ошибка при проверке индикатора 9915: {e}")
                errors.append("Ошибка при проверке целевого показателя энергосбережения")
        
        # Проверка 4: Целевой показатель по экономии ТЭР (задание на титульном
        # листе, plan.saving_fuel) сравнивается с п.5 "Годовая экономия ТЭР
        # от энергосберегающих мероприятий всего" (индикатор 9999), а не с
        # 9900 "Ожидаемая экономия ТЭР от внедрения мероприятий в текущем
        # году" — это разные показатели, сравнение с 9900 было ошибочным.
        if indicator_9999 and plan.saving_fuel:
            try:
                if indicator_9999.QYearCurrent < plan.saving_fuel:
                    errors.append(f"Годовая экономия ТЭР ({indicator_9999.QYearCurrent} т у.т.) должна быть больше или равна заданию по экономии ТЭР ({plan.saving_fuel} т у.т.).")
            except AttributeError as e:
                current_app.logger.error(f"Ошибка при проверке индикатора 9999: {e}")
                errors.append("Ошибка при проверке годовой экономии ТЭР")
        
        # Проверка 5: Доля местных ТЭР
        if indicator_9916 and plan.share_fuel:
            try:
                if indicator_9916.QYearCurrent < plan.share_fuel:
                    errors.append(f"Целевой показатель по доле местных ТЭР в КПТ ({indicator_9916.QYearCurrent}%) должен быть больше или равен заданию ({plan.share_fuel}%).")
            except AttributeError as e:
                current_app.logger.error(f"Ошибка при проверке индикатора 9916: {e}")
                errors.append("Ошибка при проверке доли местных ТЭР")
        
        # Проверка 6: Доля ВИЭ
        if indicator_9917 and plan.share_energy:
            try:
                if indicator_9917.QYearCurrent < plan.share_energy:
                    errors.append(f"Целевой показатель по доле ВИЭ в КПТ ({indicator_9917.QYearCurrent}%) должен быть больше или равен заданию ({plan.share_energy}%).")
            except AttributeError as e:
                current_app.logger.error(f"Ошибка при проверке индикатора 9917: {e}")
                errors.append("Ошибка при проверке доли ВИЭ")
        
        if errors:
            current_app.logger.warning(f"План {plan.id} не прошел проверку. Ошибок: {len(errors)}")
            return {"error": "\n".join(errors)}
        
        plan.is_control = True
        plan.is_draft = plan.is_sent = plan.is_error = plan.is_approved = False
        plan.afch = False
        
        db.session.commit()
        
        current_app.logger.info(f"План {plan.id} успешно прошел проверку на контроль")
        return "План прошел проверку на контроль"
        
    except Exception as e:
        current_app.logger.error(f"Критическая ошибка в handle_control_status для плана {plan.id if hasattr(plan, 'id') else 'unknown'}: {e}", exc_info=True)
        return {"error": f"Произошла ошибка при проверке плана. Пожалуйста, попробуйте позже."}

def handle_sent_status(plan, coordinator_ids=None, approver_id=None):
    try:
        from website.utils.plans import build_approval_chain

        if not plan.organization or not plan.organization.region_id:
            return {'error': 'У плана не указан регион'}

        # Если маршрут не передан явно — берём сохранённый на шаге
        # «Отправить на подпись» (внутренний цикл подписания, см.
        # submit_for_signature/internal_sign в plan_bp.py): к моменту
        # фактической внешней отправки клиентское состояние визарда
        # plan_send.html давно недоступно (другой человек/сессия).
        if not coordinator_ids and plan.pending_coordinator_ids:
            coordinator_ids = plan.pending_coordinator_ids.split(',')
        if not approver_id and plan.pending_approver_id:
            approver_id = plan.pending_approver_id

        # Проверяем ИМЕННО вручную выбранный маршрут — Департамент (если
        # добавится по порогу потребления) не считается заменой выбору
        # согласующих/утверждающего.
        if not coordinator_ids and not approver_id:
            return {'error': 'Не выбраны организации для согласования и утверждения'}

        chain = build_approval_chain(plan, coordinator_ids=coordinator_ids, approver_id=approver_id)

        region_org = next((org for step_type, org in chain if step_type == 'region'), None)
        if not region_org:
            return {'error': 'Региональное управление не найдено для этого региона'}

        # Раньше старый маршрут полностью удалялся при каждой повторной
        # отправке — история прошлых циклов (включая отменённые) терялась
        # без следа. Теперь прежние строки остаются как есть (история),
        # а новый цикл отправки получает следующий номер cycle.
        last_cycle = db.session.query(db.func.max(PlanApprovalPath.cycle)).filter(
            PlanApprovalPath.plan_id == plan.id
        ).scalar()
        new_cycle = (last_cycle or 0) + 1

        # Снимок отправителя на МОМЕНТ именно этой отправки — иначе строка
        # в "Подписи" брался бы живым джойном и у ВСЕХ прошлых отправок
        # задним числом менялись бы ФИО/телефон при правке профиля.
        # Фактически план отправляет тот, кто его подписал внутренним
        # ЭЦП-циклом (internal_signed_by_user_id) — а не обязательно
        # создатель плана (plan.user); если цикл не использовался
        # (старые планы/админ-override) — откатываемся на plan.user.
        sender = User.query.get(plan.internal_signed_by_user_id) if plan.internal_signed_by_user_id else plan.user
        sender_name = ' '.join(filter(None, [sender.last_name, sender.first_name, sender.patronymic_name])) if sender else None
        sender_post = sender.post if sender else None
        sender_phone = sender.telephone if sender else None
        sender_email = sender.email if sender else None

        # Внешние строки продолжают нумерацию step_order ПОСЛЕ уже
        # записанных шагов внутренней цепочки этой попытки (is_internal=True,
        # cycle=0 — "ещё не отправлено", см. internal_sign/
        # forward_internal_signature) — один непрерывный путь плана.
        internal_order_start = (db.session.query(db.func.max(PlanApprovalPath.step_order))
            .filter_by(plan_id=plan.id, cycle=0, is_internal=True).scalar() or 0) + 1

        for step_order, (step_type, org) in enumerate(chain, start=internal_order_start):
            db.session.add(PlanApprovalPath(
                plan_id=plan.id,
                step_order=step_order,
                organization_id=org.id,
                step_type=step_type,
                is_internal=False,
                created_at=current_utc_time(),
                cycle=new_cycle,
                sender_post=sender_post,
                sender_name=sender_name,
                sender_phone=sender_phone,
                sender_email=sender_email,
            ))

        # Шаги внутренней цепочки этой попытки (submit_for_signature/
        # forward_internal_signature/internal_sign) привязываются к этому
        # же номеру цикла — теперь это постоянная история, видимая в
        # "Подписи" вместе с внешними организациями.
        PlanApprovalPath.query.filter_by(plan_id=plan.id, cycle=0, is_internal=True).update({'cycle': new_cycle})

        plan.sent_time = current_utc_time()
        plan.is_sent = True
        plan.is_draft = False
        plan.is_control = False
        plan.is_error = False
        plan.is_approved = False
        plan.afch = False

        # Внутренний цикл подписания завершён — план ушёл во внешний
        # маршрут (PlanApprovalPath выше). pending_signer_user_id ОБЯЗАТЕЛЬНО
        # чистим (иначе остальные сотрудники ошибочно увидят "ожидает
        # подписи" у уже отправленного плана). internal_signed_by_user_id/
        # internal_signed_at/pending_coordinator_ids/pending_approver_id —
        # больше НЕ чистим: это теперь снимок "кто и по какому маршруту
        # последний раз подписывал и отправлял", нужный для "Отменить
        # отправку" (см. handle_draft_status) — он их безвредно перезатрёт
        # следующий submit_for_signature/internal_sign в штатном цикле.
        plan.is_signed = False
        plan.pending_signer_user_id = None
        plan.submitted_by_user_id = None

        db.session.commit()

        return {'message': 'План успешно отправлен на согласование'}
        
    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при отправке плана: {str(e)}'}

def handle_sent_without_check_status(plan, current_user, reason=None):
    try:
        cycle = _latest_cycle(plan.id)

        if current_user.is_auditor:
            # Если одна и та же организация занимает НЕСКОЛЬКО ролей/этапов
            # в цепочке согласования одного цикла (например, одновременно
            # region и approver — на малых тестовых конфигурациях это
            # обычное дело), filter_by(...).first() без сортировки мог
            # взять ЛЮБОЙ из её подтверждённых этапов — не обязательно тот,
            # который проверяющий только что подтвердил и теперь пытается
            # отменить. Снаружи это выглядело как "ничего не поменялось":
            # отменялся не тот (случайно выбранный более ранний) этап, а
            # ожидаемый на странице "Подписи" оставался как был.
            confirmed_path = PlanApprovalPath.query.filter_by(
                plan_id=plan.id,
                cycle=cycle,
                organization_id=current_user.organization_id,
                is_internal=False,
                is_viewed=True
            ).order_by(PlanApprovalPath.viewed_at.desc(), PlanApprovalPath.step_order.desc()).first()

            # Если вы ничего не подтверждали, а, наоборот, отклонили план
            # ("Есть ошибки") — can_cancel разрешает "Отменить изменения" и
            # в этом случае (см. get_audit_context: can_cancel учитывает
            # plan.is_error независимо от того, кто именно отклонил), но
            # отклонение не ставит is_viewed=True — вместо этого у этапа
            # проставлен rejected_at. Ищем такой этап отдельно, если
            # подтверждённого не нашлось.
            rejected_path = None
            if not confirmed_path:
                rejected_path = PlanApprovalPath.query.filter_by(
                    plan_id=plan.id,
                    cycle=cycle,
                    organization_id=current_user.organization_id,
                    is_internal=False,
                ).filter(PlanApprovalPath.rejected_at.isnot(None)).order_by(
                    PlanApprovalPath.rejected_at.desc(), PlanApprovalPath.step_order.desc()
                ).first()

            current_path = confirmed_path or rejected_path
            if not current_path:
                return {'error': 'Не найден подтверждённый или отклонённый вами этап для отмены'}

            plan.is_sent = True
            plan.is_draft = False
            plan.is_control = False
            plan.is_error = False
            plan.is_approved = False
            plan.afch = False

            if confirmed_path:
                current_path.is_viewed = False
                current_path.viewed_at = None
                current_path.viewed_by_user_id = None
                current_path.viewed_by_snapshot = None
            else:
                current_path.rejected_at = None
                current_path.rejected_by_snapshot = None

            _unlink_stale_remark_tickets(current_path)

            notification = Notification(
                user_id=plan.user_id,
                message=f"План {plan.year} возвращен на этап согласования",
                created_at=current_utc_time()
            )
            db.session.add(notification)
        else:
            plan.is_sent = True
            plan.is_draft = False
            plan.is_control = False
            plan.is_error = False
            plan.is_approved = False
            plan.afch = False

            PlanApprovalPath.query.filter_by(plan_id=plan.id, cycle=cycle, is_internal=False).update(
                {'is_viewed': False, 'viewed_at': None}
            )

            notification = Notification(
                user_id=plan.user_id,
                message=f"План {plan.year} возвращен в статус рассмотрения.",
                created_at=current_utc_time()
            )
            db.session.add(notification)
        
        db.session.commit()
        
        return {'message': 'План возвращен в изначальное состояние.'}
        
    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при возврате плана: {str(e)}'}

def handle_error_status(plan, current_user):
    try:
        from website.utils.plans import get_current_review_path, build_signer_snapshot, create_plan_snapshot

        # Этап, который проверяющий сейчас отклоняет — is_viewed/viewed_at
        # для него так и останутся False/None (этап не пройден), поэтому
        # сам факт и момент отклонения фиксируем отдельными полями, иначе
        # "Подписи" не смогут показать, когда и кем план был возвращён.
        current_path = get_current_review_path(plan, current_user)

        # Раньше проверялось has_pending_review_message(plan, current_user) —
        # что СВОЁ сообщение оставил именно тот, кто сейчас жмёт кнопку. Эту
        # функцию вызывает теперь не исполнитель (он решение принял раньше,
        # на шаге "Не согласовать и направить на подпись" — см.
        # plan_bp.py::step_submit_for_signature, там же и обязательное
        # вложение уже проверено), а подписавший руководитель — проверяем,
        # что сообщение с замечаниями на этом этапе вообще есть, от кого бы
        # из организации оно ни было оставлено.
        review_message = next(
            (t for t in plan.tickets if current_path and not t.is_system and t.approval_path_id == current_path.id),
            None
        ) if current_path else None
        if not review_message:
            return {'error': 'Сначала необходимо отправить сообщение с замечаниями'}

        now = current_utc_time()

        if current_path:
            current_path.rejected_at = now
            current_path.rejected_by_snapshot = build_signer_snapshot(current_user)
            # "То самое" замечание шага для столбца "Замечания" в "Подписи"
            # (см. PlanApprovalPath.ticket) — реальное сообщение из чата
            # проверки, которое уже обязательно есть (см. review_message
            # выше), отдельный технический тикет больше не создаётся.
            current_path.ticket_id = review_message.id

        plan.audit_time = now
        plan.is_error = True
        plan.is_draft = False
        plan.is_control = False
        plan.is_sent = False
        plan.is_approved = False
        plan.afch = False

        # Замораживаем план "как есть" ПРЯМО СЕЙЧАС — это единственный
        # момент, когда его содержимое гарантированно совпадает с тем, что
        # увидел и отклонил проверяющий; при первой же правке организации
        # update_ChangeTimePlan сбросит is_error/is_draft на живой строке,
        # и момент отклонения будет уже не восстановить (см.
        # create_plan_snapshot в utils/plans.py).
        create_plan_snapshot(plan)

        notification = Notification(
            user_id=plan.user_id,
            message=f"В плане на {plan.year} год нашли ошибки.",
            created_at=current_utc_time()
        )
        db.session.add(notification)
        db.session.commit()
        
        return {'message': 'Статус ошибки установлен'}
        
    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при установке статуса ошибки: {str(e)}'}

def handle_approved_status(plan, current_user):
    try:
        if not current_user.organization_id:
            return {'error': 'У пользователя не указана организация'}

        cycle = _latest_cycle(plan.id)

        current_path = PlanApprovalPath.query.filter_by(
            plan_id=plan.id,
            cycle=cycle,
            is_viewed=False
        ).order_by(PlanApprovalPath.step_order).first()

        if not current_path:
            return {'error': 'Все этапы уже пройдены'}

        if current_path.organization_id != current_user.organization_id:
            return {'error': 'У вас нет прав на согласование этого этапа'}

        prev_path = PlanApprovalPath.query.filter(
            PlanApprovalPath.plan_id == plan.id,
            PlanApprovalPath.cycle == cycle,
            PlanApprovalPath.step_order == current_path.step_order - 1
        ).first()

        if prev_path and not prev_path.is_viewed:
            return {'error': 'Предыдущий этап еще не пройден'}

        from website.utils.plans import build_signer_snapshot

        current_path.is_viewed = True
        current_path.viewed_at = current_utc_time()
        current_path.viewed_by_user_id = current_user.id
        current_path.viewed_by_snapshot = build_signer_snapshot(current_user)

        plan.audit_time = current_utc_time()
        plan.afch = False

        next_path = PlanApprovalPath.query.filter_by(
            plan_id=plan.id,
            cycle=cycle,
            is_viewed=False
        ).order_by(PlanApprovalPath.step_order).first()
        
        if not next_path:
            plan.is_approved = True
            plan.is_draft = False
            plan.is_control = False
            plan.is_sent = False
            plan.is_error = False

            notification = Notification(
                user_id=plan.user_id,
                message=f"План на {plan.year} был утвержден",
                created_at=current_utc_time()
            )
            db.session.add(notification)

            message = "План полностью согласован и утвержден"
        else:
            message = "Этап успешно согласован"
        
        db.session.commit()

        return {'message': message}

    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при согласовании: {str(e)}'}


def handle_admin_confirm_step(plan, path_id, admin_user):
    """Администратор подтверждает произвольный этап согласования, минуя
    обычную очередь (в отличие от handle_approved_status, который
    подтверждает только "свой" текущий этап).

    Нюанс: подтверждаются также все более ранние ещё не пройденные этапы
    — иначе нарушился бы порядок прохождения (обычный пользователь не
    может согласовать свой этап, пока не пройдены предыдущие — см.
    handle_approved_status), а после подтверждения выбранного этапа он
    формально стал бы "текущим", даже если раньше него остались
    непройденные. Если подтверждённый этап оказался последним по
    порядку — план, как и в обычном флоу, полностью утверждается.
    """
    try:
        target_path = PlanApprovalPath.query.filter_by(id=path_id, plan_id=plan.id).first()
        if not target_path:
            return {'error': 'Этап согласования не найден'}

        if target_path.is_viewed:
            return {'error': 'Этап уже подтверждён'}

        paths_to_confirm = PlanApprovalPath.query.filter(
            PlanApprovalPath.plan_id == plan.id,
            PlanApprovalPath.cycle == target_path.cycle,
            PlanApprovalPath.step_order <= target_path.step_order,
            PlanApprovalPath.is_viewed == False
        ).order_by(PlanApprovalPath.step_order).all()

        from website.utils.plans import build_signer_snapshot

        now = current_utc_time()
        admin_snapshot = build_signer_snapshot(admin_user)
        for path in paths_to_confirm:
            path.is_viewed = True
            path.viewed_at = now
            path.viewed_by_user_id = admin_user.id
            path.viewed_by_snapshot = admin_snapshot

        plan.audit_time = now
        plan.afch = False

        last_path = PlanApprovalPath.query.filter_by(plan_id=plan.id, cycle=target_path.cycle).order_by(
            PlanApprovalPath.step_order.desc()
        ).first()
        is_final = bool(last_path and last_path.id == target_path.id)

        if is_final:
            plan.is_approved = True
            plan.is_draft = False
            plan.is_control = False
            plan.is_sent = False
            plan.is_error = False

            notif_message = f"План на {plan.year} год был утвержден администратором"
            result_message = 'План полностью согласован и утвержден администратором'
        else:
            notif_message = f"Этап согласования плана на {plan.year} год подтвержден администратором"
            result_message = 'Этап подтвержден администратором'

        notification = Notification(
            user_id=plan.user_id,
            message=notif_message,
            created_at=now
        )
        db.session.add(notification)

        db.session.commit()

        return {'message': result_message}

    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при подтверждении этапа: {str(e)}'}


def handle_admin_cancel_step(plan, path_id, admin_user):
    """Администратор отменяет уже подтверждённый этап согласования.

    Нюанс: вместе с выбранным этапом откатываются и все более поздние
    уже подтверждённые этапы — они логически зависят от него (следующий
    этап не может считаться пройденным, если предыдущий, от которого он
    зависел, снова стал непройденным). Если план уже был утверждён
    (is_approved), отмена возвращает его в статус "отправлен на
    согласование" (is_sent), а не в статус "в редакции" — план остаётся
    в процессе рассмотрения, просто с одним или несколькими непройденными
    этапами.
    """
    try:
        target_path = PlanApprovalPath.query.filter_by(id=path_id, plan_id=plan.id).first()
        if not target_path:
            return {'error': 'Этап согласования не найден'}

        if not target_path.is_viewed:
            return {'error': 'Этап еще не подтвержден'}

        paths_to_cancel = PlanApprovalPath.query.filter(
            PlanApprovalPath.plan_id == plan.id,
            PlanApprovalPath.cycle == target_path.cycle,
            PlanApprovalPath.step_order >= target_path.step_order,
            PlanApprovalPath.is_viewed == True
        ).order_by(PlanApprovalPath.step_order).all()

        now = current_utc_time()
        for path in paths_to_cancel:
            path.is_viewed = False
            path.viewed_at = None
            path.viewed_by_user_id = None
            path.viewed_by_snapshot = None
            _unlink_stale_remark_tickets(path)

        if plan.is_approved:
            plan.is_approved = False
            plan.is_sent = True
            plan.is_draft = False
            plan.is_control = False
            plan.is_error = False

        plan.audit_time = now

        notification = Notification(
            user_id=plan.user_id,
            message=f"Подтверждение этапа согласования плана на {plan.year} год было отменено администратором",
            created_at=now
        )
        db.session.add(notification)

        db.session.commit()

        return {'message': 'Подтверждение этапа отменено'}

    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при отмене этапа: {str(e)}'}