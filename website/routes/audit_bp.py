import logging
from flask import Blueprint, current_app, flash, redirect, request, g
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

from website.routes.views import owner_only
from website.sessions import session_required
from website.models import Plan, Ticket, PlanApprovalPath, TimeByMinsk
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
        
        tickets = Ticket.query.filter_by(plan_id=current_plan.id).order_by(Ticket.begin_time.asc()).all()
        
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
                    sender = ticket.user.organization.name if ticket.user.organization.name else 'Неизвестно'
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

@audit_bp.route('/create-ticket/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def create_ticket(token):
    current_plan = g.current_plan
    if not current_plan:
        flash('План не найден', 'error')
        return redirect(request.referrer)
    
    note = request.form.get('note')
    
    if not note or not note.strip():
        current_app.logger.error("Empty message")
        flash('Сообщение не может быть пустым', 'error')
        return redirect(request.referrer)
    
    if not current_plan.is_sent:
        flash('План не находится на этапе согласования', 'error')
        return redirect(request.referrer)
    
    if current_plan.is_approved or current_plan.is_error:
        flash('План уже обработан', 'error')
        return redirect(request.referrer)
    
    current_path = PlanApprovalPath.query.filter_by(
        plan_id=current_plan.id,
        is_viewed=False
    ).order_by(PlanApprovalPath.step_order).first()
    
    if not current_path:
        flash('Нет активных шагов для проверки', 'error')
        return redirect(request.referrer)
    
    if current_path.organization_id != current_user.organization_id:
        flash('У вас нет прав на отправку сообщения для этого этапа', 'error')
        return redirect(request.referrer)
    
    prev_path = PlanApprovalPath.query.filter(
        PlanApprovalPath.plan_id == current_plan.id,
        PlanApprovalPath.step_order == current_path.step_order - 1
    ).first()
    
    if prev_path and not prev_path.is_viewed:
        flash('Предыдущий этап еще не пройден', 'error')
        return redirect(request.referrer)
    
    current_plan.afch = True
    
    new_ticket = Ticket(
        note=note.strip(),
        luck=False,
        plan_id=current_plan.id,
        user_id=current_user.id,
        is_system=(current_user.id == current_plan.user_id),
        begin_time=TimeByMinsk()
    )

    db.session.add(new_ticket)
    db.session.commit()
    
    flash('Сообщение отправлено', 'success')
    return redirect(request.referrer)