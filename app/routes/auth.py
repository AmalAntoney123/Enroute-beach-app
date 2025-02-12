from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.panel'))
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.find_by_username(username)
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been disabled. Please contact admin.', 'danger')
                return redirect(url_for('auth.login'))
                
            login_user(user)
            session['user_role'] = user.role
            session['user_email'] = user.email
            session['username'] = user.username
            
            # Debug print
            print(f"User Role: {user.role}")
            print(f"Session Role: {session.get('user_role')}")
            
            if user.role == 'admin':
                return redirect(url_for('admin.panel'))
            return redirect(url_for('main.dashboard'))
                
        flash('Invalid username or password', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.find_by_username(username):
            flash('Username already exists', 'danger')
            return redirect(url_for('auth.signup'))
        
        # Create user with default role, it will be set to admin in save() if email matches
        user = User(username=username, email=email, password=password)
        user.save()  # Role is set here based on email
        
        login_user(user)
        session['user_role'] = user.role  # Use the role set after save
        session['user_email'] = user.email
        session['username'] = user.username
        
        if user.role == 'admin':
            return redirect(url_for('admin.panel'))
        return redirect(url_for('main.dashboard'))
        
    return render_template('auth/signup.html')

@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('user_role', None)
    session.pop('user_email', None)
    session.pop('username', None)
    logout_user()
    return redirect(url_for('auth.login')) 