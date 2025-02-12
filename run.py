from app import create_app
from app import mongo

app = create_app()

if __name__ == '__main__':
    # Test MongoDB connection
    with app.app_context():
        try:
            mongo.db.command('ping')
            print("MongoDB connection successful!")
        except Exception as e:
            print(f"MongoDB connection failed: {e}")
    
    app.run(debug=True) 