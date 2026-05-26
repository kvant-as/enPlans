import logging
from venv import logger
from flask import current_app, g, request, jsonify, Blueprint
from flask_login import login_required

from website.routes.auth import user_with_all_params
from website.routes.views import owner_only
from website.sessions import session_required
from website.time import TimeByMinsk

from ..models import Direction, Indicator, IndicatorUsage, Ministry, News, Organization, Region, Event
from .. import db

api_bp = Blueprint('api_bp', __name__, url_prefix='/api/')

@api_bp.route('/news', methods=['GET'])
@login_required
def get_news():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    news_items = News.query.filter(
        News.is_published == True,
        News.published_at <= TimeByMinsk()
    ).order_by(News.published_at.desc()).paginate(page=page, per_page=per_page)
    
    return jsonify({
        'news': [{
            'id': item.id,
            'title': item.title,
            'content': item.content,
            'image_url': item.image_url,
            'published_at': item.published_at.isoformat() if item.published_at else None,
            'views_count': item.views_count
        } for item in news_items.items],
        'total': news_items.total,
        'page': news_items.page,
        'pages': news_items.pages
    })

@api_bp.route('/news/<int:news_id>', methods=['GET'])
@login_required
def get_news_detail(news_id):
    news_item = News.query.get_or_404(news_id)
    
    news_item.views_count += 1
    db.session.commit()
    
    return jsonify({
        'id': news_item.id,
        'title': news_item.title,
        'content': news_item.content,
        'image_url': news_item.image_url,
        'published_at': news_item.published_at.isoformat() if news_item.published_at else None,
        'views_count': news_item.views_count,
        'created_at': news_item.created_at.isoformat()
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
    event_type = request.args.get('type', 'saving')
    
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

    logger.debug(f"=== DEBUG get_events_data ===")
    logger.debug(f"event_type: {event_type}")
    logger.debug(f"plan_id: {current_plan.id}")
    logger.debug(f"period_events count: {len(period_events)}")
    for pe in period_events:
        logger.debug(f"  period_event: id={pe.id}, code={pe.direction.code}, EffCurrYear={pe.EffCurrYear}")

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
