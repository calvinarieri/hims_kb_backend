import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

logger = logging.getLogger(__name__)

class StaffEmailService:
    """
    Service for rendering and sending staff notification emails (Creation with Password, Password Update, Dismissal)
    using presentable HTML templates styled with slate-900 (#0f172a), amber-700 (#b45309), white (#ffffff), and black (#0f172a).
    """

    @staticmethod
    def _base_email_template(title, subtitle, body_html):
        """
        Base HTML wrapper with slate-900, amber-700, white, and black palette.
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; -webkit-font-smoothing: antialiased;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f1f5f9; padding: 40px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(15, 23, 42, 0.1), 0 4px 6px -4px rgba(15, 23, 42, 0.1);">
                    
                    <!-- Header with Slate-900 background & Amber-700 border accent -->
                    <tr>
                        <td style="background-color: #0f172a; padding: 32px 40px; text-align: left; border-bottom: 4px solid #b45309;">
                            <table width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td>
                                        <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">HIMS KB</h1>
                                        <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 14px; font-weight: 500;">Health Information Management System</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Title & Subtitle Banner -->
                    <tr>
                        <td style="padding: 32px 40px 16px 40px; background-color: #ffffff;">
                            <h2 style="color: #0f172a; margin: 0; font-size: 20px; font-weight: 700;">{title}</h2>
                            {f'<p style="color: #475569; margin: 6px 0 0 0; font-size: 15px;">{subtitle}</p>' if subtitle else ''}
                        </td>
                    </tr>

                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 0 40px 32px 40px; background-color: #ffffff; color: #0f172a; font-size: 15px; line-height: 1.6;">
                            {body_html}
                        </td>
                    </tr>

                    <!-- Footer with Slate-900 background -->
                    <tr>
                        <td style="background-color: #0f172a; padding: 24px 40px; text-align: center; color: #94a3b8; font-size: 13px; border-top: 1px solid #1e293b;">
                            <p style="margin: 0; color: #ffffff; font-weight: 600;">HIMS Knowledge Base System</p>
                            <p style="margin: 6px 0 0 0; color: #94a3b8;">This is an automated system message. Please do not reply directly to this email.</p>
                            <p style="margin: 8px 0 0 0; color: #64748b; font-size: 12px;">&copy; HIMS Administration. All rights reserved.</p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    @classmethod
    def send_staff_created_email(cls, user, raw_password):
        """
        Sends account creation notification email including raw password to new staff member.
        """
        subject = "Welcome to HIMS - Your Staff Account Credentials"
        title = "Welcome to the HIMS Team"
        subtitle = "Your staff account has been created by an administrator."

        role_name = user.role.name if user.role else "Staff Member"
        first_name = user.first_name or "Staff Member"

        frontend_base = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
        login_url = f"{frontend_base}/login" if frontend_base else "/login"

        body_html = f"""
        <p>Dear <strong>{first_name}</strong>,</p>
        <p>Your staff account for the HIMS Knowledge Base platform has been created by an administrator.</p>

        <!-- Slate-900 Box with Amber-700 Accent -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 24px 0; background-color: #0f172a; border-left: 4px solid #b45309; border-radius: 8px; color: #ffffff;">
            <tr>
                <td style="padding: 20px 24px;">
                    <div style="font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color: #b45309; font-weight: 700; margin-bottom: 12px;">Account Credentials</div>
                    <div style="margin-bottom: 8px;"><span style="color: #94a3b8;">Email Address:</span> <strong style="color: #ffffff; padding-left: 8px;">{user.email}</strong></div>
                    <div style="margin-bottom: 8px;"><span style="color: #94a3b8;">Assigned Role:</span> <strong style="color: #ffffff; padding-left: 8px;">{role_name}</strong></div>
                    <div><span style="color: #94a3b8;">Assigned Password:</span> <span style="font-family: monospace; background-color: #1e293b; color: #fbbf24; padding: 4px 8px; border-radius: 4px; font-weight: 700; margin-left: 8px;">{raw_password}</span></div>
                </td>
            </tr>
        </table>

        <!-- Amber-700 Action Button -->
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 28px 0 16px 0;">
            <tr>
                <td align="center" style="background-color: #b45309; border-radius: 6px;">
                    <a href="{login_url}" target="_blank" style="display: inline-block; padding: 12px 28px; font-size: 15px; color: #ffffff; font-weight: 600; text-decoration: none;">Log In to HIMS Portal</a>
                </td>
            </tr>
        </table>

        <p style="color: #64748b; font-size: 13px; margin-top: 20px;">
            <em>Security Tip: We strongly recommend updating your password immediately after logging in for the first time.</em>
        </p>
        """

        text_message = (
            f"Dear {first_name},\n\n"
            f"Your staff account has been created.\n\n"
            f"Email: {user.email}\n"
            f"Role: {role_name}\n"
            f"Password: {raw_password}\n\n"
            f"Log in at: {login_url}\n"
        )

        cls._send_email(user.email, subject, title, subtitle, body_html, text_message)

    @classmethod
    def send_staff_password_updated_email(cls, user, new_password):
        """
        Sends email when administrator updates staff password.
        """
        subject = "Security Notice: Your Staff Account Password Has Been Updated"
        title = "Password Updated by Admin"
        subtitle = "An administrator has updated your account password."

        first_name = user.first_name or "Staff Member"
        frontend_base = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
        login_url = f"{frontend_base}/login" if frontend_base else "/login"

        body_html = f"""
        <p>Dear <strong>{first_name}</strong>,</p>
        <p>This is to inform you that your HIMS account password has been updated by an administrator.</p>

        <!-- Slate-900 Box with Amber-700 Accent -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 24px 0; background-color: #0f172a; border-left: 4px solid #b45309; border-radius: 8px; color: #ffffff;">
            <tr>
                <td style="padding: 20px 24px;">
                    <div style="font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color: #b45309; font-weight: 700; margin-bottom: 12px;">Updated Credentials</div>
                    <div style="margin-bottom: 8px;"><span style="color: #94a3b8;">Email Address:</span> <strong style="color: #ffffff; padding-left: 8px;">{user.email}</strong></div>
                    <div><span style="color: #94a3b8;">New Password:</span> <span style="font-family: monospace; background-color: #1e293b; color: #fbbf24; padding: 4px 8px; border-radius: 4px; font-weight: 700; margin-left: 8px;">{new_password}</span></div>
                </td>
            </tr>
        </table>

        <!-- Amber-700 Action Button -->
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 28px 0 16px 0;">
            <tr>
                <td align="center" style="background-color: #b45309; border-radius: 6px;">
                    <a href="{login_url}" target="_blank" style="display: inline-block; padding: 12px 28px; font-size: 15px; color: #ffffff; font-weight: 600; text-decoration: none;">Log In Now</a>
                </td>
            </tr>
        </table>

        <p style="color: #64748b; font-size: 13px; margin-top: 20px;">
            If you did not request or expect this change, please contact your system administrator immediately.
        </p>
        """

        text_message = (
            f"Dear {first_name},\n\n"
            f"Your HIMS account password was updated by an administrator.\n\n"
            f"Email: {user.email}\n"
            f"New Password: {new_password}\n\n"
            f"Log in at: {login_url}\n"
        )

        cls._send_email(user.email, subject, title, subtitle, body_html, text_message)

    @classmethod
    def send_staff_dismissed_email(cls, user):
        """
        Sends dismissal / account deactivation notification email to staff member.
        """
        subject = "Account Status Notice: Staff Account Deactivated"
        title = "Staff Account Deactivated"
        subtitle = "Your HIMS staff account status has been updated."

        first_name = user.first_name or "Staff Member"

        body_html = f"""
        <p>Dear <strong>{first_name}</strong>,</p>
        <p>This email is to notify you that your staff access to the HIMS KB platform has been deactivated/dismissed by an administrator.</p>

        <!-- Slate-900 Box with Amber-700 Border -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 24px 0; background-color: #0f172a; border-left: 4px solid #b45309; border-radius: 8px; color: #ffffff;">
            <tr>
                <td style="padding: 20px 24px;">
                    <div style="font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color: #b45309; font-weight: 700; margin-bottom: 8px;">Notice Details</div>
                    <div style="margin-bottom: 6px;"><span style="color: #94a3b8;">Account:</span> <strong style="color: #ffffff; padding-left: 8px;">{user.email}</strong></div>
                    <div><span style="color: #94a3b8;">Status:</span> <strong style="color: #ef4444; padding-left: 8px;">Deactivated / Dismissed</strong></div>
                </td>
            </tr>
        </table>

        <p>As a result, active session tokens have been invalidated and account access has been restricted. If you have questions regarding this change, please contact system administration.</p>
        """

        text_message = (
            f"Dear {first_name},\n\n"
            f"Your staff access to HIMS KB has been deactivated/dismissed by an administrator.\n\n"
            f"Account: {user.email}\n"
            f"Status: Deactivated / Dismissed\n\n"
            f"Contact administration for further details.\n"
        )

        cls._send_email(user.email, subject, title, subtitle, body_html, text_message)

    @classmethod
    def _send_email(cls, recipient_email, subject, title, subtitle, body_html, text_message):
        """
        Helper method to build and dispatch EmailMultiAlternatives.
        Catches and logs exceptions so API requests complete cleanly even if mail server fails.
        """
        try:
            html_content = cls._base_email_template(title, subtitle, body_html)
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'HIMS KB <no-reply@hims.org>')

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_message,
                from_email=from_email,
                to=[recipient_email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            logger.info(f"Staff email '{subject}' sent successfully to {recipient_email}")
        except Exception as e:
            logger.error(f"Failed to send staff email '{subject}' to {recipient_email}. Error: {str(e)}", exc_info=True)

