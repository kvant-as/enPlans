from decimal import Decimal
import io
import zipfile
from flask import (
    Blueprint, current_app, logging, render_template, redirect, send_file, url_for, flash, request, jsonify, session, g
)

import uuid
import threading
import os
import zipfile

from sqlalchemy import select

from flask_login import (
    current_user, login_required
)

from website.utils.currency_rates import fetch_usd_rate_from_belarusbank
from website.utils.plans import get_filtered_plans, to_decimal_1, to_decimal_2, update_ChangeTimePlan
from website.sessions import session_required

from ..models import Ministry, News, Region, User, Organization, Plan, Ticket, Indicator, IndicatorUsage, Notification
from .. import db

from functools import wraps

from .auth import user_with_all_params

views = Blueprint('views', __name__)

def owner_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = kwargs.get('token')
        
        if not token:
            flash('Токен плана не указан', 'error')
            return redirect(url_for('views.plans', user=current_user.id))
        
        plan = Plan.query.filter_by(token=token).first()
        
        if plan is None:
            flash('План не найден', 'error')
            return redirect(url_for('views.plans', user=current_user.id))
        
        has_access = (
            current_user.is_admin or 
            current_user.is_auditor or 
            plan.user_id == current_user.id
        )
        
        if not has_access:
            flash('У вас нет доступа к этому плану', 'error')
            return redirect(url_for('views.plans', user=current_user.id))
    
        g.current_plan = plan
        return f(*args, **kwargs)
    return decorated_function

@views.route('/change_language/<lang_code>')
def change_language(lang_code):
    if lang_code in current_app.config['LANGUAGES']:
        session['language'] = lang_code
    return redirect(request.referrer or url_for('views.login'))

@views.route('/profile', methods = ['GET'])
@user_with_all_params()
@login_required
@session_required
def profile():
    can_change_modal = True
    if Plan.query.filter(Plan.user_id == current_user.id).count() > 0:
        can_change_modal = False

    return render_template('profile.html', 
                        can_change_modal=can_change_modal,
                        hide_header=False,
                        current_user=current_user,
                        change_orgUser_modal = True
                           )

@views.route('/profile/edit', methods = ['POST', 'GET'])
@user_with_all_params()
@login_required
@session_required
def profile_edit():
    if request.method == 'POST':
        pass
    else:

        return render_template('profile_edit.html', 
                            hide_header=False,
                            current_user=current_user)

@views.route('/edit-user-org', methods=['POST'])
@user_with_all_params()
@login_required
def edit_user_org():
    try:
        item_id = request.form.get('id_org')
        item_type = request.form.get('item_type', 'organization')
        
        if not item_id:
            flash('Элемент не выбран!', 'error')
            return redirect(request.referrer)
        
        if Plan.query.filter(Plan.user_id == current_user.id).count() > 0:
            flash('У вас существуют планы энергосбережения, редактирование запрещено', 'error')
            return redirect(url_for('views.profile'))
        
        if item_type == 'organization':
            current_user.plan_type = None
            selected_item = Organization.query.filter_by(id=item_id).first()
            
            if not selected_item:
                flash('Организация не найдена!', 'error')
                return redirect(request.referrer)
            
            current_user.organization_id = selected_item.id
            current_user.ministry_id = None 
            current_user.region_id = None   
            
            flash(f'Организация изменена на: {selected_item.name}', 'success')
            
        elif item_type == 'ministry':
            selected_item = Ministry.query.filter_by(id=item_id).first()
            
            if not selected_item:
                flash('Министерство не найдено!', 'error')
                return redirect(request.referrer)
            
            current_user.plan_type = 'ministry'
            current_user.ministry_id = selected_item.id
            current_user.organization_id = None 
            current_user.region_id = None    
            
            flash(f'Министерство изменено на: {selected_item.name}', 'success')
            
        elif item_type == 'region':
            selected_item = Region.query.filter_by(id=item_id).first()
            
            if not selected_item:
                flash('Регион не найден!', 'error')
                return redirect(request.referrer)

            current_user.plan_type = 'region'
            current_user.region_id = selected_item.id
            current_user.organization_id = None 
            current_user.ministry_id = None    
            
            flash(f'Регион изменен на: {selected_item.name}', 'success')
            
        else:
            flash('Неизвестный тип элемента!', 'error')
            return redirect(request.referrer)
        
        db.session.commit()
        
        return redirect(url_for('views.profile'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in edit_user_org: {str(e)}")
        flash('Произошла ошибка при обновлении данных', 'error')
        return redirect(request.referrer)
    
@views.route('/edit-plan-type/<token>', methods=['POST'])
@login_required
@session_required
@owner_only
def edit_plan_type(token):
    try:
        entity_type = request.form.get('entity_type')
        current_plan = g.current_plan
        
        if not current_plan:
            flash('План не найден', 'error')
            return redirect(url_for('views.profile'))
        
        if not current_plan.is_draft:
            flash('Этот план нельзя редактировать', 'error')
            return redirect(url_for('views.profile'))
        
        if not entity_type:
            flash('Пожалуйста, выберите тип плана', 'error')
            return redirect(request.referrer or url_for('views.profile'))
        
        plan_type_mapping = {
            'organization_org_small': 'org_small',  # До 25 тыс. т.
            'organization_org_large': 'org_large'   # Более 25 тыс. т.
        }
        
        plan_type_value = plan_type_mapping.get(entity_type)
        if not plan_type_value:
            flash('Неверный тип плана', 'error')
            return redirect(request.referrer or url_for('views.profile'))
        
        current_plan.plan_type = plan_type_value
        db.session.commit()
        
        if plan_type_value == 'org_small':
            flash_message = 'Тип плана установлен: Организация с потреблением до 25 тыс. т.'
        elif plan_type_value == 'org_large':
            flash_message = 'Тип плана установлен: Организация с потреблением более 25 тыс. т.'
        else:
            flash_message = 'Тип плана обновлен'
        flash(flash_message, 'success')
        
        return redirect(url_for('plan_bp.plan_review', token=current_plan.token))
    except Exception as e:
        flash(f'Произошла непредвиденная ошибка: {str(e)}', 'error')
        return redirect(request.referrer or url_for('views.profile'))

@views.route('/plans', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
def plans():
    return render_template(
        'plans.html',
        years=range(2024, 2056),
        current_user=current_user,
        hide_header=False
    )
    
    
@views.route('/plans-audit', methods=['GET'])
@user_with_all_params()
@login_required
@session_required   
def plans_audit():
    status_filter = request.args.get('status', 'all')
    year_filter = request.args.get('year', 'all')

    plans, status_counts = get_filtered_plans(current_user, status_filter, year_filter)

    context = {
        'years': range(2024, 2056),
        'plans': plans,
        'status_counts': status_counts,
        'current_status_filter': status_filter,
        'current_year_filter': year_filter
    }

    return render_template(
        'plans_audit.html',
        **context,
        current_user=current_user,
        hide_header=False
    ) 

@views.route('/export', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
def export():
    return render_template(
        'export.html',
        years=range(2024, 2056),
        current_user=current_user,
        hide_header=False
    )
    
@views.route('/export/start', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def start_export():
    try:
        export_format = request.form.get('format', '').lower()
        plan_ids = request.form.getlist('ids')
        
        if not plan_ids:
            return jsonify({'success': False, 'error': 'Не выбраны планы'})
        
        plan_ids = [int(pid) for pid in plan_ids]
        
        if export_format not in ['xlsx', 'xml', 'pdf']:
            return jsonify({'success': False, 'error': 'Неверный формат'})
        
        task_id = str(uuid.uuid4())
        
        from ..export import create_export_archive_async
        from flask import current_app
        
        thread = threading.Thread(
            target=create_export_archive_async,
            args=(export_format, task_id, current_user.id, plan_ids, current_app._get_current_object())
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@views.route('/export/status/<task_id>', methods=['GET'])
@login_required
def export_status(task_id):
    from ..export import export_tasks
    if task_id not in export_tasks:
        return jsonify({'success': False, 'error': 'Задача не найдена'})
    
    task = export_tasks[task_id]
    return jsonify({
        'success': True,
        'status': task['status'],
        'progress': task.get('progress', 0),
        'error': task.get('error', '')
    })

@views.route('/export/download/<task_id>', methods=['GET'])
@login_required
def download_export(task_id):
    from ..export import export_tasks
    if task_id not in export_tasks:
        flash('Файл не найден', 'error')
        return redirect(request.referrer or url_for('views.export_page'))
    
    task = export_tasks[task_id]
    
    if task['status'] != 'completed':
        flash('Архив еще не готов', 'error')
        return redirect(request.referrer or url_for('views.export_page'))
    
    return send_file(
        task['file_path'],
        as_attachment=True,
        download_name=f'plans_export_{task_id[:8]}.zip',
        mimetype='application/zip'
    )
    
# @views.route('/news', methods=['GET'])
# def news_page():
#     return render_template(
#         'news.html',
#         current_user=current_user,
#         hide_header=False
#     )
    
# @views.route('/news/<int:news_id>', methods=['GET'])
# def news_detail_page(news_id):
#     news_item = News.query.get_or_404(news_id)
    
#     news_item.views_count += 1
#     db.session.commit()
    
#     return render_template(
#         'news_detail.html',
#         current_user=current_user,
#         news_item=news_item,
#         hide_header=False
#     )

@views.route('/news/<int:id>', methods=['GET'])
def news_post(id):
    post = News.query.filter_by(id = id).first()
    return render_template(f'news_id.html', 
        current_user=current_user,
        post=post
    )

@views.route('/news', methods=['GET'])
def news():
    all_news = News.query.order_by(News.created_at.desc()).all()
    return render_template('news.html', 
        current_user=current_user,
        all_news=all_news
    )
    


from sqlalchemy import select

@views.route('/create-plan', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@session_required
def create_plan():
    if request.method == 'POST':
        year = int(request.form.get('year'))

        existing_plan = Plan.query.filter_by(
            user_id=current_user.id,
            year=year
        ).first()
        
        if existing_plan:
            flash(f'У вас уже есть план на {year} год!', 'error')
            return render_template('create_plan.html', hide_header=False)

        energy_saving = to_decimal_1(request.form.get('energy_saving'))
        share_fuel = to_decimal_1(request.form.get('share_fuel'))
        saving_fuel = to_decimal_1(request.form.get('saving_fuel'))
        share_energy = to_decimal_1(request.form.get('share_energy'))

        org_id = None
        ministry_id = None
        region_id = None

        if hasattr(current_user, 'organization') and current_user.organization:
            org_id = current_user.organization.id
        
        if hasattr(current_user, 'ministry') and current_user.ministry:
            ministry_id = current_user.ministry.id
        
        if hasattr(current_user, 'region') and current_user.region:
            region_id = current_user.region.id

        def get_usd_rate_for_new_plan():
            usd_rate, error = fetch_usd_rate_from_belarusbank()
            
            if usd_rate is None:
                current_app.logger.warning(f'Failed to fetch USD rate: {error}')
                flash('Не удалось получить актуальный курс доллара. Будет использовано значение по умолчанию 2.75', 'warning')
                return Decimal('2.75')
            
            return usd_rate
        
        def get_cost_per_toe_for_new_plan(year):
            if year == 2026:
                return to_decimal_2('260.00')
            elif year == 2027:
                return to_decimal_2('270.00')
            else:
                return to_decimal_2('270.00')
                # flash(f'На {year} год стоимость 1 т.у.т. еще не утверждена. План не может быть создан.', 'error')
                # return None

        usd_rate_value = get_usd_rate_for_new_plan()
        cost_per_toe_value = get_cost_per_toe_for_new_plan(year)
        
        if cost_per_toe_value is None:
            return render_template('create_plan.html', hide_header=False)

        new_plan = Plan(
            org_id=org_id,
            ministry_id=ministry_id,
            region_id=region_id,
            year=year,
            user_id=current_user.id,
            energy_saving=energy_saving,
            share_fuel=share_fuel,
            saving_fuel=saving_fuel,
            share_energy=share_energy,
            usd_rate=usd_rate_value,
            cost_per_toe_usd=cost_per_toe_value
        )
        
        db.session.add(new_plan)
        db.session.commit()

        existing_indicators = select(IndicatorUsage.id_indicator).where(
            IndicatorUsage.id_plan == new_plan.id
        )
        
        mandatory_indicators = Indicator.query\
            .filter(Indicator.IsMandatory == True)\
            .filter(~Indicator.id.in_(existing_indicators))\
            .all()
        
        for indicator in mandatory_indicators:
            indicator_usage = IndicatorUsage(
                id_indicator=indicator.id,
                id_plan=new_plan.id,
                QYearBeforePrev=to_decimal_2(0),
                QYearPrev=to_decimal_2(0),
                QYearCurrent=to_decimal_2(0)
            )
            db.session.add(indicator_usage)
        
        db.session.commit()
        flash('Новый план создан', 'success')
        return redirect(url_for('views.plans'))

    return render_template('create_plan.html', hide_header=False)
    
@views.route('/plans/plan-edit/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@owner_only
@login_required
@session_required
def edit_plan(token):
    if request.method == 'POST':
        current_plan = g.current_plan

        if not current_plan:
            flash('План не найден или у вас нет прав для его редактирования', 'error')
            return redirect(url_for('views.plans'))
        
        year = request.form.get('year')
        
        existing_plan = Plan.query.filter(
            Plan.user_id == current_user.id,
            Plan.year == year,
            Plan.token != token 
        ).first()
        
        if existing_plan:
            flash(f'У вас уже есть другой план на {year} год!', 'error')
            return redirect(url_for('views.plans'))
        
        energy_saving = to_decimal_1(request.form.get('energy_saving'))
        share_fuel = to_decimal_1(request.form.get('share_fuel'))
        saving_fuel = to_decimal_1(request.form.get('saving_fuel'))
        share_energy = to_decimal_1(request.form.get('share_energy'))

        current_plan.year = year
        current_plan.energy_saving = energy_saving
        current_plan.share_fuel = share_fuel
        current_plan.saving_fuel = saving_fuel
        current_plan.share_energy = share_energy
        db.session.commit()
        
        flash('Изменения приняты', 'success')
        update_ChangeTimePlan(current_plan.id)
        return redirect(url_for('plan_bp.plan_review', token=current_plan.token))  
    else:
        plan = g.current_plan
        
        return render_template(
            'plan_edit.html',
            current_user=current_user,
            plan=plan
        )   
    
@views.route('/delete-plan/<token>', methods=['POST'])
@user_with_all_params()
@owner_only
@login_required
@session_required
def delete_plan(token):
    try:
        current_plan = g.current_plan
        db.session.delete(current_plan)
        db.session.commit()
        flash('План успешно удален', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting plan {id}: {str(e)}")
        flash('Произошла ошибка при удалении плана', 'error')
    return redirect(url_for('views.plans'))
    
@views.route('/check-plan-year')
@user_with_all_params()
@login_required
@session_required
def check_plan_year():
    year = request.args.get('year')
    current_plan_year = request.args.get('current_plan_year')
    
    if not year:
        return jsonify({'error': 'Year parameter is required'}), 400
    
    if current_plan_year and current_plan_year == year:
        return jsonify({'exists': False})
    
    existing_plan = Plan.query.filter_by(
        user_id=current_user.id,
        year=year
    ).first()   
        
    return jsonify({'exists': existing_plan is not None})

@views.route('/stats', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@session_required
def stats():
    if request.method == 'POST':
        pass
    return render_template('stats.html', 
                        hide_header=False)
    
# @views.route('/news', methods=['GET', 'POST'])
# @user_with_all_params()
# @login_required
# @session_required
# def news():
#     if request.method == 'POST':
#         pass
#     return render_template('news.html', 
#                         hide_header=False)
    




@views.route('/api/ticket/<int:ticket_id>/details')
@login_required
def get_ticket_details(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    plan = ticket.plan
    if not plan:
        return jsonify({'error': 'План не найден'}), 404
    
    user_data = {}
    if ticket.user:
        user = ticket.user
        fio_parts = [
            part.strip() 
            for part in [user.last_name, user.first_name, user.patronymic_name] 
            if part and part.strip()
        ]
        
        user_fio = ' '.join(fio_parts) if fio_parts else 'Не указано'
        
        user_data = {
            'user_fio': user_fio,
            'user_email': user.email.strip() if user.email and user.email.strip() else 'Не указано',
            'user_phone': user.phone.strip() if user.phone and user.phone.strip() else 'Не указано'
        }
    
    return jsonify({
        'id': ticket.id,
        'is_owner': ticket.is_owner,
        'luck': ticket.luck,
        'note': ticket.note or '',
        'time': ticket.begin_time.strftime('%H:%M') if ticket.begin_time else '--:--',
        'date': ticket.begin_time.strftime('%d %b %Y') if ticket.begin_time else '',
        **user_data
    })

@views.route('/FAQ', methods=['GET'])
def FAQ_page():    
    return render_template('FAQ.html', active_tab = 'faq')

@views.route('/', methods=['GET'])
def begin_page():    
    user_data = User.query.count()
    organization_data = Organization.query.count()
    plan_data = Plan.query.count()
    return render_template('begin.html',
            user_data=user_data,
            organization_data=organization_data,
            plan_data=plan_data,
            active_tab = 'begin'
            )

@views.route('/api/notifications', methods=['GET'])
@user_with_all_params()
@login_required
def api_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return jsonify([
        {
            'id': n.id,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        for n in notifications
    ])

@views.route('/api/notifications/mark-all-read', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'message': 'Все уведомления отмечены как прочитанные'})