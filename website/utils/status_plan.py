from datetime import timedelta
from flask import current_app
from flask_login import current_user
from ..models import db, Plan, Ticket, Notification, PlanApprovalPath, Organization, TimeByMinsk
  
def handle_draft_status(plan):
    try:
        plan.is_draft = True
        plan.is_control = False
        plan.is_sent = False
        plan.is_error = False
        plan.is_approved = False
        
        plan.change_time = TimeByMinsk()
        
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
        if indicator_9999 and indicator_9900:
            try:
                if indicator_9999.QYearCurrent != indicator_9900.QYearCurrent:
                    errors.append("Годовая экономия ТЭР от энергосберегающих мероприятий всего должна быть равна ожидаемой экономии ТЭР от внедрения мероприятий в текущем году.")
                
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
        return "План прошел проверку на контроль."
        
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
            created_at=TimeByMinsk()
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
                    created_at=TimeByMinsk()
                )
                db.session.add(coord_path)
                step_order += 1
        
        if approver_id:
            approver_path = PlanApprovalPath(
                plan_id=plan.id,
                step_order=step_order,
                organization_id=int(approver_id),
                step_type='approver',
                created_at=TimeByMinsk()
            )
            db.session.add(approver_path)
        
        plan.sent_time = TimeByMinsk()
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
        
        if current_path and current_path.organization_id != current_user.organization_id:
            return {'error': 'У вас нет прав для отмены изменений на этом этапе'}
        
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
                
                ticket = Ticket(
                    note="Проверка отменена. План возвращен на этап рассмотрения.",
                    luck=True,
                    is_system=True,
                    plan_id=plan.id,
                    begin_time=TimeByMinsk()
                )
                db.session.add(ticket)
                
                notification = Notification(
                    user_id=plan.user_id,
                    message=f"План {plan.year} возвращен на этап согласования",
                    created_at=TimeByMinsk()
                )
                db.session.add(notification)
        else:
            PlanApprovalPath.query.filter_by(plan_id=plan.id).update(
                {'is_viewed': False, 'viewed_at': None}
            )
            
            ticket = Ticket(
                note="Отмена изменений. Все шаги согласования сброшены, план возвращен в изначальный статус.",
                luck=True,
                is_system=True,
                plan_id=plan.id,
                begin_time=TimeByMinsk()
            ) 
            db.session.add(ticket)
            
            notification = Notification(
                user_id=plan.user_id,
                message=f"План {plan.year} возвращен в статус рассмотрения.",
                created_at=TimeByMinsk()
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
        
        plan.audit_time = TimeByMinsk()
        plan.is_error = True
        plan.is_draft = False
        plan.is_control = False
        plan.is_sent = False
        plan.is_approved = False
        plan.afch = False

        ticket = Ticket(
            note="В плане нашли ошибки, статус изменен на Есть ошибки.",
            luck=True,
            plan_id=plan.id,
            user_id=current_user.id,
            begin_time=TimeByMinsk(),
        )
        db.session.add(ticket)

        notification = Notification(
            user_id=plan.user_id,
            message=f"В плане на {plan.year} год нашли ошибки.",
            created_at=TimeByMinsk()
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
        current_path.viewed_at = TimeByMinsk()
        
        plan.audit_time = TimeByMinsk()
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
            
            ticket = Ticket(
                note="План согласован и утвержден",
                luck=True,
                is_system=True,
                user_id=current_user.id,
                plan_id=plan.id,
                begin_time=TimeByMinsk()
            )
            db.session.add(ticket)
            
            notification = Notification(
                user_id=plan.user_id,
                message=f"План на {plan.year} был утвержден",
                created_at=TimeByMinsk()
            )
            db.session.add(notification)
            
            message = "План полностью согласован и утвержден"
        else:
            ticket = Ticket(
                note="План был согласован и передан в следующую стадию проверки.",
                luck=True,
                user_id=current_user.id,
                plan_id=plan.id,
                begin_time=TimeByMinsk()
            )
            db.session.add(ticket)
            
            message = "Этап успешно согласован"
        
        db.session.commit()
        
        return {'message': message}
        
    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при согласовании: {str(e)}'}