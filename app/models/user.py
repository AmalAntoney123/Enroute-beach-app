from app import mongo
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, username, email, password=None, role='user', is_active=True, profile_picture=None):
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password) if password else None
        self.role = role
        self._is_active = is_active
        self.created_at = datetime.utcnow()
        self.profile_picture = profile_picture
        self._id = None

    @property
    def is_active(self):
        return self._is_active

    def save(self):
        user_data = {
            'username': self.username,
            'email': self.email,
            'password_hash': self.password_hash,
            'role': 'admin' if self.email.lower() == 'admin@mail.com' else 'user',
            'is_active': True,
            'created_at': self.created_at
        }
        result = mongo.db.users.insert_one(user_data)
        self._id = result.inserted_id
        self.role = user_data['role']
        return result

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self._id)

    @staticmethod
    def find_by_username(username):
        user_data = mongo.db.users.find_one({'username': username})
        if user_data:
            user = User(
                username=user_data['username'], 
                email=user_data['email'],
                role=user_data.get('role', 'user'),
                is_active=user_data.get('is_active', True),  # Default to True if not found
                profile_picture=user_data.get('profile_picture')
            )
            user.password_hash = user_data['password_hash']
            user._id = user_data['_id']
            return user
        return None

    @staticmethod
    def find_by_id(user_id):
        from bson.objectid import ObjectId
        user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            user = User(
                username=user_data['username'], 
                email=user_data['email'],
                role=user_data.get('role', 'user'),
                is_active=user_data.get('is_active', True),  # Default to True if not found
                profile_picture=user_data.get('profile_picture')
            )
            user.password_hash = user_data['password_hash']
            user._id = user_data['_id']
            return user
        return None 