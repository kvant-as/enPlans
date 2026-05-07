from datetime import timedelta
from datetime import datetime
import io
import zipfile
from flask import (
    Blueprint, current_app, logging, render_template, redirect, send_file, url_for, flash, request, jsonify, session, g
)

from flask_login import (
    current_user, login_required, login_user
)
from sqlalchemy.orm import joinedload
from sqlalchemy import func, asc, or_

from website.plans import get_cumulative_econ_metrics, get_filtered_plans, other_data_indicatorUpdate, to_decimal_3, status_handlers, update_ChangeTimePlan
from website.sessions import session_required

from ..models import Ministry, Region, User, Organization, Plan, Ticket, Unit, Direction, Indicator, EconMeasure, EconExec, IndicatorUsage, Notification, TimeByMinsk
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
        
        # Ищем план по token, а не по id
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




@views.route('/api/organizations')
@login_required
def get_organizations_api():
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "", type=str).strip()

        query = Organization.query
        if search_query:
            query = query.filter(
                db.or_(
                    Organization.name.ilike(f"%{search_query}%"),
                    Organization.okpo.ilike(f"%{search_query}%")
                )
            )

        per_page = 10
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            "organizations": [
                {
                    "id": org.id,
                    "name": org.name,
                    "okpo": org.okpo or "",
                    "ynp": org.ynp or "",
                    "ministry": org.ministry.name if org.ministry else "",
                }
                for org in pagination.items
            ],
            "page": pagination.page,
            "has_next": pagination.has_next,
            "total_pages": pagination.pages,
            "total_items": pagination.total
        })
    except Exception as e:
        logging.error(f"Error fetching organizations: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@views.route('/api/ministries')
@login_required
def get_ministries_api():
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "", type=str).strip()
        
        query = Ministry.query.filter(Ministry.is_active == True)
        
        if search_query:
            query = query.filter(Ministry.name.ilike(f"%{search_query}%"))
        
        query = query.order_by(Ministry.name)
        per_page = 10
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            "ministrys": [
                {
                    "id": ministry.id,
                    "name": ministry.name
                }
                for ministry in pagination.items
            ],
            "page": pagination.page,
            "has_next": pagination.has_next,
            "total_pages": pagination.pages,
            "total_items": pagination.total
        })
        
    except Exception as e:
        logging.error(f"Error fetching Ministries: {str(e)}")
        current_app.logger.error(f"ERROR: {str(e)}") 
        return jsonify({"error": "Internal server error"}), 500

@views.route('/api/regions')
@login_required
def get_regions_api():
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "", type=str).strip()

        query = Region.query
        if search_query:
            query = query.filter(
                db.or_(
                    Region.name.ilike(f"%{search_query}%")
                )
            )

        per_page = 10
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            "regions": [
                {
                    "id": region.id,
                    "name": region.name
                }
                for region in pagination.items
            ],
            "page": pagination.page,
            "has_next": pagination.has_next,
            "total_pages": pagination.pages,
            "total_items": pagination.total
        })
    except Exception as e:
        logging.error(f"Error fetching regions: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

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
        
        return redirect(url_for('views.plan_review', token=current_plan.token))
    except Exception as e:
        flash(f'Произошла непредвиденная ошибка: {str(e)}', 'error')
        return redirect(request.referrer or url_for('views.profile'))

@views.route('/plans', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
def plans():
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
        'plans.html',
        **context,
        current_user=current_user,
        hide_header=False
    )

@views.route('/export', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
def export():
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
        'export.html',
        **context,
        current_user=current_user,
        hide_header=False
    )
    
@views.route('/export-to/<string:format>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def export_to(format):
    ids = request.form.getlist("ids")
    if not ids:
        flash("Не выбраны планы.", "error")
        return redirect(request.url)

    plans = Plan.query.filter(Plan.id.in_(ids)).all()
    if not plans:
        flash("Не найдены выбранные планы.", "error")
        return redirect(request.url)
    
    from ..export import (
        export_pdf_single, 
        export_xlsx_single,
        export_xml_single
        
    )
    if len(plans) == 1:
        plan = plans[0]
        if format == "xml":
            file_stream, mime, filename = export_xml_single(plan)
        elif format == "xlsx":
            file_stream, mime, filename = export_xlsx_single(plan)
        elif format == "pdf":
            file_stream, mime, filename = export_pdf_single(plan)
        else:
            flash("Неизвестный формат.", "error")
            return redirect(request.url)
        return send_file(file_stream, as_attachment=True, download_name=filename, mimetype=mime)
    
    zip_stream = io.BytesIO()
    with zipfile.ZipFile(zip_stream, "w") as zip_file:
        for plan in plans:
            if format == "xml":
                f_stream, _, fname = export_xml_single(plan)
            elif format == "xlsx":
                f_stream, _, fname = export_xlsx_single(plan)
            elif format == "pdf":
                f_stream, _, fname = export_pdf_single(plan)
            else:
                flash("Неизвестный формат.", "error")
                return redirect(request.url)

            zip_file.writestr(fname, f_stream.getvalue())

    zip_stream.seek(0)
    return send_file(zip_stream, as_attachment=True, download_name="plans.zip", mimetype="application/zip")

@views.route('/create-plan', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@session_required
def create_plan():
    if request.method == 'POST':
        year = request.form.get('year')

        existing_plan = Plan.query.filter_by(
            user_id=current_user.id,
            year=year
        ).first()
        
        if existing_plan:
            flash(f'У вас уже есть план на {year} год!', 'error')
            return render_template('create_plan.html', 
                        hide_header=False)

        energy_saving = to_decimal_3(request.form.get('energy_saving'))
        share_fuel = to_decimal_3(request.form.get('share_fuel'))
        saving_fuel = to_decimal_3(request.form.get('saving_fuel'))
        share_energy = to_decimal_3(request.form.get('share_energy'))

        org_id = None
        ministry_id = None
        region_id = None

        if hasattr(current_user, 'organization') and current_user.organization:
            org_id = current_user.organization.id
        
        if hasattr(current_user, 'ministry') and current_user.ministry:
            ministry_id = current_user.ministry.id
        
        if hasattr(current_user, 'region') and current_user.region:
            region_id = current_user.region.id

        new_plan = Plan(
            org_id=org_id,
            ministry_id=ministry_id,
            region_id=region_id,
            
            year=year,
            user_id=current_user.id,
            energy_saving=energy_saving,
            share_fuel=share_fuel,
            saving_fuel=saving_fuel,
            share_energy=share_energy
        )
        
        db.session.add(new_plan)
        db.session.commit()

        existing_indicators = db.session.query(IndicatorUsage.id_indicator)\
            .filter(IndicatorUsage.id_plan == new_plan.id)\
            .subquery()
        
        mandatory_indicators = Indicator.query\
            .filter(Indicator.IsMandatory == True)\
            .filter(~Indicator.id.in_(existing_indicators))\
            .all()
        
        for indicator in mandatory_indicators:
            indicator_usage = IndicatorUsage(
                id_indicator=indicator.id,
                id_plan=new_plan.id,
                QYearPrev=to_decimal_3(0),
                QYearCurr=to_decimal_3(0),
                QYearNext=to_decimal_3(0)
            )
            db.session.add(indicator_usage)
        
        db.session.commit()
        flash('Новый план создан', 'success')
        return redirect(url_for('views.plans'))

    return render_template('create_plan.html', 
                    hide_header=False)
    
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
        
        energy_saving = to_decimal_3(request.form.get('energy_saving'))
        share_fuel = to_decimal_3(request.form.get('share_fuel'))
        saving_fuel = to_decimal_3(request.form.get('saving_fuel'))
        share_energy = to_decimal_3(request.form.get('share_energy'))

        current_plan.year = year
        current_plan.energy_saving = energy_saving
        current_plan.share_fuel = share_fuel
        current_plan.saving_fuel = saving_fuel
        current_plan.share_energy = share_energy
        db.session.commit()
        
        flash('Изменения приняты', 'success')
        update_ChangeTimePlan(current_plan.id)
        return redirect(url_for('views.plan_review', token=current_plan.token))  
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

@views.route('/plans/plan-review/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@session_required
@owner_only
def plan_review(token):    
    current_plan = g.current_plan

    show_plan_type_modal = (
        current_plan.is_draft and 
        (current_plan.plan_type is None or current_plan.plan_type == '') and
        hasattr(current_user, 'organization') and 
        current_user.organization is not None
    )
    
    if request.method == 'POST':
        pass
    
    return render_template('plan_review.html', 
                        plan=current_plan,
                        show_plan_type_modal=show_plan_type_modal,
                        hide_header=False,
                        sentmodal=current_plan.is_control)
    
# @views.route('/plans/plan-review/<int:id>', methods=['GET'])
# @login_required
# def legacy_plan_review(id):
#     """Редирект со старых URL на новые с токенами"""
#     plan = Plan.query.get_or_404(id)
    
#     # Проверяем права
#     if not (current_user.is_admin or current_user.is_auditor or plan.user_id == current_user.id):
#         abort(403)
    
#     return redirect(url_for('views.plan_review', token=plan.token))
    
    
@views.route('/plans/plan-audit/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_audit(token):    
    current_plan = g.current_plan
    if request.method == 'POST':
        pass
    
    return render_template('plan_audit.html', 
                        plan=current_plan,     
                        hide_header=False)

@views.route('/plans/plan-directions/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_directions(token):    
    if request.method == 'POST':
        pass
    
    current_plan = g.current_plan
    directions = Direction.query.all() 
    
    econ_measures = (
        EconMeasure.query
        .filter_by(id_plan=current_plan.id)
        .join(EconMeasure.direction)
        .order_by(asc(Direction.code))
        .all()
    )
    
    return render_template('plan_directions.html', 
                        econ_measures=econ_measures,
                        directions=directions,
                        plan=current_plan,  
                        hide_header=False,
                        add_direction_modal=True,
                        confirmModal=True,
                        sentmodal=current_plan.is_control,
                        edit_direction_modal=True,
                        context_menu=True
                         )
    
@views.route('/get-econmeasure/<int:id>', methods=['GET'])
@user_with_all_params()
@login_required
def get_econmeasure(id):
    try:
        existing_measure = EconMeasure.query.get(id)
        if not existing_measure:
            return jsonify({'error': 'EconMeasure not found'}), 404
        
        return jsonify(existing_measure.as_dict())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@views.route('/create-econmeasure/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def create_econmeasure(token):
    current_plan = g.current_plan
    id_direction = request.form.get('id_direction')
    year_econ = to_decimal_3(request.form.get('year_econ'))
    estim_econ = to_decimal_3(request.form.get('estim_econ'))

    new_econmeasure = EconMeasure(
        id_plan=current_plan.id,
        id_direction=id_direction,
        year_econ=year_econ,
        estim_econ=estim_econ
    )
    
    db.session.add(new_econmeasure)
    db.session.commit()    
    flash('Направление добавлено', 'success')
    update_ChangeTimePlan(current_plan.id)
    return redirect(url_for('views.plan_directions', token=token))

@views.route('/delete-econmeasure/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def delete_econmeasure(id):
    econ_measure = EconMeasure.query.get_or_404(id)
    current_plan = Plan.query.get_or_404(econ_measure.id_plan)

    db.session.delete(econ_measure)
    db.session.commit()
    
    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)

    flash('Направление успешно удалено', 'success')
    return redirect(url_for('views.plan_directions', token=current_plan.token))

@views.route('/edit-econmeasure/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def edit_econmeasure(id):
    year_econ = to_decimal_3(request.form.get('year_econ'))
    estim_econ = to_decimal_3(request.form.get('estim_econ'))

    econmeasure = EconMeasure.query.get_or_404(id)
    
    if not econmeasure:
        flash('Запись не найдена!', 'error')
        return redirect(url_for('views.plan_directions'))

    current_plan = Plan.query.get_or_404(econmeasure.id_plan)
    econmeasure.year_econ = year_econ
    econmeasure.estim_econ = estim_econ
    db.session.commit()
    update_ChangeTimePlan(current_plan.id)
    flash('Направление обновлено', 'success')
    
    return redirect(url_for('views.plan_directions', token=current_plan.token))

@views.route('/plans/plan-events/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_events(token):    
    if request.method == 'POST':
        pass
    
    current_plan = g.current_plan
  
    econ_measures = (
        EconMeasure.query
        .filter_by(id_plan=current_plan.id)
        .join(EconMeasure.direction)
        .order_by(asc(Direction.code))
        .all()
    )
  
    econ_exec = (
        EconExec.query
        .filter_by(id_plan=current_plan.id)
        .join(EconMeasure.direction)
        .order_by(asc(Direction.code))
        .all()
    )
  
    local_econ_execes = (EconExec.query
        .join(EconMeasure)
        .join(Plan)
        .filter(Plan.id == current_plan.id, EconExec.is_local == True)
        .options(joinedload(EconExec.econ_measures).joinedload(EconMeasure.plan))
        .all())

    non_local_econ_execes = (EconExec.query
        .join(EconMeasure)
        .join(Plan)
        .filter(Plan.id == current_plan.id, EconExec.is_local == False)
        .options(joinedload(EconExec.econ_measures).joinedload(EconMeasure.plan))
        .all())
    

    local_totals = get_cumulative_econ_metrics(current_plan.id, True)
    non_local_totals = get_cumulative_econ_metrics(current_plan.id, False)
    
    total_metrics = {
        'jan_mar_eff': local_totals['jan_mar']['eff_curr_year'] + non_local_totals['jan_mar']['eff_curr_year'],
        'jan_mar_vol': local_totals['jan_mar']['volume_fin'] + non_local_totals['jan_mar']['volume_fin'],
        'jan_jun_eff': local_totals['jan_jun']['eff_curr_year'] + non_local_totals['jan_jun']['eff_curr_year'],
        'jan_jun_vol': local_totals['jan_jun']['volume_fin'] + non_local_totals['jan_jun']['volume_fin'],
        'jan_sep_eff': local_totals['jan_sep']['eff_curr_year'] + non_local_totals['jan_sep']['eff_curr_year'],
        'jan_sep_vol': local_totals['jan_sep']['volume_fin'] + non_local_totals['jan_sep']['volume_fin'],
        'jan_dec_eff': local_totals['jan_dec']['eff_curr_year'] + non_local_totals['jan_dec']['eff_curr_year'],
        'jan_dec_vol': local_totals['jan_dec']['volume_fin'] + non_local_totals['jan_dec']['volume_fin']
    }

    return render_template('plan_events.html',  
                        econ_exec=econ_exec,
                        econ_measures=econ_measures,
                        local_econ_execes=local_econ_execes,
                        non_local_econ_execes=non_local_econ_execes,
                        total_metrics=total_metrics,
                        plan=current_plan, 
                        hide_header=False,
                        add_event_modal=True,
                        confirmModal=True,
                        edit_event_modal=True,
                        sentmodal=current_plan.is_control,
                        context_menu=True
                         )
    
@views.route('/create-econexeces/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def create_econexeces(token):
    current_plan = g.current_plan
    
    id_measure = request.form.get('id_measure')
    name = request.form.get('name') or None

    Volume_value = request.form.get('Volume')
    ExpectedQuarter_value = request.form.get('ExpectedQuarter')

    Payback = to_decimal_3(request.form.get('Payback'))

    EffTut = to_decimal_3(request.form.get('EffTut'))
    EffRub = to_decimal_3(request.form.get('EffRub'))
    EffCurrYear = to_decimal_3(request.form.get('EffCurrYear'))

    VolumeFin = to_decimal_3(request.form.get('VolumeFin'))
    BudgetState = to_decimal_3(request.form.get('BudgetState')) 
    BudgetRep = to_decimal_3(request.form.get('BudgetRep')) 
    BudgetLoc = to_decimal_3(request.form.get('BudgetLoc')) 
    BudgetOther = to_decimal_3(request.form.get('BudgetOther'))
    MoneyOwn = to_decimal_3(request.form.get('MoneyOwn')) 
    MoneyLoan = to_decimal_3(request.form.get('MoneyLoan')) 
    MoneyOther = to_decimal_3(request.form.get('MoneyOther'))

    Volume = int(float(Volume_value)) if Volume_value else None
    ExpectedQuarter = int(float(ExpectedQuarter_value)) if ExpectedQuarter_value else None

    measure = EconMeasure.query.get(id_measure)
    if not measure:
        flash('Направление не найдено', 'error')
        return redirect(url_for('views.plan_events', token=token))
    
    is_local = measure.direction.is_local if measure.direction else False

    new_econexec = EconExec(
        id_measure=id_measure,
        id_plan=current_plan.id,
        name=name,
        Volume=Volume,
        EffTut=EffTut,
        EffRub=EffRub,
        ExpectedQuarter=ExpectedQuarter,
        EffCurrYear=EffCurrYear,
        Payback=Payback,
        VolumeFin=VolumeFin,
        BudgetState=BudgetState,
        BudgetRep=BudgetRep,
        BudgetLoc=BudgetLoc,
        BudgetOther=BudgetOther,
        MoneyOwn=MoneyOwn,
        MoneyLoan=MoneyLoan,
        MoneyOther=MoneyOther,
        is_local=is_local 
    )
    
    db.session.add(new_econexec)
    db.session.commit()
    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)
    flash('Мероприятие добавлено', 'success')
    return redirect(url_for('views.plan_events', token=token))
    
@views.route('/delete-econexeces/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def delete_econexeces(id):
    econ_exec = EconExec.query.get_or_404(id)
    current_plan = Plan.query.get_or_404(econ_exec.econ_measures.id_plan)

    db.session.delete(econ_exec)
    db.session.commit()

    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)
    flash('Мероприятие успешно удалено', 'success')
    return redirect(url_for('views.plan_events', token=current_plan.token))

@views.route('/edit-econexeces/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def edit_econexeces(id):
    name = request.form.get('name') or None

    Volume_value = request.form.get('Volume')
    ExpectedQuarter_value = request.form.get('ExpectedQuarter')
    Payback = to_decimal_3(request.form.get('Payback'))

    EffTut = to_decimal_3(request.form.get('EffTut'))
    EffRub = to_decimal_3(request.form.get('EffRub'))
    EffCurrYear = to_decimal_3(request.form.get('EffCurrYear'))
    
    VolumeFin = to_decimal_3(request.form.get('VolumeFin'))
    BudgetState = to_decimal_3(request.form.get('BudgetState')) 
    BudgetRep = to_decimal_3(request.form.get('BudgetRep')) 
    BudgetLoc = to_decimal_3(request.form.get('BudgetLoc')) 
    BudgetOther = to_decimal_3(request.form.get('BudgetOther'))
    MoneyOwn = to_decimal_3(request.form.get('MoneyOwn')) 
    MoneyLoan = to_decimal_3(request.form.get('MoneyLoan')) 
    MoneyOther = to_decimal_3(request.form.get('MoneyOther'))

    Volume = int(float(Volume_value)) if Volume_value else None
    ExpectedQuarter = int(float(ExpectedQuarter_value)) if ExpectedQuarter_value else None
    
    current_EconExec = EconExec.query.get(id)
    current_plan = Plan.query.get_or_404(current_EconExec.id_plan)

    if not current_EconExec:
        flash('Мероприятие не найдено', 'error')
        return redirect(url_for('views.plan_events', token=current_plan.token))
    
    current_EconExec.name=name
    current_EconExec.Volume=Volume
    current_EconExec.ExpectedQuarter=ExpectedQuarter
    current_EconExec.EffTut=EffTut
    current_EconExec.EffRub=EffRub
    current_EconExec.EffCurrYear=EffCurrYear
    current_EconExec.Payback=Payback
    current_EconExec.VolumeFin=VolumeFin
    current_EconExec.BudgetState=BudgetState
    current_EconExec.BudgetRep=BudgetRep
    current_EconExec.BudgetLoc=BudgetLoc
    current_EconExec.BudgetOther=BudgetOther
    current_EconExec.MoneyOwn=MoneyOwn
    current_EconExec.MoneyLoan=MoneyLoan
    current_EconExec.MoneyOther=MoneyOther

    db.session.commit()
    flash('Мероприятие изменено', 'success')

    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)
    return redirect(url_for('views.plan_events', token=current_plan.token))

@views.route('/get-econexece/<int:id>', methods=['GET'])
@user_with_all_params()
@login_required
def get_econexece(id):
    try:
        existing_measure = EconExec.query.get(id)
        if not existing_measure:
            return jsonify({'error': 'EconExec not found'}), 404
        
        return jsonify(existing_measure.as_dict())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@views.route('/plans/plan-indicators/<token>', methods=['GET', 'POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def plan_indicators(token):    
    if request.method == 'POST':
        pass
    
    current_plan = g.current_plan

    used_indicator_subquery = (db.session.query(IndicatorUsage.id_indicator)
                            .filter(IndicatorUsage.id_plan == current_plan.id)
                            .subquery())

    indicators_non_mandatory = (Indicator.query
                            .filter_by(IsMandatory=False)
                            .filter(~Indicator.id.in_(used_indicator_subquery))
                            .all())
    
    indicators = (IndicatorUsage.query
                .join(Indicator, IndicatorUsage.id_indicator == Indicator.id)
                .filter(IndicatorUsage.id_plan == current_plan.id)
                .order_by(Indicator.Group.asc(), Indicator.RowN.asc())
                .all())
    
    return render_template('plan_indicators.html',  
                        plan=current_plan, 
                        indicators_non_madatory=indicators_non_mandatory,
                        indicators=indicators,
                        hide_header=False,
                        add_indicator_modal=True,
                        edit_indicator_modal=True,
                        confirmModal = True,
                        sentmodal=current_plan.is_control,
                        context_menu = True)

@views.route('/get-indicator/<int:id>', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
def get_indicator(id):
    try:
        existing_IndicatorUsage = IndicatorUsage.query.get(id)
        if not existing_IndicatorUsage:
            return jsonify({'error': 'Indicator not found'}), 404
        
        return jsonify(existing_IndicatorUsage.as_dict())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@views.route('/create-indicator/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def create_indicator(token):
    current_plan = g.current_plan
    
    QYearPrev_ed = to_decimal_3(request.form.get('QYearPrev'))
    QYearCurr_ed = to_decimal_3(request.form.get('QYearCurr'))
    QYearNext_ed = to_decimal_3(request.form.get('QYearNext'))
    id_indicator = request.form.get('id_indicator')


    if id_indicator == None:
        flash('Пустой показатель', 'error')
        return redirect(url_for('views.plan_indicators', id=id))
    
    indicator = Indicator.query.filter_by(id=id_indicator).first()

    QYearPrev = to_decimal_3(QYearPrev_ed * indicator.CoeffToTut)
    QYearCurr = to_decimal_3(QYearCurr_ed * indicator.CoeffToTut)
    QYearNext = to_decimal_3(QYearNext_ed * indicator.CoeffToTut)

    new_IndicatorUsage = IndicatorUsage(
        id_plan=current_plan.id,
        id_indicator=id_indicator,
        QYearPrev=QYearPrev,
        QYearCurr=QYearCurr,
        QYearNext=QYearNext
    )
    
    db.session.add(new_IndicatorUsage)
    db.session.commit()
    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)
    flash('Показатель добавлен', 'success')
    return redirect(url_for('views.plan_indicators', token=token))

@views.route('/edit-indicator/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def edit_indicator(id):
    QYearPrev_ed = to_decimal_3(request.form.get('QYearPrev'))
    QYearCurr_ed = to_decimal_3(request.form.get('QYearCurr'))
    QYearNext_ed = to_decimal_3(request.form.get('QYearNext'))

    if id == None:
        flash('Пустой id', 'error')
        return redirect(request.url)
    
    indicator_usage = IndicatorUsage.query.filter_by(id=id).first()
    indicator_usage.QYearPrev = to_decimal_3(QYearPrev_ed * indicator_usage.indicator.CoeffToTut)
    indicator_usage.QYearCurr = to_decimal_3(QYearCurr_ed * indicator_usage.indicator.CoeffToTut)
    indicator_usage.QYearNext = to_decimal_3(QYearNext_ed * indicator_usage.indicator.CoeffToTut)
    db.session.commit()

    current_plan = Plan.query.get_or_404(indicator_usage.id_plan)
    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)
    flash('Обновление данных', 'success')
    return redirect(url_for('views.plan_indicators', token=current_plan.token))

@views.route('/delete-indicator/<int:id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def delete_indicator(id):
    indicator = IndicatorUsage.query.get_or_404(id)
    current_plan = Plan.query.get_or_404(indicator.id_plan)

    db.session.delete(indicator)
    db.session.commit()
    other_data_indicatorUpdate(current_plan.id)
    update_ChangeTimePlan(current_plan.id)
    
    flash('Показатель успешно удален', 'success')
    return redirect(url_for('views.plan_indicators', token=current_plan.token))

@views.route('/api/change-plan-status/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
def api_change_plan_status(token):
    plan = Plan.query.filter_by(token=token).first()
    
    if request.is_json:
        data = request.get_json()
        status = data.get('status')
    else:
        status = request.form.get('status')
        if status == 'sent':
            uploaded_file = request.files.get('certificate')
            from ..ecp import validate_certificate_for_sending
            is_valid, error_message = validate_certificate_for_sending(uploaded_file)
            if not is_valid:
                flash(error_message, 'error')
                flash('План не был отправлен.', 'error')
                return redirect(request.referrer)
            else:
                flash('Сертификат успешно прошел проверку.', 'success')
    
    if not status:
        if request.is_json:
            return jsonify({'error': 'Статус не указан'}), 400
        else:
            flash('Статус не указан', 'error')
            return redirect(request.referrer or url_for('views.plans'))
    
    status_mapping = {
        'draft': 'is_draft',
        'control': 'is_control',
        'sent': 'is_sent', 
        'sent_without_check': 'is_sent',
        'error': 'is_error',
        'approved': 'is_approved'
    }
    
    if status not in status_mapping:
        if request.is_json:
            return jsonify({'error': 'Неверный статус'}), 400
        else:
            flash('Неверный статус', 'error')
            return redirect(request.referrer or url_for('views.plans'))
    
    if status in status_handlers:
        try:
            result = status_handlers[status](plan)
            db.session.commit()

            if isinstance(result, dict) and "error" in result:
                if request.is_json:
                    return jsonify(result), 400
                else:
                    flash(result["error"], "error")
                    return redirect(request.referrer or url_for('views.plans'))
            message = result if isinstance(result, str) else "Статус изменен"

        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return jsonify({'error': f'Ошибка обработки статуса: {str(e)}'}), 500
            else:
                flash(f'Ошибка обработки статуса: {str(e)}', 'error')
                return redirect(request.referrer or url_for('views.plans'))
    
    if status == 'sent_without_check':
        setattr(plan, status_mapping[status], True)
        
        for other_status, attr_name in status_mapping.items():
            if other_status != status and attr_name != status_mapping[status]:
                setattr(plan, attr_name, False)
                
        new_ticket = Ticket(
            note="План возвращен в статус 'На рассмотрении'.",
            luck=True,
            is_owner = True,
            plan_id=plan.id,
        )
        db.session.add(new_ticket) 
        
        
        notification = Notification(
            user_id=plan.user_id,
            message=f"План {plan.year} возвращен в статус 'На рассмотрении'."
        )
        db.session.add(notification)       
        db.session.commit()
        
        message = "План возвращен в изначальное состояние."
        flash(message, 'success')
        return redirect(url_for('views.plan_audit', token=plan.token))
    
    if request.is_json:
        return jsonify({'message': message, 'status': status})
    else:
        flash(message, 'success')
        if status in ['approved', 'error']:
            return redirect(request.referrer or url_for('views.plans'))
        else:
            return redirect(url_for('views.plan_review', token=plan.token))
        
@views.route('/create-ticket/<token>', methods=['POST'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def create_ticket(token):
    current_plan = g.current_plan
    if not current_plan:
        flash('План не найден.', 'error')
        return redirect(request.referrer)
    
    note = request.form.get('note')
    
    if not note or not note.strip():
        current_app.logger.error("Epty message")
        flash('Сообщение не может быть пустым.', 'error')
        return redirect(request.referrer)
    
    current_plan.afch = True
    current_plan.audit_time = TimeByMinsk()
    
    new_ticket = Ticket(
        note=note.strip(),
        luck=False,
        plan_id=current_plan.id,
        user_id=current_user.id,
        is_owner=current_user.id == current_plan.user_id
    )

    db.session.add(new_ticket)
    db.session.commit()
    
    flash('Сообщение отправлено.', 'success')
    return redirect(request.referrer)

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