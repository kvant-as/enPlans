from flask import (
    Blueprint, current_app, redirect, flash, request, g
)

from flask_login import (
    current_user, login_required
)

from website.routes.views import owner_only
from website.sessions import session_required

from ..models import Ticket, TimeByMinsk
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
        current_app.logger.error("Epty message")
        flash('Сообщение не может быть пустым.', 'error')
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