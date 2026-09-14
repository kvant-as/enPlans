from flask import current_app
from flask_login import current_user
from ..models import PlanTicket, Notification, PlanApprovalPath, Organization

from common_models.timeutils import current_utc_time
from website import db


def handle_draft_status(plan):
    try:
        plan.is_draft = True
        plan.is_control = False
        plan.is_sent = False
        plan.is_error = False
        plan.is_approved = False
        
        plan.change_time = current_utc_time()
        
        db.session.commit()
        
        return {'message': 'Статус изменен на "В редакции"'}
        
    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при изменении статуса: {str(e)}'}

def handle_control_status(plan):
    errors = []
    
    try:
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
        
        # Проверка 4: Ожидаемая экономия ТЭР
        if indicator_9900 and plan.saving_fuel:
            try:
                if indicator_9900.QYearCurrent < plan.saving_fuel:
                    errors.append(f"Ожидаемая экономия ТЭР ({indicator_9900.QYearCurrent} т у.т.) должна быть больше или равна заданию ({plan.saving_fuel} т у.т.).")
            except AttributeError as e:
                current_app.logger.error(f"Ошибка при проверке индикатора 9900: {e}")
                errors.append("Ошибка при проверке ожидаемой экономии ТЭР")
        
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
        if not plan.organization or not plan.organization.region_id:
            return {'error': 'У плана не указан регион'}
        
        region_org = Organization.query.filter(
            Organization.is_region_management == True,
            Organization.region_id == plan.organization.region_id
        ).first()

        if not region_org:
            return {'error': 'Региональное управление не найдено для этого региона'}

        if not coordinator_ids and not approver_id:
            return {'error': 'Не выбраны организации для согласования и утверждения'}
        
        PlanApprovalPath.query.filter_by(plan_id=plan.id).delete()
        
        step_order = 1
        
        region_path = PlanApprovalPath(
            plan_id=plan.id,
            step_order=step_order,
            organization_id=region_org.id,
            step_type='region',
            created_at=current_utc_time()
        )
        db.session.add(region_path)
        step_order += 1
        
        for coord_id in coordinator_ids:
            if coord_id and coord_id.strip():
                coord_path = PlanApprovalPath(
                    plan_id=plan.id,
                    step_order=step_order,
                    organization_id=int(coord_id.strip()),
                    step_type='coordinator',
                    created_at=current_utc_time()
                )
                db.session.add(coord_path)
                step_order += 1
        
        if approver_id:
            approver_path = PlanApprovalPath(
                plan_id=plan.id,
                step_order=step_order,
                organization_id=int(approver_id),
                step_type='approver',
                created_at=current_utc_time()
            )
            db.session.add(approver_path)
        
        plan.sent_time = current_utc_time()
        plan.is_sent = True
        plan.is_draft = False
        plan.is_control = False
        plan.is_error = False
        plan.is_approved = False
        plan.afch = False
         
        db.session.commit()
        
        return {'message': 'План успешно отправлен на согласование'}
        
    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при отправке плана: {str(e)}'}

def handle_sent_without_check_status(plan, current_user):
    try:
        current_path = PlanApprovalPath.query.filter_by(
            plan_id=plan.id,
            is_viewed=False
        ).order_by(PlanApprovalPath.step_order).first()
        
        # if current_path and current_path.organization_id != current_user.organization_id:
        #     return {'error': 'У вас нет прав для отмены изменений на этом этапе'}
        
        plan.is_sent = True
        plan.is_draft = False
        plan.is_control = False
        plan.is_error = False
        plan.is_approved = False
        plan.afch = False
        
        if current_user.is_auditor:
            current_path = PlanApprovalPath.query.filter_by(
                plan_id=plan.id,
                organization_id=current_user.organization_id,
                is_viewed=True
            ).first()
            
            if current_path:
                current_path.is_viewed = False
                current_path.viewed_at = None
                
                ticket = PlanTicket(
                    note="Проверка отменена. План возвращен на этап рассмотрения.",
                    luck=True,
                    is_system=True,
                    plan_id=plan.id,
                    begin_time=current_utc_time()
                )
                db.session.add(ticket)
                
                notification = Notification(
                    user_id=plan.user_id,
                    message=f"План {plan.year} возвращен на этап согласования",
                    created_at=current_utc_time()
                )
                db.session.add(notification)
        else:
            PlanApprovalPath.query.filter_by(plan_id=plan.id).update(
                {'is_viewed': False, 'viewed_at': None}
            )
            
            ticket = PlanTicket(
                note="Отмена изменений. Все шаги согласования сброшены, план возвращен в изначальный статус.",
                luck=True,
                is_system=True,
                plan_id=plan.id,
                begin_time=current_utc_time()
            ) 
            db.session.add(ticket)
            
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

def handle_error_status(plan):
    try:
        if not plan.afch:
            return {'error': 'Сначала необходимо отправить сообщение с замечаниями'}
        
        plan.audit_time = current_utc_time()
        plan.is_error = True
        plan.is_draft = False
        plan.is_control = False
        plan.is_sent = False
        plan.is_approved = False
        plan.afch = False

        ticket = PlanTicket(
            note="В плане нашли ошибки, статус изменен на Есть ошибки.",
            luck=True,
            plan_id=plan.id,
            user_id=current_user.id,
            begin_time=current_utc_time(),
        )
        db.session.add(ticket)

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
        
        current_path = PlanApprovalPath.query.filter_by(
            plan_id=plan.id,
            is_viewed=False
        ).order_by(PlanApprovalPath.step_order).first()
        
        if not current_path:
            return {'error': 'Все этапы уже пройдены'}
        
        if current_path.organization_id != current_user.organization_id:
            return {'error': 'У вас нет прав на согласование этого этапа'}
        
        prev_path = PlanApprovalPath.query.filter(
            PlanApprovalPath.plan_id == plan.id,
            PlanApprovalPath.step_order == current_path.step_order - 1
        ).first()
        
        if prev_path and not prev_path.is_viewed:
            return {'error': 'Предыдущий этап еще не пройден'}
        
        current_path.is_viewed = True
        current_path.viewed_at = current_utc_time()
        
        plan.audit_time = current_utc_time()
        plan.afch = False
        
        next_path = PlanApprovalPath.query.filter_by(
            plan_id=plan.id,
            is_viewed=False
        ).order_by(PlanApprovalPath.step_order).first()
        
        if not next_path:
            plan.is_approved = True
            plan.is_draft = False
            plan.is_control = False
            plan.is_sent = False
            plan.is_error = False
            
            ticket = PlanTicket(
                note="План согласован и утвержден",
                luck=True,
                is_system=True,
                user_id=current_user.id,
                plan_id=plan.id,
                begin_time=current_utc_time()
            )
            db.session.add(ticket)
            
            notification = Notification(
                user_id=plan.user_id,
                message=f"План на {plan.year} был утвержден",
                created_at=current_utc_time()
            )
            db.session.add(notification)
            
            message = "План полностью согласован и утвержден"
        else:
            ticket = PlanTicket(
                note="План был согласован и передан в следующую стадию проверки.",
                luck=True,
                user_id=current_user.id,
                plan_id=plan.id,
                begin_time=current_utc_time()
            )
            db.session.add(ticket)
            
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
            PlanApprovalPath.step_order <= target_path.step_order,
            PlanApprovalPath.is_viewed == False
        ).order_by(PlanApprovalPath.step_order).all()

        now = current_utc_time()
        for path in paths_to_confirm:
            path.is_viewed = True
            path.viewed_at = now

        plan.audit_time = now
        plan.afch = False

        last_path = PlanApprovalPath.query.filter_by(plan_id=plan.id).order_by(
            PlanApprovalPath.step_order.desc()
        ).first()
        is_final = bool(last_path and last_path.id == target_path.id)

        org_name = target_path.organization.full_name if target_path.organization else f'этап {target_path.step_order}'

        if is_final:
            plan.is_approved = True
            plan.is_draft = False
            plan.is_control = False
            plan.is_sent = False
            plan.is_error = False

            note = f"Администратор {admin_user.email} подтвердил этап «{org_name}» и весь путь согласования. План согласован и утвержден."
            notif_message = f"План на {plan.year} год был утвержден администратором"
            result_message = 'План полностью согласован и утвержден администратором'
        else:
            note = f"Администратор {admin_user.email} подтвердил этап «{org_name}» (шаг {target_path.step_order}) в обход обычного порядка согласования."
            notif_message = f"Этап согласования плана на {plan.year} год подтвержден администратором"
            result_message = 'Этап подтвержден администратором'

        ticket = PlanTicket(
            note=note,
            luck=True,
            is_system=True,
            user_id=admin_user.id,
            plan_id=plan.id,
            begin_time=now
        )
        db.session.add(ticket)

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
            PlanApprovalPath.step_order >= target_path.step_order,
            PlanApprovalPath.is_viewed == True
        ).order_by(PlanApprovalPath.step_order).all()

        now = current_utc_time()
        for path in paths_to_cancel:
            path.is_viewed = False
            path.viewed_at = None

        if plan.is_approved:
            plan.is_approved = False
            plan.is_sent = True
            plan.is_draft = False
            plan.is_control = False
            plan.is_error = False

        plan.audit_time = now

        org_name = target_path.organization.full_name if target_path.organization else f'этап {target_path.step_order}'
        note = f"Администратор {admin_user.email} отменил подтверждение этапа «{org_name}» (шаг {target_path.step_order})"
        if len(paths_to_cancel) > 1:
            note += f" и {len(paths_to_cancel) - 1} последующих зависимых от него этапов"
        note += "."

        ticket = PlanTicket(
            note=note,
            luck=True,
            is_system=True,
            user_id=admin_user.id,
            plan_id=plan.id,
            begin_time=now
        )
        db.session.add(ticket)

        notification = Notification(
            user_id=plan.user_id,
            message=f"Согласование плана на {plan.year} год было отменено администратором на этапе «{org_name}»",
            created_at=now
        )
        db.session.add(notification)

        db.session.commit()

        return {'message': 'Подтверждение этапа отменено'}

    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при отмене этапа: {str(e)}'}