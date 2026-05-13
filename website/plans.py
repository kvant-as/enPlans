from datetime import timedelta
from decimal import Decimal, InvalidOperation

from flask_login import current_user

from . import db
from .models import Organization, Plan, Ticket, Indicator, Event, IndicatorUsage, Notification, TimeByMinsk

from sqlalchemy import func, or_

from flask import (
    current_app
)


def to_decimal_2(value):
    try:
        return Decimal(value).quantize(Decimal('0.001'))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')
    
def update_ChangeTimePlan(id):
    def owner_ticket(plan):
        new_ticket = Ticket(
            note='Внесение изменений пользователем.',
            luck = True,
            is_owner = True,
            plan_id=plan.id,
        )

        db.session.add(new_ticket)
        plan.afch = False
        db.session.commit()
        
     
    plan = Plan.query.filter_by(id=id).first()
    if not plan:
        return 
    
    plan.change_time = TimeByMinsk()
    plan.is_draft = True   
    plan.is_control = False  
    plan.is_sent = False      
    plan.is_error = False    
    plan.is_approved = False  

    if plan.afch == True:
        owner_ticket(plan)

    db.session.commit()

    
    
def get_plans_by_okpo():
    okpo_digit = str(current_user.organization.okpo)[-4]
    """Фильтрация по 4-ой цифре с конца OKPO: {okpo_digit}"""
    
    status_filter = or_(
        Plan.is_sent == True,
        Plan.is_error == True, 
        Plan.is_approved == True
    )
    
    if current_user.is_admin or (current_user.is_auditor and str(current_user.organization.okpo)[-4] == "8"):
        return Plan.query.filter(
            status_filter
        ).order_by(Plan.year.asc())
    else:
        return Plan.query.join(Organization).filter(
            status_filter,
            func.substr(Organization.okpo, func.length(Organization.okpo) - 3, 1) == okpo_digit
        ).order_by(Plan.year.asc())
        
def get_filtered_plans(user, status_filter="all", year_filter="all"):
    if user.is_auditor:
        base_query = get_plans_by_okpo()
    else:
        base_query = Plan.query.filter_by(user_id=user.id)
    
    display_query = base_query

    status_filters = {
        'draft': Plan.is_draft == True,
        'control': Plan.is_control == True,
        'sent': Plan.is_sent == True,
        'error': Plan.is_error == True,
        'approved': Plan.is_approved == True
    }

    if status_filter != 'all' and status_filter in status_filters:
        display_query = display_query.filter(status_filters[status_filter])

    if year_filter != 'all':
        display_query = display_query.filter(Plan.year == int(year_filter))

    plans = display_query.all()

    count_query = base_query
    if year_filter != 'all':
        count_query = count_query.filter(Plan.year == int(year_filter))
    if status_filter != 'all' and status_filter in status_filters:
        count_query = count_query.filter(status_filters[status_filter])

    status_counts = {
        'all': count_query.count(),
        'draft': count_query.filter(Plan.is_draft == True).count(),
        'control': count_query.filter(Plan.is_control == True).count(),
        'sent': count_query.filter(Plan.is_sent == True).count(),
        'error': count_query.filter(Plan.is_error == True).count(),
        'approved': count_query.filter(Plan.is_approved == True).count()
    }
    return plans, status_counts

def get_cumulative_econ_metrics(plan_id, is_local): 
    quarterly_results = (db.session.query(
            Event.ExpectedQuarter,  
            func.sum(Event.EffCurrYear).label('total_eff'), 
            func.sum(Event.VolumeFin).label('total_vol')
        )
        # .join(EconMeasure) 
        .join(Plan)
        .filter(Plan.id == plan_id)
        .group_by(Event.ExpectedQuarter)
        .all())
    
    cumulative_totals = {
        'jan_mar': {'eff_curr_year': 0, 'volume_fin': 0},  # Январь-Март
        'jan_jun': {'eff_curr_year': 0, 'volume_fin': 0},  # Январь-Июнь
        'jan_sep': {'eff_curr_year': 0, 'volume_fin': 0},  # Январь-Сентябрь
        'jan_dec': {'eff_curr_year': 0, 'volume_fin': 0}   # Январь-Декабрь
    }
    

    quarter_data = {1: {'eff': 0, 'vol': 0}, 2: {'eff': 0, 'vol': 0}, 
                   3: {'eff': 0, 'vol': 0}, 4: {'eff': 0, 'vol': 0}}
    
    for quarter, eff_sum, vol_sum in quarterly_results:
        if quarter in [1, 2, 3, 4]:
            quarter_data[quarter]['eff'] = eff_sum or 0
            quarter_data[quarter]['vol'] = vol_sum or 0
    

    cumulative_totals['jan_mar']['eff_curr_year'] = quarter_data[1]['eff']
    cumulative_totals['jan_mar']['volume_fin'] = quarter_data[1]['vol']
    
    cumulative_totals['jan_jun']['eff_curr_year'] = quarter_data[1]['eff'] + quarter_data[2]['eff']
    cumulative_totals['jan_jun']['volume_fin'] = quarter_data[1]['vol'] + quarter_data[2]['vol']
    
    cumulative_totals['jan_sep']['eff_curr_year'] = quarter_data[1]['eff'] + quarter_data[2]['eff'] + quarter_data[3]['eff']
    cumulative_totals['jan_sep']['volume_fin'] = quarter_data[1]['vol'] + quarter_data[2]['vol'] + quarter_data[3]['vol']
    
    cumulative_totals['jan_dec']['eff_curr_year'] = (quarter_data[1]['eff'] + quarter_data[2]['eff'] + 
                                                   quarter_data[3]['eff'] + quarter_data[4]['eff'])
    cumulative_totals['jan_dec']['volume_fin'] = (quarter_data[1]['vol'] + quarter_data[2]['vol'] + 
                                                quarter_data[3]['vol'] + quarter_data[4]['vol'])
    
    return cumulative_totals

def other_data_indicatorUpdate(id):
    plan = Plan.query.filter_by(id=id).first()
    if not plan:
        return

    indicator_usages = IndicatorUsage.query.filter_by(id_plan=plan.id).all()

    def econom_ter():
        total_eff_curr_year = db.session.query(func.sum(Event.EffCurrYear))\
            .filter(
                Event.id_plan == plan.id,
                Event.EffCurrYear.isnot(None)
            )\
            .scalar() or 0
        
        indicator_usages = IndicatorUsage.query.filter_by(id_plan=plan.id).all()
        usage_with_code_9900 = None
        for usage in indicator_usages:
            if usage.indicator.code == '9900':
                usage_with_code_9900 = usage
                break
        
        usage_with_code_9900.QYearNext = to_decimal_2(total_eff_curr_year)
        db.session.commit()

    def first_title():
        totals = db.session.query(
                func.sum(IndicatorUsage.QYearPrev).label('total_prev'),
                func.sum(IndicatorUsage.QYearCurr).label('total_curr'),
                func.sum(IndicatorUsage.QYearNext).label('total_next')
            )\
            .join(IndicatorUsage.indicator)\
            .filter(
                IndicatorUsage.id_plan == plan.id,
                Indicator.IsMandatory == False
            )\
            .first()

        total_prev = totals.total_prev or 0
        total_curr = totals.total_curr or 0
        total_next = totals.total_next or 0

        usage_with_code_1000 = None
        for usage in indicator_usages:
            if usage.indicator.code == '1000':
                usage_with_code_1000 = usage
                break
        
        if usage_with_code_1000:
            usage_with_code_1000.QYearPrev = to_decimal_2(total_prev)
            usage_with_code_1000.QYearCurr = to_decimal_2(total_curr)
            usage_with_code_1000.QYearNext = to_decimal_2(total_next)
            db.session.commit()
    
    def four_title():
        indicators_by_code = {}
        codes_to_find = ['260', '1000', '1105', '1405', '1104', '1404']
        
        for usage in indicator_usages:
            if usage.indicator.code in codes_to_find:
                indicators_by_code[usage.indicator.code] = usage
                if len(indicators_by_code) == len(codes_to_find):
                    break
        
        missing_codes = [code for code in codes_to_find if code not in indicators_by_code]
        if missing_codes:
            current_app.logger.debug(f"Не найдены индикаторы: {missing_codes}")
            return
        
        indicator_260 = indicators_by_code['260']
        indicator_1000 = indicators_by_code['1000']
        indicator_1105 = indicators_by_code['1105']
        indicator_1405 = indicators_by_code['1405']
        indicator_1104 = indicators_by_code['1104']
        indicator_1404 = indicators_by_code['1404']
        
        def get_value(indicator, field_name):
            value = getattr(indicator, field_name)
            return value if value is not None else Decimal('0')
        
        def calculate_period(period):
            base = get_value(indicator_1000, period)
            diff1 = get_value(indicator_1105, period) - get_value(indicator_1405, period)
            diff2 = get_value(indicator_1104, period) - get_value(indicator_1404, period)
            return to_decimal_2(base + (diff1 * Decimal('0.123')) + (diff2 * Decimal('0.143')))
        
        indicator_260.QYearPrev = calculate_period('QYearPrev')
        indicator_260.QYearCurr = calculate_period('QYearCurr')
        indicator_260.QYearNext = calculate_period('QYearNext')
        db.session.commit()

    def seven_title():
        usage_with_code_9999 = None
        for usage in indicator_usages:
            if usage.indicator.code == '9999':
                usage_with_code_9999 = usage
                break

        usage_with_code_9900 = None
        for usage in indicator_usages:
            if usage.indicator.code == '9900':
                usage_with_code_9900 = usage
                break
        
        usage_with_code_9910 = None
        for usage in indicator_usages:
            if usage.indicator.code == '9910':
                usage_with_code_9910 = usage
                break

        usage_with_code_9999.QYearNext = usage_with_code_9900.QYearNext + usage_with_code_9910.QYearNext

    first_title()
    four_title()
    econom_ter()
    seven_title()

def handle_draft_status(plan):
    plan.is_draft = True
    plan.is_control = plan.is_sent = plan.is_error = plan.is_approved = False
    plan.afch = False
    return "Статус переведен в редактирование."

def handle_control_status(plan):
    indicator_usage = next(
        (iu for iu in plan.indicators_usage if iu.indicator.code == '9900'), 
        None
    ) # № п/п = 5
    
    if indicator_usage and indicator_usage.QYearNext != 0:
        plan.is_control = True
        plan.is_draft = plan.is_sent = plan.is_error = plan.is_approved = False
        plan.afch = False
        return "План прошел проверку на контроль."
    else:
        return {"error": "Ожидаемая экономия ТЭР от внедрения в текущем году не может быть равна 0."}
 
def handle_sent_status(plan):
    if plan.audit_time and (TimeByMinsk() - plan.audit_time) > timedelta(hours=1):
        return {"error": "Нельзя изменить статус: прошло больше допустимого времени"}
    plan.sent_time = TimeByMinsk()
    plan.is_sent = True
    plan.is_draft = plan.is_control = plan.is_error = plan.is_approved = False
    plan.afch = False
    return "План передан на проверку."

def handle_error_status(plan):
    plan.audit_time = TimeByMinsk()
    plan.is_error = True
    plan.is_draft = plan.is_control = plan.is_sent = plan.is_approved = False

    new_ticket = Ticket(
        note="В плане нашли ошибки, статус изменен на Есть ошибки",
        luck=True,
        is_owner = True,
        plan_id=plan.id,
    )
    db.session.add(new_ticket)

    notification = Notification(
        user_id=plan.user_id,
        message=f"В плане на {plan.year} год нашли ошибки."
    )
    db.session.add(notification)
    return "Статус ошибки установлен."

def handle_approved_status(plan):
    plan.audit_time = TimeByMinsk()
    plan.is_approved = True
    plan.is_draft = plan.is_control = plan.is_sent = plan.is_error = False
    plan.afch = False 

    new_ticket = Ticket(
        note="План был одобрен, статус был изменен на Одобрен.",
        luck=True,
        is_owner = True,
        plan_id=plan.id,
    )
    db.session.add(new_ticket)

    notification = Notification(
        user_id=plan.user_id,
        message=f"План на {plan.year} год был одобрен."
    )
    db.session.add(notification)
    return "План одобрен."


status_handlers = {
    'draft': handle_draft_status,
    'control': handle_control_status,
    'sent': handle_sent_status,
    'error': handle_error_status,
    'approved': handle_approved_status
}