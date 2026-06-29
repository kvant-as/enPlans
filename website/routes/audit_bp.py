from flask import (
    Blueprint, current_app, redirect, flash, request, g
)

from flask_login import (
    current_user, login_required
)

from website.routes.views import owner_only
from website.sessions import session_required

from ..models import PlanApprovalPath, Ticket, TimeByMinsk
from .. import db

from .auth import user_with_all_params

audit_bp = Blueprint('audit_bp', __name__, url_prefix='/')
        
@audit_bp.route('/create-ticket/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def create_ticket(token):
    current_plan = g.current_plan
    if not current_plan:
        flash('План не найден.', 'error')
        return redirect(request.referrer)
    
    note = request.form.get('note')
    
    if not note or not note.strip():
        current_app.logger.error("Empty message")
        flash('Сообщение не может быть пустым.', 'error')
        return redirect(request.referrer)
    
    if not current_plan.is_sent:
        flash('План не находится на этапе согласования.', 'error')
        return redirect(request.referrer)
    
    if current_plan.is_approved or current_plan.is_error:
        flash('План уже обработан.', 'error')
        return redirect(request.referrer)
    
    current_path = PlanApprovalPath.query.filter_by(
        plan_id=current_plan.id,
        is_viewed=False
    ).order_by(PlanApprovalPath.step_order).first()
    
    if not current_path:
        flash('Нет активных шагов для проверки.', 'error')
        return redirect(request.referrer)
    
    if current_path.organization_id != current_user.organization_id:
        flash('У вас нет прав на отправку сообщения для этого этапа.', 'error')
        return redirect(request.referrer)
    
    prev_path = PlanApprovalPath.query.filter(
        PlanApprovalPath.plan_id == current_plan.id,
        PlanApprovalPath.step_order == current_path.step_order - 1
    ).first()
    
    if prev_path and not prev_path.is_viewed:
        flash('Предыдущий этап еще не пройден.', 'error')
        return redirect(request.referrer)
    
    current_plan.afch = True
    
    new_ticket = Ticket(
        note=note.strip(),
        luck=False,
        plan_id=current_plan.id,
        user_id=current_user.id,
        is_owner=current_user.id == current_plan.user_id
    )

    db.session.add(new_ticket)
    db.session.commit()
    
    flash('Сообщение отправлено.', 'success')
    return redirect(request.referrer)