import os
from flask import Flask, render_template
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key-change-in-production')
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    from routes import register_routes
    register_routes(app)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html',
                               error_title="Page Not Found",
                               error_message="The requested page could not be found. Please check the URL or return to the MedSafe home screen."), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('error.html',
                               error_title="Service Notice",
                               error_message="We couldn't process this medication request right now. Please verify your details or consult a healthcare provider."), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
