from flask import (
    Blueprint, abort, g, jsonify, render_template, request, flash, redirect, url_for
)

from flask_login import (
    current_user, login_required 
)

from website.plans import generate_unique_display_code, get_event_metrics, other_data_indicatorUpdate, to_decimal_2, update_ChangeTimePlan
from website.routes.auth import user_with_all_params
from website.routes.views import owner_only
from website.sessions import session_required
from website.plans import status_handlers
from website.user import send_email

from .. import db
from ..models import Direction, Indicator, IndicatorUsage, Notification, Plan, Ticket, Event

import logging
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)
plan_bp = Blueprint('plan_bp', __name__, url_prefix='/plans/plan')

@plan_bp.route('/review/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@session_required
@owner_only
def plan_review(token):  
    if request.method == 'POST':
        pass
    
    current_plan = g.current_plan

    show_plan_type_modal = (
        current_plan.is_draft and 
        (current_plan.plan_type is None or current_plan.plan_type == '') and
        hasattr(current_user, 'organization') and 
        current_user.organization is not None
    )

    return render_template('plan_review.html', 
                        plan=current_plan,
                        show_plan_type_modal=show_plan_type_modal,
                        hide_header=False,
                        sentmodal=current_plan.is_control)

@plan_bp.route('/audit/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_audit(token):  
    if request.method == 'POST':
        pass
    
    current_plan = g.current_plan
    return render_template('plan_audit.html', 
                        plan=current_plan,     
                        hide_header=False)

# @plan_bp.route('/indicators/<token>', methods=['GET', 'POST'])
# @user_with_all_params()
# @login_required
# @owner_only
# @session_required
# def plan_indicators(token):    
#     if request.method == 'POST':
#         pass
    
#     current_plan = g.current_plan
#     indicators_non_madatory = (Indicator.query
#                         .filter_by(IsMandatory=False)
#                         .filter(~Indicator.id.in_(
#                             db.session.query(IndicatorUsage.id_indicator)
#                             .filter(IndicatorUsage.id_plan == current_plan.id)
#                         ))
#                         .all())
    
#     current_plan_indicators = (IndicatorUsage.query
#                 .join(Indicator, IndicatorUsage.id_indicator == Indicator.id)
#                 .filter(IndicatorUsage.id_plan == current_plan.id)
#                 .order_by(Indicator.Group.asc(), Indicator.RowN.asc())
#                 .all())
    
#     return render_template('plan_indicators.html',  
#                         plan=current_plan, 
#                         indicators_non_madatory=indicators_non_madatory,
#                         current_plan_indicators=current_plan_indicators,
#                         hide_header=False,
#                         add_indicator_modal=True,
#                         edit_indicator_modal=True,
#                         confirmModal = True,
#                         sentmodal=current_plan.is_control,
#                         context_menu = True)

@plan_bp.route('/indicators/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_indicators(token):    
    if request.method == 'POST':
        pass
    
    current_plan = g.current_plan
    indicators_non_madatory = (Indicator.query
                        .filter_by(IsMandatory=False)
                        .filter(~Indicator.id.in_(
                            db.session.query(IndicatorUsage.id_indicator)
                            .filter(IndicatorUsage.id_plan == current_plan.id)
                        ))
                        .all())
    return render_template('plan_indicators.html',  
                        plan=current_plan, 
                        indicators_non_madatory=indicators_non_madatory,
                        hide_header=False,
                        add_indicator_modal=True,
                        edit_indicator_modal=True,
                        confirmModal = True,
                        sentmodal=current_plan.is_control,
                        context_menu = True)

@plan_bp.route('/create-indicator/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def create_indicator(token):
    current_plan = g.current_plan
    
    QYearBeforePrev_ed = to_decimal_2(request.form.get('QYearBeforePrev'))
    QYearPrev_ed = to_decimal_2(request.form.get('QYearPrev'))
    QYearCurrent_ed = to_decimal_2(request.form.get('QYearCurrent'))
    id_indicator = request.form.get('id_indicator')

    if id_indicator == None:
        flash('Пустой показатель', 'error')
        return redirect(url_for('plan_bp.plan_indicators', id=id))
    
    indicator = Indicator.query.filter_by(id=id_indicator).first()

    QYearBeforePrev = to_decimal_2(QYearBeforePrev_ed * indicator.CoeffToTut)
    QYearPrev = to_decimal_2(QYearPrev_ed * indicator.CoeffToTut)
    QYearCurrent = to_decimal_2(QYearCurrent_ed * indicator.CoeffToTut)

    new_IndicatorUsage = IndicatorUsage(
        id_plan=current_plan.id,
        id_indicator=id_indicator,
        QYearBeforePrev=QYearBeforePrev,
        QYearPrev=QYearPrev,
        QYearCurrent=QYearCurrent
    )
    
    db.session.add(new_IndicatorUsage)
    db.session.commit()
    other_data_indicatorUpdate(current_plan.id)

    flash('Показатель добавлен', 'success')
    return redirect(url_for('plan_bp.plan_indicators', token=token))

@plan_bp.route('/edit-indicator/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def edit_indicator(id):
    QYearBeforePrev_ed = to_decimal_2(request.form.get('QYearBeforePrev'))
    QYearPrev_ed = to_decimal_2(request.form.get('QYearPrev'))
    QYearCurrent_ed = to_decimal_2(request.form.get('QYearCurrent'))

    if id == None:
        flash('Пустой id', 'error')
        return redirect(request.url)
    
    indicator_usage = IndicatorUsage.query.filter_by(id=id).first()
    indicator_usage.QYearBeforePrev = to_decimal_2(QYearBeforePrev_ed * indicator_usage.indicator.CoeffToTut)
    indicator_usage.QYearPrev = to_decimal_2(QYearPrev_ed * indicator_usage.indicator.CoeffToTut)
    indicator_usage.QYearCurrent = to_decimal_2(QYearCurrent_ed * indicator_usage.indicator.CoeffToTut)
    db.session.commit()

    current_plan = Plan.query.get_or_404(indicator_usage.id_plan)
    other_data_indicatorUpdate(current_plan.id)
    flash('Обновление данных', 'success')
    return redirect(url_for('plan_bp.plan_indicators', token=current_plan.token))

@plan_bp.route('/delete-indicator/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def delete_indicator(id):
    indicator = IndicatorUsage.query.get_or_404(id)
    current_plan = Plan.query.get_or_404(indicator.id_plan)

    db.session.delete(indicator)
    db.session.commit()
    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)
    
    flash('Показатель успешно удален', 'success')
    return redirect(url_for('plan_bp.plan_indicators', token=current_plan.token))

@plan_bp.route('/events-<event_type>/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_event(event_type, token):
    if request.method == 'POST':
        pass
    
    if event_type not in ['saving', 'increase']:
        abort(404)
    
    current_plan = g.current_plan
    
    if event_type == 'saving':
        type_filter = Direction.is_econom == True
        directions = Direction.query.filter(Direction.is_econom == True).order_by(Direction.id.asc()).all()
        title = "Мероприятия по экономии ТЭР"
    else:
        type_filter = Direction.is_increase == True
        directions = Direction.query.filter(Direction.is_increase == True).order_by(Direction.id.asc()).all()
        title = "Мероприятия по увеличению использования МТЭР и ВИЭ"
    
    has_original_events = Event.query.filter(
        Event.id_plan == current_plan.id,
        Event.is_corrected == False
    ).join(Direction).filter(type_filter).first() is not None
    
    has_changes_events = Event.query.filter(
        Event.id_plan == current_plan.id,
        Event.is_corrected == True
    ).join(Direction).filter(type_filter).first() is not None
    
    has_events = has_original_events or has_changes_events

    return render_template('plan_events.html',  
                        title=title,
                        event_type=event_type,
                        plan=current_plan, 
                        hide_header=False,
                        add_event_modal=True,
                        confirmModal=True,
                        edit_event_modal=True,
                        directions=directions,
                        sentmodal=current_plan.is_control,
                        context_menu=True,
                        has_events=has_events
                    )

@plan_bp.route('/create-event/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def create_event(token):
    current_plan = g.current_plan
    
    id_direction = request.form.get('id_direction')
    name = request.form.get('name') or None

    Volume_value = request.form.get('Volume')
    ExpectedQuarter_value = request.form.get('ExpectedQuarter')

    Payback = to_decimal_2(request.form.get('Payback'))
    EffTut = to_decimal_2(request.form.get('EffTut'))
    EffRub = to_decimal_2(request.form.get('EffRub'))
    EffCurrYear = to_decimal_2(request.form.get('EffCurrYear'))
    VolumeFin = to_decimal_2(request.form.get('VolumeFin'))
    BudgetState = to_decimal_2(request.form.get('BudgetState')) 
    BudgetRep = to_decimal_2(request.form.get('BudgetRep')) 
    BudgetLoc = to_decimal_2(request.form.get('BudgetLoc')) 
    BudgetOther = to_decimal_2(request.form.get('BudgetOther'))
    MoneyOwn = to_decimal_2(request.form.get('MoneyOwn')) 
    MoneyLoan = to_decimal_2(request.form.get('MoneyLoan')) 
    MoneyOther = to_decimal_2(request.form.get('MoneyOther'))

    Volume = int(float(Volume_value)) if Volume_value else None
    ExpectedQuarter = int(float(ExpectedQuarter_value)) if ExpectedQuarter_value else None

    direction = Direction.query.get(id_direction)
    if not direction:
        flash('Направление не найдено', 'error')
        logger.warning(f'Direction not found: id_direction={id_direction}, plan_id={current_plan.id}')
        return redirect(url_for('plan_bp.plan_event', event_type='saving', token=token))
    
    event_type = request.form.get('event_type') or 'saving'
    
    display_code = generate_unique_display_code(direction.code, current_plan.id, id_direction)
    
    is_corrected = current_plan.audit_time is not None
    
    try:
        new_Event = Event(
            id_direction=id_direction,
            id_plan=current_plan.id,
            display_code=display_code,
            name=name,
            Volume=Volume,
            EffTut=EffTut,
            EffRub=EffRub,
            ExpectedQuarter=ExpectedQuarter,
            EffCurrYear=EffCurrYear,
            Payback=Payback,
            VolumeFin=VolumeFin,
            BudgetState=BudgetState,
            BudgetRep=BudgetRep,
            BudgetLoc=BudgetLoc,
            BudgetOther=BudgetOther,
            MoneyOwn=MoneyOwn,
            MoneyLoan=MoneyLoan,
            MoneyOther=MoneyOther,
            is_corrected=is_corrected
        )
        
        db.session.add(new_Event)
        db.session.commit()
        
        other_data_indicatorUpdate(current_plan.id) 
        flash('Мероприятие добавлено', 'success')
        logger.debug(f'Event created successfully: id={new_Event.id}, plan_id={current_plan.id}, direction_id={id_direction}')
        
        return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=token))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f'Database error while creating event: {str(e)}, plan_id={current_plan.id}, direction_id={id_direction}')
        flash('Ошибка базы данных при добавлении мероприятия', 'error')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Unexpected error while creating event: {str(e)}, plan_id={current_plan.id}, direction_id={id_direction}')
        flash('Непредвиденная ошибка при добавлении мероприятия', 'error')
    
    return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=token))

@plan_bp.route('/delete-eventes/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def delete_eventes(id):
    current_event = Event.query.get_or_404(id)
    current_plan = Plan.query.get_or_404(current_event.id_plan)
    
    event_type = request.form.get('event_type') or 'saving'

    db.session.delete(current_event)
    db.session.commit()

    other_data_indicatorUpdate(current_plan.id)
    flash('Мероприятие успешно удалено', 'success')
    return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=current_plan.token))

@plan_bp.route('/edit-event/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def edit_Eventes(id):
    try:
        current_Event = Event.query.get(id)
        if not current_Event:
            flash('Мероприятие не найдено', 'error')
            return redirect(url_for('main.index'))
        
        current_plan = Plan.query.get(current_Event.id_plan)
        if not current_plan:
            flash('План не найден', 'error')
            return redirect(url_for('main.index'))
        
        event_type = request.form.get('event_type') or 'saving'
        
        name = request.form.get('name') or None

        Volume_value = request.form.get('Volume')
        ExpectedQuarter_value = request.form.get('ExpectedQuarter')
        Payback = to_decimal_2(request.form.get('Payback'))

        EffTut = to_decimal_2(request.form.get('EffTut'))
        EffRub = to_decimal_2(request.form.get('EffRub'))
        EffCurrYear = to_decimal_2(request.form.get('EffCurrYear'))
        
        VolumeFin = to_decimal_2(request.form.get('VolumeFin'))
        BudgetState = to_decimal_2(request.form.get('BudgetState')) 
        BudgetRep = to_decimal_2(request.form.get('BudgetRep')) 
        BudgetLoc = to_decimal_2(request.form.get('BudgetLoc')) 
        BudgetOther = to_decimal_2(request.form.get('BudgetOther'))
        MoneyOwn = to_decimal_2(request.form.get('MoneyOwn')) 
        MoneyLoan = to_decimal_2(request.form.get('MoneyLoan')) 
        MoneyOther = to_decimal_2(request.form.get('MoneyOther'))

        Volume = int(float(Volume_value)) if Volume_value else None
        ExpectedQuarter = int(float(ExpectedQuarter_value)) if ExpectedQuarter_value else None
        
        current_Event.name = name
        current_Event.Volume = Volume
        current_Event.ExpectedQuarter = ExpectedQuarter
        current_Event.EffTut = EffTut
        current_Event.EffRub = EffRub
        current_Event.EffCurrYear = EffCurrYear
        current_Event.Payback = Payback
        current_Event.VolumeFin = VolumeFin
        current_Event.BudgetState = BudgetState
        current_Event.BudgetRep = BudgetRep
        current_Event.BudgetLoc = BudgetLoc
        current_Event.BudgetOther = BudgetOther
        current_Event.MoneyOwn = MoneyOwn
        current_Event.MoneyLoan = MoneyLoan
        current_Event.MoneyOther = MoneyOther

        db.session.commit()
        flash('Мероприятие изменено', 'success')

        other_data_indicatorUpdate(current_plan.id)  
        return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=current_plan.token))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при редактировании мероприятия: {str(e)}', 'error')
        return redirect(url_for('plan_bp.plan_event', event_type='saving', token=current_plan.token if 'current_plan' in locals() else ''))

@plan_bp.route('/change-plan-status/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
def api_change_plan_status(token):
    plan = Plan.query.filter_by(token=token).first()
    
    if request.is_json:
        data = request.get_json()
        status = data.get('status')
    else:
        status = request.form.get('status')
        if status == 'sent':
            uploaded_file = request.files.get('certificate')
            from ..ecp import validate_certificate_for_sending
            is_valid, error_message = validate_certificate_for_sending(uploaded_file)
            if not is_valid:
                flash(error_message, 'error')
                flash('План не был отправлен.', 'error')
                return redirect(request.referrer)
            else:
                flash('Сертификат успешно прошел проверку.', 'success')
    
    if not status:
        if request.is_json:
            return jsonify({'error': 'Статус не указан'}), 400
        else:
            flash('Статус не указан', 'error')
            return redirect(request.referrer or url_for('views.plans'))
    
    status_mapping = {
        'draft': 'is_draft',
        'control': 'is_control',
        'sent': 'is_sent', 
        'sent_without_check': 'is_sent',
        'error': 'is_error',
        'approved': 'is_approved'
    }
    
    if status not in status_mapping:
        if request.is_json:
            return jsonify({'error': 'Неверный статус'}), 400
        else:
            flash('Неверный статус', 'error')
            return redirect(request.referrer or url_for('views.plans'))
    
    if status in status_handlers:
        try:
            result = status_handlers[status](plan)
            db.session.commit()

            if isinstance(result, dict) and "error" in result:
                if request.is_json:
                    return jsonify(result), 400
                else:
                    flash(result["error"], "error")
                    return redirect(request.referrer or url_for('views.plans'))
            message = result if isinstance(result, str) else "Статус изменен"

        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return jsonify({'error': f'Ошибка обработки статуса: {str(e)}'}), 500
            else:
                flash(f'Ошибка обработки статуса: {str(e)}', 'error')
                return redirect(request.referrer or url_for('views.plans'))
    
    if status == 'sent_without_check':
        setattr(plan, status_mapping[status], True)
        
        for other_status, attr_name in status_mapping.items():
            if other_status != status and attr_name != status_mapping[status]:
                setattr(plan, attr_name, False)
                
        new_ticket = Ticket(
            note="План возвращен в статус 'На рассмотрении'.",
            luck=True,
            is_owner = True,
            plan_id=plan.id,
        )
        db.session.add(new_ticket) 
        
        
        notification = Notification(
            user_id=plan.user_id,
            message=f"План {plan.year} возвращен в статус 'На рассмотрении'."
        )
        db.session.add(notification)       
        db.session.commit()
        
        message = "План возвращен в изначальное состояние."
        flash(message, 'success')
        return redirect(url_for('plan_bp.plan_audit', token=plan.token))
    
    if request.is_json:
        return jsonify({'message': message, 'status': status})
    else:
        flash(message, 'success')
        if status in ['approved', 'error']:
            return redirect(request.referrer or url_for('views.plans'))
        else:
            return redirect(url_for('plan_bp.plan_review', token=plan.token))

