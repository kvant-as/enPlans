from flask import current_app, request, jsonify, Blueprint
from flask_login import current_user, login_required
import requests

from ..models import TimeByMinsk, Chat, ChatMessage
from .. import db

chat_bp = Blueprint('chat_bp', __name__, url_prefix='/api/chat')

@chat_bp.route('/<int:chat_id>/end', methods=['POST'])
@login_required
def end_chat(chat_id):
    try:
        chat = Chat.query.get_or_404(chat_id)
        if chat.created_by_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403

        db.session.delete(chat)
        db.session.commit()

        api_url = current_app.config.get('AI_API_URL')
        x_api_key = current_app.config.get('AI_X_API_KEY')
        external_payload = {
            'chat_id': chat_id,
        }
        external_headers = {
            'X-API-KEY': x_api_key,
            'Content-Type': 'application/json'
        }
        try:
            external_response = requests.post(
                f"{api_url}/v1/delete-chat",
                json=external_payload,
                headers=external_headers,
                timeout=30
            )
            if external_response.status_code == 200:
                bot_response_data = external_response.json()
                current_app.logger.debug(f"External API response: Yes")
                # current_app.logger.debug(f"External API response: {bot_response_data}")
            else:
                current_app.logger.warning(f"External API returned status {external_response.status_code}: {external_response.text}")
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error calling external API: {str(e)}")

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in end_chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/<int:chat_id>/messages', methods=['GET'])
@login_required
def get_messages(chat_id):
    try:
        messages = ChatMessage.query.filter_by(chat_id=chat_id).order_by(ChatMessage.created_at.asc()).all()
        messages_data = [{
            'id': msg.id,
            'chat_id': msg.chat_id,
            'content': msg.content,
            'is_user': msg.is_user,
            'created_at': msg.created_at.isoformat() if msg.created_at else None
        } for msg in messages]
        return jsonify(messages_data)
    except Exception as e:
        print(f"Error in get_messages: {str(e)}")
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/send-message', methods=['POST'])
@login_required
def send_message():
    try:
        data = request.get_json()
        content = data.get('content').strip()
        
        if current_user.is_admin:
            user_id = data.get('user_id')
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': 'enabled only for admin'
                }), 400
        
        if not content:
            current_app.logger.debug(f"Send message failed: missing field - content: {content}")
            return jsonify({
                'success': False,
                'error': 'Missing required field'
            }), 400
        chat = Chat.query.filter_by(created_by_id=current_user.id).order_by(Chat.created_at.desc()).first()
        if not chat:
            chat = Chat(
                title=f"Чат поддержки",
                created_by_id=current_user.id
            )
            db.session.add(chat)
            db.session.flush()
            current_app.logger.debug(f"Created new chat")

        message = ChatMessage(
            chat_id=chat.id,
            content=content,
            is_user=True
        )
        db.session.add(message)

        api_url = current_app.config.get('AI_API_URL')
        x_api_key = current_app.config.get('AI_X_API_KEY')
        external_payload = {
            'chat_id': chat.id,
            'message': content,
            'user_id': current_user.id
        }
        external_headers = {
            'X-API-KEY': x_api_key,
            'Content-Type': 'application/json'
        }
        try:
            external_response = requests.post(
                f"{api_url}/v1/send-message",
                json=external_payload,
                headers=external_headers,
                timeout=30  # Таймаут 30 секунд
            )
            if external_response.status_code == 200:
                bot_response_data = external_response.json()
                bot_message = bot_response_data.get('response')
                current_app.logger.debug(f"External API response: {bot_response_data}")
            else:
                bot_message = "error: Ошибка соединения"
                current_app.logger.warning(f"External API returned status {external_response.status_code}: {external_response.text}")
        except requests.exceptions.RequestException as e:
            bot_message = "error: Ошибка соединения"
            current_app.logger.error(f"Error calling external API: {str(e)}")
        message_answ = ChatMessage(
            chat_id=chat.id,
            content=bot_message,
            is_user=False
        )
        db.session.add(message_answ)
        chat.updated_at = TimeByMinsk()
        db.session.commit()
        current_app.logger.debug(f"Message sent to chat {chat.id}")
        return jsonify({
            'success': True,
            'chat_id': chat.id,
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in send_message: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/check-existing-chat', methods=['GET'])
@login_required
def check_existing_chat():
    try:
        chat = Chat.query.filter_by(created_by_id=current_user.id).order_by(Chat.created_at.desc()).first()
        if chat:
            return jsonify({
                'has_active_chat': True,
                'chat_id': chat.id,
                'chat_type': None
            })
        else:
            return jsonify({
                'has_active_chat': False
            })
    except Exception as e:
        current_app.logger.error(f"Error in check_existing_chat: {str(e)}")
        return jsonify({'error': str(e)}), 500