from datetime import timedelta
from decimal import Decimal, InvalidOperation

from flask_login import current_user

from . import db
from .models import Direction, Organization, Plan, Ticket, Indicator, Event, IndicatorUsage, Notification, TimeByMinsk

from sqlalchemy import func, or_

from flask import (
    current_app
)

from decimal import Decimal, InvalidOperation
import logging

def to_decimal_2(value):
    try:
        return Decimal(value).quantize(Decimal('0.00'))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')
    
def generate_unique_display_code(base_code, plan_id, direction_id):
    existing_events = Event.query.filter(
        Event.id_plan == plan_id,
        Event.id_direction == direction_id
    ).order_by(Event.id.asc()).all()
    
    if not existing_events:
        return f"{base_code}.1"
    
    existing_suffixes = []
    for event in existing_events:
        if event.display_code and '.' in event.display_code:
            parts = event.display_code.split('.')
            if len(parts) > 1 and parts[-1].isdigit():
                existing_suffixes.append(int(parts[-1]))
    
    if existing_suffixes:
        next_number = max(existing_suffixes) + 1
    else:
        next_number = len(existing_events) + 1
    
    return f"{base_code}.{next_number}"

    
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

def get_event_metrics(plan_id, event_type, is_original=True):
    query = (db.session.query(
        Event.ExpectedQuarter,
        func.sum(Event.EffCurrYear).label('total_eff'),
        func.sum(Event.VolumeFin).label('total_vol')
    )
    .join(Direction, Event.id_direction == Direction.id)
    .filter(Event.id_plan == plan_id)
    )
    
    if event_type == 'saving':
        query = query.filter(Direction.is_econom == True)
    else:
        query = query.filter(Direction.is_increase == True)
    
    if is_original:
        query = query.filter(Event.is_corrected == False)
    else:
        query = query.filter(Event.is_corrected == True)

    quarterly_results = query.group_by(Event.ExpectedQuarter).all()
    
    cumulative_totals = {
        'jan_mar': {'eff_curr_year': 0, 'volume_fin': 0},
        'jan_jun': {'eff_curr_year': 0, 'volume_fin': 0},
        'jan_sep': {'eff_curr_year': 0, 'volume_fin': 0},
        'jan_dec': {'eff_curr_year': 0, 'volume_fin': 0}
    }
    
    quarter_data = {1: {'eff': 0, 'vol': 0}, 2: {'eff': 0, 'vol': 0}, 
                   3: {'eff': 0, 'vol': 0}, 4: {'eff': 0, 'vol': 0}}
    
    for quarter, eff_sum, vol_sum in quarterly_results:
        if quarter in [1, 2, 3, 4]:
            quarter_data[quarter]['eff'] = float(eff_sum) if eff_sum else 0
            quarter_data[quarter]['vol'] = float(vol_sum) if vol_sum else 0
    
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

def other_data_indicatorUpdate(plan_id):
    plan = Plan.query.get(plan_id)
    if not plan:
        return
    
    logger = logging.getLogger(__name__)
    
    def get_value(indicator, field_name):
        value = getattr(indicator, field_name)
        return value if value is not None else Decimal('0')
    
    def safe_divide(numerator, denominator):
        try:
            if denominator == 0:
                return Decimal('0')
            return to_decimal_2(numerator / denominator)
        except (InvalidOperation, ZeroDivisionError):
            return Decimal('0')
    
    def get_indicator_by_code(indicator_usages, code):
        for usage in indicator_usages:
            if usage.indicator.code == code:
                return usage
        return None
    
    def get_indicators_dict(indicator_usages, codes):
        result = {}
        for usage in indicator_usages:
            if usage.indicator.code in codes:
                result[usage.indicator.code] = usage
        return result
    
    def commit_changes():
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Ошибка при сохранении: {e}")
            db.session.rollback()
    
    indicator_usages = IndicatorUsage.query.filter_by(id_plan=plan.id).all()
    
    def first_title():
        totals = db.session.query(
            func.sum(IndicatorUsage.QYearBeforePrev).label('total_before_prev'),
            func.sum(IndicatorUsage.QYearPrev).label('total_prev'),
            func.sum(IndicatorUsage.QYearCurrent).label('total_current')
        ).join(IndicatorUsage.indicator).filter(
            IndicatorUsage.id_plan == plan.id,
            Indicator.IsMandatory == False
        ).first()
        
        indicator_1000 = get_indicator_by_code(indicator_usages, '1000')
        if indicator_1000:
            indicator_1000.QYearBeforePrev = to_decimal_2(totals.total_before_prev or 0)
            indicator_1000.QYearPrev = to_decimal_2(totals.total_prev or 0)
            indicator_1000.QYearCurrent = to_decimal_2(totals.total_current or 0)
            commit_changes()
    
    def econom_ter():
        total = db.session.query(func.sum(Event.EffCurrYear)).filter(
            Event.id_plan == plan.id,
            Event.direction.has(is_econom=True),
            Event.EffCurrYear.isnot(None)
        ).scalar() or 0
        
        indicator_9900 = get_indicator_by_code(indicator_usages, '9900')
        if indicator_9900:
            indicator_9900.QYearCurrent = to_decimal_2(total)
            commit_changes()
    
    def update_indicator_with_formula(indicator_code, codes_to_find, formula_func, periods=['QYearBeforePrev', 'QYearPrev', 'QYearCurrent']):
        indicators = get_indicators_dict(indicator_usages, codes_to_find)
        
        missing_codes = [code for code in codes_to_find if code not in indicators]
        if missing_codes:
            logger.debug(f"Не найдены индикаторы для {indicator_code}: {missing_codes}")
            return False
        
        target_indicator = indicators.get(indicator_code)
        if not target_indicator:
            logger.debug(f"Целевой индикатор {indicator_code} не найден")
            return False
        
        for period in periods:
            result = formula_func(indicators, period)
            setattr(target_indicator, period, result)
        
        commit_changes()
        return True
    
    def formula_260(indicators, period):
        base = get_value(indicators['1000'], period)
        diff1 = get_value(indicators['1105'], period) - get_value(indicators['1405'], period)
        diff2 = get_value(indicators['1104'], period) - get_value(indicators['1404'], period)
        return to_decimal_2(base + diff1 + diff2)
    
    def formula_9999(indicators, period):
        logger.debug(f"formula_9999: Начало расчета для периода {period}")
        logger.debug(f"formula_9999: Доступные индикаторы: {list(indicators.keys())}")
        
        indicator_9900 = indicators.get('9900')
        indicator_9910 = indicators.get('9910')
        
        if not indicator_9900:
            logger.debug(f"formula_9999: Индикатор 9900 не найден")
        if not indicator_9910:
            logger.debug(f"formula_9999: Индикатор 9910 не найден")
        
        if not indicator_9900 or not indicator_9910:
            logger.debug(f"formula_9999: Индикаторы 9900 или 9910 не найдены, возвращаем 0")
            return Decimal('0')
        
        value_9900 = get_value(indicator_9900, period)
        value_9910 = get_value(indicator_9910, period)
        
        logger.debug(f"formula_9999: indicator_9900.{period} = {value_9900}")
        logger.debug(f"formula_9999: indicator_9910.{period} = {value_9910}")
        
        base = value_9900 + value_9910
        result = to_decimal_2(base)
        
        logger.debug(f"formula_9999: Сумма = {base}, результат = {result}")
        
        return result
    
    def formula_9915(indicators, period):
        numerator = get_value(indicators['9999'], period)
        denominator = get_value(indicators['260'], 'QYearPrev')
        return safe_divide(numerator, denominator) * 100
    
    def formula_9916(indicators, period):
        numerator = (get_value(indicators['1796'], period) + 
                    get_value(indicators['1425'], period) + 
                    get_value(indicators['1424'], period))
        denominator = get_value(indicators['1000'], period) * 100
        return safe_divide(numerator, denominator)
    
    def formula_9917(indicators, period):
        numerator = (get_value(indicators['1797'], period) + 
                    get_value(indicators['1425'], period) + 
                    get_value(indicators['1424'], period))
        denominator = get_value(indicators['1000'], period) * 100
        return safe_divide(numerator, denominator)
    
    try:
        first_title()
        econom_ter()
        
        update_indicator_with_formula('9999', ['9900', '9910'], formula_9999, periods=['QYearCurrent'])
        
        update_indicator_with_formula('260', ['260', '1000', '1105', '1405', '1104', '1404'], formula_260)
        
        # не считается хз почему
        update_indicator_with_formula('9915', ['9915', '9999', '260'], formula_9915, periods=['QYearCurrent']) 
        
        update_indicator_with_formula('9916', ['9916', '1796', '1425', '1424', '1000'], formula_9916)
        
        update_indicator_with_formula('9917', ['9917', '1797', '1425', '1424', '1000'], formula_9917)
        
        update_ChangeTimePlan(plan.id)
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении индикаторов для плана {plan.id}: {e}")
        db.session.rollback()

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
    
    if indicator_usage and indicator_usage.QYearCurrent != 0:
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