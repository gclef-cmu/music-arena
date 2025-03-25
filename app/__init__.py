import os
import logging
from flask import Flask
from flask_cors import CORS

def create_app(test_config=None):
    """Create and configure the Flask application."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    # Enable CORS
    CORS(app, supports_credentials=True)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Register blueprints
    from app.api.music_generation import music_generation_bp
    app.register_blueprint(music_generation_bp, url_prefix='/api')
    
    # Simple health check route
    @app.route('/health')
    def health_check():
        return {'status': 'ok'}
    
    return app