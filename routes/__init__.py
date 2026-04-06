def register_blueprints(app):
    from routes.admin_auth import bp as admin_auth_bp
    from routes.admin_panel import bp as admin_panel_bp
    from routes.gallery import bp as gallery_bp
    from routes.media import bp as media_bp

    app.register_blueprint(admin_auth_bp)
    app.register_blueprint(admin_panel_bp, url_prefix="/admin")
    app.register_blueprint(gallery_bp)
    app.register_blueprint(media_bp)
