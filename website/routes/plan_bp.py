from flask import (
    Blueprint, g, jsonify, render_template, request, flash, redirect, url_for
)

from flask_login import (
    current_user, login_required 
)

from website.plans import get_cumulative_econ_metrics, other_data_indicatorUpdate, to_decimal_2, update_ChangeTimePlan
from website.routes.auth import user_with_all_params
from website.routes.views import owner_only
from website.sessions import session_required
from website.user import send_email

from .. import db
from ..models import Direction, Indicator, IndicatorUsage, Notification, Plan, Ticket, Event


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
    
    current_plan_indicators = (IndicatorUsage.query
                .join(Indicator, IndicatorUsage.id_indicator == Indicator.id)
                .filter(IndicatorUsage.id_plan == current_plan.id)
                .order_by(Indicator.Group.asc(), Indicator.RowN.asc())
                .all())
    
    return render_template('plan_indicators.html',  
                        plan=current_plan, 
                        indicators_non_madatory=indicators_non_madatory,
                        current_plan_indicators=current_plan_indicators,
                        hide_header=False,
                        add_indicator_modal=True,
                        edit_indicator_modal=True,
                        confirmModal = True,
                        sentmodal=current_plan.is_control,
                        context_menu = True)

@plan_bp.route('/get-indicator/<int:id>', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
def get_indicator(id):
    try:
        existing_IndicatorUsage = IndicatorUsage.query.get(id)
        if not existing_IndicatorUsage:
            return jsonify({'error': 'Indicator not found'}), 404
        
        return jsonify(existing_IndicatorUsage.as_dict())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
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
    update_ChangeTimePlan(current_plan.id)
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
    update_ChangeTimePlan(current_plan.id)
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







@plan_bp.route('/events-saving/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_event_saving(token):    
    if request.method == 'POST':
        pass
    
    current_plan = g.current_plan
  
    directions = Direction.query.filter_by().order_by().all()
    econom_events = (Event.query
        .join(Direction, Event.id_direction == Direction.id)
        .filter(Event.id_plan == current_plan.id)
        .filter(Direction.is_econom == True)
        .order_by(Direction.code.asc())
        .all())

    increase_events = (Event.query
        .join(Direction, Event.id_direction == Direction.id)
        .filter(Event.id_plan == current_plan.id)
        .filter(Direction.is_increase == True)
        .order_by(Direction.code.asc())
        .all())

    local_totals = get_cumulative_econ_metrics(current_plan.id, True)
    non_local_totals = get_cumulative_econ_metrics(current_plan.id, False)
    
    total_metrics = {
        'jan_mar_eff': local_totals['jan_mar']['eff_curr_year'] + non_local_totals['jan_mar']['eff_curr_year'],
        'jan_mar_vol': local_totals['jan_mar']['volume_fin'] + non_local_totals['jan_mar']['volume_fin'],
        'jan_jun_eff': local_totals['jan_jun']['eff_curr_year'] + non_local_totals['jan_jun']['eff_curr_year'],
        'jan_jun_vol': local_totals['jan_jun']['volume_fin'] + non_local_totals['jan_jun']['volume_fin'],
        'jan_sep_eff': local_totals['jan_sep']['eff_curr_year'] + non_local_totals['jan_sep']['eff_curr_year'],
        'jan_sep_vol': local_totals['jan_sep']['volume_fin'] + non_local_totals['jan_sep']['volume_fin'],
        'jan_dec_eff': local_totals['jan_dec']['eff_curr_year'] + non_local_totals['jan_dec']['eff_curr_year'],
        'jan_dec_vol': local_totals['jan_dec']['volume_fin'] + non_local_totals['jan_dec']['volume_fin']
    }

    return render_template('plan_events_saving.html',  
                        directions=directions,
                        econom_events=econom_events,
                        increase_events=increase_events,
                        total_metrics=total_metrics,
                        plan=current_plan, 
                        hide_header=False,
                        add_event_modal=True,
                        confirmModal=True,
                        edit_event_modal=True,
                        sentmodal=current_plan.is_control,
                        context_menu=True
                         )
    
@plan_bp.route('/events-increase/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_event_increase(token):    
    if request.method == 'POST':
        pass
    
    current_plan = g.current_plan
  
    directions = Direction.query.filter_by().order_by().all()
    
    econ_exec = (
        Event.query
        .filter_by(id_plan=current_plan.id)
        .order_by(asc(Direction.code))
        .all()
    )
  
    econom_events = (Event.query
        .join(Direction, Event.id_direction == Direction.id)
        .join(Plan, Direction.id_plan == Plan.id)
        .filter(Plan.id == current_plan.id)
        .options(joinedload(Event.econ_measures).joinedload(Direction.plan))
        .all())

    increase_events = (Event.query
        .join(Direction, Event.id_direction == Direction.id)
        .join(Plan, Direction.id_plan == Plan.id)
        .filter(Plan.id == current_plan.id)
        .options(joinedload(Event.econ_measures).joinedload(Direction.plan))
    .all())


    local_totals = get_cumulative_econ_metrics(current_plan.id, True)
    non_local_totals = get_cumulative_econ_metrics(current_plan.id, False)
    
    total_metrics = {
        'jan_mar_eff': local_totals['jan_mar']['eff_curr_year'] + non_local_totals['jan_mar']['eff_curr_year'],
        'jan_mar_vol': local_totals['jan_mar']['volume_fin'] + non_local_totals['jan_mar']['volume_fin'],
        'jan_jun_eff': local_totals['jan_jun']['eff_curr_year'] + non_local_totals['jan_jun']['eff_curr_year'],
        'jan_jun_vol': local_totals['jan_jun']['volume_fin'] + non_local_totals['jan_jun']['volume_fin'],
        'jan_sep_eff': local_totals['jan_sep']['eff_curr_year'] + non_local_totals['jan_sep']['eff_curr_year'],
        'jan_sep_vol': local_totals['jan_sep']['volume_fin'] + non_local_totals['jan_sep']['volume_fin'],
        'jan_dec_eff': local_totals['jan_dec']['eff_curr_year'] + non_local_totals['jan_dec']['eff_curr_year'],
        'jan_dec_vol': local_totals['jan_dec']['volume_fin'] + non_local_totals['jan_dec']['volume_fin']
    }
    return render_template('plan_events_increase.html',  
                        econ_exec=econ_exec,
                        econ_measures=econ_measures,
                        econom_events=econom_events,
                        increase_events=increase_events,
                        total_metrics=total_metrics,
                        plan=current_plan, 
                        hide_header=False,
                        add_event_modal=True,
                        confirmModal=True,
                        edit_event_modal=True,
                        sentmodal=current_plan.is_control,
                        context_menu=True
                         ) 

import logging
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

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
        return redirect(url_for('plan_bp.plan_event_saving', token=token))
    
    try:
        new_Event = Event(
            id_direction=id_direction,
            id_plan=current_plan.id,
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
        )
        
        db.session.add(new_Event)
        db.session.commit()
        
        other_data_indicatorUpdate(current_plan.id)
        update_ChangeTimePlan(current_plan.id)
        
        flash('Мероприятие добавлено', 'success')
        logger.debug(f'Event created successfully: id={new_Event.id}, plan_id={current_plan.id}, direction_id={id_direction}')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f'Database error while creating event: {str(e)}, plan_id={current_plan.id}, direction_id={id_direction}')
        flash('Ошибка базы данных при добавлении мероприятия', 'error')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Unexpected error while creating event: {str(e)}, plan_id={current_plan.id}, direction_id={id_direction}')
        flash('Непредвиденная ошибка при добавлении мероприятия', 'error')
    return redirect(url_for('plan_bp.plan_event_saving', token=token))
    
    
@plan_bp.route('/delete-eventes/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def delete_eventes(id):
    current_event = Event.query.get_or_404(id)
    current_plan = Plan.query.get_or_404(current_event.id_plan)

    db.session.delete(current_event)
    db.session.commit()

    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)
    flash('Мероприятие успешно удалено', 'success')
    return redirect(url_for('plan_bp.plan_event_saving', token=current_plan.token))

@plan_bp.route('/edit-Eventes/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def edit_Eventes(id):
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
    
    current_Event = Event.query.get(id)
    current_plan = Plan.query.get_or_404(current_Event.id_plan)

    if not current_Event:
        flash('Мероприятие не найдено', 'error')
        return redirect(url_for('plan_bp.plan_event_saving', token=current_plan.token))
    
    current_Event.name=name
    current_Event.Volume=Volume
    current_Event.ExpectedQuarter=ExpectedQuarter
    current_Event.EffTut=EffTut
    current_Event.EffRub=EffRub
    current_Event.EffCurrYear=EffCurrYear
    current_Event.Payback=Payback
    current_Event.VolumeFin=VolumeFin
    current_Event.BudgetState=BudgetState
    current_Event.BudgetRep=BudgetRep
    current_Event.BudgetLoc=BudgetLoc
    current_Event.BudgetOther=BudgetOther
    current_Event.MoneyOwn=MoneyOwn
    current_Event.MoneyLoan=MoneyLoan
    current_Event.MoneyOther=MoneyOther

    db.session.commit()
    flash('Мероприятие изменено', 'success')

    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)
    return redirect(url_for('plan_bp.plan_event_saving', token=current_plan.token))

@plan_bp.route('/get-Evente/<int:id>', methods=['GET'])
@user_with_all_params()
@login_required
def get_Evente(id):
    try:
        existing_measure = Event.query.get(id)
        if not existing_measure:
            return jsonify({'error': 'Event not found'}), 404
        
        return jsonify(existing_measure.as_dict())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@plan_bp.route('/api/change-plan-status/<token>', methods=['POST'])
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

