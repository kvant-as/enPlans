from flask import current_app, request, jsonify, Blueprint
from flask_login import current_user, login_required
import requests

from ..models import Chat, ChatMessage
from common_models import current_utc_time, db
from .org_edit_bot import ORG_EDIT_CHAT_TYPE, handle_org_edit_message
from .no_org_bot import NO_ORG_CHAT_TYPE, handle_no_org_message

chat_bp = Blueprint('chat_bp', __name__, url_prefix='/api/chat')

# тип 'dif' ("Другое") в виджете виртуального помощника — вопрос уходит живому
# администратору, без обращения к ИИ; 'org-edit' и 'no-org' — автоматические
# сценарии (см. org_edit_bot.py / no_org_bot.py), тоже без ИИ; 'compl-plan'
# по-прежнему идёт через ИИ
SUPPORT_CHAT_TYPE = 'dif'
# типы, которые не обращаются к внешнему ИИ-бэкенду вовсе (значит и удаление
# чата — чисто локальное, без вызова /v1/delete-chat)
LOCAL_ONLY_CHAT_TYPES = (SUPPORT_CHAT_TYPE, ORG_EDIT_CHAT_TYPE, NO_ORG_CHAT_TYPE)

# Ограничение на длину одного чата (и со стороны пользователя, и со стороны
# администратора/бота) — дальше нужно завершить чат и начать новый; тот же
# лимит проверяется в admin_support.py при ответе администратора
MAX_MESSAGES_PER_CHAT = 50


@chat_bp.route('/<int:chat_id>/end', methods=['POST'])
@login_required
def end_chat(chat_id):
    try:
        chat = Chat.query.get_or_404(chat_id)
        if chat.created_by_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403

        is_local_only = chat.chat_type in LOCAL_ONLY_CHAT_TYPES
        db.session.delete(chat)
        db.session.commit()

        if not is_local_only:
            api_url = current_app.config.get('AI_API_URL')
            x_api_key = current_app.config.get('AI_X_API_KEY')
            external_payload = {'chat_id': chat_id}
            external_headers = {'X-API-KEY': x_api_key, 'Content-Type': 'application/json'}
            try:
                external_response = requests.post(
                    f"{api_url}/v1/delete-chat",
                    json=external_payload,
                    headers=external_headers,
                    timeout=30
                )
                if external_response.status_code != 200:
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
        chat = Chat.query.get_or_404(chat_id)
        if chat.created_by_id != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'Access denied'}), 403

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
        current_app.logger.error(f"Error in get_messages: {str(e)}")
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/send-message', methods=['POST'])
@login_required
def send_message():
    try:
        data = request.get_json() or {}
        content = (data.get('content') or '').strip()
        chat_type = data.get('chat_type')

        if not content:
            current_app.logger.debug("Send message failed: missing field - content")
            return jsonify({'success': False, 'error': 'Missing required field'}), 400

        chat = Chat.query.filter_by(created_by_id=current_user.id).order_by(Chat.created_at.desc()).first()
        if not chat:
            chat = Chat(
                title="Чат поддержки",
                created_by_id=current_user.id,
                chat_type=chat_type,
            )
            db.session.add(chat)
            db.session.flush()
            current_app.logger.debug("Created new chat")

        is_support = chat.chat_type == SUPPORT_CHAT_TYPE
        is_org_edit = chat.chat_type == ORG_EDIT_CHAT_TYPE
        is_no_org = chat.chat_type == NO_ORG_CHAT_TYPE

        # ИИ-помощник пока доступен только администраторам; обращения
        # "Другое" (живому оператору), "Изменить данные организации" и
        # "Нет организации" (автоматические сценарии) доступны всем
        # авторизованным
        if not is_support and not is_org_edit and not is_no_org and not current_user.is_admin:
            return jsonify({'success': False, 'error': 'error: enabled only for admin'}), 400

        if chat.messages.count() >= MAX_MESSAGES_PER_CHAT:
            return jsonify({
                'success': False,
                'error': f'Достигнут лимит сообщений в этом чате ({MAX_MESSAGES_PER_CHAT}). '
                         'Завершите чат («Завершить чат») и начните новый.',
            }), 400

        message = ChatMessage(
            chat_id=chat.id,
            content=content,
            is_user=True
        )
        db.session.add(message)

        if is_support:
            # Обращение к администратору: просто сохраняем сообщение, оно
            # появится у всех администраторов в панели — ответ придёт оттуда
            chat.updated_at = current_utc_time()
            db.session.commit()
            current_app.logger.debug(f"Support message saved to chat {chat.id}")
            return jsonify({'success': True, 'chat_id': chat.id}), 200

        if is_org_edit:
            # Автоматический сценарий — бот отвечает сразу же, без внешнего
            # ИИ и без участия администратора (см. org_edit_bot.py)
            bot_reply = handle_org_edit_message(chat, content, current_user)
            db.session.add(ChatMessage(chat_id=chat.id, content=bot_reply, is_user=False))
            chat.updated_at = current_utc_time()
            db.session.commit()
            current_app.logger.debug(f"Org-edit bot replied in chat {chat.id}")
            return jsonify({'success': True, 'chat_id': chat.id}), 200

        if is_no_org:
            # Автоматический сценарий — то же самое, но про поиск/регистрацию
            # организации и её роль в цепочке согласования (см. no_org_bot.py)
            bot_reply = handle_no_org_message(chat, content, current_user)
            db.session.add(ChatMessage(chat_id=chat.id, content=bot_reply, is_user=False))
            chat.updated_at = current_utc_time()
            db.session.commit()
            current_app.logger.debug(f"No-org bot replied in chat {chat.id}")
            return jsonify({'success': True, 'chat_id': chat.id}), 200

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
                timeout=30
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
        chat.updated_at = current_utc_time()
        db.session.commit()
        current_app.logger.debug(f"Message sent to chat {chat.id}")
        return jsonify({'success': True, 'chat_id': chat.id}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in send_message: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@chat_bp.route('/check-existing-chat', methods=['GET'])
@login_required
def check_existing_chat():
    try:
        chat = Chat.query.filter_by(created_by_id=current_user.id).order_by(Chat.created_at.desc()).first()
        if chat:
            return jsonify({
                'has_active_chat': True,
                'chat_id': chat.id,
                'chat_type': chat.chat_type
            })
        else:
            return jsonify({'has_active_chat': False})
    except Exception as e:
        current_app.logger.error(f"Error in check_existing_chat: {str(e)}")
        return jsonify({'error': str(e)}), 500
