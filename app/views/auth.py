from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from pydantic import ValidationError
from app.services.auth_service import AuthService
from app.schemas import UserRegisterSchema, UserLoginSchema, PasswordResetRequestSchema, PasswordResetConfirmSchema
from app.extensions import limiter
from functools import wraps

auth_bp = Blueprint("auth", __name__)
auth_service = AuthService()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def signup():
    if request.method == "POST":
        data = request.json or {}
        try:
            # Pydantic input validation
            validated_data = UserRegisterSchema(**data)
        except ValidationError as e:
            return jsonify({"success": False, "message": e.errors()}), 400
            
        user = auth_service.register_user(
            username=validated_data.username,
            password=validated_data.password,
            ip_address=request.remote_addr,
            email=validated_data.email
        )
        
        if user:
            import os
            verification_required = os.getenv("EMAIL_VERIFICATION_REQUIRED", "false").lower() == "true"
            return jsonify({
                "success": True,
                "message": "User created successfully",
                "verification_required": verification_required
            })
        return jsonify({"success": False, "message": "Username already exists"}), 400
        
    return render_template("signup.html")

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "POST":
        data = request.json or {}
        try:
            # Pydantic input validation
            validated_data = UserLoginSchema(**data)
        except ValidationError as e:
            return jsonify({"success": False, "message": e.errors()}), 400
            
        user, err_msg = auth_service.authenticate_user(
            username=validated_data.username,
            password=validated_data.password,
            ip_address=request.remote_addr
        )
        
        if user:
            session["user_id"] = user.id
            session["username"] = user.username
            return jsonify({"success": True, "message": "Logged in successfully"})
        return jsonify({"success": False, "message": err_msg}), 401
        
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    if user_id:
        auth_service.audit_service.log_event(
            user_id=user_id,
            action="LOGOUT",
            ip_address=request.remote_addr,
            details=f"User {session.get('username')} logged out"
        )
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/verify-email/<token>", methods=["GET"])
def verify_email(token):
    user = auth_service.verify_email(token)
    success = user is not None
    return render_template("verify_email.html", success=success)

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if request.method == "POST":
        data = request.json or {}
        try:
            validated_data = PasswordResetRequestSchema(**data)
        except ValidationError as e:
            return jsonify({"success": False, "message": e.errors()}), 400
            
        # Call reset password request
        auth_service.request_password_reset(validated_data.email)
        
        # Always return success to prevent user enumeration attacks
        return jsonify({
            "success": True,
            "message": "If this email is registered, a password reset link has been generated."
        })
        
    return render_template("forgot_password.html")

@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password(token):
    if request.method == "POST":
        data = request.json or {}
        try:
            validated_data = PasswordResetConfirmSchema(**data)
        except ValidationError as e:
            return jsonify({"success": False, "message": e.errors()}), 400
            
        user = auth_service.confirm_password_reset(validated_data.token, validated_data.password)
        if user:
            return jsonify({"success": True, "message": "Password reset successfully."})
        return jsonify({"success": False, "message": "Invalid or expired reset token."}), 400
        
    return render_template("reset_password.html")
