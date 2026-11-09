from datetime import timedelta

from flask import (
    Blueprint, abort, current_app, g, jsonify, render_template, render_template_string, request, flash, redirect, url_for, send_from_directory
)

from flask_login import (
    current_user, login_required 
)

from common_models import current_utc_time, get_current_application_id
from website.utils.plans import check_and_create_period_directions, generate_unique_display_code, other_data_indicatorUpdate, to_decimal_1, to_decimal_2, to_decimal_3, update_ChangeTimePlan, validate_period_values
from website.routes.auth import user_with_all_params
from website.routes.views import owner_only, reader_forbidden, historical_forbidden, org_head_forbidden
from website.sessions import session_required
from website.user import send_email

from website.utils.event import process_event_data, create_event_record, update_double_effect_payback
from website.utils.teo import save_teo_file, delete_teo_file

from ..ecp import verify_certificate

from .. import db
from ..models import Direction, Indicator, IndicatorUsage, Notification, Plan, PlanApprovalPath, PlanColumnConfig, PlanExecutor, PlanTicket, Event, Organization, User

import logging
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy import func

logger = logging.getLogger(__name__)
plan_bp = Blueprint('plan_bp', __name__, url_prefix='/plans/plan')

@plan_bp.route('/tasks/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@session_required
@owner_only
def plan_review(token):  
    if request.method == 'POST':
        pass
    
    current_plan = g.current_plan

    return render_template('plan_tasks.html',
                        plan=current_plan,
                        )


@plan_bp.route('/actions/<token>', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
@owner_only
def plan_actions(token):
    """Вкладка «Действия с планом» — объединяет то, что раньше было в
    выпадающем меню на «Задания» (Пройти контроль / Отправить на
    согласование / Отменить отправку / Редактировать / Удалить), и
    отдельную вкладку «Проверка» (чат с сообщениями по согласованию и
    смена статуса). Отображение персонализировано через is_owner/can_audit
    в самом шаблоне: разработчик плана видит плитки действий и историю
    переписки только для чтения, проверяющий (текущий этап согласования) —
    чат с возможностью писать и менять статус."""
    from website.utils.plans import get_audit_context, get_signer_candidates
    current_plan = g.current_plan
    audit_ctx = get_audit_context(current_plan, current_user)

    # Кандидаты на подпись РЕШЕНИЯ текущего этапа («Шаг 2») — организация
    # самого этапа (current_path), не плана. Нужны только пока есть
    # непройденный этап последнего цикла — иначе лишний запрос.
    step_signer_candidates = []
    step_org_head_candidates = []
    current_path = audit_ctx.get('current_path')
    if current_path:
        # Утверждающий этап (step_type='approver', ТЗ п.5 Вариант Б):
        # исполнитель направляет план dept_head (который только
        # пересылает дальше, см. step_forward_signature) ИЛИ сразу
        # org_head/org_head_deputy — picker предлагает все три роли; кто
        # из них реально утверждает (а не просто направляет) — отдельное
        # ограничение внутри step_submit_for_signature/step_internal_sign.
        step_signer_candidates = get_signer_candidates(current_path.organization_id, exclude_user_id=current_user.id)
        step_org_head_candidates = [c for c in step_signer_candidates if c.is_org_manager]

    from website.utils.plans import get_last_internal_return_ticket
    last_internal_return_ticket = get_last_internal_return_ticket(current_plan)

    plan_executor_candidates = _plan_executor_candidates(current_plan)

    # Кнопка «Направить на подпись» (forward_internal_signature) — виден
    # тот, кому план направлен сейчас, минус он сам: руководителю
    # структурного подразделения — руководитель организации и/или его
    # заместитель, руководителю организации — только заместитель,
    # заместителю — никого (дальше не передаёт).
    plan_forward_candidates = []
    if (current_plan.pending_signer_user_id == current_user.id
            and not current_plan.is_signed
            and current_user.org_role != 'org_head_deputy'):
        plan_forward_candidates = [
            c for c in get_signer_candidates(current_plan.org_id)
            if c.is_org_manager and c.id != current_user.id
        ]

    # «Отменить отправку» доступна только первые 5 минут после реальной
    # внешней отправки (plan.sent_time) — после истечения кнопка
    # неактивна уже при первой отрисовке страницы (JS на клиенте досчитывает
    # оставшееся время и сама отключает кнопку без перезагрузки, но
    # источник истины для самого запроса — серверная проверка в
    # api_change_plan_status).
    cancel_send_deadline_passed = bool(
        current_plan.is_sent
        and (not current_plan.sent_time or (current_utc_time() - current_plan.sent_time) > timedelta(minutes=5))
    )

    return render_template(
        'plan_actions.html', plan=current_plan,
        step_signer_candidates=step_signer_candidates,
        step_org_head_candidates=step_org_head_candidates,
        last_internal_return_ticket=last_internal_return_ticket,
        plan_executor_candidates=plan_executor_candidates,
        plan_forward_candidates=plan_forward_candidates,
        cancel_send_deadline_passed=cancel_send_deadline_passed,
        **audit_ctx
    )


PLAN_EXECUTORS_MAX = 2


def _plan_executor_candidates(plan):
    """Сотрудники организации плана, которых ещё можно добавить в список
    «Ответственных исполнителей» — org_role in (executor, dept_head), не
    руководитель организации (он не занимается заполнением) и не уже
    в списке."""
    already_ids = {e.user_id for e in plan.executors} or {plan.user_id}
    return User.query.filter(
        User.organization_id == plan.org_id,
        User.application_id == get_current_application_id(),
        User.org_role.in_(['executor', 'dept_head']),
        ~User.id.in_(already_ids) if already_ids else True
    ).order_by(User.org_role.desc()).all()


def _snapshot_executor(entry, user):
    """Снимок ФИО/телефона/email сотрудника на момент добавления в список
    «Ответственных исполнителей» — не меняется при последующем
    редактировании его профиля (та же причина, что у
    PlanApprovalPath.sender_*), используется для отображения в «Подписи»
    (см. utils/plans.py::get_plan_executors_summary)."""
    full_name = ' '.join(filter(None, [user.last_name, user.first_name, user.patronymic_name]))
    entry.developer_name = full_name or None
    entry.developer_phone = user.telephone
    entry.developer_email = user.email


@plan_bp.route('/add-executor/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
@owner_only
@historical_forbidden
@reader_forbidden
def add_plan_executor(token):
    """Добавляет сотрудника организации (исполнителя или руководителя
    структурного подразделения) в список «Ответственных исполнителей»
    плана — максимум 2 человека. На план без ни одной записи (старый
    план) сначала подставляется сам создатель (plan.user_id), чтобы
    список не "терял" его при первом добавлении. Доступно любому
    сотруднику организации, но только до отправки плана на согласование."""
    current_plan = g.current_plan

    if current_plan.is_sent:
        flash('Список ответственных исполнителей можно менять только до отправки плана на согласование', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    user_id = request.form.get('user_id')
    candidate = User.query.filter(
        User.id == user_id,
        User.organization_id == current_plan.org_id,
        User.application_id == get_current_application_id(),
        User.org_role.in_(['executor', 'dept_head'])
    ).first() if user_id else None

    if not candidate:
        flash('Выберите сотрудника организации', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    if not current_plan.executors and current_plan.user_id and current_plan.user_id != candidate.id:
        seed_entry = PlanExecutor(plan_id=current_plan.id, user_id=current_plan.user_id, added_at=current_utc_time())
        _snapshot_executor(seed_entry, current_plan.user)
        db.session.add(seed_entry)

    already_ids = {e.user_id for e in current_plan.executors} or {current_plan.user_id}
    if candidate.id in already_ids:
        flash('Этот сотрудник уже в списке', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    if len(current_plan.executors) >= PLAN_EXECUTORS_MAX:
        flash(f'В списке может быть не более {PLAN_EXECUTORS_MAX} ответственных исполнителей', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    new_entry = PlanExecutor(plan_id=current_plan.id, user_id=candidate.id, added_at=current_utc_time())
    _snapshot_executor(new_entry, candidate)
    db.session.add(new_entry)
    db.session.commit()

    flash('Сотрудник добавлен в список ответственных исполнителей', 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


@plan_bp.route('/remove-executor/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
@owner_only
@historical_forbidden
@reader_forbidden
def remove_plan_executor(token):
    """Убирает сотрудника из списка «Ответственных исполнителей» — нельзя
    опустошить список полностью (план должен указывать хотя бы одного
    ответственного). Доступно любому сотруднику организации, но только
    до отправки плана на внешнее согласование."""
    current_plan = g.current_plan

    if current_plan.is_sent:
        flash('Список ответственных исполнителей можно менять только до отправки плана на согласование', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    user_id = request.form.get('user_id')
    executors = current_plan.executors

    if not executors or len(executors) <= 1:
        flash('Нельзя убрать единственного ответственного исполнителя', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    entry = next((e for e in executors if str(e.user_id) == user_id), None)
    if not entry:
        flash('Сотрудник не найден в списке', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    db.session.delete(entry)
    db.session.commit()

    flash('Сотрудник убран из списка ответственных исполнителей', 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


@plan_bp.route('/signatures/<token>', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
@owner_only
def plan_signatures(token):
    """Вкладка «Подписи» — путь согласования плана (кто направил, кто уже
    согласовал/утвердил, кто на очереди) + текущий статус и прогресс сбоку.
    Планы могли отправляться несколько раз (отмена/возврат на доработку) —
    build_signature_cycles группирует историю по циклам отправки."""
    from website.utils.plans import build_signature_cycles, get_last_internal_return_ticket, build_approval_chain, get_plan_executors_summary, get_pending_internal_sign_steps
    current_plan = g.current_plan

    # Вкладка скрыта, пока у этой версии нет ни одного PlanApprovalPath
    # (см. plan_navigation_header) — прямой переход по URL тоже не пускаем.
    if not current_plan.approval_paths:
        return redirect(url_for('plan_bp.plan_actions', token=token))

    cycles = build_signature_cycles(current_plan)
    last_internal_return_ticket = get_last_internal_return_ticket(current_plan)
    plan_executors_summary = get_plan_executors_summary(current_plan)
    # Текущая, ещё не отправленная попытка (cycle=0) — и при пустой
    # истории, и когда план снова на подписи после возврата/отмены
    # (история прошлых попыток теперь остаётся на плане).
    has_current_attempt = (not cycles) or bool(current_plan.pending_signer_user_id)
    pending_internal_steps = get_pending_internal_sign_steps(current_plan) if has_current_attempt else []

    # До реальной внешней отправки (handle_sent_status, когда появляется
    # первый настоящий цикл — см. cycles выше) ни одного PlanApprovalPath
    # ещё нет, но маршрут уже выбран и сохранён (submit_for_signature) —
    # показываем его здесь же как предпросмотр, чтобы пользователь видел
    # весь путь согласования сразу после выбора, не дожидаясь подписи и
    # отправки руководителем. Сами согласующие/утверждающие организации
    # при этом ничего не видят — реальные PlanApprovalPath создаются
    # только в handle_sent_status.
    pending_chain = build_approval_chain(current_plan) if current_plan.pending_signer_user_id else []

    return render_template(
        'plan_signatures.html', plan=current_plan, cycles=cycles,
        last_internal_return_ticket=last_internal_return_ticket,
        pending_chain=pending_chain,
        plan_executors_summary=plan_executors_summary,
        pending_internal_steps=pending_internal_steps,
    )


@plan_bp.route('/send/<token>', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
@owner_only
@org_head_forbidden
@reader_forbidden
def plan_send_page(token):
    """Отдельная страница отправки плана на согласование — раньше было
    модальное окно поверх plan_tasks.html (SendModal/SendModalPreview в
    plan.js), теперь свой URL со всеми этапами. Доступна только когда план
    прошёл контроль и ещё не отправлен/утверждён — те же условия, что раньше
    просто отключали кнопку "Отправить на согласование"."""
    current_plan = g.current_plan

    if not current_plan.is_control or current_plan.is_draft or current_plan.is_sent or current_plan.is_approved or current_plan.is_error:
        flash('План должен сначала пройти контроль, прежде чем его можно будет отправить на согласование', 'error')
        return redirect(url_for('plan_bp.plan_review', token=current_plan.token))

    # Исполнитель готовит план и выбирает маршрут (шаги 1-3) наравне с
    # руководителями — он просто не сможет сам подписать/отправить
    # (кнопка «Отправить на подпись» на шаге 4 уводит план к выбранному
    # руководителю, см. submit_for_signature). Фактическая внешняя
    # отправка происходит отдельно, после подписи — см. internal_sign.
    from website.utils.plans import get_signer_candidates
    signer_candidates = get_signer_candidates(current_plan.org_id, exclude_user_id=current_user.id)

    # Департамент по энергоэффективности добавляется в маршрут
    # автоматически (см. build_approval_chain/handle_sent_status) при
    # суммарном потреблении ТЭР от 25000 т.у.т. включительно — на шаге
    # «Проверка» (step3, см. plan_send.js::updateApprovalPath) его тоже
    # нужно показать в предпросмотре пути согласования, хотя пользователь
    # его не выбирал.
    from website.utils.plans import build_approval_chain
    energy_dept_entry = next(
        (org for step_type, org in build_approval_chain(
            current_plan, coordinator_ids=[], approver_id=None, use_pending_fallback=False
        ) if step_type == 'approver'),
        None,
    )

    return render_template(
        'plan_send.html', plan=current_plan, signer_candidates=signer_candidates,
        energy_department_org=energy_dept_entry,
    )


@plan_bp.route('/submit-for-signature/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@historical_forbidden
@org_head_forbidden
@reader_forbidden
def submit_for_signature(token):
    """Шаг 4 отправки (plan_send.html) — вместо прямой отправки план
    направляется выбранному руководителю на внутреннюю подпись. Маршрут
    (согласующие/утверждающая), выбранный на шагах 1-3, сохраняется на
    план — к моменту реальной внешней отправки (internal_sign → «Отправить
    на согласование») клиентское состояние визарда уже недоступно."""
    current_plan = g.current_plan

    if not current_plan.is_control or current_plan.is_draft or current_plan.is_sent:
        flash('План должен сначала пройти контроль и ещё не быть отправлен', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    coordinator_ids = request.form.get('coordinator_ids', '')
    approver_id = request.form.get('approver_id')
    signer_id = request.form.get('signer_user_id')

    if not coordinator_ids.strip() and not approver_id:
        flash('Не выбраны организации для согласования и утверждения', 'error')
        return redirect(url_for('plan_bp.plan_send_page', token=token))

    signer = User.query.filter(
        User.id == signer_id,
        User.organization_id == current_plan.org_id,
        User.application_id == get_current_application_id(),
        User.org_role.in_(['dept_head', 'org_head', 'org_head_deputy'])
    ).first() if signer_id else None

    if not signer:
        flash('Выберите руководителя для подписания документа', 'error')
        return redirect(url_for('plan_bp.plan_send_page', token=token))

    if signer.id == current_user.id:
        flash('Нельзя направить план на подпись самому себе', 'error')
        return redirect(url_for('plan_bp.plan_send_page', token=token))

    current_plan.pending_coordinator_ids = coordinator_ids.strip() or None
    current_plan.pending_approver_id = int(approver_id) if approver_id else None
    current_plan.pending_signer_user_id = signer.id
    current_plan.submitted_by_user_id = current_user.id
    current_plan.is_signed = False

    # Первый подэтап этапа 1 (организация-разработчик): исполнитель
    # направил план руководителю на подпись. С этой строкой у плана сразу
    # появляется вкладка «Подписи» с полным маршрутом.
    from website.utils.plans import build_signer_snapshot
    next_order = (db.session.query(db.func.max(PlanApprovalPath.step_order))
        .filter_by(plan_id=current_plan.id, cycle=0, is_internal=True).scalar() or 0) + 1
    db.session.add(PlanApprovalPath(
        plan_id=current_plan.id, step_order=next_order,
        organization_id=current_plan.org_id, step_type='submitter', is_internal=True, stage=1,
        created_at=current_utc_time(), cycle=0, is_viewed=True,
        signed_by_user_id=current_user.id, signed_at=current_utc_time(),
        signed_by_snapshot=build_signer_snapshot(current_user),
        forwarded_to_user_id=signer.id,
    ))
    db.session.commit()

    db.session.add(Notification(
        user_id=signer.id,
        message=f'План на {current_plan.year} год ожидает вашей подписи',
        created_at=current_utc_time(),
    ))
    db.session.commit()

    flash('План направлен руководителю на подпись', 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


@plan_bp.route('/internal-sign/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@historical_forbidden
@reader_forbidden
def internal_sign(token):
    """Кнопка [Подписать и отправить] у руководителя, которому план
    направлен на подпись (см. submit_for_signature) — пока мок-ЭЦП
    (EcpMockModal), до подключения реального плагина.

    ТЗ п.3.3: подпись и отправка — ОДНО действие. Раньше это были два
    запроса подряд из JS (internal_sign, затем change-status status=sent):
    если второй падал (нет регионального управления, сеть и т.п.), план
    оставался «Подписан, ожидает отправки», а у подписанта не было ни одной
    кнопки, чтобы его доотправить. Теперь подпись и handle_sent_status идут
    в одной транзакции: не отправилось — подпись тоже откатывается."""
    from website.utils.plans import build_signer_snapshot
    from website.utils.status_plan import handle_sent_status

    current_plan = g.current_plan
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _fail(message, status):
        if is_ajax:
            return jsonify({'success': False, 'error': message}), status
        flash(message, 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    if current_plan.is_signed or current_plan.pending_signer_user_id != current_user.id:
        return _fail('План не направлен вам на подпись', 403)

    if current_plan.is_sent or not current_plan.is_control:
        return _fail('План должен пройти контроль и ещё не быть отправлен', 400)

    # Перед сменой статуса на «На согласовании» — сверка организации-
    # разработчика с ЕГР (наименование, регион, адрес, состояние). Без
    # успешной сверки план НЕ отправляется: нет УНП, ЕГР недоступен или не
    # нашёл организацию, либо по ЕГР она не действующая (тогда обновлённые
    # данные ЕГР сохраняем — дальше действует блокировка «только
    # просмотр»). См. utils/egr.py::refresh_before_send.
    from website.utils.egr import refresh_before_send
    egr_blocked = refresh_before_send(current_plan.organization)
    if egr_blocked:
        db.session.commit()
        return _fail(egr_blocked, 403)

    current_plan.is_signed = True
    current_plan.internal_signed_by_user_id = current_user.id
    current_plan.internal_signed_at = current_utc_time()
    current_plan.internal_signed_by_snapshot = build_signer_snapshot(current_user)

    # Финальный шаг внутренней цепочки — попадает в ту же таблицу
    # PlanApprovalPath, что и внешние организации (is_internal=True), так
    # же, как шаги направления (forward_internal_signature), чтобы вся
    # цепочка была видна в "Подписи" (forwarded_to_user_id=None у этого
    # шага как раз и отличает "сам подписал и отправил" от "направил
    # дальше"). cycle=0 — зарезервированный "ещё не отправлено".
    next_order = (db.session.query(db.func.max(PlanApprovalPath.step_order))
        .filter_by(plan_id=current_plan.id, cycle=0, is_internal=True).scalar() or 0) + 1
    db.session.add(PlanApprovalPath(
        plan_id=current_plan.id, step_order=next_order,
        organization_id=current_plan.org_id, step_type='signer', is_internal=True, stage=1,
        created_at=current_utc_time(), cycle=0, is_viewed=True,
        signed_by_user_id=current_user.id, signed_at=current_utc_time(),
        signed_by_snapshot=build_signer_snapshot(current_user),
        forwarded_to_user_id=None,
    ))
    db.session.flush()

    # handle_sent_status сам делает commit — вместе с подписью выше. Любая
    # его ошибка (в т.ч. валидационная, без собственного rollback) —
    # откатываем всё, план остаётся у подписанта неподписанным.
    result = handle_sent_status(current_plan)
    if isinstance(result, dict) and 'error' in result:
        db.session.rollback()
        return _fail(result['error'], 400)

    if is_ajax:
        return jsonify({'success': True, 'message': result.get('message')})
    flash(result.get('message', 'План подписан и отправлен на согласование'), 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


@plan_bp.route('/internal-forward/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@historical_forbidden
@reader_forbidden
def forward_internal_signature(token):
    """Альтернатива [Подписать] для того, кому план направлен на подпись
    (submit_for_signature/forward_internal_signature) — вместо подписи
    самим собой направляет план дальше (руководителю структурного
    подразделения — руководителю организации или его заместителю;
    руководителю организации — только заместителю), чтобы тот тоже
    посмотрел и сам подписал/отправил (internal_sign, без изменений).
    Заместитель дальше никому не передаёт — для него этого действия нет.

    TODO (ТЗ 3.3, открытый вопрос): если цепочка уже executor → dept_head →
    org_head, org_head всё равно может направить план дальше org_head_deputy
    (candidate_roles ниже) — получится 3 внутренних подписанта подряд при
    заявленном в ТЗ лимите в 2. Не ограничиваем по догадке до уточнения."""
    from website.utils.plans import build_signer_snapshot

    current_plan = g.current_plan

    def _fail(message, status=403):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': message}), status
        flash(message, 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    if current_plan.is_signed or current_plan.pending_signer_user_id != current_user.id:
        return _fail('План не направлен вам на подпись')

    if current_user.org_role == 'org_head':
        candidate_roles = ['org_head_deputy']
    elif current_user.org_role == 'dept_head':
        candidate_roles = ['org_head', 'org_head_deputy']
    else:
        return _fail('Направить план дальше может руководитель структурного подразделения, руководитель организации или его заместитель')

    target_id = request.form.get('target_user_id')
    target = User.query.filter(
        User.id == target_id,
        User.organization_id == current_plan.org_id,
        User.application_id == get_current_application_id(),
        User.org_role.in_(candidate_roles),
    ).first() if target_id else None
    if not target:
        return _fail('Выберите, кому направить план на подпись', 400)

    # Направление — без ЭЦП, но тоже попадает в ту же таблицу
    # PlanApprovalPath (is_internal=True, forwarded_to_user_id=target.id
    # отличает его от финального шага internal_sign) — чтобы в "Подписи"
    # было видно, что этот человек одобрил и передал дальше, а не просто
    # исчез из истории. cycle=0 — зарезервированный "ещё не отправлено".
    next_order = (db.session.query(db.func.max(PlanApprovalPath.step_order))
        .filter_by(plan_id=current_plan.id, cycle=0, is_internal=True).scalar() or 0) + 1
    db.session.add(PlanApprovalPath(
        plan_id=current_plan.id, step_order=next_order,
        organization_id=current_plan.org_id, step_type='signer', is_internal=True, stage=1,
        created_at=current_utc_time(), cycle=0, is_viewed=True,
        signed_by_user_id=current_user.id, signed_at=current_utc_time(),
        signed_by_snapshot=build_signer_snapshot(current_user),
        forwarded_to_user_id=target.id,
    ))

    current_plan.pending_signer_user_id = target.id
    db.session.commit()

    db.session.add(Notification(
        user_id=target.id,
        message=f'План на {current_plan.year} год ожидает вашей подписи',
        created_at=current_utc_time(),
    ))
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    flash('План направлен на подпись', 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


@plan_bp.route('/internal-return/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@historical_forbidden
@reader_forbidden
def internal_return(token):
    """Кнопка [Вернуть на внутреннюю доработку] — руководитель нашёл
    ошибки при ВНУТРЕННЕЙ проверке (ещё до того, как план покинул
    организацию) и возвращает его отправившему с обязательным текстом
    ошибки. Ведёт себя так же, как внешнее отклонение (handle_error_status,
    status_plan.py) — план переходит в "Есть ошибки" и замораживается
    снимком (create_plan_snapshot), чтобы версия "как её увидел
    руководитель" не терялась при первой же правке — разница только в
    том, что внешний маршрут согласования этим не затрагивается (он ещё
    не существует на этом этапе).

    Причина возврата НЕ создаёт отдельный PlanApprovalPath — маршрут
    согласования к этому моменту не существует, а специально заведённая
    под это строка задним числом путала бы "Направление плана" (там
    должен быть сразу тот, кто реально подписал и отправил — см.
    handle_sent_status, — а не исполнитель, который и так указан строкой
    выше). Причина — обычное сообщение в PlanTicket (без привязки к
    approval_path_id, которого ещё нет), показывается баннером на
    "Действиях с планом" (см. plan_actions.html) самому последнему такому
    сообщению после последнего реального возврата/отправки."""
    from website.utils.plans import create_plan_snapshot, build_signer_snapshot
    from website.utils.ticket_attachment import validate_ticket_attachment, save_ticket_attachment

    current_plan = g.current_plan

    if not current_plan.pending_signer_user_id or current_plan.pending_signer_user_id != current_user.id:
        flash('План не направлен вам на подпись', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    note = (request.form.get('note') or '').strip()
    if not note:
        flash('Укажите причину возврата', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    attachment_file = request.files.get('attachment')
    if attachment_file and attachment_file.filename:
        attachment_error = validate_ticket_attachment(attachment_file)
        if attachment_error:
            flash(attachment_error, 'error')
            return redirect(url_for('plan_bp.plan_actions', token=token))

    submitted_by_id = current_plan.submitted_by_user_id

    current_plan.is_signed = False
    current_plan.pending_signer_user_id = None
    current_plan.internal_signed_by_user_id = None
    current_plan.internal_signed_at = None
    current_plan.internal_signed_by_snapshot = None

    current_plan.audit_time = current_utc_time()
    current_plan.is_error = True
    current_plan.is_draft = False
    current_plan.is_control = False
    current_plan.is_sent = False
    current_plan.is_approved = False

    new_ticket = PlanTicket(
        note=note,
        is_system=False,
        plan_id=current_plan.id,
        user_id=current_user.id,
        begin_time=current_utc_time(),
    )
    db.session.add(new_ticket)
    db.session.flush()

    if attachment_file and attachment_file.filename:
        save_ticket_attachment(new_ticket, attachment_file)

    # Шаги внутренней цепочки этой попытки (кто направил/одобрил, cycle=0)
    # раньше УДАЛЯЛИСЬ здесь — теперь это подписи, они остаются в истории
    # текущей версии плана. Сам возврат тоже фиксируется строкой
    # (log_action='internal_returned': кто вернул, когда, с каким замечанием).
    next_order = (db.session.query(db.func.max(PlanApprovalPath.step_order))
        .filter_by(plan_id=current_plan.id, cycle=0, is_internal=True).scalar() or 0) + 1
    # Маршрут, выбранный для этой попытки (submit_for_signature) — план до
    # внешних организаций так и не дошёл, но «Подписи» должны показать,
    # куда он должен был пойти. Снимок, а не живой pending_*: при следующей
    # попытке маршрут могут выбрать другой.
    from website.utils.plans import build_approval_chain, encode_route_snapshot
    route_snapshot = encode_route_snapshot(build_approval_chain(current_plan))
    db.session.add(PlanApprovalPath(
        plan_id=current_plan.id, step_order=next_order,
        organization_id=current_plan.org_id, step_type='signer', is_internal=True, stage=1,
        created_at=current_utc_time(), cycle=0, is_viewed=False,
        rejected_at=current_utc_time(), rejected_by_snapshot=build_signer_snapshot(current_user),
        signed_by_user_id=current_user.id, signed_at=current_utc_time(),
        signed_by_snapshot=build_signer_snapshot(current_user),
        log_action='internal_returned', ticket_id=new_ticket.id,
        route_snapshot=route_snapshot,
    ))
    db.session.flush()

    # Последний шаг попытки — «План отправлен на доработку» (в «Подписях»
    # после организаций маршрута, куда план так и не ушёл).
    from website.utils.plans import add_rework_step
    add_rework_step(current_plan, 0, current_user)
    db.session.flush()

    # Вернутая попытка получает СВОЙ номер цикла (следующий после всех
    # существующих) — иначе её строки (cycle=0, «ещё не отправлено»)
    # смешались бы со следующей попыткой: handle_sent_status переносит в
    # новый цикл ВСЕ строки cycle=0. Следующая реальная отправка получит
    # номер ещё больше (handle_sent_status считает max по всем строкам).
    returned_cycle = (db.session.query(db.func.max(PlanApprovalPath.cycle))
        .filter_by(plan_id=current_plan.id).scalar() or 0) + 1
    PlanApprovalPath.query.filter_by(plan_id=current_plan.id, cycle=0, is_internal=True).update(
        {'cycle': returned_cycle}, synchronize_session=False)

    # Копия плана "как есть" БЕЗ подписей (вся история остаётся на текущей
    # версии) — тем же способом, что и при внешнем отклонении (см.
    # handle_error_status).
    create_plan_snapshot(current_plan)
    db.session.commit()

    if submitted_by_id:
        db.session.add(Notification(
            user_id=submitted_by_id,
            message=f'План на {current_plan.year} год возвращён на доработку: {note[:100]}',
            created_at=current_utc_time(),
        ))
        db.session.commit()

    flash('План возвращён на доработку', 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


def _finalize_step_decision(current_plan, current_path, current_user):
    """Финализирует подписанное решение этапа ("Шаг 2"): вызывает
    handle_approved_status/handle_error_status (использует current_user —
    именно подписавшего, а не исполнителя, направившего решение раньше)
    и сбрасывает поля внутреннего подцикла. Вызывается из step_internal_sign
    сразу после подписи — подпись и финализация решения (отправка дальше
    по маршруту либо «Есть ошибки») всегда одно действие, для всех
    step_type. Возвращает текст ошибки или None."""
    from website.utils.status_plan import handle_approved_status, handle_error_status

    decision = current_path.pending_decision
    handler = handle_approved_status if decision == 'approved' else handle_error_status
    result = handler(current_plan, current_user)

    if isinstance(result, dict) and 'error' in result:
        return result['error']

    current_path.pending_signer_user_id = None
    current_path.is_signed = False
    current_path.submitted_by_user_id = None
    current_path.pending_decision = None
    current_path.signed_by_user_id = None
    current_path.signed_at = None
    current_path.signed_by_snapshot = None
    return None


@plan_bp.route('/step/submit-for-signature/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@historical_forbidden
@reader_forbidden
def step_submit_for_signature(token):
    """«Шаг 2» внутреннего подписания — зеркало submit_for_signature выше,
    но для РЕШЕНИЯ организации на текущем этапе внешнего маршрута
    (согласование/утверждение), а не для самого плана. Исполнитель этой
    организации рассматривает план (как раньше) и вместо немедленной смены
    статуса направляет своё решение на подпись руководителю — см.
    tickets_container/get_audit_context: кнопки «Есть ошибки»/«Согласовать»
    открывают выбор подписанта, который сабмитит сюда."""
    from website.utils.plans import get_current_review_path

    current_plan = g.current_plan
    current_path = get_current_review_path(current_plan, current_user)

    if (
        not current_path or not current_plan.is_sent or current_plan.is_approved
        or current_plan.is_error or current_path.pending_signer_user_id
    ):
        flash('Этап недоступен для рассмотрения', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    is_approver_step = current_path.step_type == 'approver'

    # Утверждающая организация, Вариант А (ТЗ п.5 — план создан ею самой):
    # никакого "Шага 2" через этот роут нет вообще, org_head/org_head_deputy
    # сразу подписывают напрямую (см. step_internal_sign). get_current_review_path
    # и так не выдаёт current_path исполнителю/dept_head в этом случае — но
    # сам org_head/deputy технически мог бы дойти до этой формы, если он
    # уже имел current_path, поэтому проверяем явно.
    if is_approver_step and current_plan.org_id == current_path.organization_id:
        flash('В этом случае руководитель организации или его заместитель утверждает план напрямую, без направления', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    decision = request.form.get('decision')
    signer_id = request.form.get('signer_user_id')

    # Утверждающая организация (ТЗ п.5): решения «Есть ошибки» здесь нет
    # вовсе — исполнитель/руководитель структурного подразделения не
    # выносят вердикт, они только направляют план дальше по цепочке,
    # решение всегда считается «Одобряю» (сам факт одобрения оформляет
    # ЭЦП-подписант, см. step_internal_sign).
    if is_approver_step:
        decision = 'approved'
    elif decision not in ('approved', 'error'):
        flash('Не указано решение', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    # «Не согласовать и отправить на подпись» (stepRejectModal): текст ошибки
    # и файл с замечаниями приходят прямо в этом запросе и оба обязательны —
    # отдельного сообщения в чате перед этим больше не нужно (чат «Проверка
    # плана» со страницы убран). Само замечание создаётся ниже, после
    # проверки подписанта, чтобы при ошибке выбора не оставлять
    # осиротевший тикет.
    reject_note = (request.form.get('note') or '').strip()
    reject_attachment = request.files.get('attachment')
    if decision == 'error':
        if not reject_note:
            flash('Напишите текст ошибки', 'error')
            return redirect(url_for('plan_bp.plan_actions', token=token))
        if not reject_attachment or not reject_attachment.filename:
            flash('Прикрепите файл с замечаниями', 'error')
            return redirect(url_for('plan_bp.plan_actions', token=token))
        from website.utils.ticket_attachment import validate_ticket_attachment
        attachment_error = validate_ticket_attachment(reject_attachment)
        if attachment_error:
            flash(attachment_error, 'error')
            return redirect(url_for('plan_bp.plan_actions', token=token))

    # TODO (ТЗ, открытый вопрос к п.4.3): есть ли роль org_head_deputy в
    # САМОЙ согласующей организации и что она может делать — до прояснения
    # не добавляем её в allowed_roles для не-approver этапов (регион/
    # согласующая), хотя get_signer_candidates уже предлагает её в списке
    # кандидатов на подпись наравне с org_head.
    #
    # Утверждающая организация, Вариант Б: исполнитель направляет план
    # либо напрямую org_head/org_head_deputy, либо dept_head (который сам
    # решения не выносит, только пересылает дальше — см.
    # step_forward_signature), поэтому dept_head тоже допустимая цель.
    allowed_roles = ['dept_head', 'org_head', 'org_head_deputy'] if is_approver_step else ['dept_head', 'org_head']
    signer = User.query.filter(
        User.id == signer_id,
        User.organization_id == current_path.organization_id,
        User.application_id == get_current_application_id(),
        User.org_role.in_(allowed_roles)
    ).first() if signer_id else None

    if not signer:
        flash('Выберите руководителя для подписания решения', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    if signer.id == current_user.id:
        flash('Нельзя направить решение на подпись самому себе', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    reject_ticket = None
    if decision == 'error':
        from website.utils.ticket_attachment import save_ticket_attachment
        reject_ticket = PlanTicket(
            note=reject_note,
            is_system=False,
            plan_id=current_plan.id,
            user_id=current_user.id,
            approval_path_id=current_path.id,
            begin_time=current_utc_time(),
        )
        db.session.add(reject_ticket)
        db.session.flush()
        save_ticket_attachment(reject_ticket, reject_attachment)
        # "То самое" замечание этапа для «Подписи» (столбец «Замечания») и
        # для handle_error_status — именно это, последнее, а не любое
        # более раннее сообщение по этапу (например, пояснение
        # руководителя при прошлом «не согласен»).
        current_path.ticket_id = reject_ticket.id

    current_path.pending_decision = decision
    current_path.pending_signer_user_id = signer.id
    current_path.submitted_by_user_id = current_user.id
    current_path.is_signed = False

    from website.utils.plans import log_step2_action
    log_step2_action(
        current_plan, current_path, current_user,
        'submitted_forward' if is_approver_step else ('submitted_error' if decision == 'error' else 'submitted_approved'),
        target_user=signer, ticket=reject_ticket,
    )

    db.session.commit()

    db.session.add(Notification(
        user_id=signer.id,
        message=f'Решение по плану на {current_plan.year} год ожидает вашей подписи',
        created_at=current_utc_time(),
    ))
    db.session.commit()

    flash('Решение направлено руководителю на подпись', 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


@plan_bp.route('/step/internal-sign/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@historical_forbidden
@reader_forbidden
def step_internal_sign(token):
    """Кнопка [Подписать] у руководителя, которому направлено решение
    этапа (см. step_submit_for_signature) — тот же мок-ЭЦП, что и в «Шаге
    1». Подпись сразу же финализирует решение (через _finalize_step_decision)
    — отдельного клика [Отправить] нет: как только руководитель подписал,
    план либо уходит дальше по маршруту, либо этап становится «Есть
    ошибки» — в зависимости от того, какое решение было направлено ему на
    подпись (см. step_submit_for_signature). В "Подписи" это один и тот же
    момент, поэтому отдельная строка "Подписал(а) решение" (log_step2_action)
    здесь больше не пишется — итог виден по самому официальному шагу
    (его viewed_by_snapshot/rejected_by_snapshot и дате).

    Для step_type='approver' (ТЗ п.5) — особый случай: решения "Есть
    ошибки" в утверждающей организации нет вовсе (только «Одобрить»). А
    если план создан самой утверждающей организацией (Вариант А) — у
    org_head/org_head_deputy current_path.pending_signer_user_id вообще
    не был выставлен (нет отдельного направления, см.
    step_submit_for_signature), так что принимаем решение "на себя".

    TODO (ТЗ 5, открытый вопрос): org_head и org_head_deputy решают
    независимо — кто первый вызвал этот роут, тот и утвердил; передачи
    плана от руководителя заместителю (или наоборот) для Варианта А не
    реализуем по догадке."""
    from website.utils.plans import build_signer_snapshot, get_current_review_path

    current_plan = g.current_plan
    current_path = get_current_review_path(current_plan, current_user)

    is_direct_approve = bool(
        current_path and current_path.step_type == 'approver'
        and current_plan.org_id == current_path.organization_id
        and not current_path.pending_signer_user_id and not current_path.is_signed
        and current_user.is_org_manager
    )

    # Утверждающая организация, Вариант Б (ТЗ п.5): dept_head план только
    # направляет дальше (см. step_forward_signature) и сам решения не
    # выносит — даже если он формально сейчас pending_signer (его выбрал
    # исполнитель как промежуточную цель), подписывать ему нельзя.
    if (
        not is_direct_approve and current_path and current_path.step_type == 'approver'
        and current_path.pending_signer_user_id == current_user.id
        and not current_user.is_org_manager
    ):
        flash('Решение утверждающей организации подписывает только руководитель организации или его заместитель', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    if is_direct_approve:
        current_path.pending_decision = 'approved'
        current_path.submitted_by_user_id = current_user.id
    elif not current_path or current_path.is_signed or current_path.pending_signer_user_id != current_user.id:
        message = 'Решение не направлено вам на подпись'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': message}), 403
        flash(message, 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    current_path.is_signed = True
    current_path.signed_by_user_id = current_user.id
    current_path.signed_at = current_utc_time()
    current_path.signed_by_snapshot = build_signer_snapshot(current_user)

    decision = current_path.pending_decision
    is_approver_step = current_path.step_type == 'approver'

    error = _finalize_step_decision(current_plan, current_path, current_user)
    if error:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': error}), 400
        flash(error, 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    if is_approver_step:
        message = 'План утверждён'
    elif decision == 'approved':
        message = 'Решение подписано и отправлено'
    else:
        message = 'План возвращён на доработку'
    flash(message, 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


@plan_bp.route('/step/internal-return/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@historical_forbidden
@reader_forbidden
def step_internal_return(token):
    """Кнопка [Вернуть на повторное рассмотрение] — руководитель возвращает
    решение исполнителю, план/этап остаётся «На рассмотрении» (не
    согласован и не отклонён). Причина — PlanTicket, привязанный к этапу
    СРАЗУ двумя способами: approval_path_id (как и у сообщений живого
    чата) и, дополнительно, current_path.ticket_id — "то самое" замечание
    этапа для столбца "Замечания" в "Подписи" (см. PlanApprovalPath.ticket).

    TODO (ТЗ 5, открытый вопрос): для step_type='approver' (Вариант Б) ТЗ
    явно спрашивает, может ли org_head/org_head_deputy вернуть план своему
    исполнителю, если не согласен с ним, или у него только «Одобрить» —
    этот роут технически доступен и для approver-этапа (current_path.
    pending_signer_user_id уже может указывать на org_head/deputy после
    direct-approve веткой в step_internal_sign это не используется), но
    в шаблоне для approver-пути отдельно не выводится — оставляем как
    есть до уточнения, не скрываем и не включаем специально."""
    from website.utils.plans import get_current_review_path
    from website.utils.ticket_attachment import validate_ticket_attachment, save_ticket_attachment

    current_plan = g.current_plan
    current_path = get_current_review_path(current_plan, current_user)

    if not current_path or current_path.pending_signer_user_id != current_user.id:
        flash('Решение не направлено вам на подпись', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    # Утверждающая организация (ТЗ п.5): dept_head только направляет,
    # своего решения не выносит — значит и не возвращает его обратно (это
    # не тот же открытый вопрос, что про org_head/deputy выше — для
    # dept_head в approver-организации решения нет вообще никакого).
    # Этап утверждения — только положительное решение: возврата на
    # повторное рассмотрение нет ни у кого (кнопка в plan_actions выключена).
    if current_path.step_type == 'approver':
        flash('На этапе утверждения решение только положительное — вернуть его на повторное рассмотрение нельзя', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    note = (request.form.get('note') or '').strip()
    if not note:
        flash('Укажите причину возврата', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    attachment_file = request.files.get('attachment')
    if attachment_file and attachment_file.filename:
        attachment_error = validate_ticket_attachment(attachment_file)
        if attachment_error:
            flash(attachment_error, 'error')
            return redirect(url_for('plan_bp.plan_actions', token=token))

    submitted_by_id = current_path.submitted_by_user_id

    new_ticket = PlanTicket(
        note=note,
        is_system=False,
        plan_id=current_plan.id,
        user_id=current_user.id,
        approval_path_id=current_path.id,
        begin_time=current_utc_time(),
    )
    db.session.add(new_ticket)
    db.session.flush()

    if attachment_file and attachment_file.filename:
        save_ticket_attachment(new_ticket, attachment_file)

    current_path.ticket_id = new_ticket.id

    from website.utils.plans import log_step2_action
    log_step2_action(current_plan, current_path, current_user, 'returned', ticket=new_ticket)

    current_path.pending_signer_user_id = None
    current_path.is_signed = False
    current_path.submitted_by_user_id = None
    current_path.pending_decision = None
    current_path.signed_by_user_id = None
    current_path.signed_at = None
    current_path.signed_by_snapshot = None
    db.session.commit()

    if submitted_by_id:
        db.session.add(Notification(
            user_id=submitted_by_id,
            message=f'Решение по плану на {current_plan.year} год возвращено на повторное рассмотрение',
            created_at=current_utc_time(),
        ))
        db.session.commit()

    flash('Решение возвращено на повторное рассмотрение', 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


@plan_bp.route('/step/forward-signature/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@historical_forbidden
@reader_forbidden
def step_forward_signature(token):
    """Кнопка [Отправить на подпись] у руководителя структурного
    подразделения (Вариант Б спеки) — пересылает решение (уже без его
    подписи) руководителю организации, не меняя ни решение, ни того, кто
    его изначально направил."""
    from website.utils.plans import get_current_review_path

    current_plan = g.current_plan
    current_path = get_current_review_path(current_plan, current_user)

    if (
        not current_path or current_path.is_signed
        or current_path.pending_signer_user_id != current_user.id
        or current_user.org_role != 'dept_head'
    ):
        flash('Решение не направлено вам на подпись', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    signer_id = request.form.get('signer_user_id')
    signer = User.query.filter(
        User.id == signer_id,
        User.organization_id == current_path.organization_id,
        User.application_id == get_current_application_id(),
        User.org_role.in_(['org_head', 'org_head_deputy'])
    ).first() if signer_id else None

    if not signer:
        flash('Выберите руководителя организации', 'error')
        return redirect(url_for('plan_bp.plan_actions', token=token))

    current_path.pending_signer_user_id = signer.id

    from website.utils.plans import log_step2_action
    log_step2_action(current_plan, current_path, current_user, 'forwarded', target_user=signer)

    db.session.commit()

    db.session.add(Notification(
        user_id=signer.id,
        message=f'Решение по плану на {current_plan.year} год ожидает вашей подписи',
        created_at=current_utc_time(),
    ))
    db.session.commit()

    flash('Решение направлено руководителю организации на подпись', 'success')
    return redirect(url_for('plan_bp.plan_actions', token=token))


@plan_bp.route('/verify-certificate/<token>', methods=['POST'])
@login_required
@owner_only
@historical_forbidden
@reader_forbidden
def api_verify_certificate(token):
    """AJAX-проверка сертификата ЭЦП на лету — способ "Сертификат ЭЦП" в
    демо-модалке проверки ЭЦП (см. static/js/ecp-mock-modal.js). Ничего не
    сохраняет, только проверяет срок действия файла и логирует (DEBUG) всё,
    что получилось из него достать — для отладки."""
    cert_file = request.files.get('certificate')
    if not cert_file or not cert_file.filename:
        return jsonify({'valid': False, 'error': 'Файл сертификата не передан'}), 400

    ok, error = verify_certificate(cert_file)
    return jsonify({'valid': ok, 'error': error})


@plan_bp.route('/indicators/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_indicators(token):
    if request.method == 'POST':
        pass

    current_plan = g.current_plan

    from website.utils.plans import ensure_column_configs
    ensure_column_configs(current_plan)

    indicators_non_mandatory = (Indicator.query
        .filter_by(IsMandatory=False)
        .filter(
            db.or_(
                Indicator.is_custom == True,
                ~Indicator.id.in_(
                    db.session.query(IndicatorUsage.id_indicator)
                    .filter(IndicatorUsage.id_plan == current_plan.id)
                )
            )
        )
        .all()
    )
    return render_template('plan_indicators.html',  
                        plan=current_plan, 
                        indicators_non_madatory=indicators_non_mandatory,
                        hide_header=False,
                        context_menu = True)
    

@plan_bp.route('/update-column-label/<token>', methods=['POST'])
@login_required
@reader_forbidden
def api_update_column_label(token):
    try:
        from flask import current_app
        import logging
        
        plan = Plan.query.filter_by(token=token).first_or_404()

        if plan.is_historical:
            return jsonify({'success': False, 'error': 'Это архивная версия плана — только для просмотра'}), 403

        from website.utils.plans import plan_edit_denial
        denial = plan_edit_denial(current_user, plan)
        if denial:
            return jsonify({'success': False, 'error': denial}), 403

        data = request.get_json()

        config_id = data.get('config_id')
        new_label = data.get('label')
        
        if not config_id:
            current_app.logger.error('config_id is missing')
            return jsonify({'success': False, 'error': 'config_id is required'}), 400
        
        if new_label not in ['отчет', 'оценка', 'прогноз']:
            current_app.logger.error(f'Invalid label value: {new_label}. Expected: отчет, оценка, прогноз')
            return jsonify({'success': False, 'error': 'Invalid label value'}), 400
        
        config = PlanColumnConfig.query.filter_by(id=config_id, plan_id=plan.id).first()
        if not config:
            current_app.logger.error(f'Config not found: id={config_id}, plan_id={plan.id}')
            return jsonify({'success': False, 'error': 'Config not found'}), 404
        
        old_label = config.label
        config.label = new_label
        
        db.session.commit()
        
        current_app.logger.info(f'Column label updated successfully: config_id={config_id}, old_label={old_label}, new_label={new_label}')
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f'Error updating column label: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500
    
def process_indicator_data(indicator, QYearBeforePrev_ed, QYearPrev_ed, QYearCurrent_ed, 
                           custom_coeff_before, custom_coeff_prev, custom_coeff_current,
                           fuel_category, name_other, is_edit=False, indicator_usage=None):
    
    indicator_code = indicator.code
    
    current_app.logger.info(f'[process_indicator_data] Starting processing for indicator {indicator_code}, is_edit={is_edit}')
    current_app.logger.info(f'[process_indicator_data] Received coeffs - before: {custom_coeff_before}, prev: {custom_coeff_prev}, current: {custom_coeff_current}')
    
    if indicator.is_custom and not fuel_category and not name_other:
        return None, 'Для данного показателя необходимо выбрать категорию топлива и ввести наименование'
    
    def parse_coeff(value):
        if not value:
            return None
        value = str(value).replace(',', '.')
        return to_decimal_3(value)
    
    # Коэффициент переводит натуральную величину в т у.т. — если сама
    # единица измерения показателя уже "т у.т." или "%", пересчитывать
    # нечего, коэффициент всегда 1 и меняться не должен (см. "x" в
    # колонках "в нат. велич." таблицы показателей).
    unit_name = indicator.unit.name if indicator.unit else None
    coeff_editable = indicator.Group == 1 and unit_name not in ('т у.т.', '%')

    if is_edit and indicator_usage:
        is_coeff_editable = coeff_editable

        current_app.logger.info(f'[process_indicator_data] Edit mode: is_coeff_editable={is_coeff_editable}')
        
        if is_coeff_editable:
            if custom_coeff_before:
                coeff_before = parse_coeff(custom_coeff_before)
                indicator_usage.coeff_before_prev = coeff_before if coeff_before != indicator.CoeffToTut else None
                current_app.logger.info(f'[process_indicator_data] Set coeff_before_prev={indicator_usage.coeff_before_prev} (raw: {custom_coeff_before})')
            else:
                indicator_usage.coeff_before_prev = None
                current_app.logger.info('[process_indicator_data] coeff_before_prev set to None')
                
            if custom_coeff_prev:
                coeff_prev = parse_coeff(custom_coeff_prev)
                indicator_usage.coeff_prev = coeff_prev if coeff_prev != indicator.CoeffToTut else None
                current_app.logger.info(f'[process_indicator_data] Set coeff_prev={indicator_usage.coeff_prev} (raw: {custom_coeff_prev})')
            else:
                indicator_usage.coeff_prev = None
                current_app.logger.info('[process_indicator_data] coeff_prev set to None')
                
            if custom_coeff_current:
                coeff_current = parse_coeff(custom_coeff_current)
                indicator_usage.coeff_current = coeff_current if coeff_current != indicator.CoeffToTut else None
                current_app.logger.info(f'[process_indicator_data] Set coeff_current={indicator_usage.coeff_current} (raw: {custom_coeff_current})')
            else:
                indicator_usage.coeff_current = None
                current_app.logger.info('[process_indicator_data] coeff_current set to None')
        else:
            indicator_usage.coeff_before_prev = None
            indicator_usage.coeff_prev = None
            indicator_usage.coeff_current = None
            current_app.logger.info('[process_indicator_data] Coefficients not editable, set all to None')
        
        used_coeff_before = indicator_usage.get_coeff_for_year('before')
        used_coeff_prev = indicator_usage.get_coeff_for_year('prev')
        used_coeff_current = indicator_usage.get_coeff_for_year('current')
        
        current_app.logger.info(f'[process_indicator_data] Used coeffs - before: {used_coeff_before}, prev: {used_coeff_prev}, current: {used_coeff_current}')
        
        coeff_before = indicator_usage.coeff_before_prev
        coeff_prev = indicator_usage.coeff_prev
        coeff_current = indicator_usage.coeff_current
        
    else:
        if coeff_editable:
            coeff_before = parse_coeff(custom_coeff_before)
            coeff_prev = parse_coeff(custom_coeff_prev)
            coeff_current = parse_coeff(custom_coeff_current)
        else:
            coeff_before = coeff_prev = coeff_current = None

        current_app.logger.info(f'[process_indicator_data] Create mode: parsed coeffs - before: {coeff_before}, prev: {coeff_prev}, current: {coeff_current}')

        if coeff_before is not None and coeff_before == indicator.CoeffToTut:
            coeff_before = None
            current_app.logger.info('[process_indicator_data] coeff_before equals standard, set to None')
        if coeff_prev is not None and coeff_prev == indicator.CoeffToTut:
            coeff_prev = None
            current_app.logger.info('[process_indicator_data] coeff_prev equals standard, set to None')
        if coeff_current is not None and coeff_current == indicator.CoeffToTut:
            coeff_current = None
            current_app.logger.info('[process_indicator_data] coeff_current equals standard, set to None')
        
        used_coeff_before = coeff_before if coeff_before is not None else indicator.CoeffToTut
        used_coeff_prev = coeff_prev if coeff_prev is not None else indicator.CoeffToTut
        used_coeff_current = coeff_current if coeff_current is not None else indicator.CoeffToTut
        
        current_app.logger.info(f'[process_indicator_data] Used coeffs - before: {used_coeff_before}, prev: {used_coeff_prev}, current: {used_coeff_current}')
    
    QYearBeforePrev = to_decimal_2(QYearBeforePrev_ed * used_coeff_before) if QYearBeforePrev_ed is not None else None
    QYearPrev = to_decimal_2(QYearPrev_ed * used_coeff_prev) if QYearPrev_ed is not None else None
    QYearCurrent = to_decimal_2(QYearCurrent_ed * used_coeff_current) if QYearCurrent_ed is not None else None
    
    current_app.logger.info(f'[process_indicator_data] Calculated values - before: {QYearBeforePrev}, prev: {QYearPrev}, current: {QYearCurrent}')
    
    if indicator.is_custom and fuel_category:
        if fuel_category == 'local':
            is_local_value = True
            is_renewable_value = False
        elif fuel_category == 'renewable':
            is_local_value = False
            is_renewable_value = True
        else:
            is_local_value = False
            is_renewable_value = False
    else:
        is_local_value = indicator.is_local
        is_renewable_value = indicator.is_renewable
    
    result = {
        'QYearBeforePrev': QYearBeforePrev,
        'QYearPrev': QYearPrev,
        'QYearCurrent': QYearCurrent,
        'coeff_before_prev': coeff_before,
        'coeff_prev': coeff_prev,
        'coeff_current': coeff_current,
        'is_local': is_local_value,
        'is_renewable': is_renewable_value,
        'note': name_other
    }
    
    current_app.logger.info(f'[process_indicator_data] Final result: {result}')
    
    return result, None

def _is_ajax_request():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _indicator_action_response(token, message, category='success'):
    """Единый ответ для create/edit/delete-indicator: обычная форма — как
    раньше, flash + редирект на всю страницу; запрос от JS (см.
    indicator-calc.js) — JSON, без редиректа, чтобы обновить только саму
    таблицу показателей и не сбрасывать прокрутку страницы к началу."""
    if _is_ajax_request():
        return jsonify({'success': category != 'error', 'message': message}), (400 if category == 'error' else 200)
    flash(message, category)
    return redirect(url_for('plan_bp.plan_indicators', token=token))


@plan_bp.route('/create-indicator/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
@historical_forbidden
@org_head_forbidden
@reader_forbidden
def create_indicator(token):
    try:
        current_plan = g.current_plan
        
        QYearBeforePrev_ed = to_decimal_2(request.form.get('QYearBeforePrev'))
        QYearPrev_ed = to_decimal_2(request.form.get('QYearPrev'))
        QYearCurrent_ed = to_decimal_2(request.form.get('QYearCurrent'))
        id_indicator = request.form.get('id_indicator')
        fuel_category = request.form.get('fuel_category')
        name_other = str(request.form.get('name_other'))
        
        custom_coeff_before = request.form.get('custom_coeff_before')
        custom_coeff_prev = request.form.get('custom_coeff_prev')
        custom_coeff_current = request.form.get('custom_coeff_current')

        current_app.logger.info(f'[create_indicator] Raw form data - coeff_before: {custom_coeff_before}, coeff_prev: {custom_coeff_prev}, coeff_current: {custom_coeff_current}')

        if not id_indicator:
            current_app.logger.warning('Empty indicator')
            return _indicator_action_response(token, 'Пустой показатель', 'error')

        indicator = Indicator.query.filter_by(id=id_indicator).first()

        if not indicator:
            current_app.logger.warning(f'Indicator with id {id_indicator} not found')
            return _indicator_action_response(token, 'Показатель не найден', 'error')

        data, error = process_indicator_data(
            indicator, QYearBeforePrev_ed, QYearPrev_ed, QYearCurrent_ed,
            custom_coeff_before, custom_coeff_prev, custom_coeff_current,
            fuel_category, name_other
        )

        if error:
            return _indicator_action_response(token, error, 'error')

        new_IndicatorUsage = IndicatorUsage(
            id_plan=current_plan.id,
            id_indicator=id_indicator,
            QYearBeforePrev=data['QYearBeforePrev'],
            QYearPrev=data['QYearPrev'],
            QYearCurrent=data['QYearCurrent'],
            coeff_before_prev=data['coeff_before_prev'],
            coeff_prev=data['coeff_prev'],
            coeff_current=data['coeff_current'],
            is_local=data['is_local'],
            is_renewable=data['is_renewable'],
            note=data['note']
        )
        
        db.session.add(new_IndicatorUsage)
        db.session.commit()

        other_data_indicatorUpdate(current_plan.id)
        update_ChangeTimePlan(current_plan.id)
        
        current_app.logger.info(f'Successfully created indicator usage with id {new_IndicatorUsage.id} for plan {current_plan.id}')
        return _indicator_action_response(token, 'Показатель добавлен')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating indicator: {str(e)}', exc_info=True)
        return _indicator_action_response(token, f'Ошибка при добавлении показателя: {str(e)}', 'error')


@plan_bp.route('/edit-indicator/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
@historical_forbidden
@org_head_forbidden
@reader_forbidden
def edit_indicator(token):
    try:
        id_indicator = request.form.get('id_indicator')

        if not id_indicator:
            return _indicator_action_response(token, 'ID показателя не указан', 'error')

        indicator_usage = IndicatorUsage.query.get_or_404(id_indicator)
        current_plan = g.current_plan

        if indicator_usage.id_plan != current_plan.id:
            return _indicator_action_response(token, 'Показатель не принадлежит указанному плану', 'error')
        
        indicator = indicator_usage.indicator
        indicator_code = indicator.code
        
        QYearBeforePrev_ed = to_decimal_2(request.form.get('QYearBeforePrev'))
        QYearPrev_ed = to_decimal_2(request.form.get('QYearPrev'))
        QYearCurrent_ed = to_decimal_2(request.form.get('QYearCurrent'))
        fuel_category = request.form.get('fuel_category')
        name_other = str(request.form.get('name_other'))
        
        custom_coeff_before = request.form.get('custom_coeff_before')
        custom_coeff_prev = request.form.get('custom_coeff_prev')
        custom_coeff_current = request.form.get('custom_coeff_current')
        
        current_app.logger.info(f'[edit_indicator] Raw form data - coeff_before: {custom_coeff_before}, coeff_prev: {custom_coeff_prev}, coeff_current: {custom_coeff_current}')
        current_app.logger.info(f'[edit_indicator] Current indicator usage coeffs before update - before: {indicator_usage.coeff_before_prev}, prev: {indicator_usage.coeff_prev}, current: {indicator_usage.coeff_current}')
        
        data, error = process_indicator_data(
            indicator, QYearBeforePrev_ed, QYearPrev_ed, QYearCurrent_ed,
            custom_coeff_before, custom_coeff_prev, custom_coeff_current,
            fuel_category, name_other, is_edit=True, indicator_usage=indicator_usage
        )
        
        if error:
            return _indicator_action_response(token, error, 'error')

        is_codes_9911_9914 = indicator_code in ['9911', '9912', '9913', '9914']

        if is_codes_9911_9914:
            # 9911-9914 — экономия ТЭР от мероприятий предыдущего года
            # внедрения нарастающим итогом (январь-март/июнь/сентябрь/декабрь).
            # Каждый следующий период обязан быть >= предыдущего, иначе
            # получится отрицательный вклад квартала, чего быть не может.
            period_order = ['9911', '9912', '9913', '9914']
            period_labels = {
                '9911': 'январь-март',
                '9912': 'январь-июнь',
                '9913': 'январь-сентябрь',
                '9914': 'январь-декабрь',
            }

            period_values = {}
            for code in period_order:
                if code == indicator_code:
                    period_values[code] = data['QYearCurrent']
                    continue
                sibling_usage = next(
                    (iu for iu in current_plan.indicators_usage if iu.indicator.code == code),
                    None
                )
                period_values[code] = to_decimal_2(sibling_usage.QYearCurrent) if sibling_usage else to_decimal_2(0)

            for i in range(1, len(period_order)):
                prev_code = period_order[i - 1]
                curr_code = period_order[i]
                if period_values[curr_code] < period_values[prev_code]:
                    return _indicator_action_response(
                        token,
                        f'Экономия ТЭР за {period_labels[curr_code]} ({period_values[curr_code]}) не может быть меньше, '
                        f'чем за {period_labels[prev_code]} ({period_values[prev_code]}) — значения вводятся нарастающим итогом.',
                        'error'
                    )

            indicator_usage.QYearCurrent = data['QYearCurrent']
        else:
            indicator_usage.QYearBeforePrev = data['QYearBeforePrev']
            indicator_usage.QYearPrev = data['QYearPrev']
            indicator_usage.QYearCurrent = data['QYearCurrent']
        
        indicator_usage.is_local = data['is_local']
        indicator_usage.is_renewable = data['is_renewable']
        indicator_usage.note = data['note']
        
        db.session.commit()
        
        saved = IndicatorUsage.query.get(id_indicator)
        current_app.logger.info(f'[edit_indicator] SAVED IN DB - coeff_before_prev: {saved.coeff_before_prev}, coeff_prev: {saved.coeff_prev}, coeff_current: {saved.coeff_current}')
        current_app.logger.info(f'[edit_indicator] SAVED IN DB - QYearBeforePrev: {saved.QYearBeforePrev}, QYearPrev: {saved.QYearPrev}, QYearCurrent: {saved.QYearCurrent}')
        
        other_data_indicatorUpdate(current_plan.id)
        update_ChangeTimePlan(current_plan.id)
        
        current_app.logger.info(f'Successfully updated indicator usage {id_indicator} for plan {current_plan.id}')
        return _indicator_action_response(token, 'Показатель успешно обновлен')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error editing indicator: {str(e)}', exc_info=True)
        return _indicator_action_response(token, f'Ошибка при редактировании показателя: {str(e)}', 'error')
    
    
@plan_bp.route('/delete-indicator/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
@reader_forbidden
def delete_indicator(id):
    indicator = IndicatorUsage.query.get_or_404(id)
    current_plan = Plan.query.get_or_404(indicator.id_plan)

    if current_plan.is_historical:
        return _indicator_action_response(current_plan.token, 'Это архивная версия плана — только для просмотра', 'error')

    from website.utils.plans import plan_edit_denial
    denial = plan_edit_denial(current_user, current_plan)
    if denial:
        return _indicator_action_response(current_plan.token, denial, 'error')

    db.session.delete(indicator)
    db.session.commit()
    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)

    return _indicator_action_response(current_plan.token, 'Показатель успешно удален')

@plan_bp.route('/events-<event_type>/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_event(event_type, token):
    if event_type not in ['saving', 'increase']:
        abort(404)
    
    current_plan = g.current_plan
    
    period_codes = ['0001', '0002', '0003', '0004']

    if event_type == 'saving':
        type_filter = Direction.is_econom == True
        directions = Direction.query.filter(
            Direction.is_econom == True,
            Direction.code.notin_(period_codes),
            Direction.DateEnd.is_(None)
        ).order_by(Direction.id.asc()).all()
        title = "Мероприятия по экономии ТЭР"
        
        has_events = Event.query.filter(
            Event.id_plan == current_plan.id,
            Event.is_econom == True,
            Event.is_increase == False,
            Event.display_code.notin_(period_codes)
        ).first() is not None
    else:
        type_filter = Direction.is_increase == True
        directions = Direction.query.filter(
            Direction.is_increase == True,
            Direction.code.notin_(period_codes),
            Direction.DateEnd.is_(None)
        ).order_by(Direction.id.asc()).all()
        title = "Мероприятия по увеличению использования МТЭР и ВИЭ"
        
        has_events = Event.query.filter(
            Event.id_plan == current_plan.id,
            Event.is_econom == False,
            Event.is_increase == True,
            Event.display_code.notin_(period_codes)
        ).first() is not None

    return render_template('plan_events.html',  
                        title=title,
                        event_type=event_type,
                        plan=current_plan, 
                        hide_header=False,
                        directions=directions,
                        # SendModal=current_plan.is_control,
                        context_menu=True,
                        has_events=has_events
                    )
    
def update_period_eff_values(plan_id, event_type):
    period_codes = ['0001', '0002', '0003', '0004']
    
    if event_type == 'saving':
        period_event = Event.query.filter(
            Event.id_plan == plan_id,
            Event.display_code == '0004',
            Event.is_econom == True,
            Event.is_increase == False
        ).first()
        
        if period_event:
            all_events_sum = Event.query.filter(
                Event.id_plan == plan_id,
                Event.is_econom == True,
                Event.is_increase == False,
                Event.display_code.notin_(period_codes)
            ).with_entities(func.sum(Event.EffCurrYear)).scalar() or 0
            
            period_event.EffCurrYear = all_events_sum
            db.session.commit()
            current_app.logger.info(f'Updated period 0004 EffCurrYear for plan_id={plan_id}, event_type={event_type}')
    else:
        period_event = Event.query.filter(
            Event.id_plan == plan_id,
            Event.display_code == '0004',
            Event.is_econom == False,
            Event.is_increase == True
        ).first()
        
        if period_event:
            all_events_sum = Event.query.filter(
                Event.id_plan == plan_id,
                Event.is_econom == False,
                Event.is_increase == True,
                Event.display_code.notin_(period_codes)
            ).with_entities(func.sum(Event.EffCurrYear)).scalar() or 0
            
            period_event.EffCurrYear = all_events_sum
            db.session.commit()
            current_app.logger.info(f'Updated period 0004 EffCurrYear for plan_id={plan_id}, event_type={event_type}')
            
def _event_action_response(message, category='success', event_type=None, token=None):
    """Единый ответ для create/edit/delete-event — тот же принцип, что и
    _indicator_action_response: обычная форма получает flash + редирект,
    как раньше, а запрос от JS (см. events.js) — JSON без редиректа, чтобы
    обновлялась только сама таблица мероприятий, без перезагрузки всей
    страницы плана."""
    if _is_ajax_request():
        return jsonify({'success': category != 'error', 'message': message}), (400 if category == 'error' else 200)
    flash(message, category)
    if event_type and token:
        return redirect(url_for('plan_bp.plan_event', event_type=event_type, token=token))
    return redirect(request.referrer or url_for('views.plans'))


@plan_bp.route('/create-event/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
@historical_forbidden
@org_head_forbidden
@reader_forbidden
def create_event(token):
    current_plan = g.current_plan
    
    id_direction = request.form.get('id_direction')
    event_type = request.form.get('event_type')
    
    direction = Direction.query.get(id_direction)
    if not direction:
        current_app.logger.warning(f'Direction not found: id_direction={id_direction}, plan_id={current_plan.id}')
        return _event_action_response('Направление не найдено', 'error', event_type, token)

    try:
        check_and_create_period_directions(current_plan.id, event_type)

        event_data = process_event_data(current_plan, direction, event_type, request.form)
        new_event = create_event_record(current_plan, direction, event_data)

        db.session.add(new_event)
        db.session.flush()

        teo_file = request.files.get('teo_file')
        if teo_file and teo_file.filename:
            save_teo_file(new_event, teo_file)

        db.session.commit()

        if event_data['is_double_effect'] and event_type == 'increase':
            update_double_effect_payback(current_plan.id, direction.id)

        other_data_indicatorUpdate(current_plan.id)
        update_period_eff_values(current_plan.id, event_type)
        current_app.logger.info(f'Event created successfully: id={new_event.id}, plan_id={current_plan.id}, direction_id={id_direction}')

        return _event_action_response('Мероприятие добавлено', 'success', event_type, token)

    except ValueError as e:
        db.session.rollback()
        current_app.logger.error(f'ValueError creating event for plan_id={current_plan.id}: {str(e)}')
        return _event_action_response(str(e), 'error', event_type, token)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating event for plan_id={current_plan.id}: {str(e)}', exc_info=True)
        return _event_action_response('Ошибка при добавлении мероприятия', 'error', event_type, token)

@plan_bp.route('/edit-event/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
@reader_forbidden
def edit_event(id):
    try:
        current_app.logger.info(f'Starting edit event with id={id}')
        
        current_event = Event.query.get(id)
        if not current_event:
            current_app.logger.warning(f'Event with id={id} not found')
            return _event_action_response('Мероприятие не найдено', 'error')

        current_plan = Plan.query.get(current_event.id_plan)
        if not current_plan:
            current_app.logger.warning(f'Plan with id={current_event.id_plan} not found')
            return _event_action_response('План не найден', 'error')

        if current_plan.is_historical:
            return _event_action_response('Это архивная версия плана — только для просмотра', 'error')

        from website.utils.plans import plan_edit_denial
        denial = plan_edit_denial(current_user, current_plan)
        if denial:
            return _event_action_response(denial, 'error')

        event_type = request.form.get('event_type') or 'saving'
        edit_type = request.form.get('edit_type') or 'full'
        
        if edit_type == 'period':
            eff_curr_year_str = request.form.get('EffCurrYear')
            if eff_curr_year_str and eff_curr_year_str.strip():
                EffCurrYear = to_decimal_2(eff_curr_year_str)
            else:
                EffCurrYear = to_decimal_2('0')
            
            period_code = current_event.direction.code if current_event.direction else None
            
            if period_code in ['0001', '0002', '0003', '0004']:
                error_message = validate_period_values(
                    plan_id=current_plan.id,
                    current_period_code=period_code,
                    current_value=EffCurrYear,
                    exclude_event_id=id,
                    is_increase=bool(current_event.is_increase),
                )
                
                if error_message:
                    return _event_action_response(error_message, 'error', event_type, current_plan.token)

            current_event.EffCurrYear = EffCurrYear
            current_app.logger.info(f'Updated period EffCurrYear for event {id}: {EffCurrYear}')
            
        else:
            name = request.form.get('name') or None
            Volume_value = request.form.get('Volume')
            ExpectedQuarter_value = request.form.get('ExpectedQuarter')
            EffTut = to_decimal_2(request.form.get('EffTut'))
            EffCurrYear = to_decimal_2(request.form.get('EffCurrYear'))

            # При объёме внедрения = 1 мероприятие не может внедряться "в
            # течение" нескольких кварталов — только в одном конкретном.
            if Volume_value and ExpectedQuarter_value and '-' in ExpectedQuarter_value:
                try:
                    volume_int = int(float(Volume_value))
                except (TypeError, ValueError):
                    volume_int = None
                if volume_int == 1:
                    return _event_action_response(
                        'При объёме внедрения, равном 1, ожидаемый срок внедрения мероприятия должен '
                        'быть одним конкретным кварталом (1, 2, 3 или 4), а не диапазоном.',
                        'error', event_type, current_plan.token
                    )

            event_category = request.form.get('event_category')
            current_app.logger.info(f'event_category from form: {event_category}')
            
            if event_category == 'local':
                is_local = True
                is_corrected = False
            elif event_category == 'corrected':
                is_local = False
                is_corrected = True
            else:
                is_local = True
                is_corrected = False
            
            current_app.logger.info(f'is_local={is_local}, is_corrected={is_corrected}')
            
            is_double_effect = current_event.is_econom and current_event.is_increase
            
            if is_double_effect and current_event.is_econom:
                BudgetState = BudgetRep = BudgetLoc = BudgetOther = MoneyOwn = MoneyLoan = MoneyOther = 0
                VolumeFinCurrentYear = 0
                ObchVolumeFin = 0
                
                USD_RATE = float(current_plan.usd_rate) if current_plan.usd_rate else 2.75
                COST_PER_TOE_USD = float(current_plan.cost_per_toe_usd) if current_plan.cost_per_toe_usd else 260.0
                EffRub = int(float(EffTut) * COST_PER_TOE_USD * USD_RATE)
                Payback = to_decimal_1(0)
                
                current_app.logger.info(f'Double effect saving event: financing blocked')
                
            else:
                ObchVolumeFin = to_decimal_2(request.form.get('ObchVolumeFin'))
                BudgetState = to_decimal_2(request.form.get('BudgetState'))
                BudgetRep = to_decimal_2(request.form.get('BudgetRep'))
                BudgetLoc = to_decimal_2(request.form.get('BudgetLoc'))
                BudgetOther = to_decimal_2(request.form.get('BudgetOther'))
                MoneyOwn = to_decimal_2(request.form.get('MoneyOwn'))
                MoneyLoan = to_decimal_2(request.form.get('MoneyLoan'))
                MoneyOther = to_decimal_2(request.form.get('MoneyOther'))

                VolumeFinCurrentYear = BudgetState + BudgetRep + BudgetLoc + BudgetOther + MoneyOwn + MoneyLoan + MoneyOther

                # Код 1013 в Части 2 ("Замена неэкономичных котлов и печей...")
                # — графы 7 (EffRub) и 10 (Payback) заполняются напрямую
                # юрлицом, не по формуле.
                direction_code = current_event.direction.code if current_event.direction else None
                is_manual_eff_rub = current_event.is_econom and not current_event.is_increase and direction_code == '1013'

                if is_manual_eff_rub:
                    EffRub = int(to_decimal_2(request.form.get('EffRub')))
                else:
                    USD_RATE = float(current_plan.usd_rate) if current_plan.usd_rate else 2.75
                    COST_PER_TOE_USD = float(current_plan.cost_per_toe_usd) if current_plan.cost_per_toe_usd else 260.0
                    EffRub = int(float(EffTut) * COST_PER_TOE_USD * USD_RATE)

                if is_manual_eff_rub or current_event.is_increase:
                    # Графа 10 в Части 3 (для всех направлений) и в Части 2
                    # по коду 1013 — тоже напрямую от юрлица, не по формуле.
                    Payback = to_decimal_1(request.form.get('Payback'))
                elif EffRub > 0:
                    payback_value = float(ObchVolumeFin) / float(EffRub)
                    if payback_value < 0.01:
                        Payback = to_decimal_1(0.1)
                    else:
                        Payback = to_decimal_1(payback_value)
                else:
                    Payback = to_decimal_1(0)

                current_app.logger.info(f'Regular event calculation: EffRub={EffRub}, Payback={Payback}')

            Volume = int(float(Volume_value)) if Volume_value and Volume_value.strip() else None
            ExpectedQuarter = ExpectedQuarter_value if ExpectedQuarter_value and ExpectedQuarter_value.strip() else None
            
            current_event.name = name
            current_event.Volume = Volume
            current_event.ExpectedQuarter = ExpectedQuarter
            current_event.EffTut = EffTut
            current_event.EffRub = EffRub
            current_event.EffCurrYear = EffCurrYear
            current_event.Payback = Payback
            current_event.ObchVolumeFin = ObchVolumeFin
            current_event.VolumeFinCurrentYear = VolumeFinCurrentYear
            current_event.BudgetState = BudgetState
            current_event.BudgetRep = BudgetRep
            current_event.BudgetLoc = BudgetLoc
            current_event.BudgetOther = BudgetOther
            current_event.MoneyOwn = MoneyOwn
            current_event.MoneyLoan = MoneyLoan
            current_event.MoneyOther = MoneyOther
            current_event.is_local = is_local
            current_event.is_corrected = is_corrected

            teo_file = request.files.get('teo_file')
            if teo_file and teo_file.filename:
                save_teo_file(current_event, teo_file)

            current_app.logger.info(f'Updated all fields for event {id}, is_local={is_local}, is_corrected={is_corrected}')

        db.session.commit()
        
        if current_event.is_econom and current_event.is_increase and not current_event.is_econom:
            update_double_effect_payback(current_plan.id, current_event.id_direction)
        
        other_data_indicatorUpdate(current_plan.id)
        update_period_eff_values(current_plan.id, event_type)

        current_app.logger.info(f'Event {id} updated successfully')

        return _event_action_response('Мероприятие изменено', 'success', event_type, current_plan.token)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error editing event {id}: {str(e)}', exc_info=True)
        return _event_action_response(f'Ошибка при редактировании мероприятия: {str(e)}', 'error')

@plan_bp.route('/delete-eventes/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
@reader_forbidden
def delete_eventes(id):
    current_event = Event.query.get_or_404(id)
    current_plan = Plan.query.get_or_404(current_event.id_plan)

    if current_plan.is_historical:
        return _event_action_response('Это архивная версия плана — только для просмотра', 'error')

    from website.utils.plans import plan_edit_denial
    denial = plan_edit_denial(current_user, current_plan)
    if denial:
        return _event_action_response(denial, 'error')

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
        
    update_period_eff_values(current_plan.id, event_type)
    other_data_indicatorUpdate(current_plan.id)
    return _event_action_response('Мероприятие успешно удалено', 'success', event_type, current_plan.token)

@plan_bp.route('/event/<int:id>/teo', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
def get_event_teo(id):
    """Отдаёт файл ТЭО мероприятия. ?download=1 — принудительное скачивание
    (Content-Disposition: attachment), иначе — показ прямо в браузере (для
    .pdf) там, где это возможно."""
    current_event = Event.query.get_or_404(id)
    if not current_event.teo_filename:
        abort(404)

    folder = current_app.config['TEO_UPLOAD_FOLDER']
    as_attachment = request.args.get('download') == '1'

    return send_from_directory(
        folder,
        current_event.teo_filename,
        as_attachment=as_attachment,
        download_name=current_event.teo_original_name or current_event.teo_filename
    )

@plan_bp.route('/event/<int:id>/teo', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
@reader_forbidden
def upload_event_teo(id):
    """Прикрепление/замена файла ТЭО прямо из графы 20 таблицы мероприятий,
    без открытия модалки редактирования."""
    current_event = Event.query.get_or_404(id)

    if current_event.plan.is_historical:
        return jsonify({'success': False, 'message': 'Это архивная версия плана — только для просмотра'}), 403

    from website.utils.plans import plan_edit_denial
    denial = plan_edit_denial(current_user, current_event.plan)
    if denial:
        return jsonify({'success': False, 'message': denial}), 403

    teo_file = request.files.get('teo_file')
    if not teo_file or not teo_file.filename:
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400

    try:
        save_teo_file(current_event, teo_file)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Файл ТЭО прикреплён',
            'teo_original_name': current_event.teo_original_name
        })
    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error uploading TEO file for event {id}: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': 'Ошибка при загрузке файла ТЭО'}), 400

@plan_bp.route('/event/<int:id>/teo', methods=['DELETE'])
@user_with_all_params()
@login_required
@session_required
@reader_forbidden
def delete_event_teo(id):
    current_event = Event.query.get_or_404(id)

    if current_event.plan.is_historical:
        return jsonify({'success': False, 'message': 'Это архивная версия плана — только для просмотра'}), 403

    from website.utils.plans import plan_edit_denial
    denial = plan_edit_denial(current_user, current_event.plan)
    if denial:
        return jsonify({'success': False, 'message': denial}), 403

    try:
        delete_teo_file(current_event)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Файл ТЭО удалён'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting TEO file for event {id}: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': 'Ошибка при удалении файла ТЭО'}), 400

@plan_bp.route('/change-status/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@historical_forbidden
@reader_forbidden
def api_change_plan_status(token):
    plan = Plan.query.filter_by(token=token).first()
    
    if request.is_json:
        data = request.get_json()
        status = data.get('status')
        coordinator_ids = data.get('coordinator_ids', '').split(',') if data.get('coordinator_ids') else []
        approver_id = data.get('approver_id')
        reason = data.get('reason')
    else:
        status = request.form.get('status')
        coordinator_ids = request.form.get('coordinator_ids', '').split(',') if request.form.get('coordinator_ids') else []
        approver_id = request.form.get('approver_id')
        reason = request.form.get('reason')
    
    if not status:
        if request.is_json:
            return jsonify({'error': 'Статус не указан'}), 400
        else:
            flash('Статус не указан', 'error')
            return redirect(request.referrer or url_for('views.plans'))

    from website.utils.plans import plan_edit_denial
    control_denial = plan_edit_denial(current_user, plan) if status == 'control' else None
    if control_denial:
        message = control_denial
        if request.is_json:
            return jsonify({'error': message}), 403
        else:
            flash(message, 'error')
            return redirect(request.referrer or url_for('plan_bp.plan_actions', token=token))
    
    from website.utils.status_plan import (
        handle_sent_status,
        handle_approved_status,
        handle_sent_without_check_status,
        handle_draft_status,
        handle_control_status,
        handle_error_status
    )
    
    status_handlers = {
        'sent': handle_sent_status,
        'approved': handle_approved_status,
        'sent_without_check': handle_sent_without_check_status,
        'draft': handle_draft_status,
        'control': handle_control_status,
        'error': handle_error_status
    }
    
    if status not in status_handlers:
        if request.is_json:
            return jsonify({'error': 'Неверный статус'}), 400
        else:
            flash('Неверный статус', 'error')
            return redirect(request.referrer or url_for('views.plans'))
    
    # «Отправить на согласование» и «Отменить отправку» — обе доступны
    # всем ролям организации-разработчика, КРОМЕ Исполнителя (он готовит
    # план, но официально отправляет/отзывает его только руководитель
    # структурного подразделения или организации). status='draft' сюда
    # приходит только из этой самой кнопки (plan_actions.html :: cancelSendForm),
    # больше ниоткуда — см. grep по "status" value="draft" перед правкой.
    if status in ('sent', 'draft') and current_user.org_role == 'executor' and plan.org_id == current_user.organization_id:
        message = 'Исполнитель не может отправлять план на согласование или отменять отправку'
        if request.is_json:
            return jsonify({'error': message}), 403
        flash(message, 'error')
        return redirect(request.referrer or url_for('plan_bp.plan_actions', token=token))

    # ТЗ п.3.3/п.6: внешняя отправка — только «Подписать и отправить»
    # (internal_sign, ЭЦП + отправка одной транзакцией). Прямой status=sent
    # раньше пропускал любого не-исполнителя организации, даже если план
    # никто не подписывал или он лежал у другого подписанта. Оставлен
    # только как запасной путь для уже подписанного плана тем же
    # подписантом (или администратором).
    if status == 'sent' and not current_user.is_admin and not (
        plan.is_signed and plan.internal_signed_by_user_id == current_user.id
        and plan.pending_signer_user_id == current_user.id
    ):
        message = 'Отправить план можно только кнопкой «Подписать и отправить» — после подписи ЭЦП'
        if request.is_json:
            return jsonify({'error': message}), 403
        flash(message, 'error')
        return redirect(request.referrer or url_for('plan_bp.plan_actions', token=token))

    handler = status_handlers[status]

    if status == 'sent':
        result = handler(plan, coordinator_ids, approver_id)
    elif status == 'approved':
        result = handler(plan, current_user)
    elif status == 'sent_without_check':
        # TODO: "Отменить изменения" на этапах согласования/утверждения
        # временно отключена (см. get_audit_context::can_cancel) — кнопка
        # скрыта, но дублируем запрет и здесь на случай прямого запроса.
        error_msg = 'Отмена изменений на этапах согласования/утверждения временно недоступна'
        if request.is_json:
            return jsonify({'error': error_msg}), 403
        flash(error_msg, 'error')
        return redirect(request.referrer or url_for('plan_bp.plan_actions', token=plan.token))
        # Отмена проверяющим своего подтверждения этапа — тоже требует
        # письменного обоснования, по аналогии с отменой отправки
        # разработчиком (status == 'draft' ниже); причина попадёт в
        # сообщения по плану (см. handle_sent_without_check_status).
        # if not (reason and reason.strip()):
        #     error_msg = 'Укажите причину отмены своего согласования'
        #     if request.is_json:
        #         return jsonify({'error': error_msg}), 400
        #     flash(error_msg, 'error')
        #     return redirect(request.referrer or url_for('plan_bp.plan_actions', token=plan.token))
        # result = handler(plan, current_user, reason)
    elif status == 'draft':
        # "Отменить отправку" (план уже был отправлен) обязательно требует
        # причину — она попадёт в "Подписи" отдельной строкой в конце
        # списка. Сброс из любого другого статуса в "В редакции" причины
        # не требует (reason тогда просто не используется обработчиком).
        # Отменить реальную внешнюю отправку можно только первые 5 минут
        # после неё (plan.sent_time) — дальше кнопка и на клиенте
        # неактивна (см. cancelSendBtn/data-sent-at в plan_actions.html),
        # здесь — источник истины на случай прямого запроса.
        # Причина больше не нужна — отмена отправки теперь просто откат
        # «Подписать и отправить» без следов в «Подписях» (см.
        # handle_draft_status).
        if plan.is_sent and (not plan.sent_time or (current_utc_time() - plan.sent_time) > timedelta(minutes=5)):
            error_msg = 'Отменить отправку можно только в течение 5 минут после отправки'
            if request.is_json:
                return jsonify({'error': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(request.referrer or url_for('plan_bp.plan_actions', token=plan.token))
        result = handler(plan)
    elif status == 'error':
        result = handler(plan, current_user)
    else:
        result = handler(plan)
    
    if request.is_json:
        if isinstance(result, dict) and "error" in result:
            return jsonify({'error': result['error']}), 400

        response_data = {'message': result if isinstance(result, str) else result.get('message'), 'status': status}

        # Кнопки "Есть ошибки"/"Согласовать"/"Отменить изменения" в
        # tickets-actions-bar (plan_actions.html) шлют сюда AJAX и сами
        # перерисовывают себя без перезагрузки страницы — для этого нужен
        # не только текст сообщения, но и свежий HTML бейджа статуса плана
        # и панели чата (can_audit/can_cancel меняются сразу после смены
        # статуса, см. get_audit_context).
        if status in ('error', 'approved', 'sent_without_check'):
            from website.utils.plans import get_audit_context
            ctx = get_audit_context(plan, current_user)
            status_html = render_template_string(
                '''{% import 'macros/components.html' as components %}
                {{ components.status_plan(plan, current_user) }}''',
                plan=plan, current_user=current_user,
            )
            tickets_html = render_template_string(
                '''{% import 'macros/components.html' as components %}
                {{ components.tickets_container(plan, current_user, can_audit, has_remarks, approve_label, can_cancel) }}''',
                plan=plan, current_user=current_user,
                can_audit=ctx['can_audit'], has_remarks=ctx['has_remarks'],
                approve_label=ctx['approve_label'], can_cancel=ctx['can_cancel'],
            )
            footer_html = render_template_string(
                '''{% import 'macros/components.html' as components %}
                {{ components.plan_review_footer(plan, current_user, can_audit, has_remarks, approve_label) }}''',
                plan=plan, current_user=current_user,
                can_audit=ctx['can_audit'], has_remarks=ctx['has_remarks'],
                approve_label=ctx['approve_label'],
            )
            response_data.update({
                'status_html': status_html,
                'tickets_html': tickets_html,
                'footer_html': footer_html,
                'has_remarks': ctx['has_remarks'],
            })

        return jsonify(response_data)
    else:
        if isinstance(result, dict) and "error" in result:
            flash(result['error'], 'error')
            return redirect(request.referrer or url_for('views.plans'))
        message = result if isinstance(result, str) else result.get('message', 'Статус изменен')
        flash(message, 'success')
        if status in ['approved', 'error']:
            return redirect(request.referrer or url_for('views.plans'))
        if status in ['sent_without_check']:
            return redirect(request.referrer)
        if status == 'control':
            return redirect(url_for('plan_bp.plan_actions', token=plan.token))
        else:
            return redirect(url_for('plan_bp.plan_review', token=plan.token))


@plan_bp.route('/admin-set-approval-step/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
def api_admin_set_approval_step(token):
    """Только для администраторов: подтвердить или отменить произвольный
    этап согласования плана (см. handle_admin_confirm_step /
    handle_admin_cancel_step для деталей и нюансов)."""
    if not current_user.is_admin:
        if request.is_json:
            return jsonify({'error': 'Доступно только администраторам'}), 403
        flash('Доступно только администраторам', 'error')
        return redirect(request.referrer or url_for('views.plans'))

    plan = g.current_plan

    if request.is_json:
        data = request.get_json()
        path_id = data.get('path_id')
        action = data.get('action')
    else:
        path_id = request.form.get('path_id')
        action = request.form.get('action')

    if not path_id or action not in ('confirm', 'cancel'):
        error = 'Не указан этап или действие'
        if request.is_json:
            return jsonify({'error': error}), 400
        flash(error, 'error')
        return redirect(request.referrer or url_for('plan_bp.plan_review', token=token))

    from website.utils.status_plan import handle_admin_confirm_step, handle_admin_cancel_step

    handler = handle_admin_confirm_step if action == 'confirm' else handle_admin_cancel_step
    result = handler(plan, path_id, current_user)

    if request.is_json:
        if isinstance(result, dict) and 'error' in result:
            return jsonify({'error': result['error']}), 400
        return jsonify({'message': result.get('message')})

    if isinstance(result, dict) and 'error' in result:
        flash(result['error'], 'error')
    else:
        flash(result.get('message', 'Готово'), 'success')
    return redirect(request.referrer or url_for('plan_bp.plan_review', token=token))