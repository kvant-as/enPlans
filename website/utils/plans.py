from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from venv import logger

from flask_login import current_user

from .. import db
from ..models import Direction, Organization, Plan, PlanColumnConfig, PlanExecutor, PlanTicket, Indicator, Event, IndicatorUsage, Notification, PlanApprovalPath, User

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


def ensure_column_configs(plan):
    """Гарантирует 3 строки PlanColumnConfig (year-2/year-1/year) у плана
    — обычно их создаёт create_plan (views.py) сразу при заведении плана,
    но для планов, где по какой-то причине они не создались (например,
    из тестовых/служебных путей в обход обычного флоу), шаблон
    plan_indicators.html обращается к ним напрямую по индексу
    (configs[0]/[1]/[2]) и падает UndefinedError на пустом/неполном
    списке — подчищаем недостающие годы при каждом заходе на страницу,
    без дублирования уже существующих."""
    existing_years = {c.year for c in plan.column_configs}
    missing = [c for c in get_column_configs_for_plan(plan) if c.year not in existing_years]
    if missing:
        db.session.add_all(missing)
        db.session.commit()

def update_ChangeTimePlan(id):
    plan = Plan.query.filter_by(id=id).first()
    if not plan:
        return

    plan.change_time = current_utc_time()
    plan.is_draft = True
    plan.is_control = False
    plan.is_sent = False
    plan.is_error = False
    plan.is_approved = False

    plan.afch = False

    db.session.commit()

PLAN_EDIT_ROLE_DENIED = 'Редактировать содержимое плана может только исполнитель или руководитель структурного подразделения организации-разработчика'


def plan_edit_lock_reason(plan):
    """Почему содержимое плана сейчас заблокировано для ЛЮБОГО сотрудника
    организации-разработчика — или None, если не заблокировано.

    ТЗ п.3.3: пока план у подписанта (pending_signer_user_id), он
    заблокирован для всех; п.3.4: после отправки (is_sent) — тоже; после
    утверждения — тем более. Раньше это держалось только на disabled в
    шаблонах, а сервер принимал правку — и update_ChangeTimePlan тут же
    сбрасывал is_sent/is_control, молча выдёргивая план из маршрута
    согласования (или из-под подписанта)."""
    if plan.is_historical:
        return 'Это архивная версия плана — только для просмотра'
    if plan.is_approved:
        return 'План утверждён — его содержимое больше нельзя изменить'
    if plan.is_sent:
        return 'План отправлен на согласование — его содержимое заблокировано'
    if plan.pending_signer_user_id:
        return 'План направлен на подпись — его содержимое заблокировано до подписи или возврата на доработку'
    return None


def plan_edit_denial(user, plan):
    """Текст отказа в правке содержимого плана или None, если правка
    разрешена (см. can_edit_plan_data)."""
    if not (
        user.organization_id == plan.org_id
        and user.org_role in ('executor', 'dept_head')
        and user.organization and user.organization.is_regular
    ):
        return PLAN_EDIT_ROLE_DENIED
    return plan_edit_lock_reason(plan)


def can_edit_plan_data(user, plan):
    """Создавать план и заполнять его содержимое (показатели, мероприятия,
    метаданные) может только сотрудник ОБЫЧНОЙ организации-разработчика
    (Organization.is_regular — не только согласующей/утверждающей, см.
    get_filtered_plans/Вариант А ТЗ п.5) с ролью executor или dept_head, и
    только для плана СВОЕЙ организации. org_head/org_head_deputy этим не
    занимаются (is_org_manager — они подписывают/утверждают).

    Плюс сам план должен быть в редактируемом состоянии — не у подписанта,
    не отправлен, не утверждён (см. plan_edit_lock_reason)."""
    return plan_edit_denial(user, plan) is None


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

    if current_user.has_auditor_access and okpo_digit == "8":
        return Plan.query.filter(status_filter).order_by(Plan.year.asc())

    return Plan.query.join(Organization).filter(
        status_filter,
        func.substr(Organization.okpo, func.length(Organization.okpo) - 3, 1) == okpo_digit
    ).order_by(Plan.year.asc())

def _own_awaiting_approval(plan, org_id):
    """Свой план организации дошёл до этапа утверждения В НЕЙ ЖЕ (ТЗ п.5,
    Вариант А): отправлен, текущий (первый непройденный в последнем
    цикле) внешний этап — 'approver' этой организации. Для руководителя
    организации такой план — «На рассмотрении» (утверждает он), для
    остальных сотрудников — «На согласовании» (см. status_plan)."""
    if not plan.is_sent or plan.org_id != org_id:
        return False
    external = [p for p in plan.approval_paths if not p.is_internal]
    if not external:
        return False
    latest = max(p.cycle for p in external)
    current = next((p for p in sorted(external, key=lambda p: p.step_order)
                    if p.cycle == latest and not p.is_viewed), None)
    return bool(current and current.step_type == 'approver' and current.organization_id == org_id)


def get_filtered_plans(user, status_filter="all", year_filter="all", search_name="", search_ynp="", region_id=None, search_approver_org="", page=1, per_page=5):
    try:
        # current_app.logger.debug(f'get_filtered_plans called with region_id={region_id}')
        is_hybrid_org = False
        is_reviewer_only = False
        auditor_org_ids = []

        if user.has_auditor_access or user.has_approver_access:
            # has_approver_access (утверждающая организация) — та же
            # механика, что и у has_auditor_access (согласующая): список
            # планов по собственным этапам в PlanApprovalPath, а не по
            # org_id (который у организации-рецензента никогда не
            # совпадёт с org_id плана).
            auditor_org_ids = []
            if user.organization_id:
                auditor_org_ids.append(user.organization_id)

            if hasattr(user, 'organizations') and user.organizations:
                auditor_org_ids.extend([org.id for org in user.organizations])

            # ТЗ п.5, Вариант А: организация может ОДНОВРЕМЕННО быть
            # обычной (is_regular — готовит свои планы) и согласующей/
            # утверждающей для чужих. INNER JOIN по PlanApprovalPath ниже
            # отфильтровал бы собственные (ещё не отправленные/без единого
            # этапа) планы такой организации полностью — объединяем через
            # OUTER JOIN с условием "или наша организация — автор плана".
            is_hybrid_org = bool(user.organization and user.organization.is_regular)
            # Вкладки статуса ("На рассмотрении"/"Ожидание очереди" у
            # чисто проверяющей организации, или "В редакции"/"На
            # подписании"/"На согласовании" у is_regular, включая
            # гибридную) должны совпадать с тем, что показывает шаблон
            # (plan_count/plans.html) — там решает тот же is_regular.
            is_reviewer_only = not is_hybrid_org

            if not auditor_org_ids:
                base_query = Plan.query.filter(False)
            else:
                reviewer_condition = db.and_(
                    PlanApprovalPath.organization_id.in_(auditor_org_ids),
                    db.or_(
                        Plan.is_sent == True,
                        Plan.is_error == True,
                        Plan.is_approved == True
                    )
                )
                if is_hybrid_org:
                    own_condition = Plan.org_id == user.organization_id
                    base_query = Plan.query.outerjoin(PlanApprovalPath, Plan.id == PlanApprovalPath.plan_id)\
                        .filter(db.or_(reviewer_condition, own_condition))\
                        .distinct()
                else:
                    base_query = Plan.query.join(PlanApprovalPath, Plan.id == PlanApprovalPath.plan_id)\
                        .filter(reviewer_condition)\
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

        # Руководитель гибридной организации (сама разрабатывает и
        # утверждает) — свои планы на ЕГО утверждении показываем как «На
        # рассмотрении» (см. _own_awaiting_approval).
        manager_reviews_own = bool(is_hybrid_org and auditor_org_ids and getattr(user, 'is_org_manager', False))

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
        
        if is_reviewer_only and status_filter in ('sogl', 'sent', 'in_transit'):
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
        elif is_hybrid_org and auditor_org_ids and status_filter in ('in_transit', 'review', 'sogl'):
            # Гибридная организация (сама разработчик И проверяющая, ТЗ п.5
            # Вариант А): кроме вкладок своих планов — вкладки про ЧУЖИЕ
            # планы в её маршруте: 'in_transit' («В ожидании», очередь не
            # дошла), 'review' («На рассмотрении», дошла, ждёт её решения),
            # 'sogl' («Согласованные» — только у согласующей: уже согласовала,
            # план идёт дальше). Своя 'sent' («На согласовании») — только про
            # свои планы, поэтому отдельное значение 'review'.
            candidates = filtered_query.filter(
                Plan.is_sent == True,
                Plan.org_id != user.organization_id,
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
                elif not my_path.is_viewed and _is_queued_for_org(p, auditor_org_ids) == (status_filter == 'in_transit'):
                    matching_ids.append(p.id)
            # Руководителю «На рассмотрении» — ещё и свои планы, ждущие его
            # утверждения (Вариант А).
            if status_filter == 'review' and manager_reviews_own:
                own_sent = filtered_query.filter(Plan.is_sent == True, Plan.org_id == user.organization_id).distinct().all()
                matching_ids += [p.id for p in own_sent if _own_awaiting_approval(p, user.organization_id)]
            filtered_query = Plan.query.filter(Plan.id.in_(matching_ids))
        elif status_filter != 'all' and status_filter in status_filters:
            filtered_query = filtered_query.filter(status_filters[status_filter])
            if is_hybrid_org:
                # У гибридной организации base_query объединяет (через OR)
                # и её собственные планы, и чужие планы в её маршруте.
                # «В редакции»/«Контроль»/«На подписании»/«На согласовании» —
                # только СВОИ (у чужих этих статусов для неё нет). «Есть
                # ошибки»/«Утвержденные» — итог: свои И чужие, в маршруте
                # которых она есть, — как у чисто проверяющей организации
                # (иначе утверждённый ею чужой план не попадал ни в одну
                # вкладку, кроме «Все»).
                if status_filter in ('error', 'approved') and auditor_org_ids:
                    filtered_query = filtered_query.filter(db.or_(
                        Plan.org_id == user.organization_id,
                        PlanApprovalPath.organization_id.in_(auditor_org_ids),
                    )).distinct()
                else:
                    filtered_query = filtered_query.filter(Plan.org_id == user.organization_id)
                    # у руководителя свой план на его утверждении — во
                    # «На рассмотрении», а не в «На согласовании»
                    if status_filter == 'sent' and manager_reviews_own:
                        own_ids = [p.id for p in filtered_query.distinct().all()
                                   if _own_awaiting_approval(p, user.organization_id)]
                        if own_ids:
                            filtered_query = filtered_query.filter(~Plan.id.in_(own_ids))

        if year_filter != 'all':
            filtered_query = filtered_query.filter(Plan.year == int(year_filter))
        
        total_count = filtered_query.count()
        # current_app.logger.debug(f'total_count={total_count}')
        
        plans = filtered_query.order_by(Plan.begin_time.desc()).offset((page - 1) * per_page).limit(per_page).all()
        # current_app.logger.debug(f'plans count={len(plans)}')

        # «В ожидании» (очередь до организации ещё не дошла) — для любой
        # проверяющей организации, в т.ч. гибридной (она же разработчик, ТЗ
        # п.5 Вариант А): раньше флаг ставился только чисто проверяющим, и
        # гибридная видела чужой план «На рассмотрении», хотя он ещё у
        # предыдущей организации. Свои планы — не очередь.
        for plan in plans:
            plan.is_queued_for_viewer = bool(
                auditor_org_ids
                and plan.org_id != user.organization_id
                and _is_queued_for_org(plan, auditor_org_ids)
            )

        count_query = base_query
        if year_filter != 'all':
            count_query = count_query.filter(Plan.year == int(year_filter))

        status_counts = {
            'all': count_query.count()
        }

        if is_reviewer_only and auditor_org_ids:
            # Организация ТОЛЬКО согласует/утверждает чужие планы (не
            # is_regular) — вкладки про очередь на рассмотрение, не про
            # жизненный цикл своего плана (его у неё просто нет).
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
            # is_regular (в т.ч. гибридная согласующая/утверждающая, ТЗ
            # п.5 Вариант А) — вкладки про СВОИ планы (В редакции/На
            # подписании/На согласовании/...), как у обычной организации.
            # У гибридной count_query (= base_query) через OR включает ещё
            # и чужие планы в очереди на рассмотрение — сужаем явно по
            # org_id, иначе они задвоили бы "На согласовании"/"Есть
            # ошибки"/"Утверждённые" (is_sent/is_error/is_approved такие
            # же и у плана, который просто ждёт нашего решения).
            own_count_query = count_query.filter(Plan.org_id == user.organization_id) if is_hybrid_org else count_query
            status_counts['draft'] = own_count_query.filter(Plan.is_draft == True).count()
            status_counts['control'] = own_count_query.filter(Plan.is_control == True, Plan.pending_signer_user_id.is_(None)).count()
            # "На подписании" — внутренний цикл подписания (см. Plan.pending_signer_user_id
            # в plan_bp.py :: submit_for_signature/internal_sign/internal_return) — план
            # ещё черновик (is_draft/is_control не менялись), но уже направлен руководителю.
            status_counts['signing'] = own_count_query.filter(Plan.pending_signer_user_id.isnot(None)).count()
            status_counts['sent'] = own_count_query.filter(Plan.is_sent == True).count()
            status_counts['error'] = own_count_query.filter(Plan.is_error == True).count()
            status_counts['approved'] = own_count_query.filter(Plan.is_approved == True).count()

            # Гибридная — ещё счётчики чужих планов в её маршруте (вкладки
            # «В ожидании»/«На рассмотрении»/«Согласованные», см. фильтр
            # выше), а «Есть ошибки»/«Утвержденные» — свои И чужие.
            if is_hybrid_org and auditor_org_ids:
                in_route = db.or_(
                    Plan.org_id == user.organization_id,
                    PlanApprovalPath.organization_id.in_(auditor_org_ids),
                )
                status_counts['error'] = count_query.filter(Plan.is_error == True, in_route).distinct().count()
                status_counts['approved'] = count_query.filter(Plan.is_approved == True, in_route).distinct().count()

                status_counts['in_transit'] = 0
                status_counts['review'] = 0
                status_counts['sogl'] = 0
                foreign = count_query.filter(
                    Plan.is_sent == True,
                    Plan.org_id != user.organization_id,
                    PlanApprovalPath.organization_id.in_(auditor_org_ids),
                ).distinct().all()
                for p in foreign:
                    my_path = _latest_path_for_org(p, auditor_org_ids)
                    if not my_path:
                        continue
                    if my_path.is_viewed:
                        status_counts['sogl'] += 1
                    elif _is_queued_for_org(p, auditor_org_ids):
                        status_counts['in_transit'] += 1
                    else:
                        status_counts['review'] += 1

                # руководителю свои планы на его утверждении — из «На
                # согласовании» в «На рассмотрении»
                if manager_reviews_own:
                    own_waiting = sum(
                        1 for p in own_count_query.filter(Plan.is_sent == True).all()
                        if _own_awaiting_approval(p, user.organization_id)
                    )
                    status_counts['sent'] -= own_waiting
                    status_counts['review'] += own_waiting
        
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

def validate_period_values(plan_id, current_period_code, current_value, exclude_event_id=None, is_increase=None):
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

    # Периоды части 2 (экономия) и части 3 (увеличение) — разные строки с
    # ОДИНАКОВЫМИ кодами 0001-0004: без этого фильтра значения двух частей
    # перемешивались в один словарь по коду (какая строка последней, та и
    # побеждала). Сверяем только внутри своей части.
    if is_increase is not None:
        period_events = period_events.filter(Event.is_increase == bool(is_increase))

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
        # Заполнение — строго по нарастающей: нельзя обнулить период, пока
        # следующий за ним уже заполнен (иначе следующий оказался бы
        # заполненным "раньше" своего предшественника).
        if current_value_num == 0 and next_value:
            return 'Нельзя обнулить "{}", пока заполнен "{}" — сначала обнулите "{}"'.format(
                period_names[current_period_code], period_names[next_code], period_names[next_code]
            )

    # Порядок заполнения: «Январь-Март» → «Январь-Июнь» → «Январь-Сентябрь».
    # Следующий период можно заполнить, только когда предыдущий не равен 0,
    # и значение не может быть меньше предыдущего (нарастающий итог).
    prev_code = {'0002': '0001', '0003': '0002'}.get(current_period_code)
    if prev_code:
        prev_value = _as_float(prev_code) or 0
        if current_value_num != 0 and prev_value == 0:
            return 'Сначала заполните "{}" — периоды заполняются по нарастающей'.format(period_names[prev_code])
        if current_value_num != 0 and current_value_num < prev_value:
            return 'Значение "{}" ({:.2f} т у.т.) не может быть меньше "{}" ({:.2f} т у.т.) — значения вводятся нарастающим итогом'.format(
                period_names[current_period_code], current_value_num,
                period_names[prev_code], prev_value
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
    # Внешние (организации маршрута) и внутренние (цепочка подписания
    # внутри организации-разработчика, is_internal=True, см. internal_sign/
    # forward_internal_signature) шаги живут в ОДНОЙ таблице — группируем
    # отдельно по циклам, чтобы 'paths' (используется для расчёта статуса/
    # first_unviewed в шаблоне) остался строго внешним, как и раньше.
    # is_internal=True строки бывают двух видов, различаем по log_action:
    # NULL — "Шаг 1" до реальной отправки (внутри организации-разработчика,
    # internal_sign/forward_internal_signature, см. is_internal выше);
    # заполнено — "Шаг 2" ВНУТРИ уже внешней организации (регион/
    # согласующая/утверждающая, log_step2_action) — их прикрепляем к
    # "своему" официальному шагу по совпадению (cycle, step_order), а не
    # показываем общим списком наверху цикла.
    paths_by_cycle = {}
    internal_by_cycle = {}
    step2_by_cycle_order = {}
    rework_by_cycle = {}
    for path in plan.approval_paths:
        # «План отправлен на доработку» — финальная строка попытки (см.
        # add_rework_step), показывается отдельно после всех организаций.
        if path.is_internal and path.log_action == REWORK_LOG_ACTION:
            rework_by_cycle[path.cycle] = path
            continue
        # 'internal_returned' — возврат на внутреннюю доработку
        # (plan_bp.internal_return): это шаг внутренней цепочки
        # организации-разработчика, а не "Шаг 2" внешней организации.
        if path.is_internal and path.log_action and path.log_action != 'internal_returned':
            step2_by_cycle_order.setdefault((path.cycle, path.step_order), []).append(path)
        elif path.is_internal:
            internal_by_cycle.setdefault(path.cycle, []).append(path)
        else:
            paths_by_cycle.setdefault(path.cycle, []).append(path)

    # Кроме циклов внешней отправки — ещё и вернутые на внутреннюю
    # доработку попытки: у них только внутренние шаги (свой номер цикла,
    # см. internal_return), внешних этапов нет. cycle=0 — текущая, ещё не
    # отправленная попытка — показывается отдельно (pending_internal_steps).
    cycle_numbers = sorted(set(paths_by_cycle) | {c for c in internal_by_cycle if c})
    if not cycle_numbers:
        return []
    last_external_cycle = max(paths_by_cycle) if paths_by_cycle else None

    for cycle_paths in paths_by_cycle.values():
        cycle_paths.sort(key=lambda p: p.step_order)
    for cycle_steps in internal_by_cycle.values():
        cycle_steps.sort(key=lambda p: p.step_order)
    for step2_steps in step2_by_cycle_order.values():
        step2_steps.sort(key=lambda p: (p.created_at or current_utc_time(), p.id))

    for cycle_paths in paths_by_cycle.values():
        for path in cycle_paths:
            path.step2_history = step2_by_cycle_order.get((path.cycle, path.step_order), [])

    cancel_tickets = sorted(
        [t for t in plan.tickets if t.note and t.note.startswith(CANCEL_SEND_NOTE_PREFIX) and t.begin_time],
        key=lambda t: t.begin_time,
    )

    def cycle_start(cycle_paths):
        starts = [p.created_at for p in cycle_paths if p.created_at]
        return min(starts) if starts else None

    cycles = []
    for idx, cycle_num in enumerate(cycle_numbers):
        cycle_paths = paths_by_cycle.get(cycle_num, [])
        # Вернутая на внутреннюю доработку попытка — внешних этапов нет,
        # план никуда не отправлялся (sent_at=None).
        is_returned_internal = not cycle_paths
        sent_at = cycle_start(cycle_paths)

        next_start = None
        if idx + 1 < len(cycle_numbers):
            next_num = cycle_numbers[idx + 1]
            next_start = cycle_start(paths_by_cycle.get(next_num, []) or internal_by_cycle.get(next_num, []))

        cancel_ticket = None
        for ticket in cancel_tickets:
            if sent_at and ticket.begin_time >= sent_at and (next_start is None or ticket.begin_time < next_start):
                cancel_ticket = ticket
                break

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

        # Шаги внутренней цепочки этого цикла (submit_for_signature/
        # forward_internal_signature/internal_sign, is_internal=True).
        # Пусто для циклов, созданных ДО этой фичи — для них шаблон сам
        # откатывается на единственную строку dev_post/dev_name/... выше.
        internal_steps = internal_by_cycle.get(cycle_num, [])

        # Вернутая попытка: куда план должен был пойти (снимок маршрута на
        # строке возврата, см. internal_return) — шаблон показывает эти
        # организации со статусом «Не отправлен».
        planned_route = []
        if is_returned_internal:
            return_step = next((s for s in internal_steps if s.log_action == 'internal_returned'), None)
            planned_route = decode_route_snapshot(return_step.route_snapshot) if return_step else []

        cycles.append({
            'cycle': cycle_num,
            'sent_at': sent_at,
            'paths': cycle_paths,
            'planned_route': planned_route,
            'rework_step': rework_by_cycle.get(cycle_num),
            'cancel_ticket': cancel_ticket,
            # «Последний» — последняя ВНЕШНЯЯ отправка (по ней шаблон
            # считает текущий этап и статус); вернутые внутренние попытки
            # на это не влияют.
            'is_latest': cycle_num == last_external_cycle,
            'is_returned_internal': is_returned_internal,
            'dev_post': dev_post,
            'dev_name': dev_name,
            'dev_phone': dev_phone,
            'dev_email': dev_email,
            'internal_steps': internal_steps,
            # Этап 1 (организация-разработчик) — основной шаг и подэтапы.
            'dev_main': split_dev_stage(internal_steps)[0],
            'dev_substeps': split_dev_stage(internal_steps)[1],
        })

    return cycles


def split_dev_stage(internal_steps):
    """Шаги организации-разработчика одной попытки -> (основной, подэтапы).
    Основной (итоговый) шаг этапа — «Подписал ЭЦП и направил» (internal_sign,
    forwarded_to_user_id=None) или возврат на доработку ('internal_returned');
    всё, что было до него (исполнитель направил на подпись, руководитель
    подразделения согласовал и направил дальше), — подэтапы. Пока итогового
    шага нет (план ещё на подписи), основной шаг — None."""
    main = next((s for s in reversed(internal_steps)
                 if s.log_action == 'internal_returned'
                 or (not s.log_action and s.forwarded_to_user_id is None)), None)
    return main, [s for s in internal_steps if s is not main]


def get_pending_internal_sign_steps(plan):
    """Шаги внутренней цепочки ТЕКУЩЕЙ, ещё не отправленной реально во
    внешний маршрут попытки (cycle IS NULL) — для pre-send блока
    "Подписи" (пока PlanApprovalPath для этого захода ещё не созданы,
    см. handle_sent_status). Если попытка уже направлялась (см.
    forward_internal_signature) — показывает уже пройденные шаги цепочки
    ДО текущего держателя (которого показывает отдельная живая строка).
    cycle=0 — зарезервированный "ещё не отправлено" (PlanApprovalPath.cycle
    в остальном NOT NULL, реальные циклы нумеруются с 1, см. handle_sent_status)."""
    # log_action IS NULL — только шаги "направил/подписал"; строка возврата
    # на внутреннюю доработку (log_action='internal_returned', см.
    # plan_bp.internal_return) показывается отдельной строкой "Не
    # согласован" из last_internal_return_ticket, не как пройденный шаг.
    return PlanApprovalPath.query.filter_by(
        plan_id=plan.id, cycle=0, is_internal=True
    ).filter(PlanApprovalPath.log_action.is_(None)).order_by(PlanApprovalPath.step_order).all()


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
    external_cycles = [c for c in cycles if not c.get('is_returned_internal')]
    latest = external_cycles[-1] if external_cycles else None
    latest_paths = latest['paths'] if latest else []
    first_unviewed = next((p for p in latest_paths if not p.is_viewed), None)

    rows = []
    for cycle in cycles:
        dev_line = (
            f"Разработчик плана: {cycle['dev_name']}, тел.: {cycle['dev_phone'] or '—'}, email: {cycle['dev_email'] or '—'}"
            if cycle['dev_name'] else 'Разработчик плана: —'
        )
        rows.append(('header', dev_line))

        # Вернутая на внутреннюю доработку попытка — только шаги внутри
        # организации-разработчика: кто одобрил и кто вернул (с причиной).
        if cycle.get('is_returned_internal'):
            org_name = plan.organization.full_name if plan.organization else '—'
            for step in cycle['internal_steps']:
                if step.log_action == 'internal_returned':
                    rows.append(('data', [
                        'Направление плана', org_name,
                        step.rejected_by_snapshot or step.signed_by_snapshot or '—',
                        'Не согласован',
                        step.rejected_at.strftime('%d.%m.%Y') if step.rejected_at else '—',
                        step.ticket.note if step.ticket else '—',
                    ]))
                else:
                    rows.append(('data', [
                        'Направление плана', org_name,
                        step.signed_by_snapshot or '—',
                        'Направление на подпись' if step.step_type == 'submitter' else 'Согласован',
                        step.signed_at.strftime('%d.%m.%Y') if step.signed_at else '—',
                        '—',
                    ]))
            for step_type, org in cycle.get('planned_route', []):
                rows.append(('data', [
                    'Утверждение' if step_type == 'approver' else 'Согласование',
                    org.full_name, '—', 'Не отправлен', '—', '—',
                ]))
            if cycle.get('rework_step'):
                rows.append(('header', 'План отправлен на доработку'))
            continue

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
            # Статусы в печатной форме — те же пять слов, что и на странице
            # "Подписи" (components.html::plan_signatures_page).
            if path.is_viewed:
                status = 'Согласован'
            elif is_abandoned:
                status = 'Ожидание очереди'
            elif is_rejected_step:
                status = 'Не согласован'
            elif is_active:
                status = 'На рассмотрении'
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

            # замечание этапа — только при подписанном «Не согласован»
            # (как в «Подписях», components.html::plan_signatures_page)
            remark = path.ticket.note if (is_rejected_step and path.ticket) else '—'

            rows.append(('data', [
                action_label,
                path.organization.full_name if path.organization else '—',
                position,
                status,
                date_str,
                remark,
            ]))

        if cycle.get('rework_step'):
            rows.append(('header', 'План отправлен на доработку'))

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
    None, если план не отправлен или этой организации в цепочке нет.
    is_internal=True (внутренняя цепочка подписания до отправки, cycle=0
    пока план ещё не уходил во внешний маршрут) исключаем явно — иначе
    organization_id внутреннего шага (= сама организация-разработчик)
    мог бы случайно совпасть с org_ids."""
    external_paths = [p for p in plan.approval_paths if not p.is_internal]
    if not external_paths:
        return None
    latest_cycle = max(p.cycle for p in external_paths)
    return next(
        (p for p in external_paths if p.cycle == latest_cycle and p.organization_id in org_ids),
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
    latest_paths = [p for p in plan.approval_paths if p.cycle == my_path.cycle and not p.is_internal]
    return any(p.step_order < my_path.step_order and not p.is_viewed for p in latest_paths)


def get_current_review_path(plan, current_user):
    """Текущий (непройденный, первый по порядку) этап согласования из
    ПОСЛЕДНЕГО цикла отправки — или None, если либо план не отправлен, либо
    все этапы пройдены, либо organization_id пользователя на нём не стоит.
    is_internal=True (внутренняя цепочка до реальной отправки) исключаем —
    иначе план с уже начатой, но ещё не отправленной цепочкой (cycle=0)
    ошибочно выглядел бы "отправленным" для этой функции."""
    external_paths = [p for p in plan.approval_paths if not p.is_internal]
    if not external_paths:
        return None
    latest_cycle = max(p.cycle for p in external_paths)
    latest_paths = sorted(
        (p for p in external_paths if p.cycle == latest_cycle),
        key=lambda p: p.step_order,
    )
    current_path = next((p for p in latest_paths if not p.is_viewed), None)
    if not current_path or not current_user.organization_id:
        return None
    if current_path.organization_id != current_user.organization_id:
        return None
    # Утверждающая организация (ТЗ п.5) — доступ зависит от того, кто
    # создал план:
    # - Вариант А (план создан самой утверждающей организацией,
    #   plan.org_id == organization_id этапа): доступ только у
    #   org_head/org_head_deputy, исполнитель и руководитель структурного
    #   подразделения в утверждении не участвуют вовсе;
    # - Вариант Б (план создан другой организацией): исполнитель получает
    #   план первым и может направить его дальше (как и везде в "Шаге 2"),
    #   доступ не ограничен — решение в любом случае выносят только
    #   org_head/org_head_deputy (см. step_submit_for_signature/
    #   step_internal_sign).
    if current_path.step_type == 'approver' and plan.org_id == current_path.organization_id:
        if not current_user.is_org_manager:
            return None
    return current_path


STAFF_REVIEW_ROLES = ('executor', 'dept_head')


def org_head_block_reason(plan, current_path, user):
    """Почему руководитель организации (org_head/org_head_deputy) на этапе
    своей организации пока ничего не может сделать с планом, или None.

    План сначала рассматривает исполнитель или руководитель структурного
    подразделения и направляет решение руководителю на подпись
    (step_submit_for_signature / step_forward_signature). Пока решение не
    направлено (pending_signer пуст) — кнопки руководителя заблокированы:
    - 'waiting'  — такие сотрудники в организации есть, ждём их;
    - 'no_staff' — их нет вовсе (руководитель — единственный аккаунт):
      решение вынести некому, их нужно добавить в профиле организации.

    Исключение — Вариант А (утверждающая организация утверждает
    собственный план): там действует только руководитель, напрямую."""
    if not current_path or not getattr(user, 'is_org_manager', False):
        return None
    if current_path.pending_signer_user_id:
        return None
    if current_path.step_type == 'approver' and plan.org_id == current_path.organization_id:
        return None
    from common_models import get_current_application_id
    staff = User.query.filter(
        User.organization_id == current_path.organization_id,
        User.application_id == get_current_application_id(),
        User.org_role.in_(STAFF_REVIEW_ROLES),
        User.is_verified == True,
        User.id != user.id,
    ).first()
    return 'waiting' if staff else 'no_staff'


def org_head_waits_for_staff(plan, current_path, user):
    """True — руководитель пока не может вынести решение (см. org_head_block_reason)."""
    return org_head_block_reason(plan, current_path, user) is not None


ORG_HEAD_BLOCK_MESSAGES = {
    'waiting': 'План сначала рассматривает исполнитель или руководитель структурного подразделения и направляет решение вам на подпись',
    'no_staff': 'В организации нет исполнителя или руководителя структурного подразделения: решение по плану выносят они, а вы подписываете. Добавьте такого сотрудника в профиле организации',
}


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
    # Руководитель ждёт, пока сотрудники рассмотрят план и направят ему
    # решение на подпись — до этого его кнопки заблокированы.
    org_head_block = org_head_block_reason(plan, current_path, current_user) if can_audit else None
    org_head_waits = bool(org_head_block)
    if org_head_waits:
        can_audit = False

    approve_label = 'Согласовать'
    if current_path:
        current_cycle_paths = [p for p in plan.approval_paths if p.cycle == current_path.cycle and not p.is_internal]
        max_step = max((p.step_order for p in current_cycle_paths), default=current_path.step_order)
        if current_path.step_order == max_step:
            approve_label = 'Одобрить'

    # TODO: "Отменить изменения" на этапах согласования/утверждения
    # временно отключена по просьбе пользователя (закомментировано, не
    # удалено) — can_cancel всегда False, пока не понадобится вернуть.
    # Старая логика (кто и когда мог отменить своё подтверждение/
    # отклонение этапа) оставлена ниже закомментированной как есть.
    can_cancel = False
    # external_paths = [p for p in plan.approval_paths if not p.is_internal]
    # latest_cycle = max((p.cycle for p in external_paths), default=None)
    # cycle_paths = [p for p in external_paths if latest_cycle is None or p.cycle == latest_cycle]
    #
    # own_cycle_paths = [p for p in cycle_paths if p.organization_id == current_user.organization_id]
    # own_confirmed = [p for p in own_cycle_paths if p.is_viewed]
    # own_rejected = [p for p in own_cycle_paths if p.rejected_at]
    # user_has_viewed_current = bool(own_confirmed) or bool(own_rejected)
    #
    # blocked_by_later_step = False
    # if user_has_viewed_current:
    #     own_last_step_order = max(
    #         (p.step_order for p in own_confirmed + own_rejected), default=None
    #     )
    #     if own_last_step_order is not None:
    #         blocked_by_later_step = any(
    #             p.step_order > own_last_step_order and (p.is_viewed or p.rejected_at)
    #             for p in cycle_paths
    #         )
    #
    # can_cancel = user_has_viewed_current and not blocked_by_later_step

    has_remarks = has_pending_review_message(plan, current_user) if can_audit else False

    # ТЗ п.5, Вариант А (план создан самой утверждающей организацией):
    # никакого направления/решения нет — org_head/org_head_deputy сразу
    # видят только одну кнопку «Одобрить» с ЭЦП (см. step_internal_sign,
    # ветка для step_type='approver' без pending_signer_user_id). В
    # Варианте Б до этого момента доводит обычный "Шаг 2" (submit-for-
    # signature/forward-signature), see get_current_review_path.
    is_approver_step = bool(current_path and current_path.step_type == 'approver')
    step_direct_approve = bool(
        can_audit and is_approver_step and plan.org_id == current_path.organization_id
    )

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
        'is_approver_step': is_approver_step,
        'step_direct_approve': step_direct_approve,
        'org_head_waits': org_head_waits,
        'org_head_block': org_head_block,
    }


def get_plan_executors_summary(plan):
    """Список строк "ФИО (тел.: ..., email: ...)" — одна строка на
    каждого «Ответственного исполнителя» плана (до 2 человек, см.
    plan_bp::add_plan_executor/remove_plan_executor) — если их больше
    одного, шаблон показывает второго с новой строки (components.html::
    plan_signatures_page), а не через запятую на одной. Снимок каждого
    (developer_name/phone/email на PlanExecutor) сделан в момент
    добавления в список и не меняется при редактировании его профиля —
    та же причина, что у PlanApprovalPath.sender_*. Показывается и до
    отправки, и во всех уже отправленных циклах в «Подписи», одинаково,
    независимо от того, сколько раз план пересылался (в отличие от
    cycle.dev_* ниже — тот снимок про ПОДПИСАВШЕГО/отправившего
    конкретный цикл, отдельное понятие, см. build_signature_cycles).
    Возвращает пустой список, если ответственных исполнителей нет (старый
    план без ни одной записи — на этот случай в шаблоне есть собственный
    запасной вариант через plan.user)."""
    parts = []
    for e in plan.executors:
        if not e.developer_name:
            continue
        phone = e.developer_phone or '—'
        email = e.developer_email or '—'
        parts.append(f'{e.developer_name} (тел.: {phone}, email: {email})')
    return parts


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


def build_approval_chain(plan, coordinator_ids=None, approver_id=None, use_pending_fallback=True):
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
    сохранённый на шаге внутренней отправки на подпись). use_pending_fallback=False
    отключает этот откат — нужно там, где явно хотят узнать маршрут БЕЗ
    выбора пользователя (plan_send_page: обязательный ли Департамент по
    энергоэффективности сам по себе), иначе при повторной отправке плана
    сюда подставлялся бы устаревший pending_approver_id из прошлой,
    уже отменённой/возвращённой попытки — и утверждающая организация
    задваивалась бы в предпросмотре маршрута (видна и как выбор
    пользователя на этом шаге, и как "обязательный" Департамент).

    ТЗ п.7: доработанный план всегда проходит маршрут заново с самого
    начала (регион → согласующие → утверждающий), без пропуска уже
    пройденных организаций — ровно то, что эта функция и делает."""
    chain = []

    if not plan.organization or not plan.organization.region_id:
        return chain

    region_org = Organization.query.filter(
        Organization.is_region_management == True,
        Organization.region_id == plan.organization.region_id
    ).first()
    if region_org:
        chain.append(('region', region_org))

    if use_pending_fallback and not coordinator_ids and plan.pending_coordinator_ids:
        coordinator_ids = plan.pending_coordinator_ids.split(',')
    if use_pending_fallback and not approver_id and plan.pending_approver_id:
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
            # Департамент — СОГЛАСУЮЩАЯ организация (последняя перед
            # утверждающей), не утверждающая: на его этапе обычные правила
            # согласования («Не согласовать» доступно), а в экспорте он не
            # попадает в строку утверждающей организации.
            chain.append(('coordinator', energy_dept_org))

    if approver_id:
        approver_org = Organization.query.get(int(approver_id))
        if approver_org:
            chain.append(('approver', approver_org))

    return chain


REWORK_LOG_ACTION = 'sent_to_rework'


def add_rework_step(plan, cycle, user):
    """Финальный шаг попытки «План отправлен на доработку» — после всех
    организаций маршрута (и при внешнем «Есть ошибки», и при возврате на
    внутреннюю доработку). Внутренняя строка (is_internal=True) с
    log_action='sent_to_rework' и step_order после всех строк цикла —
    логика согласования (этапы, очередь, "Шаг 2") её не видит, она только
    для «Подписей»/печати (build_signature_cycles → cycle['rework_step'])."""
    now = current_utc_time()
    next_order = (db.session.query(db.func.max(PlanApprovalPath.step_order))
        .filter_by(plan_id=plan.id, cycle=cycle).scalar() or 0) + 1
    step = PlanApprovalPath(
        plan_id=plan.id, step_order=next_order, cycle=cycle,
        organization_id=plan.org_id, step_type='rework', is_internal=True,
        is_viewed=True, created_at=now,
        signed_by_user_id=user.id if user else None, signed_at=now,
        signed_by_snapshot=build_signer_snapshot(user) if user else None,
        log_action=REWORK_LOG_ACTION,
    )
    db.session.add(step)
    return step


def encode_route_snapshot(chain):
    """[(step_type, Organization), ...] из build_approval_chain ->
    "region:7946,approver:8945" для PlanApprovalPath.route_snapshot."""
    return ','.join(f'{step_type}:{org.id}' for step_type, org in chain) or None


def decode_route_snapshot(value):
    """Обратно: "region:7946,approver:8945" -> [(step_type, Organization)];
    организации, которых больше нет, пропускаются."""
    route = []
    for part in (value or '').split(','):
        step_type, _, org_id = part.partition(':')
        if not step_type or not org_id.isdigit():
            continue
        org = Organization.query.get(int(org_id))
        if org:
            route.append((step_type, org))
    return route


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

    # «Ответственные исполнители» + отмеченный «Разработчик плана»
    # (is_developer со снимком developer_*) — без этого копирования
    # архивная версия теряла бы информацию о разработчике: она хранится
    # только на PlanExecutor, а не на самом Plan (см. get_plan_developer).
    for ex in plan.executors:
        db.session.add(PlanExecutor(
            plan_id=snapshot.id,
            user_id=ex.user_id,
            added_at=ex.added_at,
            is_developer=ex.is_developer,
            developer_name=ex.developer_name,
            developer_phone=ex.developer_phone,
            developer_email=ex.developer_email,
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


def log_step2_action(plan, path, current_user, action, target_user=None, ticket=None):
    """Пишет историческую строку "Шага 2" ВНУТРИ внешней организации
    (регион/согласующая/утверждающая) — кто направил решение, кто
    переслал без подписи, кто подписал, кто вернул на доработку. Сам
    официальный шаг (path, is_internal=False) не трогает — это только
    для "Подписи": build_signature_cycles прикрепляет такие строки к
    "своему" официальному шагу по совпадению step_order (см. там же).
    Та же идея, что internal_sign/forward_internal_signature у
    организации-разработчика (is_internal=True), только organization_id
    здесь — внешняя организация, а не сама plan.org_id, и состояний
    больше двух, поэтому — log_action вместо forwarded_to_user_id."""
    db.session.add(PlanApprovalPath(
        plan_id=plan.id,
        step_order=path.step_order,
        organization_id=path.organization_id,
        step_type=path.step_type,
        is_internal=True,
        stage=path.stage,
        cycle=path.cycle,
        is_viewed=True,
        created_at=current_utc_time(),
        signed_by_user_id=current_user.id,
        signed_at=current_utc_time(),
        signed_by_snapshot=build_signer_snapshot(current_user),
        forwarded_to_user_id=target_user.id if target_user else None,
        log_action=action,
        ticket_id=ticket.id if ticket else None,
    ))


def get_signer_candidates(org_id, exclude_user_id=None):
    """Сотрудники организации — кандидаты на подпись/направление: «Руководитель
    структурного подразделения»/«Руководитель организации»/заместитель —
    используется и при первичной отправке плана (plan_send_page), и на
    "Шаге 2" при направлении решения этапа согласования/утверждения. Кто из
    них может реально ПОДПИСАТЬ (а не только направить дальше) — отдельное
    ограничение по роли в вызывающем коде (ТЗ п.5: утверждает только
    org_head/org_head_deputy, см. step_internal_sign/step_submit_for_signature).

    exclude_user_id — тот, кто направляет: самому себе направить на подпись
    нельзя (например, dept_head, сам подготовивший план, не видит себя в
    списке подписантов)."""
    from common_models import get_current_application_id

    roles = ['dept_head', 'org_head', 'org_head_deputy']
    query = User.query.filter(
        User.organization_id == org_id,
        User.application_id == get_current_application_id(),
        User.org_role.in_(roles)
    )
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    return query.order_by(User.org_role.desc()).all()


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