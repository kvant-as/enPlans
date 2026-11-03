from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from venv import logger

from flask_login import current_user

from .. import db
from ..models import Direction, Organization, Plan, PlanColumnConfig, PlanTicket, Indicator, Event, IndicatorUsage, Notification, PlanApprovalPath, User

from common_models import current_utc_time

from sqlalchemy import func, or_, and_

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

def get_filtered_plans(user, status_filter="all", year_filter="all", search_name="", search_ynp="", region_id=None, search_approver_org="", page=1, per_page=5):
    try:
        # current_app.logger.debug(f'get_filtered_plans called with region_id={region_id}')
        
        if user.is_auditor or user.is_approver:
            # is_approver (утверждающая организация) — та же механика, что
            # и у is_auditor (согласующая): список планов по собственным
            # этапам в PlanApprovalPath, а не по org_id (который у
            # организации-рецензента никогда не совпадёт с org_id плана).
            # Раньше is_approver здесь не проверялся вовсе — такие аккаунты
            # проваливались в ветку "else" ниже и не видели ни одного плана.
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
                    (Plan.org_id == user.organization_id, 0),
                    else_=1
                ),
                Plan.begin_time.desc()
            )
        else:
            # План закреплён за организацией, а не за конкретным
            # пользователем — все сотрудники организации (любой org_role)
            # видят одни и те же планы в списке.
            base_query = Plan.query.filter_by(org_id=user.organization_id)

        # Замороженные снимки (см. Plan.is_historical/create_plan_snapshot в
        # этом же файле) — история одного "живого" плана, а не отдельные
        # планы организации; в списках не показываются вовсе, открываются
        # только напрямую по собственному token со страницы плана (свитчер
        # версий — component.plan_version_switcher).
        base_query = base_query.filter(Plan.snapshot_of_plan_id.is_(None))

        needs_join = bool(search_name or search_ynp or region_id)
        
        if needs_join:
            base_query = base_query.join(Organization, Plan.org_id == Organization.id)
            
            if search_name:
                base_query = base_query.filter(Organization.full_name.ilike(f'%{search_name}%'))
            
            if search_ynp:
                base_query = base_query.filter(Organization.ynp.ilike(f'%{search_ynp}%'))
            
            if region_id:
                base_query = base_query.filter(Organization.region_id == region_id)

        if search_approver_org:
            from sqlalchemy.orm import aliased
            ApproverPath = aliased(PlanApprovalPath)
            ApproverOrg = aliased(Organization)
            base_query = base_query.join(ApproverPath, Plan.id == ApproverPath.plan_id)\
                .join(ApproverOrg, ApproverPath.organization_id == ApproverOrg.id)\
                .filter(ApproverPath.step_type == 'approver')\
                .filter(ApproverOrg.full_name.ilike(f'%{search_approver_org}%'))\
                .distinct()

        status_filters = {
            'draft': Plan.is_draft == True,
            # "Контроль пройден" и "На подписании" — взаимоисключающие: план,
            # отправленный на внутреннюю подпись (pending_signer_user_id),
            # больше не считается "просто" control, иначе он попадал бы
            # сразу в обе плитки статистики.
            'control': and_(Plan.is_control == True, Plan.pending_signer_user_id.is_(None)),
            'signing': Plan.pending_signer_user_id.isnot(None),
            'sent': Plan.is_sent == True,
            'sogl': Plan.is_sent == True,
            'error': Plan.is_error == True,
            'approved': Plan.is_approved == True
        }
        
        filtered_query = base_query
        
        if user.is_auditor and status_filter in ('sogl', 'sent', 'in_transit'):
            # Раньше "На рассмотрении"/"Согласованные" у проверяющего
            # сверялись по PlanApprovalPath.is_viewed БЕЗ учёта цикла
            # отправки — approval_paths больше не чистятся при пересылке
            # (см. cycle), поэтому брошенный непройденный этап из СТАРОГО
            # (отменённого) цикла попадал в выборку наравне с актуальным.
            # Берём все планы, где у организации вообще есть путь, и сами
            # разбираем по _latest_path_for_org/_is_queued_for_org — это
            # ещё и разделяет "ждёт именно вас" ('sent') от "ещё не дошёл
            # до вас по цепочке" ('in_transit', см. is_queued_for_viewer).
            candidates = filtered_query.filter(
                Plan.is_sent == True,
                PlanApprovalPath.organization_id.in_(auditor_org_ids),
            ).distinct().all()
            matching_ids = []
            for p in candidates:
                my_path = _latest_path_for_org(p, auditor_org_ids)
                if not my_path:
                    continue
                if status_filter == 'sogl':
                    if my_path.is_viewed:
                        matching_ids.append(p.id)
                elif not my_path.is_viewed:
                    if _is_queued_for_org(p, auditor_org_ids) == (status_filter == 'in_transit'):
                        matching_ids.append(p.id)
            filtered_query = Plan.query.filter(Plan.id.in_(matching_ids))
        elif status_filter != 'all' and status_filter in status_filters:
            filtered_query = filtered_query.filter(status_filters[status_filter])
        
        if year_filter != 'all':
            filtered_query = filtered_query.filter(Plan.year == int(year_filter))
        
        total_count = filtered_query.count()
        # current_app.logger.debug(f'total_count={total_count}')
        
        plans = filtered_query.order_by(Plan.begin_time.desc()).offset((page - 1) * per_page).limit(per_page).all()
        # current_app.logger.debug(f'plans count={len(plans)}')

        if user.is_auditor and auditor_org_ids:
            for plan in plans:
                plan.is_queued_for_viewer = _is_queued_for_org(plan, auditor_org_ids)
        else:
            for plan in plans:
                plan.is_queued_for_viewer = False

        count_query = base_query
        if year_filter != 'all':
            count_query = count_query.filter(Plan.year == int(year_filter))

        status_counts = {
            'all': count_query.count()
        }

        if user.is_auditor and auditor_org_ids:
            all_org_candidates = count_query.filter(
                Plan.is_sent == True,
                PlanApprovalPath.organization_id.in_(auditor_org_ids),
            ).distinct().all()

            status_counts['sent'] = 0
            status_counts['in_transit'] = 0
            status_counts['sogl'] = 0
            for p in all_org_candidates:
                my_path = _latest_path_for_org(p, auditor_org_ids)
                if not my_path:
                    continue
                if my_path.is_viewed:
                    status_counts['sogl'] += 1
                elif _is_queued_for_org(p, auditor_org_ids):
                    status_counts['in_transit'] += 1
                else:
                    status_counts['sent'] += 1

            status_counts['error'] = count_query.filter(Plan.is_error == True).distinct().count()
            status_counts['approved'] = count_query.filter(Plan.is_approved == True).distinct().count()
            status_counts['draft'] = 0
            status_counts['control'] = 0
        else:
            status_counts['draft'] = count_query.filter(Plan.is_draft == True).count()
            status_counts['control'] = count_query.filter(Plan.is_control == True, Plan.pending_signer_user_id.is_(None)).count()
            # "На подписании" — внутренний цикл подписания (см. Plan.pending_signer_user_id
            # в plan_bp.py :: submit_for_signature/internal_sign/internal_return) — план
            # ещё черновик (is_draft/is_control не менялись), но уже направлен руководителю.
            status_counts['signing'] = count_query.filter(Plan.pending_signer_user_id.isnot(None)).count()
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

        # Текст замечания, из-за которого план вернули на доработку, — это
        # обычное (не системное) сообщение, которое проверяющий написал ДО
        # нажатия "Есть ошибки" (см. has_pending_review_message/create_ticket).
        # Раньше "чьё это сообщение и к какому этапу относится" подбиралось
        # эвристикой (org_id + временное окно между отправками), что могло
        # ошибиться на организации с несколькими этапами в одном цикле —
        # теперь сообщение жёстко привязано к этапу по id
        # (PlanTicket.approval_path_id), однозначно. Подвешиваем найденное
        # на path (не персистится, только для рендера).
        for path in cycle_paths:
            remark_tickets = [
                t for t in plan.tickets
                if not t.is_system and t.approval_path_id == path.id
            ]
            path.remark_ticket = remark_tickets[-1] if remark_tickets else None

        # Снимок разработчика на момент ЭТОЙ конкретной отправки (см.
        # sender_* в handle_sent_status) — одинаков на всех строках цикла,
        # берём с первой. Для циклов, отправленных ДО появления этих полей
        # (sender_name там будет NULL), откатываемся на живые данные
        # plan.user — это лучше, чем показать пустую строку, но верно
        # только для старых, уже существовавших на момент миграции циклов.
        first_path = cycle_paths[0] if cycle_paths else None
        if first_path and first_path.sender_name:
            dev_post = first_path.sender_post
            dev_name = first_path.sender_name
            dev_phone = first_path.sender_phone
            dev_email = first_path.sender_email
        else:
            dev_post = plan.user.post if plan.user else None
            dev_name = (' '.join(filter(None, [plan.user.last_name, plan.user.first_name, plan.user.patronymic_name]))
                        if plan.user else None)
            dev_phone = plan.user.telephone if plan.user else None
            dev_email = plan.user.email if plan.user else None

        cycles.append({
            'cycle': cycle_num,
            'sent_at': sent_at,
            'paths': cycle_paths,
            'cancel_ticket': cancel_ticket,
            'is_latest': idx == len(cycle_numbers) - 1,
            'dev_post': dev_post,
            'dev_name': dev_name,
            'dev_phone': dev_phone,
            'dev_email': dev_email,
        })

    return cycles


def build_signature_print_rows(plan, cycles):
    """Та же таблица, что в "Подписи" (plan_signatures_page, components.html),
    но в виде плоского списка строк для печати (см. print_signatures в
    audit_bp.py) — колонки и статусная логика продублированы сознательно и
    ограниченно, по тому же принципу, что print_tickets уже дублирует
    tickets_container для печати сообщений.

    Возвращает список кортежей:
      ('header', текст) — строка на всю ширину (разработчик плана / отмена
                           отправки), печатается объединённой ячейкой;
      ('data', [тип, организация, должность/ФИО/телефон, статус, дата,
                замечания]) — обычная строка таблицы.
    """
    latest = cycles[-1] if cycles else None
    latest_paths = latest['paths'] if latest else []
    first_unviewed = next((p for p in latest_paths if not p.is_viewed), None)

    rows = []
    for cycle in cycles:
        dev_line = (
            f"Разработчик плана: {cycle['dev_name']}, тел.: {cycle['dev_phone'] or '—'}, email: {cycle['dev_email'] or '—'}"
            if cycle['dev_name'] else 'Разработчик плана: —'
        )
        rows.append(('header', dev_line))

        rows.append(('data', [
            'Направление плана',
            plan.organization.full_name if plan.organization else '—',
            f"{cycle['dev_post'] or '—'}, {cycle['dev_name']}" if cycle['dev_name'] else '—',
            'Направлен',
            cycle['sent_at'].strftime('%d.%m.%Y') if cycle['sent_at'] else '—',
            '—',
        ]))

        for path in cycle['paths']:
            is_active = cycle['is_latest'] and path == first_unviewed
            is_rejected_step = bool(path.rejected_at) and not path.is_viewed
            is_abandoned = (not cycle['is_latest']) and not path.is_viewed and not is_rejected_step
            action_label = 'Утверждение' if path.step_type == 'approver' else 'Согласование'
            done_label = 'Утверждено' if (path.step_type == 'approver' and path.is_viewed) else 'Согласовано'

            if path.is_viewed:
                status = done_label
            elif is_abandoned:
                status = 'Не пройдено'
            elif is_rejected_step:
                status = 'Есть ошибки'
            elif is_active:
                status = 'На подписании' if path.pending_signer_user_id else 'На рассмотрении'
            else:
                status = 'Ожидание очереди'

            if path.is_viewed and path.viewed_by_snapshot:
                position = path.viewed_by_snapshot
            elif is_rejected_step and path.rejected_by_snapshot:
                position = path.rejected_by_snapshot
            else:
                position = '—'

            if path.is_viewed and path.viewed_at:
                date_str = path.viewed_at.strftime('%d.%m.%Y')
            elif is_rejected_step and path.rejected_at:
                date_str = path.rejected_at.strftime('%d.%m.%Y')
            else:
                date_str = '—'

            if path.remark:
                remark = path.remark
            elif is_rejected_step and path.remark_ticket:
                remark = path.remark_ticket.note
            else:
                remark = '—'

            rows.append(('data', [
                action_label,
                path.organization.full_name if path.organization else '—',
                position,
                status,
                date_str,
                remark,
            ]))

        cancel_ticket = cycle.get('cancel_ticket')
        if cancel_ticket:
            name = ''
            if cancel_ticket.user:
                name = f" — {cancel_ticket.user.last_name} {cancel_ticket.user.first_name} {cancel_ticket.user.patronymic_name or ''}"
            date_part = f", {cancel_ticket.begin_time.strftime('%d.%m.%Y')}" if cancel_ticket.begin_time else ''
            rows.append(('header', f"{cancel_ticket.note}{name}{date_part}"))

    return rows


def _latest_path_for_org(plan, org_ids):
    """Этап согласования ОДНОЙ из организаций org_ids в ПОСЛЕДНЕМ цикле
    отправки плана (approval_paths больше не чистятся при пересылке — см.
    PlanApprovalPath.cycle, — поэтому у организации может быть ещё и
    брошенный этап из старого цикла, который для статуса "не в счёт").
    None, если план не отправлен или этой организации в цепочке нет."""
    if not plan.approval_paths:
        return None
    latest_cycle = max(p.cycle for p in plan.approval_paths)
    return next(
        (p for p in plan.approval_paths if p.cycle == latest_cycle and p.organization_id in org_ids),
        None,
    )


def _is_queued_for_org(plan, org_ids):
    """True, если план отправлен, но ещё НЕ дошёл до одной из организаций
    в org_ids — т.е. в последнем цикле её этап не пройден (is_viewed=False),
    но перед ним по порядку (step_order) есть ещё не пройденный этап другой
    организации. Используется для отдельного фильтра "Ожидание очереди" на /plans —
    такие планы видны проверяющему в списке (для осведомлённости), но
    открыть их нельзя (см. is_queued_for_viewer/plans_list_items), в отличие
    от этапа, до которого очередь уже дошла по-настоящему."""
    my_path = _latest_path_for_org(plan, org_ids)
    if not my_path or my_path.is_viewed:
        return False
    latest_paths = [p for p in plan.approval_paths if p.cycle == my_path.cycle]
    return any(p.step_order < my_path.step_order and not p.is_viewed for p in latest_paths)


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
    """Весь контекст, нужный вкладке «Действия с планом» (plan_actions.html): какой
    этап сейчас "ваш", можно ли писать/менять статус/отменять изменения,
    оставил ли проверяющий уже сообщение по этому этапу, и как подписать
    кнопку подтверждения («Одобрить» на последнем этапе, иначе
    «Согласовать»). Централизовано здесь вместо повторения этой логики
    прямо в шаблоне — там было легко забыть ограничить запрос последним
    циклом отправки (approval_paths больше не чистятся при пересылке)."""
    current_path = get_current_review_path(plan, current_user)
    # plan.is_sent — иначе если разработчик поправил план (план вернулся в
    # "В редакции", is_error сброшен), а заново ещё не отправил, непройденный
    # approval_path с прошлой отправки остаётся в базе и без этой проверки
    # проверяющий продолжал бы видеть этап как "свой"/действующий прямо
    # сейчас — хотя план фактически снова у разработчика, а не у него.
    #
    # Дополнительное ограничение (внутренний цикл подписания РЕШЕНИЯ этапа,
    # "Шаг 2"): пока решение уже направлено на подпись руководителю
    # (current_path.pending_signer_user_id) — этап read-only для всех
    # остальных сотрудников организации, как план read-only для организации-
    # разработчика между "Отправить на подпись" и подписью ("Шаг 1").
    #
    # org_role НЕ ограничивает, кто может вынести решение (в отличие от
    # create_plan, где org_head не создаёт планы) — у многих согласующих/
    # утверждающих организаций исторически всего один аккаунт, бэкфилленный
    # в org_head (см. миграцию f4a5b6c7d8e9); запрет оставил бы их без
    # возможности вообще рассматривать планы. org_role важен только для
    # того, КОМУ можно направить решение на подпись (get_signer_candidates —
    # dept_head/org_head) и для Варианта Б (пересылка от dept_head к
    # org_head) — см. plan_bp.py.
    can_audit = (
        bool(current_path) and plan.is_sent and not plan.is_approved and not plan.is_error
        and not current_path.pending_signer_user_id
    )

    approve_label = 'Согласовать'
    if current_path:
        current_cycle_paths = [p for p in plan.approval_paths if p.cycle == current_path.cycle]
        max_step = max((p.step_order for p in current_cycle_paths), default=current_path.step_order)
        if current_path.step_order == max_step:
            approve_label = 'Одобрить'

    # Раньше при current_path is None (обычный случай сразу после того, как
    # организация подтвердила СВОЙ этап — "текущим" становится этап
    # СЛЕДУЮЩЕЙ организации, не её) ограничение по циклу полностью
    # пропадало — user_has_viewed_current сканировал approval_paths ВСЕХ
    # циклов подряд. На планах с несколькими циклами (после отклонения и
    # повторной отправки) это могло найти подтверждённый этап организации
    # из СТАРОГО цикла и ошибочно разрешить/запретить отмену не по тому
    # этапу. Цикл для сравнения берём последний всегда, а не только когда
    # current_path есть.
    latest_cycle = max((p.cycle for p in plan.approval_paths), default=None)
    cycle_paths = [p for p in plan.approval_paths if latest_cycle is None or p.cycle == latest_cycle]

    own_cycle_paths = [p for p in cycle_paths if p.organization_id == current_user.organization_id]
    own_confirmed = [p for p in own_cycle_paths if p.is_viewed]
    own_rejected = [p for p in own_cycle_paths if p.rejected_at]
    user_has_viewed_current = bool(own_confirmed) or bool(own_rejected)

    # Раньше "следующий этап уже подтверждён — отменить нельзя" проверялся
    # через next_path, который считался ТОЛЬКО когда current_path есть —
    # а current_path как раз всегда None сразу после того, как организация
    # подтвердила/отклонила СВОЙ этап (см. выше), то есть ИМЕННО в тот
    # момент, когда организация пытается отменить своё решение. Из-за
    # этого проверка следующего этапа фактически никогда не срабатывала:
    # первый проверяющий мог отменить своё "Согласовано" даже после того,
    # как второй уже подтвердил свой этап поверх него — цепочка
    # согласования теряла целостность (второй этап остаётся "подтверждён",
    # хотя этап, от которого он зависел, снова не пройден).
    #
    # Правильная проверка — по шагам ПОСЛЕ последнего шага ЭТОЙ организации
    # в текущем цикле: если там уже есть подтверждённый ИЛИ отклонённый
    # этап, отменять свой — нельзя.
    blocked_by_later_step = False
    if user_has_viewed_current:
        own_last_step_order = max(
            (p.step_order for p in own_confirmed + own_rejected), default=None
        )
        if own_last_step_order is not None:
            blocked_by_later_step = any(
                p.step_order > own_last_step_order and (p.is_viewed or p.rejected_at)
                for p in cycle_paths
            )

    can_cancel = user_has_viewed_current and not blocked_by_later_step

    has_remarks = has_pending_review_message(plan, current_user) if can_audit else False

    return {
        'current_path': current_path,
        'can_audit': can_audit,
        'can_cancel': can_cancel,
        'has_remarks': has_remarks,
        'approve_label': approve_label,
        'step_pending_signer_id': current_path.pending_signer_user_id if current_path else None,
        'step_is_signed': current_path.is_signed if current_path else False,
        'step_submitted_by_id': current_path.submitted_by_user_id if current_path else None,
        'step_pending_decision': current_path.pending_decision if current_path else None,
    }


def get_last_internal_return_ticket(plan):
    """Причина последнего [Вернуть на внутреннюю доработку] ("Шаг 1" —
    руководитель вернул план отправившему, не дойдя до реальной внешней
    отправки) — обычное сообщение в чате (см. internal_return в
    plan_bp.py), без approval_path_id (на этом этапе цикла ещё нет ни
    одного PlanApprovalPath). "Свежее" — позже последней РЕАЛЬНОЙ отправки
    (plan.sent_time обновляется только в handle_sent_status), иначе после
    следующей успешной отправки старая причина продолжала бы висеть.
    Используется и баннером на "Действиях с планом", и первой строкой
    "Подписи" до момента реальной отправки (см. plan_signatures_page)."""
    if plan.pending_signer_user_id:
        return None
    candidate_ticket = PlanTicket.query.filter_by(
        plan_id=plan.id, is_system=False, approval_path_id=None
    ).order_by(PlanTicket.begin_time.desc()).first()
    if candidate_ticket and (not plan.sent_time or candidate_ticket.begin_time > plan.sent_time):
        return candidate_ticket
    return None


def build_approval_chain(plan, coordinator_ids=None, approver_id=None):
    """Строит упорядоченный список (step_type, organization) для маршрута
    внешнего согласования плана: региональное управление (всегда первым) +
    выбранные согласующие + Департамент по энергоэффективности (если
    суммарное потребление ТЭР — показатель 260, колонка за год плана — от
    25000 т.у.т. включительно) + выбранный утверждающий. Департамент
    вставляется ПРЕДПОСЛЕДНИМ — непосредственно перед утверждающим, если
    он выбран, иначе (при отсутствии утверждающего) оказывается просто
    последним шагом маршрута. Используется и для реального создания
    PlanApprovalPath (handle_sent_status), и для предварительного показа
    маршрута до отправки (вкладка "Подписи" сразу после
    submit_for_signature) — поэтому не создаёт никаких записей в БД сам,
    только читает справочники.

    Если coordinator_ids/approver_id не переданы явно — берутся из
    plan.pending_coordinator_ids/plan.pending_approver_id (маршрут,
    сохранённый на шаге внутренней отправки на подпись)."""
    chain = []

    if not plan.organization or not plan.organization.region_id:
        return chain

    region_org = Organization.query.filter(
        Organization.is_region_management == True,
        Organization.region_id == plan.organization.region_id
    ).first()
    if region_org:
        chain.append(('region', region_org))

    if not coordinator_ids and plan.pending_coordinator_ids:
        coordinator_ids = plan.pending_coordinator_ids.split(',')
    if not approver_id and plan.pending_approver_id:
        approver_id = plan.pending_approver_id

    for coord_id in (coordinator_ids or []):
        if coord_id and str(coord_id).strip():
            coord_org = Organization.query.get(int(str(coord_id).strip()))
            if coord_org:
                chain.append(('coordinator', coord_org))

    indicator_260_usage = next(
        (u for u in plan.indicators_usage if u.indicator.code == '260'), None
    )
    total_consumption = indicator_260_usage.QYearCurrent if indicator_260_usage and indicator_260_usage.QYearCurrent is not None else 0
    if total_consumption >= 25000:
        energy_dept_org = Organization.query.filter_by(is_energy_department=True).first()
        if energy_dept_org:
            chain.append(('approver', energy_dept_org))

    if approver_id:
        approver_org = Organization.query.get(int(approver_id))
        if approver_org:
            chain.append(('approver', approver_org))

    return chain


def create_plan_snapshot(plan):
    """Замораживает точную копию плана "как есть" отдельной строкой Plan —
    вызывается из handle_error_status (status_plan.py) СРАЗУ после того,
    как план помечен is_error, пока его содержимое ещё гарантированно
    совпадает с тем, что увидел и отклонил проверяющий (следующая же
    правка через update_ChangeTimePlan сбросит is_error на живой строке).

    Снимок — полноценная независимая строка Plan со своим token (не
    передаём — генерируется автоматически), связанная с живым планом
    через snapshot_of_plan_id. Копируются только содержательные данные
    (сам план + IndicatorUsage/Event/PlanColumnConfig, включая файлы ТЭО
    на диске — см. copy_teo_file); PlanApprovalPath/PlanTicket/Notification
    НЕ копируются — это история согласования/переписки конкретной
    попытки отправки, она и так остаётся на живой строке (как cycle уже
    хранит историю прошлых циклов отправки). Поля внутреннего цикла
    подписания тоже не копируются — у снимка их не может быть, он
    никуда больше не отправляется."""
    from website.utils.teo import copy_teo_file

    now = current_utc_time()

    snapshot = Plan(
        year=plan.year,
        begin_time=plan.begin_time,
        change_time=now,
        energy_saving=plan.energy_saving,
        share_fuel=plan.share_fuel,
        saving_fuel=plan.saving_fuel,
        share_energy=plan.share_energy,
        usd_rate=plan.usd_rate,
        cost_per_toe_usd=plan.cost_per_toe_usd,
        is_draft=False,
        is_control=False,
        is_sent=False,
        is_error=True,
        is_approved=False,
        plan_type=plan.plan_type,
        user_id=plan.user_id,
        developer_name=plan.developer_name,
        developer_phone=plan.developer_phone,
        developer_email=plan.developer_email,
        org_id=plan.org_id,
        snapshot_of_plan_id=plan.id,
        snapshot_at=now,
    )
    db.session.add(snapshot)
    db.session.flush()  # нужен snapshot.id для дочерних строк ниже

    for usage in plan.indicators_usage:
        db.session.add(IndicatorUsage(
            id_indicator=usage.id_indicator,
            note=usage.note,
            id_plan=snapshot.id,
            QYearBeforePrev=usage.QYearBeforePrev,
            QYearPrev=usage.QYearPrev,
            QYearCurrent=usage.QYearCurrent,
            is_local=usage.is_local,
            is_renewable=usage.is_renewable,
            coeff_before_prev=usage.coeff_before_prev,
            coeff_prev=usage.coeff_prev,
            coeff_current=usage.coeff_current,
        ))

    for ev in plan.events:
        copied_teo_filename = copy_teo_file(ev.teo_filename) if ev.teo_filename else None
        db.session.add(Event(
            id_direction=ev.id_direction,
            id_plan=snapshot.id,
            name=ev.name,
            display_code=ev.display_code,
            Volume=ev.Volume,
            EffTut=ev.EffTut,
            EffRub=ev.EffRub,
            ExpectedQuarter=ev.ExpectedQuarter,
            EffCurrYear=ev.EffCurrYear,
            Payback=ev.Payback,
            ObchVolumeFin=ev.ObchVolumeFin,
            VolumeFinCurrentYear=ev.VolumeFinCurrentYear,
            BudgetState=ev.BudgetState,
            BudgetRep=ev.BudgetRep,
            BudgetLoc=ev.BudgetLoc,
            BudgetOther=ev.BudgetOther,
            MoneyOwn=ev.MoneyOwn,
            MoneyLoan=ev.MoneyLoan,
            MoneyOther=ev.MoneyOther,
            is_local=ev.is_local,
            is_corrected=ev.is_corrected,
            is_econom=ev.is_econom,
            is_increase=ev.is_increase,
            teo_filename=copied_teo_filename,
            teo_original_name=ev.teo_original_name if copied_teo_filename else None,
            teo_uploaded_at=ev.teo_uploaded_at if copied_teo_filename else None,
            order=ev.order,
        ))

    for cfg in plan.column_configs:
        db.session.add(PlanColumnConfig(
            plan_id=snapshot.id,
            year=cfg.year,
            label=cfg.label,
        ))

    db.session.commit()
    return snapshot


def get_plan_versions(plan):
    """Живой план + все его замороженные снимки (см. create_plan_snapshot
    выше), живой всегда первым, снимки — от новых к старым. Работает и
    когда переданный plan сам уже снимок (резолвит через snapshot_of).
    Используется component.plan_version_switcher (macros/components.html,
    зарегистрирован как Jinja global в website/__init__.py, поэтому
    макросу не нужно получать этот список параметром из каждого роута)."""
    live_plan = plan.snapshot_of if plan.is_historical else plan
    snapshots = Plan.query.filter_by(snapshot_of_plan_id=live_plan.id).order_by(Plan.snapshot_at.desc()).all()
    return [live_plan] + snapshots


def build_signer_snapshot(user):
    """Текстовый снимок "должность, ФИО, тел.: ..." пользователя на МОМЕНТ
    подписи — сохраняется строкой в PlanApprovalPath (viewed_by_snapshot/
    rejected_by_snapshot), а не связью на User: должность/ФИО/телефон
    проверяющего могут со временем измениться, а "Подписи" должны навсегда
    показывать, кем, с какой должностью и по какому телефону план был
    согласован/отклонён именно тогда, а не как выглядит профиль сейчас."""
    if not user:
        return None
    name = ' '.join(filter(None, [user.last_name, user.first_name, user.patronymic_name]))
    parts = [p for p in [user.post, name] if p]
    if user.telephone:
        parts.append(f"тел.: {user.telephone}")
    return ', '.join(parts) if parts else None


def get_signer_candidates(org_id, approver_only=False):
    """Сотрудники организации — кандидаты на подпись: обычно «Руководитель
    структурного подразделения»/«Руководитель организации» (используется и
    при первичной отправке плана — plan_send_page, — и на "Шаге 2" при
    направлении решения этапа согласования на подпись). approver_only=True
    (этап step_type='approver' — организация выступает именно утверждающей,
    см. PlanApprovalPath.STEP_TYPES) сужает список до одного org_head:
    утверждать план может только руководитель организации, в отличие от
    подписания/согласования/отправки, доступных и руководителю структурного
    подразделения."""
    roles = ['org_head'] if approver_only else ['dept_head', 'org_head']
    return User.query.filter(
        User.organization_id == org_id,
        User.org_role.in_(roles)
    ).order_by(User.org_role.desc()).all()


def has_pending_review_attachment(plan, current_user):
    """Как has_pending_review_message, но проверяет, что у ПОСЛЕДНЕГО
    своего сообщения по текущему этапу есть вложение — "Не согласовать и
    направить на подпись" требует приложенный файл с замечаниями (см.
    "Шаг 2" внутреннего подписания), в отличие от обычного сообщения в
    чате, где вложение было и остаётся необязательным."""
    current_path = get_current_review_path(plan, current_user)
    if not current_path:
        return False
    own_tickets = [
        t for t in plan.tickets
        if not t.is_system and t.user_id == current_user.id and t.approval_path_id == current_path.id
    ]
    if not own_tickets:
        return False
    last_ticket = max(own_tickets, key=lambda t: t.begin_time or current_utc_time())
    return bool(last_ticket.attachment_filename)


def has_pending_review_message(plan, current_user):
    """Заменяет флаг Plan.afch: вместо хранимого булева (который раньше
    нужно было вручную сбрасывать — и это легко забыть/разъехаться с
    реальностью) каждый раз живым запросом проверяем, оставил ли ИМЕННО
    ТЕКУЩИЙ проверяющий (current_user) хотя бы одно своё (не системное)
    сообщение по ТЕКУЩЕМУ этапу последнего цикла. Раньше "своё" сообщение
    по этапу определялось эвристикой (не системное + begin_time не раньше
    created_at этапа) — теперь сообщение жёстко привязано к этапу по id
    (PlanTicket.approval_path_id, см. audit_bp.create_ticket), так что
    проверка — точное совпадение, без временных окон и догадок."""
    current_path = get_current_review_path(plan, current_user)
    if not current_path:
        return False
    for ticket in plan.tickets:
        if ticket.is_system or ticket.user_id != current_user.id:
            continue
        if ticket.approval_path_id == current_path.id:
            return True
    return False