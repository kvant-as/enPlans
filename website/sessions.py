"""Idle-session tracking now lives in ``common_models.sessions``.

This module is kept as a thin re-export so existing
``from website.sessions import ...`` imports keep working. Per-app behaviour
(cookie name, timeouts, redirects) is set in ``create_app`` via the
``SESSION_*`` config keys.
"""

from common_models.sessions import (  # noqa: F401
    JWT_ALGORITHM,
    SESSION_DURATION,
    get_user_session_timeout,
    get_session_time_left,
    create_session_token,
    set_session_cookie,
    create_login_response,
    verify_session_token,
    get_session_from_cookie,
    update_session_activity,
    describe_device,
    build_session_info,
    get_or_refresh_session,
    force_logout,
    session_required,
    get_current_user,
    clear_session_cookie,
)

from common_models.sessions import __all__ as __all__
