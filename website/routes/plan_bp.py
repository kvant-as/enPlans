from flask import (
    Blueprint, abort, current_app, g, jsonify, render_template, request, flash, redirect, url_for
)

from flask_login import (
    current_user, login_required 
)

from website.utils.plans import check_and_create_period_directions, generate_unique_display_code, other_data_indicatorUpdate, to_decimal_1, to_decimal_2, to_decimal_3, update_ChangeTimePlan
from website.routes.auth import user_with_all_params
from website.routes.views import owner_only
from website.sessions import session_required
from website.utils.plans import status_handlers
from website.user import send_email

from website.utils.event import process_event_data, create_event_record, update_double_effect_payback

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
                        confirmModal = True,
                        sentmodal=current_plan.is_control,
                        context_menu = True)

@plan_bp.route('/create-indicator/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def create_indicator(token):
    try:
        current_plan = g.current_plan
        
        QYearBeforePrev_ed = to_decimal_2(request.form.get('QYearBeforePrev'))
        QYearPrev_ed = to_decimal_2(request.form.get('QYearPrev'))
        QYearCurrent_ed = to_decimal_2(request.form.get('QYearCurrent'))
        id_indicator = request.form.get('id_indicator')
        coeff_type = request.form.get('coeff_type')
        custom_coeff_raw = request.form.get('custom_coeff')
        fuel_category = request.form.get('fuel_category')
        name_other = str(request.form.get('name_other'))

        # current_app.logger.info(f'Attempting to create indicator for plan {current_plan.id}')
        # current_app.logger.debug(f'Form data: QYearBeforePrev_ed={QYearBeforePrev_ed}, QYearPrev_ed={QYearPrev_ed}, QYearCurrent_ed={QYearCurrent_ed}, id_indicator={id_indicator}, coeff_type={coeff_type}, custom_coeff_raw={custom_coeff_raw}, fuel_category={fuel_category}')

        if not id_indicator:
            current_app.logger.warning('Empty indicator')
            flash('Пустой показатель', 'error')
            return redirect(url_for('plan_bp.plan_indicators', token=token))
        
        indicator = Indicator.query.filter_by(id=id_indicator).first()
        
        if not indicator:
            current_app.logger.warning(f'Indicator with id {id_indicator} not found')
            flash('Показатель не найден', 'error')
            return redirect(url_for('plan_bp.plan_indicators', token=token))
        
        current_app.logger.info(f'Found indicator: code={indicator.code}, name={indicator.name}, CoeffToTut={indicator.CoeffToTut}, is_local={indicator.is_local}, is_renewable={indicator.is_renewable}')
        
        if indicator.code in ['2023', '2024'] and not fuel_category and not name_other:
            current_app.logger.warning(f'Indicator {indicator.code} requires fuel category and Note but not provided')
            flash('Для данного показателя необходимо выбрать категорию топлива и ввести наименование', 'error')
            return redirect(url_for('plan_bp.plan_indicators', token=token))
        
        if coeff_type == 'custom' and custom_coeff_raw:
            try:
                used_coeff = to_decimal_3(custom_coeff_raw)
                custom_coeff_value = used_coeff
                current_app.logger.info(f'Using custom coefficient: {used_coeff}')
            except Exception as e:
                current_app.logger.error(f'Error parsing custom coefficient: {e}')
                flash('Некорректное значение коэффициента', 'error')
                return redirect(url_for('plan_bp.plan_indicators', token=token))
        else:
            used_coeff = indicator.CoeffToTut
            custom_coeff_value = None
            current_app.logger.info(f'Using standard coefficient: {used_coeff}')

        QYearBeforePrev = to_decimal_2(QYearBeforePrev_ed * used_coeff)
        QYearPrev = to_decimal_2(QYearPrev_ed * used_coeff)
        QYearCurrent = to_decimal_2(QYearCurrent_ed * used_coeff)
        
        if indicator.code in ['2023', '2024'] and fuel_category:
            if fuel_category == 'local':
                is_local_value = True
                is_renewable_value = False
                current_app.logger.info(f'Setting is_local=True for indicator {indicator.code}')
            elif fuel_category == 'renewable':
                is_local_value = False
                is_renewable_value = True
                current_app.logger.info(f'Setting is_renewable=True for indicator {indicator.code}')
            else:
                is_local_value = indicator.is_local
                is_renewable_value = indicator.is_renewable
        else:
            is_local_value = indicator.is_local
            is_renewable_value = indicator.is_renewable
            current_app.logger.debug(f'Using indicator default values: is_local={is_local_value}, is_renewable={is_renewable_value}')

        new_IndicatorUsage = IndicatorUsage(
            id_plan=current_plan.id,
            id_indicator=id_indicator,
            QYearBeforePrev=QYearBeforePrev,
            QYearPrev=QYearPrev,
            QYearCurrent=QYearCurrent,
            custom_coeff_to_tut=custom_coeff_value,
            is_local=is_local_value,
            is_renewable=is_renewable_value,
            note=name_other
        )
        
        db.session.add(new_IndicatorUsage)
        db.session.commit()
        other_data_indicatorUpdate(current_plan.id)
        
        current_app.logger.info(f'Successfully created indicator usage with id {new_IndicatorUsage.id} for plan {current_plan.id}')

        flash('Показатель добавлен', 'success')
        return redirect(url_for('plan_bp.plan_indicators', token=token))
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating indicator: {str(e)}', exc_info=True)
        flash(f'Ошибка при добавлении показателя: {str(e)}', 'error')
        return redirect(url_for('plan_bp.plan_indicators', token=token))

@plan_bp.route('/edit-indicator/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def edit_indicator(token):
    try:
        id_indicator = request.form.get('id_indicator')
        
        if not id_indicator:
            flash('ID показателя не указан', 'error')
            return redirect(url_for('plan_bp.plan_indicators', token=token))
        
        indicator_usage = IndicatorUsage.query.get_or_404(id_indicator)
        current_plan = g.current_plan
        
        if indicator_usage.id_plan != current_plan.id:
            flash('Показатель не принадлежит указанному плану', 'error')
            return redirect(url_for('plan_bp.plan_indicators', token=token))
        
        QYearBeforePrev_ed = to_decimal_2(request.form.get('QYearBeforePrev'))
        QYearPrev_ed = to_decimal_2(request.form.get('QYearPrev'))
        QYearCurrent_ed = to_decimal_2(request.form.get('QYearCurrent'))
        coeff_type = request.form.get('coeff_type')
        custom_coeff_raw = request.form.get('custom_coeff')
        fuel_category = request.form.get('fuel_category')
        name_other = str(request.form.get('name_other'))
        
        indicator = indicator_usage.indicator
        indicator_code = indicator.code
        indicator_code_num = int(indicator_code) if indicator_code.isdigit() else 0
        
        is_coeff_editable = 2000 <= indicator_code_num <= 2024
        is_codes_9911_9914 = indicator_code in ['9911', '9912', '9913', '9914']
        
        current_app.logger.info(f'Editing indicator usage {id_indicator} for plan {current_plan.id}')
        current_app.logger.debug(f'Indicator code: {indicator_code}, is_coeff_editable: {is_coeff_editable}, is_codes_9911_9914: {is_codes_9911_9914}')
        
        if indicator.code in ['2023', '2024'] and not fuel_category and not name_other:
            current_app.logger.warning(f'Indicator {indicator.code} requires fuel category and Note but not provided')
            flash('Для данного показателя необходимо выбрать категорию топлива и ввести наименование', 'error')
            return redirect(url_for('plan_bp.plan_indicators', token=token))
        
        if is_coeff_editable and coeff_type == 'custom' and custom_coeff_raw:
            try:
                custom_coeff_raw = custom_coeff_raw.replace(',', '.')
                used_coeff = to_decimal_3(custom_coeff_raw)
                custom_coeff_value = used_coeff
                current_app.logger.info(f'Using custom coefficient: {used_coeff}')
            except Exception as e:
                current_app.logger.error(f'Error parsing custom coefficient: {e}')
                flash('Некорректное значение коэффициента', 'error')
                return redirect(url_for('plan_bp.plan_indicators', token=token))
        else:
            used_coeff = indicator.CoeffToTut
            custom_coeff_value = None
            current_app.logger.info(f'Using standard coefficient: {used_coeff}')
        
        QYearBeforePrev = to_decimal_2(QYearBeforePrev_ed * used_coeff)
        QYearPrev = to_decimal_2(QYearPrev_ed * used_coeff)
        QYearCurrent = to_decimal_2(QYearCurrent_ed * used_coeff)
        
        if indicator_code in ['2023', '2024'] and fuel_category:
            if fuel_category == 'local':
                is_local_value = True
                is_renewable_value = False
                current_app.logger.info(f'Setting is_local=True for indicator {indicator_code}')
            elif fuel_category == 'renewable':
                is_local_value = False
                is_renewable_value = True
                current_app.logger.info(f'Setting is_renewable=True for indicator {indicator_code}')
            else:
                is_local_value = indicator_usage.is_local
                is_renewable_value = indicator_usage.is_renewable
        else:
            is_local_value = indicator_usage.is_local
            is_renewable_value = indicator_usage.is_renewable
        
        if is_codes_9911_9914:
            indicator_usage.QYearCurrent = QYearCurrent
            current_app.logger.info(f'Updated only QYearCurrent for {indicator_code}')
        else:
            indicator_usage.QYearBeforePrev = QYearBeforePrev
            indicator_usage.QYearPrev = QYearPrev
            indicator_usage.QYearCurrent = QYearCurrent
            current_app.logger.info(f'Updated all QYear fields for {indicator_code}')
        
        if is_coeff_editable:
            indicator_usage.custom_coeff_to_tut = custom_coeff_value
            current_app.logger.info(f'Updated custom coefficient for {indicator_code}')
        
        indicator_usage.is_local = is_local_value
        indicator_usage.is_renewable = is_renewable_value
        indicator_usage.note=name_other
        
        db.session.commit()
        other_data_indicatorUpdate(current_plan.id)
        
        current_app.logger.info(f'Successfully updated indicator usage {id_indicator} for plan {current_plan.id}')
        flash('Показатель успешно обновлен', 'success')
        return redirect(url_for('plan_bp.plan_indicators', token=token))
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error editing indicator: {str(e)}', exc_info=True)
        flash(f'Ошибка при редактировании показателя: {str(e)}', 'error')
        return redirect(url_for('plan_bp.plan_indicators', token=token))

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
    
    period_codes = ['0001', '0002', '0003', '0004']

    if event_type == 'saving':
        type_filter = Direction.is_econom == True
        directions = Direction.query.filter(
            Direction.is_econom == True,
            Direction.code.notin_(period_codes)
        ).order_by(Direction.id.asc()).all()
        title = "Мероприятия по экономии ТЭР"
    else:
        type_filter = Direction.is_increase == True
        directions = Direction.query.filter(
            Direction.is_increase == True,
            Direction.code.notin_(period_codes)
        ).order_by(Direction.id.asc()).all()
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
                        confirmModal=True,
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
    event_type = request.form.get('event_type')
    
    direction = Direction.query.get(id_direction)
    if not direction:
        flash('Направление не найдено', 'error')
        current_app.logger.warning(f'Direction not found: id_direction={id_direction}, plan_id={current_plan.id}')
        return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=token))
    
    try:
        check_and_create_period_directions(current_plan.id, event_type)

        event_data = process_event_data(current_plan, direction, event_type, request.form)
        new_event = create_event_record(current_plan, direction, event_data)
        
        db.session.add(new_event)
        db.session.commit()
        
        if event_data['is_double_effect'] and event_type == 'increase':
            update_double_effect_payback(current_plan.id, direction.id)
        
        other_data_indicatorUpdate(current_plan.id)
        
        flash('Мероприятие добавлено', 'success')
        current_app.logger.info(f'Event created successfully: id={new_event.id}, plan_id={current_plan.id}, direction_id={id_direction}')
        
        return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=token))
        
    except ValueError as e:
        db.session.rollback()
        current_app.logger.error(f'ValueError creating event for plan_id={current_plan.id}: {str(e)}')
        flash(str(e), 'error')
        return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=token))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating event for plan_id={current_plan.id}: {str(e)}', exc_info=True)
        flash('Ошибка при добавлении мероприятия', 'error')
        return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=token))

@plan_bp.route('/edit-event/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def edit_Eventes(id):
    try:
        current_app.logger.info(f'Starting edit event with id={id}')
        
        current_event = Event.query.get(id)
        if not current_event:
            current_app.logger.warning(f'Event with id={id} not found')
            flash('Мероприятие не найдено', 'error')
            return redirect(request.referrer)
        
        current_plan = Plan.query.get(current_event.id_plan)
        if not current_plan:
            current_app.logger.warning(f'Plan with id={current_event.id_plan} not found')
            flash('План не найден', 'error')
            return redirect(request.referrer)
        
        event_type = request.form.get('event_type') or 'saving'
        edit_type = request.form.get('edit_type') or 'full'
        
        if edit_type == 'period':
            eff_curr_year_str = request.form.get('EffCurrYear')
            if eff_curr_year_str and eff_curr_year_str.strip():
                EffCurrYear = to_decimal_2(eff_curr_year_str)
            else:
                EffCurrYear = to_decimal_2('0')
            
            current_event.EffCurrYear = EffCurrYear
            current_app.logger.info(f'Updated period EffCurrYear for event {id}: {EffCurrYear}')
        else:
            name = request.form.get('name') or None
            Volume_value = request.form.get('Volume')
            ExpectedQuarter_value = request.form.get('ExpectedQuarter')
            EffTut = to_decimal_2(request.form.get('EffTut'))
            EffCurrYear = to_decimal_2(request.form.get('EffCurrYear'))
            
            is_double_effect = current_event.is_econom and current_event.is_increase
            
            if is_double_effect and current_event.is_econom:
                BudgetState = BudgetRep = BudgetLoc = BudgetOther = MoneyOwn = MoneyLoan = MoneyOther = 0
                VolumeFin = 0
                
                USD_RATE = float(current_plan.usd_rate) if current_plan.usd_rate else 2.75
                COST_PER_TOE_USD = float(current_plan.cost_per_toe_usd) if current_plan.cost_per_toe_usd else 260.0
                EffRub = int(float(EffTut) * COST_PER_TOE_USD * USD_RATE)
                Payback = None
                
                current_app.logger.info(f'Double effect saving event: financing blocked')
            else:
                BudgetState = to_decimal_2(request.form.get('BudgetState')) 
                BudgetRep = to_decimal_2(request.form.get('BudgetRep')) 
                BudgetLoc = to_decimal_2(request.form.get('BudgetLoc')) 
                BudgetOther = to_decimal_2(request.form.get('BudgetOther'))
                MoneyOwn = to_decimal_2(request.form.get('MoneyOwn')) 
                MoneyLoan = to_decimal_2(request.form.get('MoneyLoan')) 
                MoneyOther = to_decimal_2(request.form.get('MoneyOther'))
                
                VolumeFin = BudgetState + BudgetRep + BudgetLoc + BudgetOther + MoneyOwn + MoneyLoan + MoneyOther
                
                USD_RATE = float(current_plan.usd_rate) if current_plan.usd_rate else 2.75
                COST_PER_TOE_USD = float(current_plan.cost_per_toe_usd) if current_plan.cost_per_toe_usd else 260.0
                EffRub = int(float(EffTut) * COST_PER_TOE_USD * USD_RATE)
                
                if EffRub > 0:
                    payback_value = float(VolumeFin) / float(EffRub)
                    Payback = to_decimal_1(payback_value)
                else:
                    Payback = None
                
                current_app.logger.info(f'Regular event calculation: VolumeFin={VolumeFin}, EffRub={EffRub}, Payback={Payback}')

            Volume = int(float(Volume_value)) if Volume_value and Volume_value.strip() else None
            ExpectedQuarter = int(float(ExpectedQuarter_value)) if ExpectedQuarter_value and ExpectedQuarter_value.strip() else None
            
            current_event.name = name
            current_event.Volume = Volume
            current_event.ExpectedQuarter = ExpectedQuarter
            current_event.EffTut = EffTut
            current_event.EffRub = EffRub
            current_event.EffCurrYear = EffCurrYear
            current_event.Payback = Payback
            current_event.VolumeFin = VolumeFin
            current_event.BudgetState = BudgetState
            current_event.BudgetRep = BudgetRep
            current_event.BudgetLoc = BudgetLoc
            current_event.BudgetOther = BudgetOther
            current_event.MoneyOwn = MoneyOwn
            current_event.MoneyLoan = MoneyLoan
            current_event.MoneyOther = MoneyOther
            
            current_app.logger.info(f'Updated all fields for event {id}')

        db.session.commit()
        
        if current_event.is_econom and current_event.is_increase and not current_event.is_econom:
            update_double_effect_payback(current_plan.id, current_event.id_direction)
        
        other_data_indicatorUpdate(current_plan.id)
        
        flash('Мероприятие изменено', 'success')
        current_app.logger.info(f'Event {id} updated successfully')
        
        return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=current_plan.token))
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error editing event {id}: {str(e)}', exc_info=True)
        flash(f'Ошибка при редактировании мероприятия: {str(e)}', 'error')
        return redirect(request.referrer)


@plan_bp.route('/delete-eventes/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def delete_eventes(id):
    current_event = Event.query.get_or_404(id)
    current_plan = Plan.query.get_or_404(current_event.id_plan)
    
    if current_event.is_econom and not current_event.is_increase:
        event_type = 'saving'
    elif not current_event.is_econom and current_event.is_increase:
        event_type = 'increase'
    else:
        event_type = 'saving'
    
    is_double_effect = current_event.is_econom and current_event.is_increase
    direction_id = current_event.id_direction
    
    non_period_events_count = Event.query.filter(
        Event.id_plan == current_plan.id,
        Event.id != current_event.id,
        Event.is_econom == current_event.is_econom,
        Event.is_increase == current_event.is_increase,
        Event.display_code.notin_(['0001', '0002', '0003', '0004'])
    ).count()
    
    db.session.delete(current_event)
    
    if non_period_events_count == 0:
        period_events = Event.query.filter(
            Event.id_plan == current_plan.id,
            Event.display_code.in_(['0001', '0002', '0003', '0004']),
            Event.is_econom == current_event.is_econom,
            Event.is_increase == current_event.is_increase
        ).all()
        
        for period_event in period_events:
            db.session.delete(period_event)
        current_app.logger.info(f'Deleted {len(period_events)} period events for plan_id={current_plan.id}, event_type={event_type}')
    
    db.session.commit()
    
    if is_double_effect:
        update_double_effect_payback(current_plan.id, direction_id)
    
    other_data_indicatorUpdate(current_plan.id)
    flash('Мероприятие успешно удалено', 'success')
    return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=current_plan.token))

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

