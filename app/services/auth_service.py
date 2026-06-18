import hashlib
import datetime
import secrets
from typing import Optional, Tuple
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.models.user import User

class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.audit_service = AuditService()

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, stored_hash: str, password: str) -> bool:
        return stored_hash == self.hash_password(password)

    def register_user(self, username: str, password: str, ip_address: str, email: Optional[str] = None) -> Optional[User]:
        username = username.strip()
        password = password.strip()
        
        if not username or not password:
            return None

        # Check if username exists
        existing_user = self.user_repo.get_by_username(username)
        if existing_user:
            self.audit_service.log_event(
                user_id=None,
                action="SIGNUP_FAILED",
                ip_address=ip_address,
                details=f"Attempted registration for existing username: {username}"
            )
            return None

        # Password complexity is verified by the Pydantic schema before calling this service.
        # Check if email verification is required
        import os
        verification_required = os.getenv("EMAIL_VERIFICATION_REQUIRED", "false").lower() == "true"
        
        password_hash = self.hash_password(password)
        
        # Create user
        user = User(
            username=username,
            password_hash=password_hash,
            email=email,
            role="user",
            is_verified=not verification_required,
            verification_token=secrets.token_hex(32) if verification_required else None
        )
        
        self.user_repo.add(user)
        self.user_repo.commit()
        
        if verification_required:
            # Mock sending verification email
            mock_link = f"/verify-email/{user.verification_token}"
            print(f"\n[EMAIL MOCK] Verification link for user '{username}': {mock_link}\n")
            details = f"User {username} registered successfully. Verification link: {mock_link}"
        else:
            details = f"User {username} registered and auto-verified successfully"
        
        self.audit_service.log_event(
            user_id=user.id,
            action="SIGNUP_SUCCESS",
            ip_address=ip_address,
            details=details
        )
        return user

    def authenticate_user(self, username: str, password: str, ip_address: str) -> Tuple[Optional[User], str]:
        """
        Returns (User, error_message)
        """
        username = username.strip()
        password = password.strip()
        
        user = self.user_repo.get_by_username(username)
        if not user:
            self.audit_service.log_event(
                user_id=None,
                action="LOGIN_FAILED",
                ip_address=ip_address,
                details=f"Failed login attempt for non-existent username: {username}"
            )
            return None, "Invalid credentials"

        # Check Lockout status
        now = datetime.datetime.utcnow()
        if user.locked_until and user.locked_until > now:
            cooldown_remaining = int((user.locked_until - now).total_seconds())
            self.audit_service.log_event(
                user_id=user.id,
                action="LOGIN_LOCKED",
                ip_address=ip_address,
                details=f"Blocked login attempt for locked user {username} ({cooldown_remaining}s remaining)"
            )
            return None, f"Account is locked. Try again in {cooldown_remaining} seconds."

        # Verify Password
        if not self.verify_password(user.password_hash, password):
            # Increment failed attempts
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now + datetime.timedelta(minutes=10)
                self.user_repo.commit()
                self.audit_service.log_event(
                    user_id=user.id,
                    action="ACCOUNT_LOCKED",
                    ip_address=ip_address,
                    details=f"User {username} locked out due to 5 failed login attempts"
                )
                return None, "Account locked due to too many failed attempts. Try again in 10 minutes."
            
            self.user_repo.commit()
            self.audit_service.log_event(
                user_id=user.id,
                action="LOGIN_FAILED",
                ip_address=ip_address,
                details=f"Failed password verify for user {username}. Attempts: {user.failed_login_attempts}/5"
            )
            return None, "Invalid credentials"

        # Check Email Verification
        if not user.is_verified:
            self.audit_service.log_event(
                user_id=user.id,
                action="LOGIN_UNVERIFIED",
                ip_address=ip_address,
                details=f"Blocked login for unverified user {username}"
            )
            return None, "Please verify your email address before logging in."

        # Success - Reset Failed Attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        self.user_repo.commit()

        self.audit_service.log_event(
            user_id=user.id,
            action="LOGIN_SUCCESS",
            ip_address=ip_address,
            details=f"User {username} logged in successfully"
        )
        return user, ""

    def verify_email(self, token: str) -> Optional[User]:
        user = self.user_repo.session.query(User).filter(
            User.verification_token == token,
            User.deleted_at.is_(None)
        ).first()
        
        if user:
            user.is_verified = True
            user.verification_token = None
            self.user_repo.commit()
            self.audit_service.log_event(
                user_id=user.id,
                action="EMAIL_VERIFIED",
                ip_address=None,
                details=f"Email verified successfully for user {user.username}"
            )
            return user
        return None

    def request_password_reset(self, email: str) -> bool:
        user = self.user_repo.session.query(User).filter(
            User.email == email,
            User.deleted_at.is_(None)
        ).first()
        
        if not user:
            return False
            
        user.reset_token = secrets.token_hex(32)
        user.reset_token_expires = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        self.user_repo.commit()
        
        # Mock sending reset email
        mock_link = f"/reset-password/{user.reset_token}"
        print(f"\n[EMAIL MOCK] Password reset link for user '{user.username}': {mock_link}\n")
        
        self.audit_service.log_event(
            user_id=user.id,
            action="PASSWORD_RESET_REQUESTED",
            ip_address=None,
            details=f"Password reset link generated: {mock_link}"
        )
        return True

    def confirm_password_reset(self, token: str, new_password: str) -> Optional[User]:
        now = datetime.datetime.utcnow()
        user = self.user_repo.session.query(User).filter(
            User.reset_token == token,
            User.reset_token_expires > now,
            User.deleted_at.is_(None)
        ).first()
        
        if user:
            user.password_hash = self.hash_password(new_password)
            user.reset_token = None
            user.reset_token_expires = None
            user.failed_login_attempts = 0
            user.locked_until = None
            self.user_repo.commit()
            
            self.audit_service.log_event(
                user_id=user.id,
                action="PASSWORD_RESET_SUCCESS",
                ip_address=None,
                details=f"Password successfully reset for user {user.username}"
            )
            return user
        return None

    def unlock_user(self, user_id: int) -> bool:
        user = self.user_repo.get_by_id(user_id)
        if user:
            user.failed_login_attempts = 0
            user.locked_until = None
            self.user_repo.commit()
            return True
        return False

    def change_user_role(self, user_id: int, new_role: str) -> bool:
        if new_role not in ["user", "moderator", "admin"]:
            return False
        user = self.user_repo.get_by_id(user_id)
        if user:
            old_role = user.role
            user.role = new_role
            self.user_repo.commit()
            self.audit_service.log_event(
                user_id=user.id,
                action="ROLE_CHANGED",
                ip_address=None,
                details=f"Changed user {user.username} role from {old_role} to {new_role}"
            )
            return True
        return False
