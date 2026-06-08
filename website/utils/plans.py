from datetime import timedelta
from decimal import Decimal, InvalidOperation
from venv import logger

from flask_login import current_user

from .. import db
from ..models import Direction, Organization, Plan, Ticket, Indicator, Event, IndicatorUsage, Notification, TimeByMinsk

from sqlalchemy import func, or_

from flask import (
    current_app
)

from decimal import Decimal, InvalidOperation
import logging

def to_decimal_1(value):
    try:
        if value is None or value == '':
            return Decimal('0.0')
        
        if isinstance(value, Decimal):
            return value.quantize(Decimal('0.0'))
        
        if isinstance(value, (int, float)):
            return Decimal(str(value)).quantize(Decimal('0.0'))
        
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return Decimal('0.0')
            
            value = value.replace(',', '.')
            
            if value.count('.') > 1:
                parts = value.split('.')
                value = parts[0] + '.' + ''.join(parts[1:])
            
            return Decimal(value).quantize(Decimal('0.0'))
        
        return Decimal('0.0')
        
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.0')

def to_decimal_2(value):
    try:
        if value is None or value == '':
            return Decimal('0.00')
        
        if isinstance(value, Decimal):
            return value.quantize(Decimal('0.00'))
        
        if isinstance(value, (int, float)):
            return Decimal(str(value)).quantize(Decimal('0.00'))
        
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return Decimal('0.00')
            
            value = value.replace(',', '.')
            
            if value.count('.') > 1:
                parts = value.split('.')
                value = parts[0] + '.' + ''.join(parts[1:])
            
            return Decimal(value).quantize(Decimal('0.00'))
        
        return Decimal('0.00')
        
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')
    
def to_decimal_3(value):
    try:
        if value is None or value == '':
            return Decimal('0.000')
        
        if isinstance(value, Decimal):
            return value.quantize(Decimal('0.000'))
        
        if isinstance(value, (int, float)):
            return Decimal(str(value)).quantize(Decimal('0.000'))
        
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return Decimal('0.000')
            
            value = value.replace(',', '.')
            
            if value.count('.') > 1:
                parts = value.split('.')
                value = parts[0] + '.' + ''.join(parts[1:])
            
            return Decimal(value).quantize(Decimal('0.000'))
        
        return Decimal('0.000')
        
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.000')
    
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

def get_filtered_plans(user, status_filter="all", year_filter="all", search_name="", search_okpo="", page=1, per_page=5):
    if user.is_auditor and not user.is_admin:
        base_query = Plan.query.filter(Plan.is_sent == True)
    elif user.is_admin:
        base_query = Plan.query.filter_by(user_id=user.id)
    else:
        base_query = Plan.query.filter_by(user_id=user.id)
    
    if search_name:
        base_query = base_query.join(Organization).filter(Organization.name.ilike(f'%{search_name}%'))
    
    if search_okpo:
        base_query = base_query.join(Organization).filter(Organization.okpo.ilike(f'%{search_okpo}%'))
    
    status_filters = {
        'draft': Plan.is_draft == True,
        'control': Plan.is_control == True,
        'sent': Plan.is_sent == True,
        'error': Plan.is_error == True,
        'approved': Plan.is_approved == True
    }
    
    filtered_query = base_query
    if status_filter != 'all' and status_filter in status_filters:
        filtered_query = filtered_query.filter(status_filters[status_filter])
    
    if year_filter != 'all':
        filtered_query = filtered_query.filter(Plan.year == int(year_filter))
    
    total_count = filtered_query.count()
    plans = filtered_query.order_by(Plan.begin_time.desc()).offset((page - 1) * per_page).limit(per_page).all()
    
    count_query = base_query
    if year_filter != 'all':
        count_query = count_query.filter(Plan.year == int(year_filter))
    
    status_counts = {
        'all': count_query.count(),
        'draft': count_query.filter(Plan.is_draft == True).count(),
        'control': count_query.filter(Plan.is_control == True).count(),
        'sent': count_query.filter(Plan.is_sent == True).count(),
        'error': count_query.filter(Plan.is_error == True).count(),
        'approved': count_query.filter(Plan.is_approved == True).count()
    }
    
    return plans, total_count, status_counts

# def get_event_metrics(plan_id, event_type, is_original=True):
#     query = (db.session.query(
#         Event.ExpectedQuarter,
#         func.sum(Event.EffCurrYear).label('total_eff'),
#         func.sum(Event.VolumeFin).label('total_vol')
#     )
#     .join(Direction, Event.id_direction == Direction.id)
#     .filter(Event.id_plan == plan_id)
#     )
    
#     if event_type == 'saving':
#         query = query.filter(Direction.is_econom == True)
#     else:
#         query = query.filter(Direction.is_increase == True)
    
#     if is_original:
#         query = query.filter(Event.is_corrected == False)
#     else:
#         query = query.filter(Event.is_corrected == True)

#     quarterly_results = query.group_by(Event.ExpectedQuarter).all()
    
#     cumulative_totals = {
#         'jan_mar': {'eff_curr_year': 0},
#         'jan_jun': {'eff_curr_year': 0},
#         'jan_sep': {'eff_curr_year': 0},
#         'jan_dec': {'eff_curr_year': 0}
#     }
    
#     quarter_data = {1: {'eff': 0, 'vol': 0}, 2: {'eff': 0, 'vol': 0}, 
#                    3: {'eff': 0, 'vol': 0}, 4: {'eff': 0, 'vol': 0}}
    
#     for quarter, eff_sum, vol_sum in quarterly_results:
#         if quarter in [1, 2, 3, 4]:
#             quarter_data[quarter]['eff'] = float(eff_sum) if eff_sum else 0
#             quarter_data[quarter]['vol'] = float(vol_sum) if vol_sum else 0
    
#     cumulative_totals['jan_mar']['eff_curr_year'] = quarter_data[1]['eff']
#     cumulative_totals['jan_jun']['eff_curr_year'] = quarter_data[1]['eff'] + quarter_data[2]['eff']
#     cumulative_totals['jan_sep']['eff_curr_year'] = quarter_data[1]['eff'] + quarter_data[2]['eff'] + quarter_data[3]['eff']
#     cumulative_totals['jan_dec']['eff_curr_year'] = (quarter_data[1]['eff'] + quarter_data[2]['eff'] + quarter_data[3]['eff'] + quarter_data[4]['eff'])

#     return cumulative_totals

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
    
    def update_indicator_1000():
        """Обновление индикатора 1000 (сумма всех необязательных показателей)"""
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
    
    def update_indicator_1796():
        """Обновление индикатора 1796 (сумма местных видов топлива)"""
        logger.info(f'Calculating local total (1796) for plan {plan.id}')
        
        indicator_1796 = Indicator.query.filter_by(code='1796').first()
        if not indicator_1796:
            logger.error('Indicator with code 1796 not found')
            return
        
        usage_1796 = get_indicator_by_code(indicator_usages, '1796')
        if not usage_1796:
            logger.warning('IndicatorUsage for 1796 not found')
            return
        
        total_local_before_prev = 0
        total_local_prev = 0
        total_local_current = 0
        
        for usage in indicator_usages:
            if usage.is_local:
                total_local_before_prev += float(get_value(usage, 'QYearBeforePrev') or 0)
                total_local_prev += float(get_value(usage, 'QYearPrev') or 0)
                total_local_current += float(get_value(usage, 'QYearCurrent') or 0)
        
        usage_1796.QYearBeforePrev = to_decimal_2(total_local_before_prev)
        usage_1796.QYearPrev = to_decimal_2(total_local_prev)
        usage_1796.QYearCurrent = to_decimal_2(total_local_current)
        
        logger.info(f'Success sum for 1796')
        commit_changes()
    
    def update_indicator_1797():
        """Обновление индикатора 1797 (сумма возобновляемых видов топлива)"""
        logger.info(f'Calculating renewable total (1797) for plan {plan.id}')
        
        indicator_1797 = Indicator.query.filter_by(code='1797').first()
        if not indicator_1797:
            logger.error('Indicator with code 1797 not found')
            return
        
        usage_1797 = get_indicator_by_code(indicator_usages, '1797')
        if not usage_1797:
            logger.warning('IndicatorUsage for 1797 not found')
            return
        
        total_renewable_before_prev = 0
        total_renewable_prev = 0
        total_renewable_current = 0
        
        for usage in indicator_usages:
            if usage.is_renewable:
                total_renewable_before_prev += float(get_value(usage, 'QYearBeforePrev') or 0)
                total_renewable_prev += float(get_value(usage, 'QYearPrev') or 0)
                total_renewable_current += float(get_value(usage, 'QYearCurrent') or 0)
        
        usage_1797.QYearBeforePrev = to_decimal_2(total_renewable_before_prev)
        usage_1797.QYearPrev = to_decimal_2(total_renewable_prev)
        usage_1797.QYearCurrent = to_decimal_2(total_renewable_current)
        
        logger.info(f'Success sum for 1797')
        commit_changes()
    
    def update_indicator_9900():
        """Обновление индикатора 9900 (экономия ТЭР от мероприятий в текущем году)"""
        total = db.session.query(func.sum(Event.EffCurrYear)).filter(
            Event.id_plan == plan.id,
            Event.direction.has(is_econom=True),
            db.or_(
                Event.is_local == True,
                Event.is_corrected == True
            )
        ).scalar() or 0
        
        indicator_9900 = get_indicator_by_code(indicator_usages, '9900')
        if indicator_9900:
            indicator_9900.QYearCurrent = to_decimal_2(total)
            commit_changes()
    
    def update_indicator_9910():
        """Обновление индикатора 9910 (экономия от мероприятий прошлого года) из 9914"""
        logger.info(f'Calculating econom from events last year (9910) for plan {plan.id}')
        
        indicator_9910 = get_indicator_by_code(indicator_usages, '9910')
        if not indicator_9910:
            logger.warning('Indicator with code 9910 not found')
            return
        
        indicator_9914 = get_indicator_by_code(indicator_usages, '9914')
        
        if indicator_9914:
            value = get_value(indicator_9914, 'QYearCurrent')
            indicator_9910.QYearCurrent = to_decimal_2(value)
            logger.info(f'Set 9910.QYearCurrent = {value} (from 9914)')
        else:
            logger.warning('Indicator 9914 not found, setting 9910.QYearCurrent = 0')
            indicator_9910.QYearCurrent = to_decimal_2(0)
        commit_changes()
    
    def update_indicator_9999():
        """Обновление индикатора 9999 (общая годовая экономия) = 9900 + 9910"""
        logger.info(f'Calculating 9999 (total econom) for plan {plan.id}')
        
        indicator_9999 = get_indicator_by_code(indicator_usages, '9999')
        if not indicator_9999:
            logger.warning('Indicator with code 9999 not found')
            return
        
        indicator_9900 = get_indicator_by_code(indicator_usages, '9900')
        indicator_9910 = get_indicator_by_code(indicator_usages, '9910')
        
        if not indicator_9900:
            logger.warning('Indicator with code 9900 not found')
            return
        
        if not indicator_9910:
            logger.warning('Indicator with code 9910 not found')
            return
        
        value_9900 = get_value(indicator_9900, 'QYearCurrent')
        value_9910 = get_value(indicator_9910, 'QYearCurrent')
        
        total = value_9900 + value_9910
        
        indicator_9999.QYearCurrent = to_decimal_2(total)
        
        logger.info(f'Set 9999.QYearCurrent = {total} (9900: {value_9900} + 9910: {value_9910})')
        commit_changes()
    
    def update_indicator_260():
        """Обновление индикатора 260 (суммарное потребление ТЭР)"""
        logger.info(f'Calculating 260 (total consumption) for plan {plan.id}')
        
        indicator_260 = get_indicator_by_code(indicator_usages, '260')
        if not indicator_260:
            logger.warning('Indicator with code 260 not found')
            return
        
        indicator_1000 = get_indicator_by_code(indicator_usages, '1000')
        indicator_1105 = get_indicator_by_code(indicator_usages, '1105')
        indicator_1405 = get_indicator_by_code(indicator_usages, '1405')
        indicator_1104 = get_indicator_by_code(indicator_usages, '1104')
        indicator_1404 = get_indicator_by_code(indicator_usages, '1404')
        
        if not all([indicator_1000, indicator_1105, indicator_1405, indicator_1104, indicator_1404]):
            logger.warning('Missing required indicators for 260 calculation')
            return
        
        periods = ['QYearBeforePrev', 'QYearPrev', 'QYearCurrent']
        
        for period in periods:
            base = get_value(indicator_1000, period)
            diff1 = get_value(indicator_1105, period) - get_value(indicator_1405, period)
            diff2 = get_value(indicator_1104, period) - get_value(indicator_1404, period)
            result = to_decimal_2(base + diff1 + diff2)
            setattr(indicator_260, period, result)
            logger.info(f'Set 260.{period} = {result}')
        
        commit_changes()
    
    def update_indicator_9915():
        """Обновление индикатора 9915 (целевой показатель энергосбережения)"""
        logger.info(f'Calculating 9915 (energy saving target) for plan {plan.id}')
        
        indicator_9915 = get_indicator_by_code(indicator_usages, '9915')
        if not indicator_9915:
            logger.warning('Indicator with code 9915 not found')
            return
        
        indicator_9999 = get_indicator_by_code(indicator_usages, '9999')
        indicator_260 = get_indicator_by_code(indicator_usages, '260')
        
        if not indicator_9999 or not indicator_260:
            logger.warning('Missing required indicators for 9915 calculation')
            return
        
        numerator = get_value(indicator_9999, 'QYearCurrent')
        denominator = get_value(indicator_260, 'QYearPrev')
        
        result = safe_divide(numerator, denominator) * 100
        indicator_9915.QYearCurrent = to_decimal_2(-abs(result))
        
        logger.info(f'Set 9915.QYearCurrent = {result}')
        commit_changes()
    
    def update_indicator_9916():
        """Обновление индикатора 9916 (Целевой показатель по доле местных ТЭР в КПТ)"""
        logger.info(f'Calculating 9916 (local share) for plan {plan.id}')
        
        indicator_9916 = get_indicator_by_code(indicator_usages, '9916')
        if not indicator_9916:
            logger.warning('Indicator with code 9916 not found')
            return
        
        indicator_1796 = get_indicator_by_code(indicator_usages, '1796')
        indicator_1424 = get_indicator_by_code(indicator_usages, '1424')
        indicator_1425 = get_indicator_by_code(indicator_usages, '1425')
        indicator_1000 = get_indicator_by_code(indicator_usages, '1000')
        
        if not indicator_1000:
            logger.warning('Indicator 1000 not found')
            return
        
        periods = ['QYearBeforePrev', 'QYearPrev', 'QYearCurrent']
        
        for period in periods:
            numerator = Decimal('0')
            
            if indicator_1796:
                numerator += get_value(indicator_1796, period)
            if indicator_1424:
                numerator += get_value(indicator_1424, period)
            if indicator_1425:
                numerator += get_value(indicator_1425, period)
            
            denominator = get_value(indicator_1000, period)
            
            if denominator == 0:
                result = Decimal('0')
            else:
                result = (numerator / denominator) * 100
            
            setattr(indicator_9916, period, to_decimal_2(result))
            logger.info(f'Set 9916.{period} = {result}')
        
        commit_changes()
    
    def update_indicator_9917():
        """Обновление индикатора 9917 (доля возобновляемых источников в КПТ)"""
        logger.info(f'Calculating 9917 (renewable share) for plan {plan.id}')
        
        indicator_9917 = get_indicator_by_code(indicator_usages, '9917')
        if not indicator_9917:
            logger.warning('Indicator with code 9917 not found')
            return
        
        indicator_1797 = get_indicator_by_code(indicator_usages, '1797')
        indicator_1424 = get_indicator_by_code(indicator_usages, '1424')
        indicator_1425 = get_indicator_by_code(indicator_usages, '1425')
        indicator_1000 = get_indicator_by_code(indicator_usages, '1000')
        
        if not indicator_1000:
            logger.warning('Indicator 1000 not found')
            return
        
        periods = ['QYearBeforePrev', 'QYearPrev', 'QYearCurrent']
        
        for period in periods:
            numerator = Decimal('0')
            
            if indicator_1797:
                numerator += get_value(indicator_1797, period)
            if indicator_1424:
                numerator += get_value(indicator_1424, period)
            if indicator_1425:
                numerator += get_value(indicator_1425, period)
            
            denominator = get_value(indicator_1000, period)
            
            if denominator == 0:
                result = Decimal('0')
            else:
                result = (numerator / denominator) * 100
            
            setattr(indicator_9917, period, to_decimal_2(result))
            logger.info(f'Set 9917.{period} = {result}')
        
        commit_changes()
    
    try:
        update_indicator_9900()
        update_indicator_1000()
        update_indicator_1796()
        update_indicator_1797()
        update_indicator_9910()
        update_indicator_9999()
        update_indicator_260()
        update_indicator_9915()
        update_indicator_9916()
        update_indicator_9917()
        
        update_ChangeTimePlan(plan.id)
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении индикаторов для плана {plan.id}: {e}")
        db.session.rollback()

def check_and_create_period_directions(plan_id, event_type):
    try:
        period_codes = ['0001', '0002', '0003', '0004']
        period_names = {
            '0001': 'Январь-Март',
            '0002': 'Январь-Июнь',
            '0003': 'Январь-Сентябрь',
            '0004': 'Январь-Декабрь'
        }
        
        for code in period_codes:
            if event_type == 'saving':
                direction = Direction.query.filter_by(code=code, is_econom=True, is_increase=False).first()
            else:
                direction = Direction.query.filter_by(code=code, is_econom=False, is_increase=True).first()
            
            if not direction:
                logger.warning(f'Direction with code {code} and event_type {event_type} not found')
                continue
            
            existing_event = Event.query.filter_by(
                id_plan=plan_id,
                id_direction=direction.id,
                is_corrected=False
            ).first()
            
            if not existing_event:
                new_event = Event(
                    id_plan=plan_id,
                    id_direction=direction.id,
                    name=period_names[code],
                    display_code=code,
                    is_econom=(event_type == 'saving'),
                    is_increase=(event_type == 'increase')
                )
                db.session.add(new_event)
                logger.debug(f'Created period event for {event_type}: code={code}, direction_id={direction.id}, plan_id={plan_id}')
        
        db.session.commit()
        logger.debug(f'Period events created for plan_id={plan_id}, event_type={event_type}')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error creating period events for plan_id={plan_id}, event_type={event_type}: {str(e)}')
        raise
    
def handle_draft_status(plan):
    plan.is_draft = True
    plan.is_control = plan.is_sent = plan.is_error = plan.is_approved = False
    plan.afch = False
    return "Статус переведен в редактирование."

def handle_control_status(plan):
    errors = []
    
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
    
    if indicator_9999 and indicator_9900:
        if indicator_9999.QYearCurrent != indicator_9900.QYearCurrent:
            errors.append("Годовая экономия ТЭР от энергосберегающих мероприятий всего должна быть равна ожидаемой экономии ТЭР от внедрения мероприятий в текущем году.")
        
        if indicator_9999.QYearCurrent < (indicator_9914.QYearCurrent if indicator_9914 else 0):
            errors.append("Годовая экономия ТЭР от энергосберегающих мероприятий всего должна быть больше или равна экономии ТЭР от мероприятий предыдущего года внедрения (январь-декабрь).")
    
    if indicator_9911 and indicator_9912 and indicator_9913 and indicator_9914:
        if indicator_9914.QYearCurrent < indicator_9913.QYearCurrent:
            errors.append("Экономия ТЭР за январь-декабрь должна быть больше или равна экономии за январь-сентябрь.")
        
        if indicator_9913.QYearCurrent < indicator_9912.QYearCurrent:
            errors.append("Экономия ТЭР за январь-сентябрь должна быть больше или равна экономии за январь-июнь.")
        
        if indicator_9912.QYearCurrent < indicator_9911.QYearCurrent:
            errors.append("Экономия ТЭР за январь-июнь должна быть больше или равна экономии за январь-март.")
    
    
    if indicator_9915 and plan.energy_saving:
        if indicator_9915.QYearCurrent > plan.energy_saving:
            errors.append(f"Целевой показатель энергосбережения ({indicator_9915.QYearCurrent}%) не должен превышать задание ({plan.energy_saving}%).")
    
    if indicator_9900 and plan.saving_fuel:
        if indicator_9900.QYearCurrent < plan.saving_fuel:
            errors.append(f"Ожидаемая экономия ТЭР ({indicator_9900.QYearCurrent} т у.т.) должна быть больше или равна заданию ({plan.saving_fuel} т у.т.).")
        
    if indicator_9916 and plan.share_fuel:
        if indicator_9916.QYearCurrent < plan.share_fuel:
            errors.append(f"Целевой показатель по доле местных ТЭР в КПТ ({indicator_9916.QYearCurrent}%) должен быть больше или равен заданию ({plan.share_fuel}%).")
    
    if indicator_9917 and plan.share_energy:
        if indicator_9917.QYearCurrent < plan.share_energy:
            errors.append(f"Целевой показатель по доле ВИЭ в КПТ ({indicator_9917.QYearCurrent}%) должен быть больше или равен заданию ({plan.share_energy}%).")
    
    if errors:
        return {"error": "\n".join(errors)}
    
    plan.is_control = True
    plan.is_draft = plan.is_sent = plan.is_error = plan.is_approved = False
    plan.afch = False
    
    return "План прошел проверку на контроль."
    
    
    
    
    
 
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