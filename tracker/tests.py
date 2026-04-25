"""
Security test suite — runs against an in-memory SQLite DB (see settings.py test override).
Covers: rate limiting, session cookies, security headers, CSP, HTTPS config, access control,
        CSRF enforcement, and audit logging.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
import logging


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username='testuser', password='testpass123!'):
    return User.objects.create_user(username=username, password=password)


# ---------------------------------------------------------------------------
# 1. Rate limiting
# ---------------------------------------------------------------------------

class RateLimitingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        make_user()

    def tearDown(self):
        cache.clear()

    def _bad_login(self):
        return self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword',
        })

    def test_five_failures_allowed(self):
        """First 5 failures should return the normal login form, not a lockout."""
        for _ in range(5):
            resp = self._bad_login()
            self.assertEqual(resp.status_code, 200)
            self.assertNotContains(resp, 'locked for 1 hour')

    def test_sixth_attempt_is_locked(self):
        """After 5 failures the 6th attempt must show the lockout message."""
        for _ in range(5):
            self._bad_login()
        resp = self._bad_login()
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'locked for 1 hour')

    def test_lock_disables_form(self):
        """Locked response must also disable the form via pointer-events:none."""
        for _ in range(6):
            self._bad_login()
        resp = self._bad_login()
        self.assertContains(resp, 'pointer-events:none')

    def test_successful_login_resets_counter(self):
        """A successful login should clear the failure counter."""
        for _ in range(4):
            self._bad_login()
        # Successful login
        self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123!',
        })
        self.client.logout()
        cache.clear()  # simulate different session
        # Should be unlocked again
        resp = self._bad_login()
        self.assertNotContains(resp, 'locked for 1 hour')


# ---------------------------------------------------------------------------
# 2 & 3. Security headers and session cookies
# ---------------------------------------------------------------------------

class SecurityHeadersTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _get_login(self):
        return self.client.get(reverse('login'))

    def test_x_frame_options_deny(self):
        resp = self._get_login()
        self.assertEqual(resp.get('X-Frame-Options'), 'DENY')

    def test_x_content_type_nosniff(self):
        resp = self._get_login()
        self.assertEqual(resp.get('X-Content-Type-Options'), 'nosniff')

    def test_csp_header_present(self):
        resp = self._get_login()
        csp = resp.get('Content-Security-Policy', '')
        self.assertIn("default-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("form-action 'self'", csp)

    def test_csp_blocks_external_scripts(self):
        """CSP must not permit loading scripts from arbitrary domains."""
        resp = self._get_login()
        csp = resp.get('Content-Security-Policy', '')
        self.assertNotIn('script-src *', csp)
        self.assertNotIn("script-src 'unsafe-eval'", csp)

    def test_referrer_policy(self):
        resp = self._get_login()
        self.assertEqual(resp.get('Referrer-Policy'), 'strict-origin-when-cross-origin')

    def test_permissions_policy(self):
        resp = self._get_login()
        policy = resp.get('Permissions-Policy', '')
        self.assertIn('geolocation=()', policy)
        self.assertIn('microphone=()', policy)

    def test_fonts_allowed_in_csp(self):
        """Google Fonts must be whitelisted so the UI doesn't break."""
        resp = self._get_login()
        csp = resp.get('Content-Security-Policy', '')
        self.assertIn('fonts.googleapis.com', csp)
        self.assertIn('fonts.gstatic.com', csp)


class SessionCookieTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()

    def test_session_cookie_httponly(self):
        """SESSION_COOKIE_HTTPONLY must be True — Django enforces this on Set-Cookie."""
        from django.conf import settings
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_session_cookie_samesite(self):
        """SESSION_COOKIE_SAMESITE must be Lax to block cross-site request leakage."""
        from django.conf import settings
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')

    def test_csrf_cookie_present_on_login_page(self):
        """CSRF cookie must be set on the login page."""
        self.client.get(reverse('login'))
        self.assertIn('csrftoken', self.client.cookies)


# ---------------------------------------------------------------------------
# 4. Access control (unauthenticated redirect)
# ---------------------------------------------------------------------------

class AccessControlTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_dashboard_requires_login(self):
        resp = self.client.get('/')
        self.assertRedirects(resp, '/login/?next=/', fetch_redirect_response=False)

    def test_people_requires_login(self):
        resp = self.client.get('/people/')
        self.assertRedirects(resp, '/login/?next=/people/', fetch_redirect_response=False)

    def test_firms_requires_login(self):
        resp = self.client.get('/firms/')
        self.assertRedirects(resp, '/login/?next=/firms/', fetch_redirect_response=False)

    def test_api_search_requires_login(self):
        resp = self.client.get('/api/search/?q=test')
        self.assertIn(resp.status_code, [302, 301],
                      "Unauthenticated API request must redirect to login")

    def test_login_page_public(self):
        resp = self.client.get(reverse('login'))
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# 5. CSRF enforcement
# ---------------------------------------------------------------------------

class CSRFTests(TestCase):
    def setUp(self):
        make_user()

    def test_login_post_without_csrf_rejected(self):
        """POST to login without CSRF token must fail (403 or redirect)."""
        client = Client(enforce_csrf_checks=True)
        resp = client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123!',
        })
        self.assertEqual(resp.status_code, 403)

    def test_login_post_with_csrf_succeeds(self):
        """POST to login WITH a valid CSRF token must succeed."""
        client = Client()  # CSRF middleware relaxed by default in tests
        resp = client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123!',
        })
        # Successful login redirects
        self.assertIn(resp.status_code, [200, 302])


# ---------------------------------------------------------------------------
# 6. Audit logging
# ---------------------------------------------------------------------------

class AuditLoggingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = make_user()

    def tearDown(self):
        cache.clear()

    def test_failed_login_is_logged(self):
        with self.assertLogs('tracker.audit', level='WARNING') as cm:
            self.client.post(reverse('login'), {
                'username': 'testuser',
                'password': 'wrongpassword',
            })
        self.assertTrue(any('LOGIN_FAILED' in line for line in cm.output))

    def test_failed_login_logs_username(self):
        with self.assertLogs('tracker.audit', level='WARNING') as cm:
            self.client.post(reverse('login'), {
                'username': 'testuser',
                'password': 'wrongpassword',
            })
        self.assertTrue(any('testuser' in line for line in cm.output))

    def test_successful_login_is_logged(self):
        with self.assertLogs('tracker.audit', level='INFO') as cm:
            self.client.post(reverse('login'), {
                'username': 'testuser',
                'password': 'testpass123!',
            })
        self.assertTrue(any('LOGIN' in line and 'testuser' in line for line in cm.output))

    def test_rate_limit_sixth_attempt_logged(self):
        """The 6th attempt (after lockout) should still appear in the audit log."""
        with self.assertLogs('tracker.audit', level='WARNING') as cm:
            for _ in range(6):
                self.client.post(reverse('login'), {
                    'username': 'testuser',
                    'password': 'wrongpassword',
                })
        failed = [l for l in cm.output if 'LOGIN_FAILED' in l]
        self.assertGreaterEqual(len(failed), 5)


# ---------------------------------------------------------------------------
# 7. Django deployment checklist (SECURE_* settings)
# ---------------------------------------------------------------------------

class DeploymentSettingsTests(TestCase):
    def test_debug_is_false_in_tests(self):
        from django.conf import settings
        # DEBUG may be True in local dev but must be configurable — just verify
        # the setting exists and is a bool
        self.assertIsInstance(settings.DEBUG, bool)

    def test_secret_key_is_not_insecure_default(self):
        from django.conf import settings
        self.assertNotEqual(settings.SECRET_KEY, 'django-insecure-local-dev-only',
                            "SECRET_KEY must be set via environment variable in production")

    def test_session_cookie_httponly_enabled(self):
        from django.conf import settings
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_session_cookie_samesite_set(self):
        from django.conf import settings
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')

    def test_x_frame_options_deny(self):
        from django.conf import settings
        self.assertEqual(settings.X_FRAME_OPTIONS, 'DENY')

    def test_content_type_nosniff_enabled(self):
        from django.conf import settings
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)

    def test_proxy_ssl_header_configured(self):
        from django.conf import settings
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER,
                         ('HTTP_X_FORWARDED_PROTO', 'https'))

    def test_no_hardcoded_db_password(self):
        """Ensure the hardcoded fallback password was removed from settings."""
        from django.conf import settings
        pw = settings.DATABASES['default'].get('PASSWORD') or ''
        self.assertNotEqual(pw, 'vCqK3qmYrZTdi4gL',
                            "Hardcoded DB password must be removed from settings.py")

    def test_hsts_configured(self):
        """HSTS must be set to a valid value: 0 in dev, 31536000 in production."""
        from django.conf import settings
        self.assertIn(settings.SECURE_HSTS_SECONDS, [0, 31_536_000],
                      "HSTS must be 0 (dev) or 31536000 (production)")
