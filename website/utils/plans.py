from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from venv import logger

from flask_login import current_user

from .. import db
from ..models import Direction, Organization, Plan, PlanColumnConfig, PlanTicket, Indicator, Event, IndicatorUsage, Notification, PlanApprovalPath

from common_models import current_utc_time

from sqlalchemy import func, or_

from flask import (
    current_app
)

from decimal import Decimal, InvalidOperation
import logging

# quantize() без явного rounding по умолчанию использует ROUND_HALF_EVEN
# ("банковское" округление: 2,25 -> 2,2), а не привычное "математическое"
# округление половины вверх (2,25 -> 2,3) — отсюда расхождения, заметные
# только на границе X,X5 ("в отдельных случаях применяется некорректное
# округление"). Везде ниже округляем явно через ROUND_HALF_UP.
def to_decimal_1(value):
    try:
        if value is None or value == '':
            return Decimal('0.0')

        if isinstance(value, Decimal):
            return value.quantize(Decimal('0.0'), rounding=ROUND_HALF_UP)

        if isinstance(value, (int, float)):
            return Decimal(str(value)).quantize(Decimal('0.0'), rounding=ROUND_HALF_UP)

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return Decimal('0.0')

            value = value.replace(',', '.')

            if value.count('.') > 1:
                parts = value.split('.')
                value = parts[0] + '.' + ''.join(parts[1:])

            return Decimal(value).quantize(Decimal('0.0'), rounding=ROUND_HALF_UP)

        return Decimal('0.0')

    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.0')

def to_decimal_2(value):
    try:
        if value is None or value == '':
            return Decimal('0.00')

        if isinstance(value, Decimal):
            return value.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

        if isinstance(value, (int, float)):
            return Decimal(str(value)).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return Decimal('0.00')

            value = value.replace(',', '.')

            if value.count('.') > 1:
                parts = value.split('.')
                value = parts[0] + '.' + ''.join(parts[1:])

            return Decimal(value).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

        return Decimal('0.00')

    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')

def to_decimal_3(value):
    try:
        if value is None or value == '':
            return Decimal('0.000')

        if isinstance(value, Decimal):
            return value.quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)

        if isinstance(value, (int, float)):
            return Decimal(str(value)).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return Decimal('0.000')

            value = value.replace(',', '.')

            if value.count('.') > 1:
                parts = value.split('.')
                value = parts[0] + '.' + ''.join(parts[1:])

            return Decimal(value).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)

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
    current_year = current_utc_time().year
    
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
        new_ticket = PlanTicket(
            note='Внесение изменений пользователем.',
            luck = True,
            is_system = True,
            plan_id=plan.id,
            begin_time=current_utc_time()
        )

        db.session.add(new_ticket)
        plan.afch = False
        db.session.commit()
        
     
    plan = Plan.query.filter_by(id=id).first()
    if not plan:
        return 
    
    plan.change_time = current_utc_time()
    plan.is_draft = True   
    plan.is_control = False  
    plan.is_sent = False      
    plan.is_error = False    
    plan.is_approved = False  

    if plan.afch == True:
        owner_ticket(plan)

    db.session.commit()

def get_plans_by_okpo():
    """Фильтрация по 4-ой цифре с конца ОКПО организации пользователя —
    кроме admin/is_reader, которые видят всё вне зависимости от ОКПО (и
    могут вообще не иметь привязанной организации, поэтому эта ветка
    проверяется первой, до обращения к current_user.organization)."""
    status_filter = or_(
        Plan.is_sent == True,
        Plan.is_error == True,
        Plan.is_approved == True
    )

    if current_user.is_admin or current_user.is_reader:
        return Plan.query.filter(status_filter).order_by(Plan.year.asc())

    org_okpo = str(current_user.organization.okpo) if current_user.organization else ''
    okpo_digit = org_okpo[-4] if len(org_okpo) >= 4 else None

    if current_user.is_auditor and okpo_digit == "8":
        return Plan.query.filter(status_filter).order_by(Plan.year.asc())

    return Plan.query.join(Organization).filter(
        status_filter,
        func.substr(Organization.okpo, func.length(Organization.okpo) - 3, 1) == okpo_digit
    ).order_by(Plan.year.asc())

def get_filtered_plans(user, status_filter="all", year_filter="all", search_name="", search_ynp="", region_id=None, page=1, per_page=5):
    try:
        # current_app.logger.debug(f'get_filtered_plans called with region_id={region_id}')
        
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
        elif user.is_admin or user.is_reader:
            # is_reader — читатель, видит все планы (как admin), но
            # изменить/создать ничего не может (см. reader_forbidden в
            # routes/views.py и одноимённый декоратор в plan_bp.py/audit_bp.py)
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
                base_query = base_query.filter(Organization.full_name.ilike(f'%{search_name}%'))
            
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
        # current_app.logger.debug(f'total_count={total_count}')
        
        plans = filtered_query.order_by(Plan.begin_time.desc()).offset((page - 1) * per_page).limit(per_page).all()
        # current_app.logger.debug(f'plans count={len(plans)}')
        
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
    
    current_app.logger = logging.getLogger(__name__)
    
    def get_value(indicator, field_name):
        value = getattr(indicator, field_name)
        return value if value is not None else Decimal('0')

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
            current_app.logger.error(f"Ошибка при сохранении: {e}")
            db.session.rollback()
    
    indicator_usages = IndicatorUsage.query.filter_by(id_plan=plan.id).all()
    
    def update_indicator_1101():
        """Обновление индикатора 1101 (сумма всех необязательных показателей)"""
        totals = db.session.query(
            func.sum(IndicatorUsage.QYearBeforePrev).label('total_before_prev'),
            func.sum(IndicatorUsage.QYearPrev).label('total_prev'),
            func.sum(IndicatorUsage.QYearCurrent).label('total_current')
        ).join(IndicatorUsage.indicator).filter(
            IndicatorUsage.id_plan == plan.id,
            Indicator.IsMandatory == False
        ).first()

        indicator_1101 = get_indicator_by_code(indicator_usages, '1101')
        if indicator_1101:
            indicator_1101.QYearBeforePrev = to_decimal_2(totals.total_before_prev or 0)
            indicator_1101.QYearPrev = to_decimal_2(totals.total_prev or 0)
            indicator_1101.QYearCurrent = to_decimal_2(totals.total_current or 0)
            commit_changes()
    
    def update_indicator_1796():
        """Обновление индикатора 1796 (сумма местных видов топлива)"""
        current_app.logger.info(f'Calculating local total (1796) for plan {plan.id}')
        
        indicator_1796 = Indicator.query.filter_by(code='1796').first()
        if not indicator_1796:
            current_app.logger.error('Indicator with code 1796 not found')
            return
        
        usage_1796 = get_indicator_by_code(indicator_usages, '1796')
        if not usage_1796:
            current_app.logger.warning('IndicatorUsage for 1796 not found')
            return
        
        total_local_before_prev = 0
        total_local_prev = 0
        total_local_current = 0
        
        for usage in indicator_usages:
            if usage.is_local or usage.is_renewable:
                total_local_before_prev += float(get_value(usage, 'QYearBeforePrev') or 0)
                total_local_prev += float(get_value(usage, 'QYearPrev') or 0)
                total_local_current += float(get_value(usage, 'QYearCurrent') or 0)
        
        usage_1796.QYearBeforePrev = to_decimal_2(total_local_before_prev)
        usage_1796.QYearPrev = to_decimal_2(total_local_prev)
        usage_1796.QYearCurrent = to_decimal_2(total_local_current)
        
        current_app.logger.info(f'Success sum for 1796')
        commit_changes()
    
    def update_indicator_1797():
        """Обновление индикатора 1797 (сумма возобновляемых видов топлива)"""
        current_app.logger.info(f'Calculating renewable total (1797) for plan {plan.id}')
        
        indicator_1797 = Indicator.query.filter_by(code='1797').first()
        if not indicator_1797:
            current_app.logger.error('Indicator with code 1797 not found')
            return
        
        usage_1797 = get_indicator_by_code(indicator_usages, '1797')
        if not usage_1797:
            current_app.logger.warning('IndicatorUsage for 1797 not found')
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
        
        current_app.logger.info(f'Success sum for 1797')
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
        current_app.logger.info(f'Calculating econom from events last year (9910) for plan {plan.id}')
        
        indicator_9910 = get_indicator_by_code(indicator_usages, '9910')
        if not indicator_9910:
            current_app.logger.warning('Indicator with code 9910 not found')
            return
        
        indicator_9914 = get_indicator_by_code(indicator_usages, '9914')
        
        if indicator_9914:
            value = get_value(indicator_9914, 'QYearCurrent')
            indicator_9910.QYearCurrent = to_decimal_2(value)
            current_app.logger.info(f'Set 9910.QYearCurrent = {value} (from 9914)')
        else:
            current_app.logger.warning('Indicator 9914 not found, setting 9910.QYearCurrent = 0')
            indicator_9910.QYearCurrent = to_decimal_2(0)
        commit_changes()
    
    def update_indicator_9999():
        """Обновление индикатора 9999 (общая годовая экономия) = 9900 + 9910"""
        current_app.logger.info(f'Calculating 9999 (total econom) for plan {plan.id}')
        
        indicator_9999 = get_indicator_by_code(indicator_usages, '9999')
        if not indicator_9999:
            current_app.logger.warning('Indicator with code 9999 not found')
            return
        
        indicator_9900 = get_indicator_by_code(indicator_usages, '9900')
        indicator_9910 = get_indicator_by_code(indicator_usages, '9910')
        
        if not indicator_9900:
            current_app.logger.warning('Indicator with code 9900 not found')
            return
        
        if not indicator_9910:
            current_app.logger.warning('Indicator with code 9910 not found')
            return
        
        value_9900 = get_value(indicator_9900, 'QYearCurrent')
        value_9910 = get_value(indicator_9910, 'QYearCurrent')
        
        total = value_9900 + value_9910
        
        indicator_9999.QYearCurrent = to_decimal_2(total)
        
        current_app.logger.info(f'Set 9999.QYearCurrent = {total} (9900: {value_9900} + 9910: {value_9910})')
        commit_changes()
    
    def update_indicator_260():
        """Обновление индикатора 260 (суммарное потребление ТЭР)"""
        current_app.logger.info(f'Calculating 260 (total consumption) for plan {plan.id}')
        
        indicator_260 = get_indicator_by_code(indicator_usages, '260')
        if not indicator_260:
            current_app.logger.warning('Indicator with code 260 not found')
            return
        
        indicator_1101 = get_indicator_by_code(indicator_usages, '1101')
        indicator_1105 = get_indicator_by_code(indicator_usages, '1105')
        indicator_1405 = get_indicator_by_code(indicator_usages, '1405')
        indicator_1104 = get_indicator_by_code(indicator_usages, '1104')
        indicator_1404 = get_indicator_by_code(indicator_usages, '1404')

        if not all([indicator_1101, indicator_1105, indicator_1405, indicator_1104, indicator_1404]):
            current_app.logger.warning('Missing required indicators for 260 calculation')
            return

        periods = ['QYearBeforePrev', 'QYearPrev', 'QYearCurrent']

        for period in periods:
            base = get_value(indicator_1101, period)
            diff1 = get_value(indicator_1105, period) - get_value(indicator_1405, period)
            diff2 = get_value(indicator_1104, period) - get_value(indicator_1404, period)
            result = to_decimal_2(base + diff1 + diff2)
            setattr(indicator_260, period, result)
            current_app.logger.info(f'Set 260.{period} = {result}')
        
        commit_changes()
    
    def update_indicator_9915():
        """Обновление индикатора 9915 (целевой показатель энергосбережения)"""
        current_app.logger.info(f'Calculating 9915 (energy saving target) for plan {plan.id}')
        
        indicator_9915 = get_indicator_by_code(indicator_usages, '9915')
        if not indicator_9915:
            current_app.logger.warning('Indicator with code 9915 not found')
            return
        
        indicator_9999 = get_indicator_by_code(indicator_usages, '9999')
        indicator_260 = get_indicator_by_code(indicator_usages, '260')
        
        if not indicator_9999 or not indicator_260:
            current_app.logger.warning('Missing required indicators for 9915 calculation')
            return
        
        numerator = get_value(indicator_9999, 'QYearCurrent')
        denominator = get_value(indicator_260, 'QYearPrev')

        # Раньше тут было safe_divide(...) * 100 — safe_divide округляет
        # ОТНОШЕНИЕ до 2 знаков ДО умножения на 100, а значит итоговый
        # процент мог быть только кратен целому (0,01 * 100 = 1): дробная
        # доля процента терялась ещё до этого умножения, поэтому
        # результат всегда выглядел как "X,0". Делим без промежуточного
        # округления и округляем только готовый процент.
        if denominator == 0:
            result = Decimal('0.00')
        else:
            result = (numerator / denominator) * 100
        indicator_9915.QYearCurrent = to_decimal_2(-abs(result))
        
        current_app.logger.info(f'Set 9915.QYearCurrent = {result}')
        commit_changes()
    
    def update_indicator_9916():
        """Обновление индикатора 9916 (Целевой показатель по доле местных ТЭР в КПТ)"""
        current_app.logger.info(f'Calculating 9916 (local share) for plan {plan.id}')
        
        indicator_9916 = get_indicator_by_code(indicator_usages, '9916')
        if not indicator_9916:
            current_app.logger.warning('Indicator with code 9916 not found')
            return
        
        indicator_1796 = get_indicator_by_code(indicator_usages, '1796')
        indicator_1424 = get_indicator_by_code(indicator_usages, '1424')
        indicator_1425 = get_indicator_by_code(indicator_usages, '1425')
        indicator_1101 = get_indicator_by_code(indicator_usages, '1101')

        if not indicator_1101:
            current_app.logger.warning('Indicator 1101 not found')
            return

        periods = ['QYearBeforePrev', 'QYearPrev', 'QYearCurrent']

        for period in periods:
            numerator = Decimal('0.0')

            if indicator_1796:
                numerator += get_value(indicator_1796, period)
            if indicator_1424:
                numerator += get_value(indicator_1424, period)
            if indicator_1425:
                numerator += get_value(indicator_1425, period)

            denominator = get_value(indicator_1101, period)

            if denominator == 0:
                result = Decimal('0.0')
            else:
                result = (numerator / denominator) * 100

            setattr(indicator_9916, period, to_decimal_2(result))
            current_app.logger.info(f'Set 9916.{period} = {result}')
        
        commit_changes()
    
    def update_indicator_9917():
        """Обновление индикатора 9917 (доля возобновляемых источников в КПТ)"""
        current_app.logger.info(f'Calculating 9917 (renewable share) for plan {plan.id}')
        
        indicator_9917 = get_indicator_by_code(indicator_usages, '9917')
        if not indicator_9917:
            current_app.logger.warning('Indicator with code 9917 not found')
            return
        
        indicator_1797 = get_indicator_by_code(indicator_usages, '1797')
        indicator_1424 = get_indicator_by_code(indicator_usages, '1424')
        indicator_1425 = get_indicator_by_code(indicator_usages, '1425')
        indicator_1101 = get_indicator_by_code(indicator_usages, '1101')

        if not indicator_1101:
            current_app.logger.warning('Indicator 1101 not found')
            return

        periods = ['QYearBeforePrev', 'QYearPrev', 'QYearCurrent']

        for period in periods:
            numerator = Decimal('0.0')

            if indicator_1797:
                numerator += get_value(indicator_1797, period)
            if indicator_1424:
                numerator += get_value(indicator_1424, period)
            if indicator_1425:
                numerator += get_value(indicator_1425, period)

            denominator = get_value(indicator_1101, period)
            
            if denominator == 0:
                result = Decimal('0.0')
            else:
                result = (numerator / denominator) * 100
            
            setattr(indicator_9917, period, to_decimal_2(result))
            current_app.logger.info(f'Set 9917.{period} = {result}')
        
        commit_changes()
    
    try:
        update_indicator_9900()
        update_indicator_1101()
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
        current_app.logger.error(f"Ошибка при обновлении индикаторов для плана {plan.id}: {e}")
        db.session.rollback()

def validate_period_values(plan_id, current_period_code, current_value, exclude_event_id=None):
    period_codes = ['0001', '0002', '0003', '0004']
    
    if current_period_code not in period_codes:
        return None
    
    period_names = {
        '0001': 'Январь-Март',
        '0002': 'Январь-Июнь',
        '0003': 'Январь-Сентябрь',
        '0004': 'Январь-Декабрь'
    }
    
    period_events = Event.query.filter(
        Event.id_plan == plan_id,
        Event.direction.has(Direction.code.in_(period_codes)),
        Event.is_corrected == False
    )
    
    if exclude_event_id:
        period_events = period_events.filter(Event.id != exclude_event_id)
    
    period_events = period_events.all()
    
    # Январь-декабрь (0004) считается автоматически как сумма всех реальных
    # мероприятий плана (см. update_period_eff_values) и служит потолком
    # сразу для всех трёх периодов — март, июнь и сентябрь по отдельности
    # не могут превышать декабрь. Пока декабрь равен 0 (реальных мероприятий
    # с эффектом ещё нет), заполнить ненулевое значение нельзя ни в одном
    # из периодов.
    #
    # Сверх этого — цепочка март <= июнь <= сентябрь: но сосед проверяется
    # только если он уже РЕАЛЬНО заполнен (None, а не 0, если ещё не
    # тронут) — иначе возвращается бага "нельзя заполнить март, пока не
    # заполнен июнь" (июнь молча считался бы за 0, и любое март > 0 всегда
    # "превышало" бы этот фиктивный 0).
    raw_period_values = {}
    for pe in period_events:
        if pe.direction and pe.direction.code:
            raw_period_values[pe.direction.code] = pe.EffCurrYear

    def _as_float(code):
        raw = raw_period_values.get(code)
        return float(raw) if raw is not None else None

    current_value_num = float(current_value) if current_value else 0
    december_value = _as_float('0004') or 0

    if current_value_num > december_value:
        return 'Значение "{}" ({:.2f} т у.т.) не может быть больше "{}" ({:.2f} т у.т.)'.format(
            period_names[current_period_code], current_value_num,
            period_names['0004'], december_value
        )

    next_code = {'0001': '0002', '0002': '0003'}.get(current_period_code)
    if next_code:
        next_value = _as_float(next_code)
        if next_value is not None and current_value_num > next_value:
            return 'Значение "{}" ({:.2f} т у.т.) не может быть больше "{}" ({:.2f} т у.т.)'.format(
                period_names[current_period_code], current_value_num,
                period_names[next_code], next_value
            )

    return None

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
                current_app.logger.warning(f'Direction with code {code} and event_type {event_type} not found')
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
                current_app.logger.debug(f'Created period event for {event_type}: code={code}, direction_id={direction.id}, plan_id={plan_id}')
        
        db.session.commit()
        current_app.logger.debug(f'Period events created for plan_id={plan_id}, event_type={event_type}')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating period events for plan_id={plan_id}, event_type={event_type}: {str(e)}')
        raise


CANCEL_SEND_NOTE_PREFIX = 'Отправка отменена'


def build_signature_cycles(plan):
    """Группирует plan.approval_paths по циклам отправки (PlanApprovalPath.cycle)
    для вкладки "Подписи". Раньше при каждой повторной отправке (после отмены
    или возврата на доработку) старые строки маршрута удалялись и история
    терялась — теперь они остаются в БД с привязкой к своему циклу, а эта
    функция собирает их в упорядоченный список для шаблона:

        [{'cycle': 1, 'sent_at': datetime|None, 'paths': [...],
          'cancel_ticket': PlanTicket|None, 'is_latest': bool}, ...]

    Для НЕ последнего цикла непройденные этапы в шаблоне должны показываться
    как "Не пройдено" (цикл брошен/отменён), а не "На рассмотрении"/"Ожидание
    очереди" — это решает флаг is_latest, фактическую метку выбирает шаблон.
    """
    paths_by_cycle = {}
    for path in plan.approval_paths:
        paths_by_cycle.setdefault(path.cycle, []).append(path)

    cycle_numbers = sorted(paths_by_cycle.keys())
    if not cycle_numbers:
        return []

    for cycle_paths in paths_by_cycle.values():
        cycle_paths.sort(key=lambda p: p.step_order)

    cancel_tickets = sorted(
        [t for t in plan.tickets if t.note and t.note.startswith(CANCEL_SEND_NOTE_PREFIX) and t.begin_time],
        key=lambda t: t.begin_time,
    )

    def cycle_start(cycle_paths):
        starts = [p.created_at for p in cycle_paths if p.created_at]
        return min(starts) if starts else None

    cycles = []
    for idx, cycle_num in enumerate(cycle_numbers):
        cycle_paths = paths_by_cycle[cycle_num]
        sent_at = cycle_start(cycle_paths)

        next_start = None
        if idx + 1 < len(cycle_numbers):
            next_start = cycle_start(paths_by_cycle[cycle_numbers[idx + 1]])

        cancel_ticket = None
        for ticket in cancel_tickets:
            if sent_at and ticket.begin_time >= sent_at and (next_start is None or ticket.begin_time < next_start):
                cancel_ticket = ticket
                break

        cycles.append({
            'cycle': cycle_num,
            'sent_at': sent_at,
            'paths': cycle_paths,
            'cancel_ticket': cancel_ticket,
            'is_latest': idx == len(cycle_numbers) - 1,
        })

    return cycles


def get_current_review_path(plan, current_user):
    """Текущий (непройденный, первый по порядку) этап согласования из
    ПОСЛЕДНЕГО цикла отправки — или None, если либо план не отправлен, либо
    все этапы пройдены, либо organization_id пользователя на нём не стоит."""
    if not plan.approval_paths:
        return None
    latest_cycle = max(p.cycle for p in plan.approval_paths)
    latest_paths = sorted(
        (p for p in plan.approval_paths if p.cycle == latest_cycle),
        key=lambda p: p.step_order,
    )
    current_path = next((p for p in latest_paths if not p.is_viewed), None)
    if not current_path or not current_user.organization_id:
        return None
    if current_path.organization_id != current_user.organization_id:
        return None
    return current_path


def get_audit_context(plan, current_user):
    """Весь контекст, нужный вкладке «Проверка» (plan_audit.html): какой
    этап сейчас "ваш", можно ли писать/менять статус/отменять изменения,
    оставил ли проверяющий уже сообщение по этому этапу, и как подписать
    кнопку подтверждения («Одобрить» на последнем этапе, иначе
    «Согласовать»). Централизовано здесь вместо повторения этой логики
    прямо в шаблоне — там было легко забыть ограничить запрос последним
    циклом отправки (approval_paths больше не чистятся при пересылке)."""
    current_path = get_current_review_path(plan, current_user)
    can_audit = bool(current_path) and not plan.is_approved and not plan.is_error

    approve_label = 'Согласовать'
    if current_path:
        cycle_paths = [p for p in plan.approval_paths if p.cycle == current_path.cycle]
        max_step = max((p.step_order for p in cycle_paths), default=current_path.step_order)
        if current_path.step_order == max_step:
            approve_label = 'Одобрить'

    user_has_viewed_current = any(
        p.organization_id == current_user.organization_id and p.is_viewed
        for p in plan.approval_paths
        if (not current_path) or p.cycle == current_path.cycle
    )
    next_path = None
    if current_path:
        next_path = next(
            (p for p in plan.approval_paths
             if p.cycle == current_path.cycle and p.step_order == current_path.step_order + 1),
            None,
        )
    can_cancel = (user_has_viewed_current and (not next_path or not next_path.is_viewed)) or plan.is_error or plan.is_approved

    has_remarks = has_pending_review_message(plan, current_user) if can_audit else False

    return {
        'current_path': current_path,
        'can_audit': can_audit,
        'can_cancel': can_cancel,
        'has_remarks': has_remarks,
        'approve_label': approve_label,
    }


def has_pending_review_message(plan, current_user):
    """Заменяет флаг Plan.afch: вместо хранимого булева (который раньше
    нужно было вручную сбрасывать, например при удалении сообщения — и
    это легко забыть/разъехаться с реальностью) каждый раз живым запросом
    проверяем, оставил ли ИМЕННО ТЕКУЩИЙ проверяющий (current_user) хотя бы
    одно своё (не системное) сообщение по текущему этапу последнего цикла.
    Удаление сообщения автоматически "сбрасывает" результат — отдельного
    действия не требуется."""
    current_path = get_current_review_path(plan, current_user)
    if not current_path:
        return False
    cutoff = current_path.created_at
    for ticket in plan.tickets:
        if ticket.is_system or ticket.user_id != current_user.id:
            continue
        if cutoff and ticket.begin_time and ticket.begin_time < cutoff:
            continue
        return True
    return False