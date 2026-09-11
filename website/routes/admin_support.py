"""Обращения "Другое" из виджета виртуального помощника: живая переписка
с администратором вместо ИИ. Список открытых обращений выводится на
главной странице кастомной админки (см. website/admin.py), здесь —
сам просмотр переписки и форма ответа.
"""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from common_models import current_utc_time, db

from ..models import Chat, ChatMessage, Notification
from .chat_bp import MAX_MESSAGES_PER_CHAT, SUPPORT_CHAT_TYPE

admin_support_bp = Blueprint('admin_support', __name__, url_prefix='/admin/support-chats')


@admin_support_bp.before_request
def _guard():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


def _is_ajax():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _truncate(text, limit=140):
    text = text.strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


@admin_support_bp.route('/<int:chat_id>', methods=['GET', 'POST'])
@login_required
def thread(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if chat.chat_type != SUPPORT_CHAT_TYPE:
        abort(404)

    if request.method == 'POST':
        content = (request.form.get('content') or '').strip()
        if not content:
            if _is_ajax():
                return jsonify({'success': False, 'error': 'Введите текст ответа'}), 400
            flash('Введите текст ответа', 'error')
            return redirect(url_for('admin_support.thread', chat_id=chat.id))

        if chat.messages.count() >= MAX_MESSAGES_PER_CHAT:
            error = f'Достигнут лимит сообщений в этом чате ({MAX_MESSAGES_PER_CHAT}).'
            if _is_ajax():
                return jsonify({'success': False, 'error': error}), 400
            flash(error, 'error')
            return redirect(url_for('admin_support.thread', chat_id=chat.id))

        message = ChatMessage(chat_id=chat.id, content=content, is_user=False)
        db.session.add(message)
        chat.updated_at = current_utc_time()

        # Уведомляем пользователя об ответе администратора — тот же
        # колокольчик уведомлений, что и для планов (see status_plan.py)
        if chat.created_by_id:
            db.session.add(Notification(
                user_id=chat.created_by_id,
                message=_truncate(f'Администратор ответил в вашем обращении: «{content}»'),
                created_at=current_utc_time(),
            ))

        db.session.commit()

        # Ответ отправляется через fetch (см. скрипт в шаблоне) — обновляем
        # чат сразу, без перезагрузки страницы; обычный POST остаётся как
        # запасной вариант, если JS по какой-то причине недоступен.
        if _is_ajax():
            return jsonify({
                'success': True,
                'message': {
                    'id': message.id,
                    'content': message.content,
                    'is_user': message.is_user,
                    'created_at': message.created_at.isoformat() if message.created_at else None,
                },
            })
        return redirect(url_for('admin_support.thread', chat_id=chat.id))

    messages = ChatMessage.query.filter_by(chat_id=chat.id).order_by(ChatMessage.created_at.asc()).all()

    from ..admin import site  # noqa: E402  (ленивый импорт — не тянуть admin.py на старте)
    return render_template(
        'admin/support_thread.html',
        chat=chat, messages=messages, author_name=_author_name(chat.created_by),
        **site.nav_context(),
    )


def _author_name(user):
    if not user:
        return 'Пользователь удалён'
    full = ' '.join(filter(None, [user.last_name, user.first_name])).strip()
    return user.fio or full or user.email or f'Пользователь №{user.id}'
