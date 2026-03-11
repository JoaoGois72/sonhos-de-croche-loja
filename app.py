import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import cloudinary
import cloudinary.uploader



db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "admin_login"


# CLOUDINARY
cloudinary.config(
    cloud_name="diugrslyt",
    api_key="229962315311773",
    api_secret="rOF-znJdUlAF54Hft3OhQXMJcg8",
    secure=True
)


# MODELS
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(120))


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200))
    description = db.Column(db.Text)

    image = db.Column(db.String(500))

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    images = db.relationship(
        "ProductImage",
        backref="product",
        cascade="all, delete-orphan"
    )


class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False
    )

    image = db.Column(db.String(500))


class CustomOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120))
    whatsapp = db.Column(db.String(50))

    product_type = db.Column(db.String(120))

    description = db.Column(db.Text)

    status = db.Column(db.String(50), default="Nova")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# LOGIN
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# APP
import os

def create_app():

    app = Flask(__name__)
    
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "chave-super-secreta")  # Substitua por uma chave secreta real em produção

    db_url = os.getenv("DATABASE_URL")

    # converter postgres do Railway para psycopg3
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)

        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    # fallback local
    if not db_url:
        db_url = "sqlite:///database.db"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)


    login_manager.init_app(app)


    # FUNÇÃO UPLOAD CLOUDINARY
    def upload_image(file):

        if not file:
            return None

        result = cloudinary.uploader.upload(
            file,
            folder="sonhos_croche"
        )

        return result["secure_url"]


    # HOME
    @app.route("/")
    def index():

        products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()

        return render_template(
            "index.html",
            products=products
        )


    # PRODUTO
    @app.route("/produto/<int:product_id>")
    def product_detail(product_id):

        product = Product.query.get_or_404(product_id)

        related_products = (
            Product.query
            .filter(Product.id != product.id)
            .limit(4)
            .all()
        )

        return render_template(
            "product_detail.html",
            product=product,
            related_products=related_products
        )


    # ENCOMENDAS
    @app.route("/encomendas", methods=["GET", "POST"])
    def encomendas():

        if request.method == "POST":

            order = CustomOrder(
                name=request.form.get("name"),
                whatsapp=request.form.get("whatsapp"),
                product_type=request.form.get("product_type"),
                description=request.form.get("description")
            )

            db.session.add(order)
            db.session.commit()

            flash("Encomenda enviada com sucesso!")

            return redirect(url_for("index"))

        return render_template("encomendas.html")

    @app.route("/encomendas/enviar", methods=["POST"])
    def enviar_encomenda():

        name = request.form.get("name")
        whatsapp = request.form.get("whatsapp")
        product_type = request.form.get("product_type")
        description = request.form.get("description")

        order = CustomOrder(
            name=name,
            whatsapp=whatsapp,
            product_type=product_type,
            description=description,
            status="Nova"
        )

        db.session.add(order)
        db.session.commit()

        flash("Encomenda enviada com sucesso!", "success")

        return redirect(url_for("index"))
    
    @app.route("/admin/encomenda/<int:id>/delete")
    @login_required
    def admin_encomenda_delete(id):

        order = CustomOrder.query.get_or_404(id)

        db.session.delete(order)

        db.session.commit()

        flash("Encomenda removida")

        return redirect(url_for("admin_encomendas"))


    # LOGIN ADMIN
    @app.route("/admin")
    def admin_login():
        return render_template("admin_login.html")


    @app.route("/admin/login", methods=["POST"])
    def admin_login_post():

        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if not user:
            flash("Usuário não encontrado")
            return redirect(url_for("admin_login"))

        if not check_password_hash(user.password_hash, password):
            flash("Senha inválida")
            return redirect(url_for("admin_login"))

        login_user(user)

        return redirect(url_for("admin_dashboard"))


    @app.route("/admin/logout")
    @login_required
    def admin_logout():

        logout_user()

        return redirect(url_for("index"))


    # DASHBOARD
    @app.route("/admin/dashboard")
    @login_required
    def admin_dashboard():

        products = Product.query.order_by(Product.created_at.desc()).all()

        orders = CustomOrder.query.order_by(CustomOrder.created_at.desc()).limit(10).all()

        return render_template(
            "admin_dashboard.html",
            products=products,
            orders=orders
        )


    # PRODUTOS
    @app.route("/admin/produtos")
    @login_required
    def admin_products():

        products = Product.query.order_by(Product.created_at.desc()).all()

        return render_template(
            "admin_products.html",
            products=products
        )


    # NOVO PRODUTO
    @app.route("/admin/produtos/novo", methods=["GET", "POST"])
    @login_required
    def admin_product_new():

        if request.method == "POST":

            image = upload_image(request.files.get("image"))

            product = Product(
                name=request.form.get("name"),
                description=request.form.get("description"),
                image=image,
                is_active=True
            )

            db.session.add(product)
            db.session.commit()

            flash("Produto criado!")

            return redirect(url_for("admin_products"))

        return render_template("admin_product_form.html", product=None)


    # EDITAR PRODUTO
    @app.route("/admin/produtos/<int:product_id>/editar", methods=["GET", "POST"])
    @login_required
    def admin_product_edit(product_id):

        product = Product.query.get_or_404(product_id)

        if request.method == "POST":

            product.name = request.form.get("name")
            product.description = request.form.get("description")

            file = request.files.get("image")

            if file and file.filename != "":
                product.image = upload_image(file)

            db.session.commit()

            flash("Produto atualizado!")

            return redirect(url_for("admin_products"))

        return render_template(
            "admin_product_form.html",
            product=product
        )


    # EXCLUIR PRODUTO
    @app.route("/admin/produtos/<int:product_id>/delete")
    @login_required
    def admin_product_delete(product_id):

        product = Product.query.get_or_404(product_id)

        db.session.delete(product)
        db.session.commit()

        flash("Produto removido")

        return redirect(url_for("admin_products"))


    # ENCOMENDAS ADMIN
    @app.route("/admin/encomendas")
    @login_required
    def admin_encomendas():

        orders = CustomOrder.query.order_by(CustomOrder.created_at.desc()).all()

        return render_template(
            "admin_encomendas.html",
            orders=orders
        )


    @app.route("/admin/encomenda/<int:id>/status", methods=["POST"])
    @login_required
    def admin_encomenda_status(id):

        order = CustomOrder.query.get_or_404(id)
        
        status = request.form.get("status")

        order.status = status

        db.session.commit()
        
        flash("Status da encomenda atualizado!")

        return redirect(url_for("admin_encomendas"))


    # TEMPLATE GLOBAL
    @app.context_processor
    def inject_globals():

        return dict(
            STORE_NAME=lambda: "Sonhos de Crochê"
        )


    # CRIAR BANCO E ADMIN AUTOMÁTICO
    with app.app_context():

        db.create_all()

        # cria admin automaticamente
        if not User.query.filter_by(email="admin@sonhosdecroche.com").first():

            admin = User(
                email="admin@sonhosdecroche.com",
                password_hash=generate_password_hash("123456")
            )

            db.session.add(admin)
            db.session.commit()


    return app


# APP GLOBAL PARA O GUNICORN (Railway)
app = create_app()
    
