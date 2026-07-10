from datetime import timedelta
from decimal import Decimal, InvalidOperation
from venv import logger

from flask_login import current_user

from .. import db
from ..models import Direction, Organization, Plan, PlanColumnConfig, Ticket, Indicator, Event, IndicatorUsage, Notification,PlanApprovalPath, TimeByMinsk

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

def get_column_configs_for_plan(plan):
    plan_year = plan.year
    current_year = TimeByMinsk().year
    
    if plan_year > current_year:
        labels = ['прогноз', 'прогноз', 'прогноз']
    elif plan_year == current_year:
        labels = ['отчет', 'оценка', 'прогноз']
    elif plan_year == current_year - 1:
        labels = ['отчет', 'отчет', 'оценка']
    else:
        labels = ['отчет', 'отчет', 'отчет']
    
    configs = []
    years = [plan_year - 2, plan_year - 1, plan_year]
    
    for year, label in zip(years, labels):
        config = PlanColumnConfig(
            plan_id=plan.id,
            year=year,
            label=label
        )
        configs.append(config)
    
    return configs

def update_ChangeTimePlan(id):
    def owner_ticket(plan):
        new_ticket = Ticket(
            note='Внесение изменений пользователем.',
            luck = True,
            is_owner = True,
            plan_id=plan.id,
            begin_time=TimeByMinsk()
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

def get_filtered_plans(user, status_filter="all", year_filter="all", search_name="", search_ynp="", region_id=None, page=1, per_page=5):
    try:
        current_app.logger.debug(f'get_filtered_plans called with region_id={region_id}')
        
        if user.is_auditor:
            auditor_org_ids = []
            if user.organization_id:
                auditor_org_ids.append(user.organization_id)
            
            if hasattr(user, 'organizations') and user.organizations:
                auditor_org_ids.extend([org.id for org in user.organizations])
            
            if not auditor_org_ids:
                base_query = Plan.query.filter(False)
            else:
                base_query = Plan.query.join(PlanApprovalPath, Plan.id == PlanApprovalPath.plan_id)\
                    .filter(PlanApprovalPath.organization_id.in_(auditor_org_ids))\
                    .filter(
                        db.or_(
                            Plan.is_sent == True,
                            Plan.is_error == True,
                            Plan.is_approved == True
                        )
                    )\
                    .distinct()
        elif user.is_admin:
            base_query = Plan.query.order_by(
                db.case(
                    (Plan.user_id == user.id, 0),
                    else_=1
                ),
                Plan.begin_time.desc()
            )
        else:
            base_query = Plan.query.filter_by(user_id=user.id)

        needs_join = bool(search_name or search_ynp or region_id)
        
        if needs_join:
            base_query = base_query.join(Organization, Plan.org_id == Organization.id)
            
            if search_name:
                base_query = base_query.filter(Organization.name.ilike(f'%{search_name}%'))
            
            if search_ynp:
                base_query = base_query.filter(Organization.ynp.ilike(f'%{search_ynp}%'))
            
            if region_id:
                base_query = base_query.filter(Organization.region_id == region_id)
        
        status_filters = {
            'draft': Plan.is_draft == True,
            'control': Plan.is_control == True,
            'sent': Plan.is_sent == True,
            'sogl': Plan.is_sent == True,
            'error': Plan.is_error == True,
            'approved': Plan.is_approved == True
        }
        
        filtered_query = base_query
        
        if user.is_auditor and status_filter == 'sogl':
            filtered_query = filtered_query.filter(
                Plan.is_sent == True,
                PlanApprovalPath.organization_id.in_(auditor_org_ids),
                PlanApprovalPath.is_viewed == True
            ).distinct()
        elif user.is_auditor and status_filter == 'sent':
            filtered_query = filtered_query.filter(
                Plan.is_sent == True,
                PlanApprovalPath.organization_id.in_(auditor_org_ids),
                PlanApprovalPath.is_viewed == False
            ).distinct()
        elif status_filter != 'all' and status_filter in status_filters:
            filtered_query = filtered_query.filter(status_filters[status_filter])
        
        if year_filter != 'all':
            filtered_query = filtered_query.filter(Plan.year == int(year_filter))
        
        total_count = filtered_query.count()
        current_app.logger.debug(f'total_count={total_count}')
        
        plans = filtered_query.order_by(Plan.begin_time.desc()).offset((page - 1) * per_page).limit(per_page).all()
        current_app.logger.debug(f'plans count={len(plans)}')
        
        count_query = base_query
        if year_filter != 'all':
            count_query = count_query.filter(Plan.year == int(year_filter))
        
        status_counts = {
            'all': count_query.count()
        }
        
        if user.is_auditor and auditor_org_ids:
            status_counts['sent'] = count_query.filter(
                Plan.is_sent == True,
                PlanApprovalPath.organization_id.in_(auditor_org_ids),
                PlanApprovalPath.is_viewed == False
            ).distinct().count()
            
            status_counts['sogl'] = count_query.filter(
                Plan.is_sent == True,
                PlanApprovalPath.organization_id.in_(auditor_org_ids),
                PlanApprovalPath.is_viewed == True
            ).distinct().count()
            
            status_counts['error'] = count_query.filter(Plan.is_error == True).distinct().count()
            status_counts['approved'] = count_query.filter(Plan.is_approved == True).distinct().count()
            status_counts['draft'] = 0
            status_counts['control'] = 0
        else:
            status_counts['draft'] = count_query.filter(Plan.is_draft == True).count()
            status_counts['control'] = count_query.filter(Plan.is_control == True).count()
            status_counts['sent'] = count_query.filter(Plan.is_sent == True).count()
            status_counts['error'] = count_query.filter(Plan.is_error == True).count()
            status_counts['approved'] = count_query.filter(Plan.is_approved == True).count()
        
        return plans, total_count, status_counts
        
    except Exception as e:
        current_app.logger.error(f'Error in get_filtered_plans: {str(e)}', exc_info=True)
        raise

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
            indicator_9900.QYearCurrent = to_decimal_1(total)
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