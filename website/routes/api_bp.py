import logging
from venv import logger
from flask import current_app, request, jsonify, Blueprint
from flask_login import login_required

from website.routes.auth import user_with_all_params
from website.sessions import session_required

from ..models import IndicatorUsage, Ministry, Organization, Region, Event
from .. import db

api_bp = Blueprint('api_bp', __name__, url_prefix='/api/')

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


    
    

    

