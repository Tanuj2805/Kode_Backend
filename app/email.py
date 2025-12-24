import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
import logging

logger = logging.getLogger(__name__)

async def send_email(to_email: str, subject: str, html_content: str):
    """Send an email using SMTP"""
    
    # Check if email is configured
    if not settings.smtp_username or not settings.smtp_password or not settings.smtp_from_email:
        logger.warning("Email not configured. Skipping email send.")
        # logger.info(f"Would have sent email to {to_email} with subject: {subject}")
        # logger.info(f"Content: {html_content}")
        return False
    
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = to_email
        message["Subject"] = subject
        
        # Add HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        # Send email
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=True
        )
        
        # logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def generate_reset_password_email(username: str, reset_token: str) -> str:
    """Generate HTML content for password reset email"""
    
    reset_link = f"{settings.frontend_url}/reset-password?token={reset_token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 10px;
                padding: 30px;
                border: 1px solid #e0e0e0;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .header h1 {{
                color: #4a9eff;
                margin: 0;
            }}
            .content {{
                background-color: white;
                padding: 25px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #4a9eff;
                color: white !important;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
                font-weight: bold;
            }}
            .button:hover {{
                background-color: #3a8edf;
            }}
            .footer {{
                text-align: center;
                color: #888;
                font-size: 12px;
                margin-top: 20px;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
            </div>
            
            <div class="content">
                <p>Hello <strong>{username}</strong>,</p>
                
                <p>We received a request to reset your password for your Online Code Compiler account.</p>
                
                <p>Click the button below to reset your password:</p>
                
                <div style="text-align: center;">
                    <a href="{reset_link}" class="button">Reset Password</a>
                </div>
                
                <p>Or copy and paste this link into your browser:</p>
                <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; word-break: break-all;">
                    {reset_link}
                </p>
                
                <div class="warning">
                    <strong>⚠️ Important:</strong> This link will expire in 1 hour for security reasons.
                </div>
                
                <p>If you didn't request a password reset, please ignore this email or contact support if you have concerns.</p>
                
                <p>Best regards,<br>The Online Code Compiler Team</p>
            </div>
            
            <div class="footer">
                <p>This is an automated email. Please do not reply to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def generate_otp_login_email(username: str, otp: str) -> str:
    """Generate HTML content for OTP login email"""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 10px;
                padding: 30px;
                border: 1px solid #e0e0e0;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .header h1 {{
                color: #4a9eff;
                margin: 0;
            }}
            .content {{
                background-color: white;
                padding: 25px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            .otp-box {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 8px;
                text-align: center;
                padding: 20px;
                border-radius: 10px;
                margin: 25px 0;
                font-family: 'Courier New', monospace;
            }}
            .footer {{
                text-align: center;
                color: #888;
                font-size: 12px;
                margin-top: 20px;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Your Login OTP</h1>
            </div>
            
            <div class="content">
                <p>Hello <strong>{username}</strong>,</p>
                
                <p>You requested to login to your Online Code Compiler account using OTP.</p>
                
                <p>Your One-Time Password (OTP) is:</p>
                
                <div class="otp-box">
                    {otp}
                </div>
                
                <div class="warning">
                    <strong>⚠️ Important:</strong> This OTP will expire in 10 minutes for security reasons.
                </div>
                
                <p><strong>Security Tips:</strong></p>
                <ul>
                    <li>Do not share this OTP with anyone</li>
                    <li>Our team will never ask for your OTP</li>
                    <li>If you didn't request this, please ignore this email</li>
                </ul>
                
                <p>Best regards,<br>The Online Code Compiler Team</p>
            </div>
            
            <div class="footer">
                <p>This is an automated email. Please do not reply to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def generate_password_reset_otp_email(username: str, otp: str) -> str:
    """Generate HTML content for password reset OTP email"""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 10px;
                padding: 30px;
                border: 1px solid #e0e0e0;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .header h1 {{
                color: #ff6b6b;
                margin: 0;
            }}
            .content {{
                background-color: white;
                padding: 25px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            .otp-box {{
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 8px;
                text-align: center;
                padding: 20px;
                border-radius: 10px;
                margin: 25px 0;
                font-family: 'Courier New', monospace;
            }}
            .footer {{
                text-align: center;
                color: #888;
                font-size: 12px;
                margin-top: 20px;
            }}
            .warning {{
                background-color: #ffebee;
                border-left: 4px solid #ff6b6b;
                padding: 15px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔒 Password Reset OTP</h1>
            </div>
            
            <div class="content">
                <p>Hello <strong>{username}</strong>,</p>
                
                <p>We received a request to reset your password for your Online Code Compiler account.</p>
                
                <p>Your One-Time Password (OTP) for password reset is:</p>
                
                <div class="otp-box">
                    {otp}
                </div>
                
                <div class="warning">
                    <strong>⚠️ Important:</strong> This OTP will expire in 10 minutes for security reasons.
                </div>
                
                <p><strong>Security Notice:</strong></p>
                <ul>
                    <li>Only use this OTP if you requested a password reset</li>
                    <li>Do not share this OTP with anyone</li>
                    <li>If you didn't request this, someone may be trying to access your account</li>
                    <li>Consider changing your password immediately if you suspect unauthorized access</li>
                </ul>
                
                <p>After entering this OTP, you'll be able to set a new password for your account.</p>
                
                <p>Best regards,<br>The Online Code Compiler Team</p>
            </div>
            
            <div class="footer">
                <p>This is an automated email. Please do not reply to this message.</p>
                <p>If you didn't request this, please contact support immediately.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def generate_email_verification_otp_email(username: str, otp: str) -> str:
    """Generate HTML content for email verification OTP email"""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 10px;
                padding: 30px;
                border: 1px solid #e0e0e0;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .header h1 {{
                color: #2ed573;
                margin: 0;
            }}
            .content {{
                background-color: white;
                padding: 25px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            .button {{
                display: inline-block;
                padding: 15px 40px;
                background: linear-gradient(135deg, #2ed573 0%, #00b894 100%);
                color: white !important;
                text-decoration: none;
                border-radius: 8px;
                margin: 25px 0;
                font-weight: bold;
                font-size: 16px;
                box-shadow: 0 4px 15px rgba(46, 213, 115, 0.3);
            }}
            .button:hover {{
                background: linear-gradient(135deg, #26c561 0%, #009b7d 100%);
            }}
            .footer {{
                text-align: center;
                color: #888;
                font-size: 12px;
                margin-top: 20px;
            }}
            .warning {{
                background-color: #e7f9f0;
                border-left: 4px solid #2ed573;
                padding: 15px;
                margin: 20px 0;
            }}
            .otp-box {{
                background: linear-gradient(135deg, #2ed573 0%, #00b894 100%);
                color: white;
                font-size: 36px;
                font-weight: bold;
                letter-spacing: 10px;
                text-align: center;
                padding: 25px;
                border-radius: 12px;
                margin: 30px 0;
                font-family: 'Courier New', monospace;
                box-shadow: 0 4px 15px rgba(46, 213, 115, 0.3);
            }}
            .emoji {{
                font-size: 48px;
                text-align: center;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Welcome to KodeCompiler!</h1>
            </div>
            
            <div class="content">
                <div class="emoji">👋</div>
                
                <p>Hello <strong>{username}</strong>,</p>
                
                <p>Thank you for registering with <strong>KodeCompiler</strong>! We're excited to have you join our community of developers.</p>
                
                <p>To complete your registration and start coding, please verify your email address using the OTP below:</p>
                
                <div class="otp-box">
                    {otp}
                </div>
                
                <p style="text-align: center; margin: 20px 0; color: #666;">
                    Enter this OTP on the verification page to activate your account.
                </p>
                
                <div class="warning">
                    <strong>⏰ Important:</strong> This OTP will expire in 10 minutes for security reasons.
                </div>
                
                <p><strong>What happens after verification?</strong></p>
                <ul>
                    <li>✅ Full access to our online code compiler</li>
                    <li>✅ Solve coding problems and practice</li>
                    <li>✅ Save your code snippets</li>
                    <li>✅ Track your progress and compete on leaderboards</li>
                </ul>
                
                <p>If you didn't create an account with KodeCompiler, please ignore this email.</p>
                
                <p>Happy Coding!<br><strong>The KodeCompiler Team</strong></p>
            </div>
            
            <div class="footer">
                <p>This is an automated email. Please do not reply to this message.</p>
                <p>© 2025 KodeCompiler. Built with ❤️ for developers.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

