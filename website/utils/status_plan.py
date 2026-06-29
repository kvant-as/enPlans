from datetime import timedelta
from flask import current_app
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
    try:
        plan.is_draft = False
        plan.is_control = True
        plan.is_sent = False
        plan.is_error = False
        plan.is_approved = False
        
        plan.change_time = TimeByMinsk()
        
        db.session.commit()
        
        return {'message': 'План прошел проверку на контроль'}
        
    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при изменении статуса: {str(e)}'}

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
                    is_owner=True,
                    plan_id=plan.id,
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
                is_owner=True,
                plan_id=plan.id
            ) 
            db.session.add(ticket)
            
            notification = Notification(
                user_id=plan.user_id,
                message=f"План {plan.year} возвращен в статус рассмотрения. Все шаги согласования сброшены.",
                created_at=TimeByMinsk()
            )
            db.session.add(notification)
        
        db.session.commit()
        
        return {'message': 'План возвращен в изначальное состояние. Все шаги согласования сброшены.'}
        
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
            is_owner=True,
            plan_id=plan.id,
            begin_time=TimeByMinsk()
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
        
        if not plan.afch:
            return {'error': 'Сначала необходимо отправить сообщение с замечаниями или подтверждением'}
        
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
                is_owner=True,
                plan_id=plan.id
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
                is_owner=True,
                plan_id=plan.id
            )
            db.session.add(ticket)
            
            message = "Этап успешно согласован"
        
        db.session.commit()
        
        return {'message': message}
        
    except Exception as e:
        db.session.rollback()
        return {'error': f'Ошибка при согласовании: {str(e)}'}