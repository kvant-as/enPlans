import datetime
import logging
from venv import logger
from flask import current_app, g, render_template, request, jsonify, Blueprint
from flask_login import current_user, login_required

from website.routes.auth import user_with_all_params
from website.routes.views import owner_only
from website.sessions import session_required
from website.time import TimeByMinsk
from website.utils.plans import get_filtered_plans

from ..models import Direction, Indicator, IndicatorUsage, Ministry, News, Organization, Plan, Region, Event
from .. import db

api_bp = Blueprint('api_bp', __name__, url_prefix='/api/')

from flask import render_template_string

@api_bp.route('/plans', methods=['GET'])
@login_required
def api_get_plans():
    try:
        status_filter = request.args.get('status', 'all')
        year_filter = request.args.get('year', 'all')
        search_name = request.args.get('search_name', '')
        search_okpo = request.args.get('search_okpo', '')
        region = request.args.get('region', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 5, type=int)
        
        region_id = None
        if region and region != 'all':
            try:
                region_id = int(region)
            except (ValueError, TypeError):
                region_id = None
        
        plans, total_count, status_counts = get_filtered_plans(
            current_user, status_filter, year_filter, search_name, search_okpo, region_id, page, per_page
        )
        
        is_compact = current_user.is_auditor or current_user.is_municipal or current_user.is_departament or current_user.is_higher_organization
        
        html = render_template_string(
            '''
            {% import 'macros/components.html' as components %}
            {{ components.plans_list_items(plans, current_user, show_checkboxes, show_actions, custom_empty_message, compact_view) }}
            ''',
            plans=plans,
            current_user=current_user,
            show_checkboxes=False,
            show_actions=True,
            custom_empty_message=None,
            compact_view=is_compact
        )
        
        return jsonify({
            'success': True,
            'html': html,
            'counts': status_counts,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_count': total_count,
                'has_next': page * per_page < total_count
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
@api_bp.route('/export-plans', methods=['GET'])
@login_required
def api_get_export_plans():
    try:
        status_filter = request.args.get('status', 'all')
        year_filter = request.args.get('year', 'all')
        search_name = request.args.get('search_name', '')
        search_okpo = request.args.get('search_okpo', '')
        region = request.args.get('region', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 5, type=int)
                
        region_id = None
        if region and region != 'all':
            try:
                region_id = int(region)
            except (ValueError, TypeError):
                region_id = None
                
        plans, total_count, status_counts = get_filtered_plans(
            current_user, status_filter, year_filter, search_name, search_okpo, region_id, page, per_page
        )
        
        is_compact = current_user.is_auditor or current_user.is_municipal or current_user.is_departament or current_user.is_higher_organization
        
        html = render_template_string(
            '''
            {% import 'macros/components.html' as components %}
            {{ components.plans_list_items(plans, current_user, show_checkboxes, show_actions, custom_empty_message, compact_view) }}
            ''',
            plans=plans,
            current_user=current_user,
            show_checkboxes=True,
            show_actions=False,
            custom_empty_message=None,
            compact_view=is_compact
        )
        
        return jsonify({
            'success': True,
            'html': html,
            'counts': status_counts,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_count': total_count,
                'has_next': page * per_page < total_count
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
@api_bp.route('/approve-plan/<token>', methods=['POST'])
@login_required
def api_approve_plan(token):
    plan = Plan.query.filter_by(token=token).first_or_404()
    data = request.get_json()
    stage = data.get('stage')
    current_time = TimeByMinsk()
    
    if stage == 'regional':
        if not current_user.is_region:
            return jsonify({'success': False, 'error': 'Нет прав'}), 403
        plan.is_region_approved = True
        plan.region_approved_time = current_time
        if plan.plan_type == 'org_large':
            plan.approval_stage = 'municipal'
        else:
            plan.approval_stage = 'department'
        
    elif stage == 'municipal':
        if not current_user.is_municipal:
            return jsonify({'success': False, 'error': 'Нет прав'}), 403
        plan.is_municipal_approved = True
        plan.municipal_approved_time = current_time
        plan.approval_stage = 'department'
        
    elif stage == 'department':
        if not current_user.is_departament:
            return jsonify({'success': False, 'error': 'Нет прав'}), 403
        plan.is_department_approved = True
        plan.department_approved_time = current_time
        if plan.plan_type == 'org_large':
            plan.approval_stage = 'higher'
        else:
            plan.approval_stage = 'completed'
            plan.is_approved = True
            
    elif stage == 'higher':
        if not current_user.is_higher_organization:
            return jsonify({'success': False, 'error': 'Нет прав'}), 403
        plan.is_higher_organization_approved = True
        plan.higher_organization_approved_time = current_time
        plan.approval_stage = 'completed'
        plan.is_approved = True
    
    db.session.commit()
    
    return jsonify({'success': True})

@api_bp.route('/news', methods=['GET'])
def api_news():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 9, type=int)
    filter_type = request.args.get('filter', 'published')
    sort_by = request.args.get('sort', 'date')
    
    current_time = TimeByMinsk()
    query = News.query
    
    if filter_type == 'published':
        query = query.filter(News.published_at <= current_time, News.published_at.isnot(None))

    if sort_by == 'date':
        query = query.order_by(News.published_at.desc().nullslast(), News.created_at.desc())
    elif sort_by == 'views':
        query = query.order_by(News.views_count.desc().nullslast(), News.published_at.desc().nullslast())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'news': [{
            'id': n.id,
            'title': n.title,
            'content': n.content,
            'image_url': n.image_url,
            'published_at': n.published_at.isoformat() if n.published_at else n.created_at.isoformat(),
            'created_at': n.created_at.isoformat(),
            'views_count': n.views_count or 0,
            'is_published': n.published_at is not None and n.published_at <= current_time
        } for n in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'total_views': db.session.query(db.func.sum(News.views_count)).scalar() or 0
    })

@api_bp.route('/news/<int:id>', methods=['GET'])
def api_news_post(id):
    current_time = TimeByMinsk()
    post = News.query.get(id)
    if not post:
        return jsonify({'success': False, 'error': 'Новость не найдена'}), 404
    
    post.views_count = (post.views_count or 0) + 1
    db.session.commit()
    
    return jsonify({
        'success': True,
        'news': {
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'image_url': post.image_url,
            'published_at': post.published_at.isoformat() if post.published_at else post.created_at.isoformat(),
            'created_at': post.created_at.isoformat(),
            'views_count': post.views_count or 0,
            'is_published': post.published_at is not None and post.published_at <= current_time
        }
    })

@api_bp.route('/organizations')
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

@api_bp.route('/ministries')
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

@api_bp.route('/regions')
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
    
@api_bp.route('/get-event/<int:id>', methods=['GET'])
@user_with_all_params()
@login_required
@session_required
def get_event(id):
    try:
        current_event = Event.query.get(id)
        if not current_event:
            return jsonify({'error': 'Event not found'}), 404
        
        result = current_event.as_dict()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_event: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    
@api_bp.route('/get-indicator/<int:id>', methods=['GET'])
@login_required
def get_indicator_api(id):
    try:
        indicator_usage = IndicatorUsage.query.get_or_404(id)
        
        used_coeff = indicator_usage.custom_coeff_to_tut if indicator_usage.custom_coeff_to_tut is not None else indicator_usage.indicator.CoeffToTut
        
        data = {
            'id': indicator_usage.id,
            'id_indicator': indicator_usage.id_indicator,
            'code': indicator_usage.indicator.code,
            'name': indicator_usage.indicator.name,
            'note': indicator_usage.note,
            'unit_name': indicator_usage.indicator.unit.name if indicator_usage.indicator.unit else '',
            'CoeffToTut': float(indicator_usage.indicator.CoeffToTut) if indicator_usage.indicator.CoeffToTut else 0,
            'custom_coeff_to_tut': float(indicator_usage.custom_coeff_to_tut) if indicator_usage.custom_coeff_to_tut else None,
            'used_coeff': float(used_coeff) if used_coeff else 0,
            'is_custom': indicator_usage.custom_coeff_to_tut is not None,
            'QYearBeforePrev': float(indicator_usage.QYearBeforePrev) if indicator_usage.QYearBeforePrev else 0,
            'QYearPrev': float(indicator_usage.QYearPrev) if indicator_usage.QYearPrev else 0,
            'QYearCurrent': float(indicator_usage.QYearCurrent) if indicator_usage.QYearCurrent else 0,
            'is_local': indicator_usage.is_local,
            'is_renewable': indicator_usage.is_renewable
        }
        
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f'Error getting indicator {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@api_bp.route('/indicators/<token>', methods=['GET'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def get_indicators_data(token):
    current_plan = g.current_plan
    
    current_plan_indicators = (IndicatorUsage.query
                .join(Indicator, IndicatorUsage.id_indicator == Indicator.id)
                .filter(IndicatorUsage.id_plan == current_plan.id)
                .order_by(Indicator.Group.asc(), Indicator.RowN.asc())
                .all())
    
    indicators_data = []
    for row in current_plan_indicators:
        indicators_data.append({
            'id': row.id,
            'id_indicator': row.id_indicator,
            'code': row.indicator.code,
            'name': row.indicator.name,
            'note': row.note,
            'unit_name': row.indicator.unit.name,
            'group': float(row.indicator.Group) if row.indicator.Group else None,
            'row_n': row.indicator.RowN,
            'coeff_to_tut': float(row.indicator.CoeffToTut) if row.indicator.CoeffToTut else 1,
            
            'QYearBeforePrev_unit': float(row.QYearBeforePrev / (row.custom_coeff_to_tut if row.custom_coeff_to_tut is not None else row.indicator.CoeffToTut)) if row.QYearBeforePrev and ((row.custom_coeff_to_tut is not None and row.custom_coeff_to_tut) or row.indicator.CoeffToTut) else 0,
            'QYearBeforePrev_tut': float(row.QYearBeforePrev) if row.QYearBeforePrev else 0,

            'QYearPrev_unit': float(row.QYearPrev / (row.custom_coeff_to_tut if row.custom_coeff_to_tut is not None else row.indicator.CoeffToTut)) if row.QYearPrev and ((row.custom_coeff_to_tut is not None and row.custom_coeff_to_tut) or row.indicator.CoeffToTut) else 0,
            'QYearPrev_tut': float(row.QYearPrev) if row.QYearPrev else 0,

            'QYearCurrent_unit': float(row.QYearCurrent / (row.custom_coeff_to_tut if row.custom_coeff_to_tut is not None else row.indicator.CoeffToTut)) if row.QYearCurrent and ((row.custom_coeff_to_tut is not None and row.custom_coeff_to_tut) or row.indicator.CoeffToTut) else 0,
            'QYearCurrent_tut': float(row.QYearCurrent) if row.QYearCurrent else 0,
            
            'difference': float(row.QYearCurrent - row.QYearPrev) if row.QYearCurrent and row.QYearPrev else 0
        })
    
    return jsonify({
        'success': True,
        'plan_id': current_plan.id,
        'plan_year': current_plan.year,
        'indicators': indicators_data
    })
    
@api_bp.route('/events/<token>', methods=['GET'])
@user_with_all_params()
@login_required
@owner_only
@session_required
def get_events_data(token):
    current_plan = g.current_plan
    event_type = request.args.get('type')
    
    if event_type not in ['saving', 'increase']:
        return jsonify({'success': False, 'error': 'Invalid event type'}), 400
    
    if event_type == 'saving':
        type_filter = Event.is_econom == True
    else:
        type_filter = Event.is_increase == True
    
    period_codes = ['0001', '0002', '0003', '0004']
    
    original_events = (Event.query
        .join(Direction, Event.id_direction == Direction.id)
        .filter(Event.id_plan == current_plan.id)
        .filter(type_filter)
        .filter(Event.is_corrected == False)
        .filter(Direction.code.notin_(period_codes))
        .order_by(Event.id.asc())
        .all())
    
    events_with_changes = (Event.query
        .join(Direction, Event.id_direction == Direction.id)
        .filter(Event.id_plan == current_plan.id)
        .filter(type_filter)
        .filter(Event.is_corrected == True)
        .filter(Direction.code.notin_(period_codes))
        .order_by(Event.id.asc())
        .all())
    
    period_events = (Event.query
        .join(Direction, Event.id_direction == Direction.id)
        .filter(Event.id_plan == current_plan.id)
        .filter(type_filter)
        .filter(Direction.code.in_(period_codes))
        .filter(Event.is_corrected == False)
        .order_by(Direction.code.asc())
        .all())

    # logger.debug(f"=== DEBUG get_events_data ===")
    # logger.debug(f"event_type: {event_type}")
    # logger.debug(f"plan_id: {current_plan.id}")
    # logger.debug(f"period_events count: {len(period_events)}")
    # for pe in period_events:
    #     logger.debug(f"  period_event: id={pe.id}, code={pe.direction.code}, EffCurrYear={pe.EffCurrYear}")

    period_metrics = {}
    for period_event in period_events:
        code = period_event.direction.code
        
        period_metrics[code] = {
            'id': period_event.id,
            'eff_curr_year': float(period_event.EffCurrYear) if period_event.EffCurrYear else 0
        }
    
    total_metrics = {
        'jan_mar_eff': period_metrics.get('0001', {}).get('eff_curr_year', 0),
        'jan_jun_eff': period_metrics.get('0002', {}).get('eff_curr_year', 0),
        'jan_sep_eff': period_metrics.get('0003', {}).get('eff_curr_year', 0),
        'jan_dec_eff': period_metrics.get('0004', {}).get('eff_curr_year', 0)
    }
    
    def serialize_event(event):
        unit_name = None
        if event.direction and event.direction.unit:
            unit_name = event.direction.unit.name
        
        return {
            'id': event.id,
            'id_direction': event.id_direction,
            'direction_code': event.direction.code if event.direction else None,
            'display_code': getattr(event, 'display_code', event.direction.code if event.direction else None),
            'name': event.name,
            'unit_name': unit_name,
            'Volume': float(event.Volume) if event.Volume else None,
            'EffTut': float(event.EffTut) if event.EffTut else None,
            'EffRub': float(event.EffRub) if event.EffRub else None,
            'ExpectedQuarter': event.ExpectedQuarter,
            'EffCurrYear': float(event.EffCurrYear) if event.EffCurrYear else None,
            'Payback': float(event.Payback) if event.Payback else None,
            'VolumeFin': float(event.VolumeFin) if event.VolumeFin else None,
            'BudgetState': float(event.BudgetState) if event.BudgetState else None,
            'BudgetRep': float(event.BudgetRep) if event.BudgetRep else None,
            'BudgetLoc': float(event.BudgetLoc) if event.BudgetLoc else None,
            'BudgetOther': float(event.BudgetOther) if event.BudgetOther else None,
            'MoneyOwn': float(event.MoneyOwn) if event.MoneyOwn else None,
            'MoneyLoan': float(event.MoneyLoan) if event.MoneyLoan else None,
            'MoneyOther': float(event.MoneyOther) if event.MoneyOther else None,
            'is_corrected': event.is_corrected
        }
    
    return jsonify({
        'success': True,
        'plan_id': current_plan.id,
        'plan_year': current_plan.year,
        'event_type': event_type,
        'original_events': [serialize_event(e) for e in original_events],
        'events_with_changes': [serialize_event(e) for e in events_with_changes],
        'period_metrics': period_metrics,
        'total_metrics': total_metrics
    })

@api_bp.route('/plan-rates/<token>', methods=['GET'])
@login_required
def get_plan_rates(token):
    from website.models import Plan
    
    plan = Plan.query.filter_by(token=token).first()
    if not plan:
        return jsonify({'success': False, 'error': 'Plan not found'}), 404
    
    return jsonify({
        'success': True,
        'usd_rate': float(plan.usd_rate) if plan.usd_rate else None,
        'cost_per_toe_usd': float(plan.cost_per_toe_usd) if plan.cost_per_toe_usd else None
    })

@api_bp.route('/refresh-plan-rates/<token>', methods=['POST'])
@login_required
def refresh_plan_rates(token):
    from website.models import Plan
    from website.utils.currency_rates import fetch_usd_rate_from_belarusbank
    
    plan = Plan.query.filter_by(token=token).first()
    if not plan:
        return jsonify({'success': False, 'error': 'Plan not found'}), 404
    
    usd_rate, error = fetch_usd_rate_from_belarusbank()
    
    if usd_rate is None:
        return jsonify({'success': False, 'error': error}), 500
    
    plan.usd_rate = usd_rate
    
    if plan.cost_per_toe_usd is None or plan.cost_per_toe_usd <= 0:
        plan.cost_per_toe_usd = 260.0
    
    try:
        from website import db
        db.session.commit()
        
        return jsonify({
            'success': True,
            'usd_rate': float(plan.usd_rate),
            'cost_per_toe_usd': float(plan.cost_per_toe_usd)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500