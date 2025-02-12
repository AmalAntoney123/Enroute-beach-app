from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
from app import mongo
from datetime import datetime
from flask import current_app

main_bp = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'app/static/uploads'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main_bp.route('/')
def index():
    current_time = datetime.utcnow()
    
    # Fetch latest active, non-expired alert and update expired alerts
    latest_alert = mongo.db.alerts.find_one({
        'is_active': True,
        'expires_at': {'$gt': current_time}
    }, sort=[('created_at', -1)])
    
    # Update expired alerts
    mongo.db.alerts.update_many(
        {
            'is_active': True,
            'expires_at': {'$lte': current_time}
        },
        {'$set': {'is_active': False}}
    )
    
    return render_template('index.html', latest_alert=latest_alert)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    beach_filter = request.args.get('beach')
    district_filter = request.args.get('district')
    
    # Base query for alerts
    query = {'is_active': True}
    
    # Add filters if provided
    if beach_filter:
        query['beach_id'] = beach_filter
    if district_filter:
        # Get all beaches in the selected district
        beach_ids = [str(beach['_id']) for beach in mongo.db.beaches.find({'district': district_filter})]
        if beach_ids:
            query['beach_id'] = {'$in': beach_ids}
    
    # Get data
    alerts = list(mongo.db.alerts.find(query).sort('created_at', -1))
    
    # If it's an AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Prepare alerts for JSON serialization
        for alert in alerts:
            alert['_id'] = str(alert['_id'])
            if isinstance(alert['expires_at'], datetime):
                alert['expires_at'] = alert['expires_at'].isoformat()
        return jsonify({'alerts': alerts})
    
    # For regular requests, get the data for the template
    beaches = list(mongo.db.beaches.find({'is_active': True}))
    accommodations = list(mongo.db.accommodations.find({'is_active': True}))
    districts = sorted(list({beach.get('district') for beach in beaches if beach.get('district')}))
    
    return render_template('main/dashboard.html',
                         alerts=alerts,
                         beaches=beaches,
                         districts=districts,
                         accommodations=accommodations,
                         config=current_app.config)

@main_bp.route('/alerts')
@login_required
def alerts():
    beach_filter = request.args.get('beach')
    district_filter = request.args.get('district')
    
    # Base query
    query = {'is_active': True}
    
    # Add filters if provided
    if beach_filter:
        query['beach_id'] = beach_filter
    if district_filter:
        # Get all beaches in the selected district
        beach_ids = [str(beach['_id']) for beach in mongo.db.beaches.find({'district': district_filter})]
        if beach_ids:
            query['beach_id'] = {'$in': beach_ids}
    
    # Get alerts with filters
    alerts = list(mongo.db.alerts.find(query).sort('created_at', -1))
    
    # If it's an AJAX request, prepare the alerts for JSON serialization
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        for alert in alerts:
            alert['_id'] = str(alert['_id'])
            if isinstance(alert['expires_at'], datetime):
                alert['expires_at'] = alert['expires_at'].isoformat()
        return jsonify({'alerts': alerts})
    
    # For regular requests, get the data for the template
    beaches = list(mongo.db.beaches.find({'is_active': True}))
    districts = sorted(list({beach.get('district') for beach in beaches if beach.get('district')}))
    
    return render_template('main/alerts.html', 
                         alerts=alerts,
                         beaches=beaches,
                         districts=districts)

@main_bp.route('/accommodations')
@login_required
def accommodations():
    accommodations = list(mongo.db.accommodations.find({'is_active': True}))
    beaches = list(mongo.db.beaches.find({'is_active': True}))
    print(f"Found {len(accommodations)} accommodations and {len(beaches)} beaches")
    return render_template('main/accommodations.html', 
                         accommodations=accommodations,
                         beaches=beaches)

@main_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    if request.method == 'POST':
        try:
            # Verify current password
            current_password = request.form.get('current_password')
            if not current_password or not current_user.check_password(current_password):
                flash('Current password is incorrect', 'danger')
                return redirect(url_for('main.dashboard'))

            # Update basic info
            updates = {
                'username': request.form.get('username'),
                'email': request.form.get('email'),
                'updated_at': datetime.utcnow()
            }

            # Handle profile picture upload
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(f"{current_user._id}_{file.filename}")
                    if not os.path.exists(UPLOAD_FOLDER):
                        os.makedirs(UPLOAD_FOLDER)
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    updates['profile_picture'] = filename

            # Handle password update
            new_password = request.form.get('new_password')
            if new_password:
                updates['password_hash'] = generate_password_hash(new_password)

            # Update in database
            mongo.db.users.update_one(
                {'_id': current_user._id},
                {'$set': updates}
            )

            flash('Profile updated successfully', 'success')
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'danger')

    return redirect(url_for('main.dashboard')) 