from django.apps import AppConfig
import logging

audit_logger = logging.getLogger('tracker.audit')


def _write_audit(event_type, username, ip):
    try:
        from tracker.models import AuditLog
        AuditLog.objects.create(event_type=event_type, username=username, ip_address=ip)
    except Exception:
        pass  # never crash the app if audit_log table is unavailable


class TrackerConfig(AppConfig):
    name = 'tracker'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_logged_out
        from tracker.views import _client_ip

        def on_login(sender, request, user, **kwargs):
            ip = _client_ip(request)
            audit_logger.info('LOGIN user=%s ip=%s', user.username, ip)
            _write_audit('LOGIN', user.username, ip)

        def on_logout(sender, request, user, **kwargs):
            ip = _client_ip(request)
            username = getattr(user, 'username', '?')
            audit_logger.info('LOGOUT user=%s ip=%s', username, ip)
            _write_audit('LOGOUT', username, ip)

        user_logged_in.connect(on_login)
        user_logged_out.connect(on_logout)
