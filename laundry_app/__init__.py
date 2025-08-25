from flask import Flask
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from laundry_app.config import Config


db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    from laundry_app.models import TokenBlocklist
    
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        return db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar() is not None

    from laundry_app.routes.authentication import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from laundry_app.routes.order import orders_bp
    app.register_blueprint(orders_bp, url_prefix='/api/orders')

    from laundry_app.routes.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    from laundry_app.routes.customer import customer_bp
    app.register_blueprint(customer_bp, url_prefix='/customer')

    return app
