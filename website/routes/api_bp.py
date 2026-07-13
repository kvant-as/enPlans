import logging
from venv import logger
from flask import current_app, g, request, jsonify, Blueprint, render_template_string
from flask_login import current_user, login_required

from website.routes.auth import user_with_all_params
from website.routes.views import owner_only
from website.sessions import session_required
from website.time import TimeByMinsk
from website.utils.plans import get_filtered_plans

from ..models import Direction, Indicator, IndicatorUsage, News, Notification, Organization, Region, Event, StatPlan, StatPlanValue
from .. import db

api_bp = Blueprint('api_bp', __name__, url_prefix='/api/')

logger = logging.getLogger(__name__)

@api_bp.route('/plans', methods=['GET'])
@login_required
def api_get_plans():
    try:
        status_filter = request.args.get('status', 'all')
        year_filter = request.args.get('year', 'all')
        search_name = request.args.get('search_name', '')
        search_ynp = request.args.get('search_ynp', '')
        region = request.args.get('region', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 5, type=int)
        show_checkboxes = request.args.get('show_checkboxes', 'false').lower() == 'true'
        
        region_id = None
        if region and region != 'all':
            try:
                region_id = int(region)
            except (ValueError, TypeError):
                region_id = None
        
        plans, total_count, status_counts = get_filtered_plans(
            current_user, status_filter, year_filter, search_name, search_ynp, region_id, page, per_page
        )
        
        is_compact = current_user.is_auditor
        
        html = render_template_string(
            '''
            {% import 'macros/components.html' as components %}
            {{ components.plans_list_items(plans, current_user, show_checkboxes, show_actions, custom_empty_message, compact_view) }}
            ''',
            plans=plans,
            current_user=current_user,
            show_checkboxes=show_checkboxes,
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
        org_type = request.args.get("type", "", type=str).strip()
        hide_region_management = request.args.get("hide_rm", "false", type=str).lower() == "true"

        query = Organization.query.filter_by(is_active=True)

        if hide_region_management:
            query = query.filter(Organization.is_region_management == False)

        if org_type == 'respondent':
            query = query.filter(Organization.is_regular == True)
        elif org_type == 'auditor':
            query = query.filter(Organization.is_coordinator == True)
        elif org_type == 'approver':
            query = query.filter(Organization.is_approver == True)

        if search_query:
            query = query.filter(
                db.or_(
                    Organization.name.ilike(f"%{search_query}%"),
                    Organization.okpo.ilike(f"%{search_query}%"),
                    Organization.ynp.ilike(f"%{search_query}%")
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
        
        coeff_before = indicator_usage.coeff_before_prev if indicator_usage.coeff_before_prev is not None else indicator_usage.indicator.CoeffToTut
        coeff_prev = indicator_usage.coeff_prev if indicator_usage.coeff_prev is not None else indicator_usage.indicator.CoeffToTut
        coeff_current = indicator_usage.coeff_current if indicator_usage.coeff_current is not None else indicator_usage.indicator.CoeffToTut
        
        data = {
            'id': indicator_usage.id,
            'id_indicator': indicator_usage.id_indicator,
            'code': indicator_usage.indicator.code,
            'name': indicator_usage.indicator.name,
            'note': indicator_usage.note,
            'unit_name': indicator_usage.indicator.unit.name if indicator_usage.indicator.unit else '',
            'CoeffToTut': float(indicator_usage.indicator.CoeffToTut) if indicator_usage.indicator.CoeffToTut else 0,
            'coeff_before_prev': float(indicator_usage.coeff_before_prev) if indicator_usage.coeff_before_prev else None,
            'coeff_prev': float(indicator_usage.coeff_prev) if indicator_usage.coeff_prev else None,
            'coeff_current': float(indicator_usage.coeff_current) if indicator_usage.coeff_current else None,
            'used_coeff_before': float(coeff_before) if coeff_before else 0,
            'used_coeff_prev': float(coeff_prev) if coeff_prev else 0,
            'used_coeff_current': float(coeff_current) if coeff_current else 0,
            'is_custom_before': indicator_usage.coeff_before_prev is not None,
            'is_custom_prev': indicator_usage.coeff_prev is not None,
            'is_custom_current': indicator_usage.coeff_current is not None,
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
        coeff_before = row.coeff_before_prev if row.coeff_before_prev is not None else row.indicator.CoeffToTut
        coeff_prev = row.coeff_prev if row.coeff_prev is not None else row.indicator.CoeffToTut
        coeff_current = row.coeff_current if row.coeff_current is not None else row.indicator.CoeffToTut
        
        QYearBeforePrev_unit = float(row.QYearBeforePrev / coeff_before) if row.QYearBeforePrev and coeff_before else 0
        QYearPrev_unit = float(row.QYearPrev / coeff_prev) if row.QYearPrev and coeff_prev else 0
        QYearCurrent_unit = float(row.QYearCurrent / coeff_current) if row.QYearCurrent and coeff_current else 0
        
        indicators_data.append({
            'id': row.id,
            'id_indicator': row.id_indicator,
            'code': row.indicator.code,
            'name': row.indicator.name,
            'note': row.note,
            'unit_name': row.indicator.unit.name,
            'group': float(row.indicator.Group) if row.indicator.Group else None,
            'row_n': row.indicator.RowN,
            'coeff_before_prev': float(row.coeff_before_prev) if row.coeff_before_prev else None,
            'coeff_prev': float(row.coeff_prev) if row.coeff_prev else None,
            'coeff_current': float(row.coeff_current) if row.coeff_current else None,
            
            'QYearBeforePrev_unit': QYearBeforePrev_unit,
            'QYearBeforePrev_tut': float(row.QYearBeforePrev) if row.QYearBeforePrev else 0,

            'QYearPrev_unit': QYearPrev_unit,
            'QYearPrev_tut': float(row.QYearPrev) if row.QYearPrev else 0,

            'QYearCurrent_unit': QYearCurrent_unit,
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
            'ObchVolumeFin': float(event.ObchVolumeFin) if event.ObchVolumeFin else None,
            'VolumeFinCurrentYear': float(event.VolumeFinCurrentYear) if event.VolumeFinCurrentYear else None,
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
    
@api_bp.route('/notifications', methods=['GET'])
@user_with_all_params()
@login_required
def api_notifications():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 3, type=int)
    
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'notifications': [
            {
                'id': n.id,
                'message': n.message,
                'is_read': n.is_read,
                'created_at': n.created_at.strftime('%Y-%m-%d %H:%M:%S') if n.created_at else None
            }
            for n in notifications.items
        ],
        'page': notifications.page,
        'per_page': notifications.per_page,
        'total': notifications.total,
        'has_next': notifications.has_next
    })

@api_bp.route('/notifications/mark-all-read', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'message': 'Все уведомления отмечены как прочитанные'})

@api_bp.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@user_with_all_params()
@login_required
@session_required
def mark_notification_read(notification_id):
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
    if notification:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Уведомление не найдено'}), 404

@api_bp.route('/stat-data/<int:organization_id>')
def get_stat_data(organization_id):
    try:
        stat_reports = StatPlan.query.filter_by(
            organization_id=organization_id
        ).all()

        if not stat_reports:
            return jsonify({
                'success': False,
                'message': 'Статистические данные не найдены'
            }), 404

        # Маппинг кодов плана к строкам и колонкам в статистике
        mapping = {
            # 12-тэк
            '1000': {'report': '12-tek', 'row': '110', 'col': '1'},
            '1104': {'report': '12-tek', 'row': '110', 'col': '2'},
            '1105': {'report': '12-tek', 'row': '110', 'col': '3'},
            '9900': {'report': '12-tek', 'row': '110', 'col': '5'},
            '1404': {'report': '12-tek', 'row': '140', 'col': '5'},
            '1424': {'report': '12-tek', 'row': '142', 'col': '5'},
            '9915': {'report': '12-tek', 'row': '110', 'col': '4'},
            '1405': {'report': '12-tek', 'row': '140', 'col': '4'},
            '1425': {'report': '12-tek', 'row': '142', 'col': '4'},
            '260': {'report': '12-tek', 'row': '260', 'col': '1'},
            
            # 4-тэк
            '2000': {'report': '4-tek', 'row': '1090', 'col': '3', 'subtract': ['1090_5', '1090_6', '1092_7']},
            '2001': {'report': '4-tek', 'row': '1050', 'col': '3', 'subtract': ['1050_5', '1050_6']},
            '2002': {'report': '4-tek', 'row': '1040', 'col': '3', 'subtract': ['1040_5', '1040_6']},
            '2003': {'report': '4-tek', 'row': '1660', 'col': '3', 'subtract': ['1660_5', '1660_6']},
            '2004': {'report': '4-tek', 'row': '1075', 'col': '3', 'subtract': ['1075_5', '1075_6']},
            '2005': {'report': '4-tek', 'row': '1160', 'col': '3', 'subtract': ['1160_5', '1160_6']},
            '2006': {'report': '4-tek', 'row': '1150', 'col': '3', 'subtract': ['1150_5', '1150_6', '1152_7']},
            '2007': {'report': '4-tek', 'row': '1060', 'col': '3', 'subtract': ['1060_5', '1060_6']},
            '2008': {'report': '4-tek', 'row': '1750', 'col': '3', 'subtract': ['1750_5', '1750_6']},
            '2009': {'report': '4-tek', 'row': '1790', 'col': '3', 'subtract': ['1790_5', '1790_6']},
            '2010': {'report': '4-tek', 'row': '1110', 'col': '3', 'subtract': ['1110_5', '1110_6']},
            '2011': {'report': '4-tek', 'row': '1620+1630', 'col': '3', 'subtract': ['1620_5', '1620_6', '1630_5', '1630_6']},
            '2012': {'report': '4-tek', 'row': '1640', 'col': '3', 'subtract': ['1640_5', '1640_6']},
            '2013': {'report': '4-tek', 'row': '1794', 'col': '3', 'subtract': ['1794_5', '1794_6']},
            '2014': {'report': '4-tek', 'row': '1745', 'col': '3', 'subtract': ['1745_5', '1745_6']},
            '2015': {'report': '4-tek', 'row': '1690', 'col': '3', 'subtract': ['1690_5', '1690_6']},
            '2016': {'report': '4-tek', 'row': '1680', 'col': '3', 'subtract': ['1680_5', '1680_6']},
            '2017': {'report': '4-tek', 'row': '1742', 'col': '3', 'subtract': ['1742_5', '1742_6']},
            '2018': {'report': '4-tek', 'row': '1744', 'col': '3', 'subtract': ['1744_5', '1744_6']},
            '2019': {'report': '4-tek', 'row': '1785', 'col': '3', 'subtract': ['1785_5', '1785_6']},
            '2020': {'report': '4-tek', 'row': '1730', 'col': '3', 'subtract': ['1730_5', '1730_6']},
            '2021': {'report': '4-tek', 'row': '1740', 'col': '3', 'subtract': ['1740_5', '1740_6']},
            '2022': {'report': '4-tek', 'row': '1780', 'col': '3', 'subtract': ['1780_5', '1780_6']},
        }

        result = {
            'success': True,
            'organization_id': organization_id,
            'years': [],
            'data': {},
            'mapping': mapping
        }

        for report in stat_reports:
            year = str(report.year)
            
            if year not in result['years']:
                result['years'].append(year)
            
            if year not in result['data']:
                result['data'][year] = {}
            
            report_type = report.type
            
            if report_type not in result['data'][year]:
                result['data'][year][report_type] = []
            
            for val in report.values:
                result['data'][year][report_type].append({
                    'row': str(val.row_code),
                    'column': str(val.column_code),
                    'value': float(val.value) if val.value is not None else 0
                })

        result['years'].sort()
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting stat data: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500