"""
Route blueprints for MedSafe application.
"""
from flask import Flask

def register_routes(app: Flask):
    """Register all route blueprints to the Flask app."""
    from routes.main import main_bp
    from routes.prescription import prescription_bp
    from routes.medicine import medicine_bp
    from routes.demo import demo_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(prescription_bp, url_prefix='/prescription')
    app.register_blueprint(medicine_bp, url_prefix='/medicine')
    app.register_blueprint(demo_bp, url_prefix='/demo')
