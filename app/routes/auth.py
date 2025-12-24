from fastapi import APIRouter, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse, JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.models import UserCreate, UserLogin, UserResponse, OTPLoginRequest, OTPVerifyRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.auth import get_password_hash, verify_password, create_access_token
from app.database import get_database
from app.email import send_email, generate_otp_login_email, generate_password_reset_otp_email, generate_email_verification_otp_email
from datetime import datetime, timedelta
import random
import string
import httpx
import os
from urllib.parse import urlencode

router = APIRouter()

# Initialize rate limiter for auth endpoints
limiter = Limiter(key_func=get_remote_address)

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/api/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Cookie settings
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds
SECURE_COOKIE = os.getenv("ENVIRONMENT", "development") == "production"  # Only secure in production

# Account lockout settings
MAX_LOGIN_ATTEMPTS = 5  # Maximum failed login attempts
LOCKOUT_DURATION = 10 * 60  # 10 minutes in seconds

def set_auth_cookie(response: Response, token: str):
    """Set httpOnly authentication cookie"""
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,  # Prevents JavaScript access (XSS protection)
        secure=SECURE_COOKIE,  # Only send over HTTPS in production
        samesite="none",  # CSRF protection
        max_age=COOKIE_MAX_AGE,
        path="/"
    )

# Account Lockout Helper Functions
async def check_account_lockout(db, email: str):
    """Check if account is locked due to failed login attempts"""
    user = await db.users.find_one({"email": email})
    
    if not user:
        return False, 0, None
    
    failed_attempts = user.get("failed_login_attempts", 0)
    locked_until = user.get("locked_until")
    
    # Check if account is currently locked
    if locked_until and locked_until > datetime.utcnow():
        remaining_seconds = int((locked_until - datetime.utcnow()).total_seconds())
        remaining_minutes = remaining_seconds // 60
        return True, failed_attempts, remaining_minutes
    
    # If lock expired, reset failed attempts
    if locked_until and locked_until <= datetime.utcnow():
        await db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "failed_login_attempts": 0,
                    "locked_until": None
                }
            }
        )
        return False, 0, None
    
    return False, failed_attempts, None

async def record_failed_login(db, email: str):
    """Record a failed login attempt and lock account if threshold reached"""
    user = await db.users.find_one({"email": email})
    
    if not user:
        return
    
    failed_attempts = user.get("failed_login_attempts", 0) + 1
    
    update_data = {
        "failed_login_attempts": failed_attempts,
        "last_failed_login": datetime.utcnow()
    }
    
    # Lock account if max attempts reached
    if failed_attempts >= MAX_LOGIN_ATTEMPTS:
        locked_until = datetime.utcnow() + timedelta(seconds=LOCKOUT_DURATION)
        update_data["locked_until"] = locked_until
    
    await db.users.update_one(
        {"email": email},
        {"$set": update_data}
    )

async def reset_failed_login_attempts(db, email: str):
    """Reset failed login attempts after successful login"""
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "failed_login_attempts": 0,
                "locked_until": None,
                "last_failed_login": None
            }
        }
    )

# Helper function to generate OTP
def generate_otp(length=6):
    """Generate a random OTP of specified length"""
    return ''.join(random.choices(string.digits, k=length))

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # Max 5 registration attempts per minute per IP
async def register(request: Request, user: UserCreate, response: Response):
    try:
        db = get_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available. Please install and start MongoDB to register."
        )
    
    # Check if username already exists
    existing_username = await db.users.find_one({"username": user.username})
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="USERNAME_EXISTS: This username is already taken. Please choose a different username."
        )
    
    # Check if email already exists
    existing_email = await db.users.find_one({"email": user.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMAIL_EXISTS: This email is already registered. Please use a different email or login."
        )
    
    # Generate 6-digit OTP for email verification
    verification_otp = generate_otp(6)
    otp_expires = datetime.utcnow() + timedelta(minutes=10)
    
    # Create user with email_verified=False
    user_dict = {
        "username": user.username,
        "email": user.email,
        "password": get_password_hash(user.password),
        "email_verified": True,
        "createdAt": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_dict)
    user_id = str(result.inserted_id)
    
    # Store OTP in database
    await db.otps.update_one(
        {"email": user.email, "type": "email_verification"},
        {
            "$set": {
                "email": user.email,
                "otp": verification_otp,
                "type": "email_verification",
                "expires": otp_expires,
                "createdAt": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    # Send verification email with OTP
    try:
        html_content = generate_email_verification_otp_email(user.username, verification_otp)
        await send_email(user.email, "✅ Verify Your Email - KodeCompiler", html_content)
    except Exception as e:
        # Log error but don't fail registration
        print(f"Failed to send verification email: {str(e)}")
    
    # DO NOT set auth cookie - user must verify email first
    # Return success message
    return {
        "_id": user_id,
        "username": user.username,
        "email": user.email,
        "message": "Account created! Please check your email for the verification OTP."
    }

@router.post("/login", response_model=UserResponse)
@limiter.limit("10/minute")  # Max 10 login attempts per minute per IP
async def login(request: Request, credentials: UserLogin, response: Response):
    try:
        db = get_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available. Please install and start MongoDB to login."
        )
    
    # Check if account is locked
    is_locked, failed_attempts, remaining_minutes = await check_account_lockout(db, credentials.email)
    
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked due to too many failed login attempts. Please try again in {remaining_minutes} minutes."
        )
    
    # Find user
    user = await db.users.find_one({"email": credentials.email})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please sign up to create an account."
        )
    
    # Check if email is verified (skip for OAuth users and existing users without email_verified field)
    if not user.get("email_verified", True) and user.get("password") is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EMAIL_NOT_VERIFIED: Please verify your email address before logging in. Check your inbox for the verification link."
        )
    
    # Verify password
    if not verify_password(credentials.password, user["password"]):
        # Record failed login attempt
        await record_failed_login(db, credentials.email)
        
        # Calculate remaining attempts
        new_failed_attempts = failed_attempts + 1
        remaining_attempts = MAX_LOGIN_ATTEMPTS - new_failed_attempts
        
        if remaining_attempts > 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid email or password. {remaining_attempts} attempt(s) remaining before account lockout."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked due to too many failed login attempts. Please try again in 10 minutes."
            )
    
    # Successful login - reset failed attempts
    await reset_failed_login_attempts(db, credentials.email)
    
    # Generate token
    token = create_access_token({"id": str(user["_id"])})
    
    # Set httpOnly cookie (token only sent via secure cookie, not in response body)
    set_auth_cookie(response, token)
    
    # Return user data only (token is in httpOnly cookie for security)
    return {
        "_id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"]
    }

@router.post("/logout")
async def logout(response: Response):
    """Logout endpoint - clears httpOnly cookie"""
    # Clear the httpOnly cookie by setting it to expire immediately
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=SECURE_COOKIE,
        samesite="lax",
        max_age=0,  # Expire immediately
        path="/"
    )
    
    return {
        "message": "Logged out successfully"
    }

@router.post("/verify-email-otp")
@limiter.limit("10/minute")  # Max 10 OTP verification attempts per minute per IP
async def verify_email_otp(request: Request, verify_request: dict, response: Response):
    """Verify user email with OTP"""
    try:
        db = get_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    email = verify_request.get("email")
    otp = verify_request.get("otp")
    
    if not email or not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and OTP are required"
        )
    
    # Find OTP record
    otp_record = await db.otps.find_one({
        "email": email,
        "type": "email_verification",
        "otp": otp
    })
    
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP. Please check the code and try again."
        )
    
    # Check if OTP expired
    if otp_record["expires"] < datetime.utcnow():
        # Delete expired OTP
        await db.otps.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP has expired. Please request a new one."
        )
    
    # Find user and update verification status
    user = await db.users.find_one({"email": email})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if already verified
    if user.get("email_verified", False):
        # Already verified - log them in
        user_id = str(user["_id"])
        auth_token = create_access_token({"id": user_id})
        set_auth_cookie(response, auth_token)
        
        # Delete used OTP
        await db.otps.delete_one({"_id": otp_record["_id"]})
        
        return {
            "message": "Email already verified! You are now logged in.",
            "already_verified": True,
            "_id": user_id,
            "username": user["username"],
            "email": user["email"]
        }
    
    # Update user to verified
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "email_verified": True,
                "verified_at": datetime.utcnow()
            }
        }
    )
    
    # Delete used OTP
    await db.otps.delete_one({"_id": otp_record["_id"]})
    
    # Log user in automatically after verification
    user_id = str(user["_id"])
    auth_token = create_access_token({"id": user_id})
    set_auth_cookie(response, auth_token)
    
    return {
        "message": "Email verified successfully! You are now logged in.",
        "verified": True,
        "_id": user_id,
        "username": user["username"],
        "email": user["email"]
    }

@router.post("/resend-verification")
@limiter.limit("3/hour")  # Max 3 resend attempts per hour per IP
async def resend_verification(request: Request, email_request: dict):
    """Resend verification OTP to user"""
    try:
        db = get_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    email = email_request.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )
    
    # Find user
    user = await db.users.find_one({"email": email})
    
    if not user:
        # Don't reveal if user exists
        return {
            "success": True,
            "message": "If this email is registered, a verification OTP has been sent."
        }
    
    # Check if already verified
    if user.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified. You can log in now."
        )
    
    # Generate new verification OTP
    verification_otp = generate_otp(6)
    otp_expires = datetime.utcnow() + timedelta(minutes=10)
    
    # Store OTP in database
    await db.otps.update_one(
        {"email": email, "type": "email_verification"},
        {
            "$set": {
                "email": email,
                "otp": verification_otp,
                "type": "email_verification",
                "expires": otp_expires,
                "createdAt": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    # Send verification email
    try:
        html_content = generate_email_verification_otp_email(user["username"], verification_otp)
        await send_email(email, "✅ Verify Your Email - KodeCompiler", html_content)
    except Exception as e:
        print(f"Failed to send verification email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again later."
        )
    
    return {
        "success": True,
        "message": "Verification OTP sent! Please check your inbox."
    }

@router.post("/login/otp/request")
@limiter.limit("3/minute")  # Max 3 OTP requests per minute per IP
async def request_otp_login(request: Request, otp_request: OTPLoginRequest):
    """Request OTP for email-based login"""
    try:
        db = get_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Find user by email
    user = await db.users.find_one({"email": otp_request.email})
    
    if not user:
        # Don't reveal if user exists or not for security
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="If this email is registered, an OTP has been sent"
        )
    
    # Generate OTP
    otp = generate_otp(6)
    otp_expires = datetime.utcnow() + timedelta(minutes=10)
    
    # Store OTP in database
    await db.otps.update_one(
        {"email": otp_request.email, "type": "login"},
        {
            "$set": {
                "email": otp_request.email,
                "otp": otp,
                "type": "login",
                "expires": otp_expires,
                "createdAt": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    # Send OTP email
    html_content = generate_otp_login_email(user["username"], otp)
    await send_email(otp_request.email, "Your Login OTP - Code Compiler", html_content)
    
    return {
        "success": True,
        "message": f"OTP sent to {otp_request.email}",
        "expires_in": 600  # 10 minutes in seconds
    }

@router.post("/login/otp/verify", response_model=UserResponse)
@limiter.limit("10/minute")  # Max 10 OTP verification attempts per minute per IP
async def verify_otp_login(request: Request, otp_verify: OTPVerifyRequest, response: Response):
    """Verify OTP and login user"""
    try:
        db = get_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Find OTP record
    otp_record = await db.otps.find_one({
        "email": otp_verify.email,
        "type": "login",
        "otp": otp_verify.otp
    })
    
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP"
        )
    
    # Check if OTP expired
    if otp_record["expires"] < datetime.utcnow():
        # Delete expired OTP
        await db.otps.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP has expired. Please request a new one"
        )
    
    # Find user
    user = await db.users.find_one({"email": otp_verify.email})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete used OTP
    await db.otps.delete_one({"_id": otp_record["_id"]})
    
    # Generate token
    token = create_access_token({"id": str(user["_id"])})
    
    # Set httpOnly cookie (token only sent via secure cookie, not in response body)
    set_auth_cookie(response, token)
    
    # Return user data only (token is in httpOnly cookie for security)
    return {
        "_id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"]
    }

@router.post("/password/forgot")
async def forgot_password(request: ForgotPasswordRequest):
    """Request OTP for password reset"""
    try:
        db = get_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Find user by email
    user = await db.users.find_one({"email": request.email})
    
    # Don't reveal if user exists or not for security
    # Always return success message
    if not user:
        return {
            "success": True,
            "message": "If this email is registered, a password reset OTP has been sent"
        }
    
    # Generate OTP
    otp = generate_otp(6)
    otp_expires = datetime.utcnow() + timedelta(minutes=10)
    
    # Store OTP in database
    await db.otps.update_one(
        {"email": request.email, "type": "password_reset"},
        {
            "$set": {
                "email": request.email,
                "otp": otp,
                "type": "password_reset",
                "expires": otp_expires,
                "createdAt": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    # Send OTP email
    html_content = generate_password_reset_otp_email(user["username"], otp)
    await send_email(request.email, "Password Reset OTP - Code Compiler", html_content)
    
    return {
        "success": True,
        "message": "If this email is registered, a password reset OTP has been sent",
        "expires_in": 600  # 10 minutes in seconds
    }

@router.post("/password/reset")
async def reset_password(request: ResetPasswordRequest):
    """Reset password using OTP"""
    try:
        db = get_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Find OTP record
    otp_record = await db.otps.find_one({
        "email": request.email,
        "type": "password_reset",
        "otp": request.otp
    })
    
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP"
        )
    
    # Check if OTP expired
    if otp_record["expires"] < datetime.utcnow():
        # Delete expired OTP
        await db.otps.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP has expired. Please request a new one"
        )
    
    # Find user
    user = await db.users.find_one({"email": request.email})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    new_password_hash = get_password_hash(request.new_password)
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": new_password_hash, "updatedAt": datetime.utcnow()}}
    )
    
    # Delete used OTP
    await db.otps.delete_one({"_id": otp_record["_id"]})
    
    return {
        "success": True,
        "message": "Password reset successful. You can now login with your new password"
    }

# ============================================
# GOOGLE OAUTH ROUTES
# ============================================

@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth flow - returns the Google authorization URL"""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured"
        )
    
    # Build Google OAuth URL
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"  # Always show account selection
    }
    
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    
    return {"auth_url": google_auth_url}

@router.get("/google/callback")
async def google_callback(code: str = None, error: str = None):
    """Handle Google OAuth callback with proper CORS handling"""
    
    # Handle user denial
    if error:
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=google_auth_cancelled",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache"
            }
        )
    
    if not code:
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=missing_auth_code",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache"
            }
        )
    
    try:
        # Step 1: Exchange authorization code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
            )
            
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get access token from Google"
                )
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            
            # Step 2: Get user info from Google
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if user_info_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user info from Google"
                )
            
            google_user = user_info_response.json()
        
        # Step 3: Check if user exists in database
        db = get_database()
        user = await db.users.find_one({"email": google_user["email"]})
        
        if user:
            # User exists - update google_id if not set
            user_id = str(user["_id"])
            username = user["username"]
            
            if not user.get("google_id"):
                await db.users.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "google_id": google_user["id"],
                            "auth_provider": "google",
                            "updatedAt": datetime.utcnow()
                        }
                    }
                )
        else:
            # New user - create account
            # Generate username from email or Google name
            base_username = google_user.get("name", google_user["email"].split("@")[0]).replace(" ", "_").lower()
            username = base_username
            
            # Ensure username is unique
            counter = 1
            while await db.users.find_one({"username": username}):
                username = f"{base_username}{counter}"
                counter += 1
            
            user_dict = {
                "username": username,
                "email": google_user["email"],
                "google_id": google_user["id"],
                "auth_provider": "google",
                "password": None,  # No password for OAuth users
                "createdAt": datetime.utcnow()
            }
            
            result = await db.users.insert_one(user_dict)
            user_id = str(result.inserted_id)
        
        # Step 4: Generate JWT token
        token = create_access_token({"id": user_id})
        
        # Step 5: Create redirect response with httpOnly cookie
        redirect_params = urlencode({
            "email": google_user["email"],
            "username": username,
            "auth": "google",
            "t": str(int(datetime.utcnow().timestamp()))  # Cache-busting timestamp
        })
        
        redirect_response = RedirectResponse(
            url=f"{FRONTEND_URL}/welcome?{redirect_params}",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
        # Set httpOnly cookie for authentication
        set_auth_cookie(redirect_response, token)
        
        return redirect_response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Google OAuth Error: {str(e)}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=google_auth_failed",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache"
            }
        )



