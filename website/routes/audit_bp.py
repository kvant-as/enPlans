import logging
from datetime import timedelta
from flask import Blueprint, current_app, flash, redirect, request, g, jsonify, render_template_string, abort, send_from_directory
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
from flask import send_file
import os

from website.routes.views import owner_only, reader_forbidden
from website.sessions import session_required
from common_models import current_utc_time
from website.models import Plan, PlanTicket, PlanApprovalPath
from website import db
from .auth import user_with_all_params
        
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import platform

audit_bp = Blueprint('audit_bp', __name__, url_prefix='/')
logger = logging.getLogger(__name__)

@audit_bp.route('/print-tickets/<token>', methods=['GET'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def print_tickets(token):
    try:
        current_plan = Plan.query.filter_by(token=token).first()
        
        if not current_plan:
            flash('План не найден', 'error')
            return redirect(request.referrer)
        
        tickets = PlanTicket.query.filter_by(plan_id=current_plan.id).order_by(PlanTicket.begin_time.asc()).all()
        
        if not tickets:
            flash('Нет квитанций для печати', 'error')
            return redirect(request.referrer)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        elements = []
        
        if platform.system() == 'Windows':
            font_path = 'C:/Windows/Fonts/arial.ttf'
        elif platform.system() == 'Linux':
            font_path = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
        else:
            font_path = '/System/Library/Fonts/Helvetica.ttc'
        
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('CustomFont', font_path))
            font_name = 'CustomFont'
        else:
            font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'fonts', 'Montserrat-Regular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                font_name = 'CustomFont'
            else:
                font_name = 'Helvetica'
        
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.HexColor('#00798f'),
            fontName=font_name
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading2'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=12,
            fontName=font_name
        )
        
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER,
            fontName=font_name
        )
        
        elements.append(Paragraph('КВИТАНЦИИ ПЛАНА №' + current_plan.token[:8].upper(), title_style))
        elements.append(Paragraph('Год: ' + str(current_plan.year), header_style))
        elements.append(Spacer(1, 10))
        
        data = [
            ['Дата', 'Отправитель', 'Сообщение']
        ]
        
        for ticket in tickets:
            try:
                if ticket.is_system:
                    sender = 'Система'
                elif ticket.user:
                    sender = ticket.user.organization.full_name if ticket.user.organization.full_name else 'Неизвестно'
                else:
                    sender = 'Неизвестно'
                
                date_str = ticket.begin_time.strftime('%d.%m.%Y %H:%M') if ticket.begin_time else ''
                
                data.append([
                    Paragraph(date_str, cell_style),
                    Paragraph(sender, cell_style),
                    Paragraph(ticket.note, cell_style)
                ])
            except Exception as e:
                current_app.logger.error(f"Error processing ticket {ticket.id if hasattr(ticket, 'id') else 'unknown'}: {str(e)}")
                data.append([
                    Paragraph('Ошибка', cell_style),
                    Paragraph('Ошибка', cell_style),
                    Paragraph('Ошибка при обработке квитанции', cell_style)
                ])
        
        table = Table(data, colWidths=[50*mm, 50*mm, 100*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00798f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f9ff')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True),
        ]))
        
        elements.append(table)
        
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=False,
            download_name=f'mesplan_{current_plan.token[:8]}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        current_app.logger.error(f"Error generating tickets PDF for plan {token}: {str(e)}")
        flash('Произошла ошибка при генерации PDF', 'error')
        return redirect(request.referrer)

@audit_bp.route('/print-signatures/<token>', methods=['GET'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def print_signatures(token):
    """PDF-версия вкладки "Подписи" — тот же формат документа, что и
    print_tickets для сообщений, только для таблицы пути согласования
    (build_signature_print_rows строит те же строки/статусы, что
    components.html::plan_signatures_page)."""
    try:
        from website.utils.plans import build_signature_cycles, build_signature_print_rows

        current_plan = Plan.query.filter_by(token=token).first()

        if not current_plan:
            flash('План не найден', 'error')
            return redirect(request.referrer)

        cycles = build_signature_cycles(current_plan)

        if not cycles:
            flash('План ещё не отправлялся — печатать нечего', 'error')
            return redirect(request.referrer)

        print_rows = build_signature_print_rows(current_plan, cycles)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                                 leftMargin=12*mm, rightMargin=12*mm)
        styles = getSampleStyleSheet()
        elements = []

        if platform.system() == 'Windows':
            font_path = 'C:/Windows/Fonts/arial.ttf'
        elif platform.system() == 'Linux':
            font_path = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
        else:
            font_path = '/System/Library/Fonts/Helvetica.ttc'

        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('CustomFont', font_path))
            font_name = 'CustomFont'
        else:
            font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'fonts', 'Montserrat-Regular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                font_name = 'CustomFont'
            else:
                font_name = 'Helvetica'

        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.HexColor('#00798f'),
            fontName=font_name
        )

        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading2'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=12,
            fontName=font_name
        )

        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            fontName=font_name
        )

        dev_row_style = ParagraphStyle(
            'DevRowStyle',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            fontName=font_name,
            textColor=colors.HexColor('#555555'),
        )

        elements.append(Paragraph('ПОДПИСИ ПЛАНА №' + current_plan.token[:8].upper(), title_style))
        elements.append(Paragraph('Год: ' + str(current_plan.year), header_style))
        elements.append(Spacer(1, 10))

        headers = ['Тип действия', 'Организация', 'Должность, ФИО, телефон', 'Статус', 'Дата', 'Замечания']
        data = [headers]
        span_rows = []  # индексы строк в data, которые нужно объединить на всю ширину

        for kind, payload in print_rows:
            if kind == 'header':
                row_idx = len(data)
                data.append([Paragraph(payload, dev_row_style), '', '', '', '', ''])
                span_rows.append(row_idx)
            else:
                data.append([Paragraph(str(cell), cell_style) for cell in payload])

        table = Table(data, colWidths=[28*mm, 40*mm, 48*mm, 24*mm, 18*mm, 28*mm], repeatRows=1)

        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00798f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f9ff')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        for row_idx in span_rows:
            table_style.append(('SPAN', (0, row_idx), (-1, row_idx)))
            table_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#eef1f4')))

        table.setStyle(TableStyle(table_style))

        elements.append(table)

        doc.build(elements)
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=False,
            download_name=f'podpisi_{current_plan.token[:8]}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        current_app.logger.error(f"Error generating signatures PDF for plan {token}: {str(e)}")
        flash('Произошла ошибка при генерации PDF', 'error')
        return redirect(request.referrer)


# Окно, в течение которого автор сообщения может его отредактировать (как
# "редактировать" в мессенджерах) — после истечения кнопка в разметке
# остаётся видимой (время по умолчанию при рендере не проверяем, см.
# macros/components.html), но сервер всё равно откажет. Удаление сообщений
# убрано целиком — у истории замечаний по планам должна оставаться полная
# цепочка, а не дыры; вместо него — редактирование (см. edit_ticket ниже).
TICKET_EDIT_WINDOW_MINUTES = 5


@audit_bp.route('/edit-ticket/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
@reader_forbidden
def edit_ticket(token):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _error(message, status_code=400):
        if is_ajax:
            return jsonify({'success': False, 'error': message}), status_code
        flash(message, 'error')
        return redirect(request.referrer)

    current_plan = g.current_plan
    ticket_id = request.form.get('ticket_id', type=int)
    if not ticket_id:
        return _error('Сообщение не найдено', 404)

    ticket = PlanTicket.query.filter_by(id=ticket_id, plan_id=current_plan.id).first()
    if not ticket:
        return _error('Сообщение не найдено', 404)

    if ticket.is_system:
        return _error('Системные сообщения нельзя редактировать', 403)

    if ticket.user_id != current_user.id:
        return _error('Можно редактировать только свои сообщения', 403)

    # Редактировать можно только самое последнее сообщение в чате — иначе
    # правка задним числом сообщения, на которое уже кто-то успел ответить,
    # запутывала бы историю переписки (см. is_own_editable_ticket в
    # macros/components.html, та же логика).
    last_ticket = PlanTicket.query.filter_by(plan_id=current_plan.id).order_by(
        PlanTicket.begin_time.desc(), PlanTicket.id.desc()
    ).first()
    if not last_ticket or last_ticket.id != ticket.id:
        return _error('Редактировать можно только последнее сообщение')

    if not ticket.begin_time or (current_utc_time() - ticket.begin_time) > timedelta(minutes=TICKET_EDIT_WINDOW_MINUTES):
        return _error(f'Редактирование доступно только в течение {TICKET_EDIT_WINDOW_MINUTES} минут после отправки')

    note = request.form.get('note')
    if not note or not note.strip():
        return _error('Сообщение не может быть пустым')

    attachment_file = request.files.get('attachment')
    remove_attachment = request.form.get('remove_attachment') == '1'

    if attachment_file and attachment_file.filename:
        from website.utils.ticket_attachment import validate_ticket_attachment
        attachment_error = validate_ticket_attachment(attachment_file)
        if attachment_error:
            return _error(attachment_error)

    ticket.note = note.strip()
    # Время сообщения обновляется на момент редактирования — отображаемое
    # время должно отражать правку, а окно в TICKET_EDIT_WINDOW_MINUTES
    # отсчитывается заново от неё же (отредактированное только что
    # сообщение остаётся редактируемым ещё 5 минут, а не "протухает"
    # сразу же из-за старого begin_time).
    ticket.begin_time = current_utc_time()

    # Привязка к этапу (approval_path_id) — та же, что ставится при
    # создании сообщения (см. create_ticket) — пересчитывается и здесь: на
    # момент правки текущий этап отправителя должен быть именно тем же
    # (сообщение можно редактировать только пока оно последнее и пока не
    # истекли TICKET_EDIT_WINDOW_MINUTES), но если вдруг расходится —
    # "Подписи" должны ориентироваться на актуальный этап, а не на
    # устаревшую привязку с момента первой отправки.
    from website.utils.plans import get_current_review_path
    current_path = get_current_review_path(current_plan, current_user)
    if current_path:
        ticket.approval_path_id = current_path.id

    if attachment_file and attachment_file.filename:
        from website.utils.ticket_attachment import delete_ticket_attachment, save_ticket_attachment
        delete_ticket_attachment(ticket)
        save_ticket_attachment(ticket, attachment_file)
    elif remove_attachment:
        from website.utils.ticket_attachment import delete_ticket_attachment
        delete_ticket_attachment(ticket)

    db.session.commit()

    if is_ajax:
        from website.utils.plans import get_audit_context
        ctx = get_audit_context(current_plan, current_user)
        html = render_template_string(
            '''
            {% import 'macros/components.html' as components %}
            {{ components.tickets_container(plan, current_user, can_audit, has_remarks, approve_label, can_cancel) }}
            ''',
            plan=current_plan,
            current_user=current_user,
            can_audit=ctx['can_audit'],
            has_remarks=ctx['has_remarks'],
            approve_label=ctx['approve_label'],
            can_cancel=ctx['can_cancel'],
        )
        return jsonify({'success': True, 'html': html, 'has_remarks': ctx['has_remarks']})

    flash('Сообщение изменено', 'success')
    return redirect(request.referrer)


@audit_bp.route('/ticket-attachment/<token>/<int:ticket_id>', methods=['GET'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def get_ticket_attachment(token, ticket_id):
    """Отдаёт файл, прикреплённый к сообщению (замечанию). ?download=1 —
    принудительное скачивание, иначе — показ прямо в браузере (как ТЭО,
    см. get_event_teo в plan_bp.py)."""
    current_plan = g.current_plan
    ticket = PlanTicket.query.filter_by(id=ticket_id, plan_id=current_plan.id).first()
    if not ticket or not ticket.attachment_filename:
        abort(404)

    folder = current_app.config['TICKET_ATTACHMENT_UPLOAD_FOLDER']
    as_attachment = request.args.get('download') == '1'

    return send_from_directory(
        folder,
        ticket.attachment_filename,
        as_attachment=as_attachment,
        download_name=ticket.attachment_original_name or ticket.attachment_filename
    )

@audit_bp.route('/create-ticket/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
@reader_forbidden
def create_ticket(token):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _error(message):
        if is_ajax:
            return jsonify({'success': False, 'error': message}), 400
        flash(message, 'error')
        return redirect(request.referrer)

    current_plan = g.current_plan
    if not current_plan:
        return _error('План не найден')

    note = request.form.get('note')

    if not note or not note.strip():
        current_app.logger.error("Empty message")
        return _error('Сообщение не может быть пустым')

    if not current_plan.is_sent:
        return _error('План не находится на этапе согласования')

    if current_plan.is_approved or current_plan.is_error:
        return _error('План уже обработан')

    # approval_paths больше не чистятся при повторной отправке (см. cycle) —
    # искать "текущий" этап нужно строго в последнем цикле, иначе можно
    # найти брошенный непройденный этап из отменённого старого цикла.
    latest_cycle = db.session.query(db.func.max(PlanApprovalPath.cycle)).filter(
        PlanApprovalPath.plan_id == current_plan.id
    ).scalar() or 1

    current_path = PlanApprovalPath.query.filter_by(
        plan_id=current_plan.id,
        cycle=latest_cycle,
        is_viewed=False
    ).order_by(PlanApprovalPath.step_order).first()

    if not current_path:
        return _error('Нет активных шагов для проверки')

    if current_path.organization_id != current_user.organization_id:
        return _error('У вас нет прав на отправку сообщения для этого этапа')

    prev_path = PlanApprovalPath.query.filter(
        PlanApprovalPath.plan_id == current_plan.id,
        PlanApprovalPath.cycle == latest_cycle,
        PlanApprovalPath.step_order == current_path.step_order - 1
    ).first()

    if prev_path and not prev_path.is_viewed:
        return _error('Предыдущий этап еще не пройден')

    attachment_file = request.files.get('attachment')
    if attachment_file and attachment_file.filename:
        from website.utils.ticket_attachment import validate_ticket_attachment
        attachment_error = validate_ticket_attachment(attachment_file)
        if attachment_error:
            return _error(attachment_error)

    current_plan.afch = True

    new_ticket = PlanTicket(
        note=note.strip(),
        luck=False,
        plan_id=current_plan.id,
        user_id=current_user.id,
        is_system=(current_user.id == current_plan.user_id),
        begin_time=current_utc_time(),
        approval_path_id=current_path.id,
    )

    db.session.add(new_ticket)

    if attachment_file and attachment_file.filename:
        from website.utils.ticket_attachment import save_ticket_attachment
        save_ticket_attachment(new_ticket, attachment_file)

    db.session.commit()

    if is_ajax:
        from website.utils.plans import get_audit_context
        # Только что отправленное сообщение разблокирует кнопку "Есть
        # ошибки" — пересчитываем весь контекст живьём (см.
        # get_audit_context), а не доверяем plan.afch.
        ctx = get_audit_context(current_plan, current_user)
        html = render_template_string(
            '''
            {% import 'macros/components.html' as components %}
            {{ components.tickets_container(plan, current_user, can_audit, has_remarks, approve_label, can_cancel) }}
            ''',
            plan=current_plan,
            current_user=current_user,
            can_audit=ctx['can_audit'],
            has_remarks=ctx['has_remarks'],
            approve_label=ctx['approve_label'],
            can_cancel=ctx['can_cancel'],
        )
        return jsonify({'success': True, 'html': html, 'has_remarks': ctx['has_remarks']})

    flash('Сообщение отправлено', 'success')
    return redirect(request.referrer)