from flask import Blueprint, render_template, flash, redirect, url_for, request, session, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import mongo
from bson import ObjectId
from datetime import datetime, timezone, timedelta

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or session.get('user_role') != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin')
@admin_bp.route('/admin/panel')
@login_required
@admin_required
def panel():
    stats = {
        'total_users': mongo.db.users.count_documents({}),
        'active_users': mongo.db.users.count_documents({'is_active': True}),
        'total_alerts': mongo.db.alerts.count_documents({}),
        'active_alerts': mongo.db.alerts.count_documents({'active': True})
    }
    return render_template('admin/dashboard.html', stats=stats, active_tab='panel')

@admin_bp.route('/admin/users')
@login_required
@admin_required
def manage_users():
    users = list(mongo.db.users.find())
    for user in users:
        user['_id'] = str(user['_id'])
    return render_template('admin/users.html', users=users, active_tab='users')

@admin_bp.route('/admin/user/<user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        # Check if user exists and is not the current admin
        if user and user['email'] != current_user.email:
            current_status = user.get('is_active', True)
            mongo.db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'is_active': not current_status}}
            )
            status_msg = 'disabled' if current_status else 'enabled'
            flash(f'User {status_msg} successfully', 'success')
        else:
            flash('Cannot modify your own admin account', 'danger')
    except Exception as e:
        flash(f'Error toggling user status: {str(e)}', 'danger')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/admin/user/<user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('admin.panel'))

    if request.method == 'POST':
        if user['email'] == 'admin@gmail.com':
            flash('Cannot modify admin user', 'danger')
            return redirect(url_for('admin.panel'))

        # Update user data
        update_data = {
            'username': request.form.get('username'),
            'email': request.form.get('email'),
            'updated_at': datetime.utcnow()
        }
        
        try:
            mongo.db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_data}
            )
            flash('User updated successfully', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            flash(f'Error updating user: {str(e)}', 'danger')
    
    return render_template('admin/edit_user.html', user=user)

@admin_bp.route('/admin/alerts')
@login_required
@admin_required
def manage_alerts():
    # Get current time in UTC
    current_time = datetime.now(timezone.utc)
    
    beaches = list(mongo.db.beaches.find({'is_active': True}))
    alerts = list(mongo.db.alerts.find().sort('created_at', -1))
    
    for alert in alerts:
        alert['_id'] = str(alert['_id'])
        
        # Convert string datetime to datetime object if needed
        if isinstance(alert['expires_at'], str):
            try:
                # Parse the expiry time and make it timezone-aware as IST
                expires_at = datetime.strptime(alert['expires_at'], '%Y-%m-%d %H:%M')
                ist_offset = timedelta(hours=5, minutes=30)
                alert['expires_at'] = expires_at.replace(tzinfo=timezone(ist_offset))
            except ValueError:
                alert['expires_at'] = datetime.fromisoformat(alert['expires_at'].replace('Z', '+00:00'))
        
        # Compare with current UTC time
        is_expired = alert['expires_at'].astimezone(timezone.utc) <= current_time
        
        if is_expired:
            # Update database
            mongo.db.alerts.update_one(
                {'_id': ObjectId(alert['_id'])},
                {'$set': {'is_active': False, 'is_expired': True}}
            )
            # Update in-memory alert object
            alert['is_active'] = False
            alert['is_expired'] = True
        else:
            alert['is_expired'] = False
            alert['is_active'] = alert.get('is_active', True)

    return render_template('admin/alerts.html', alerts=alerts, beaches=beaches, active_tab='alerts')

@admin_bp.route('/admin/alert/<alert_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_alert(alert_id):
    try:
        mongo.db.alerts.delete_one({'_id': ObjectId(alert_id)})
        flash('Alert deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting alert: {str(e)}', 'danger')
    return redirect(url_for('admin.manage_alerts'))

@admin_bp.route('/admin/alert/<alert_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_alert(alert_id):
    try:
        alert = mongo.db.alerts.find_one({'_id': ObjectId(alert_id)})
        if alert:
            current_status = alert.get('is_active', True)
            mongo.db.alerts.update_one(
                {'_id': ObjectId(alert_id)},
                {'$set': {'is_active': not current_status}}
            )
            status_msg = 'disabled' if current_status else 'enabled'
            flash(f'Alert {status_msg} successfully', 'success')
    except Exception as e:
        flash(f'Error toggling alert status: {str(e)}', 'danger')
    return redirect(url_for('admin.manage_alerts'))

@admin_bp.route('/admin/stats')
@login_required
@admin_required
def stats():
    # Get basic statistics
    stats = {
        'total_users': mongo.db.users.count_documents({}),
        'active_alerts': mongo.db.alerts.count_documents({'active': True}),
        'recent_users': list(mongo.db.users.find().sort('created_at', -1).limit(5))
    }
    return render_template('admin/stats.html', stats=stats) 

@admin_bp.route('/admin/alert/add', methods=['POST'])
@login_required
@admin_required
def add_alert():
    if request.method == 'POST':
        beach_id = request.form.get('beach')
        message = request.form.get('alert_text')
        alert_type = request.form.get('alert_type')
        severity = request.form.get('severity')
        expires_at = datetime.strptime(request.form.get('expires_at'), '%Y-%m-%dT%H:%M')
        
        beach = mongo.db.beaches.find_one({'_id': ObjectId(beach_id)})
        
        if beach and message and alert_type:
            alert = {
                'text': message,
                'type': alert_type,
                'beach_id': beach_id,
                'beach_name': beach['name'],
                'created_at': datetime.utcnow(),
                'expires_at': expires_at,
                'created_by': current_user.username,
                'severity': severity,
                'is_active': True
            }
            mongo.db.alerts.insert_one(alert)
            flash('Alert created successfully', 'success')
        else:
            flash('All fields are required', 'danger')
            
    return redirect(url_for('admin.manage_alerts'))

@admin_bp.route('/admin/beaches')
@login_required
@admin_required
def manage_beaches():
    beaches = list(mongo.db.beaches.find())
    return render_template('admin/beaches.html', beaches=beaches, active_tab='beaches')

@admin_bp.route('/admin/beach/add', methods=['POST'])
@login_required
@admin_required
def add_beach():
    if request.method == 'POST':
        beach = {
            'name': request.form.get('beach_name'),
            'location': request.form.get('location'),
            'district': request.form.get('district'),
            'description': request.form.get('description'),
            'is_active': True,
            'created_at': datetime.utcnow(),
            'created_by': current_user.username
        }
        
        mongo.db.beaches.insert_one(beach)
        flash('Beach added successfully', 'success')
        
    return redirect(url_for('admin.manage_beaches'))

@admin_bp.route('/admin/beach/<beach_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_beach(beach_id):
    if request.method == 'POST':
        update_data = {
            'name': request.form.get('beach_name'),
            'location': request.form.get('location'),
            'district': request.form.get('district'),
            'description': request.form.get('description'),
            'updated_at': datetime.utcnow(),
            'updated_by': current_user.username
        }
        
        mongo.db.beaches.update_one(
            {'_id': ObjectId(beach_id)},
            {'$set': update_data}
        )
        flash('Beach updated successfully', 'success')
        
    return redirect(url_for('admin.manage_beaches'))

@admin_bp.route('/admin/beach/<beach_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_beach_status(beach_id):
    beach = mongo.db.beaches.find_one({'_id': ObjectId(beach_id)})
    if beach:
        new_status = not beach.get('is_active', True)
        mongo.db.beaches.update_one(
            {'_id': ObjectId(beach_id)},
            {'$set': {'is_active': new_status}}
        )
        return jsonify({'success': True})
    return jsonify({'success': False}), 404