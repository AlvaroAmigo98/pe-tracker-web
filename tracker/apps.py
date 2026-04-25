from django.apps import AppConfig
import logging

audit_logger = logging.getLogger('tracker.audit')


class TrackerConfig(AppConfig):
    name = 'tracker'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_logged_out
        from tracker.views import _client_ip

        def on_login(sender, request, user, **kwargs):
            audit_logger.info('LOGIN user=%s ip=%s', user.username, _client_ip(request))

        def on_logout(sender, request, user, **kwargs):
            audit_logger.info('LOGOUT user=%s ip=%s',
                              getattr(user, 'username', '?'), _client_ip(request))

        user_logged_in.connect(on_login)
        user_logged_out.connect(on_logout)
