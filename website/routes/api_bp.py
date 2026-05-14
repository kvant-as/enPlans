from flask import current_app, request, jsonify, Blueprint
from flask_login import current_user, login_required
import requests

from ..models import Chat, ChatMessage

from ..time import TimeByMinsk
from .. import db

api_bp = Blueprint('api_bp', __name__, url_prefix='/api/')


