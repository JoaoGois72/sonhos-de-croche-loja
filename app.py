import os
import uuid
from datetime import datetime
from decimal import Decimal

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    images = db.relationship("ProductImage", backref="product", cascade="all, delete-orphan", lazy=True)


class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    image_url = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    whatsapp = db.Column(db.String(50), nullable=False)
    city_state = db.Column(db.String(120), default="")
    address = db.Column(db.Text, default="")
    notes = db.Column(db.Text, default="")
    payment_method = db.Column(db.String(20), nullable=False)  # pix|card
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    amount_original = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(60), default="Aguardando pagamento")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product_name_snapshot = db.Column(db.String(120), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    qty = db.Column(db.Integer, nullable=False, default=1)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif db_url.startswith("postgresql://") and "postgresql+psycopg2://" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        db_url = "sqlite:///sonhos.db"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["STORE_NAME"] = os.getenv("STORE_NAME", "Sonhos de Crochê")
    app.config["PIX_KEY"] = os.getenv("PIX_KEY", "SUA_CHAVE_PIX_AQUI")
    app.config["PIX_RECEIVER_NAME"] = os.getenv("PIX_RECEIVER_NAME", "Sonhos de Crochê")
    app.config["PIX_DISCOUNT_PERCENT"] = int(os.getenv("PIX_DISCOUNT_PERCENT", "0"))
    app.config["MERCADOPAGO_PAYMENT_LINK"] = os.getenv("MERCADOPAGO_PAYMENT_LINK", "")

    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "img", "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    def save_upload(file_storage) -> str:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        original = secure_filename(file_storage.filename or "")
        ext = (original.rsplit(".", 1)[1].lower() if "." in original else "jpg")
        unique = f"produto_{uuid.uuid4().hex[:12]}.{ext}"
        file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], unique))
        return f"/static/img/uploads/{unique}"

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "admin_login"

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    def cart():
        return session.setdefault("cart", {})

    def cart_count():
        return sum(int(q) for q in cart().values())

    def money_br(value: Decimal):
        s = f"{value:.2f}"
        return "R$ " + s.replace(".", ",")

    def price_with_pix_discount(price: Decimal):
        pct = app.config.get("PIX_DISCOUNT_PERCENT", 0) or 0
        if pct <= 0:
            return price
        factor = (Decimal(100) - Decimal(pct)) / Decimal(100)
        return (price * factor).quantize(Decimal("0.01"))

    app.jinja_env.globals.update(
        STORE_NAME=lambda: app.config["STORE_NAME"],
        cart_count=cart_count,
        money_br=money_br,
        pix_discount_percent=lambda: app.config.get("PIX_DISCOUNT_PERCENT", 0),
        is_admin=lambda: current_user.is_authenticated,
    )

    def bootstrap_db(seed: bool = True):
        db.create_all()

        admin_email = os.getenv("ADMIN_EMAIL", "admin@sonhosdecroche.com")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        if not User.query.filter_by(email=admin_email).first():
            u = User(
                email=admin_email,
                password_hash=generate_password_hash(admin_password),
                created_at=datetime.utcnow()
            )
            db.session.add(u)
            db.session.commit()

        if seed and Product.query.count() == 0:
            names = [
                "Bolsa Floral", "Bolsa Girassol", "Bolsa Verão", "Bolsa Boho", "Bolsa Elegance",
                "Bolsa Pérola", "Bolsa Primavera", "Bolsa Mandala", "Bolsa Natural", "Bolsa Color Mix",
                "Bolsa Aurora", "Bolsa Sol", "Bolsa Areia", "Bolsa Romance", "Bolsa Jardim",
                "Bolsa Lua", "Bolsa Doce", "Bolsa Serena", "Bolsa Charm", "Bolsa Clássica"
            ]
            for n in names:
                db.session.add(Product(
                    name=n,
                    description="Bolsa artesanal em crochê. Personalize cores e tamanho sob encomenda.",
                    price=Decimal("120.00"),
                    is_active=True,
                    created_at=datetime.utcnow()
                ))
            db.session.commit()

    with app.app_context():
        bootstrap_db(seed=True)

    @app.route("/")
    def index():
        q = request.args.get("q", "").strip()
        if q:
            products = Product.query.filter(Product.is_active == True, Product.name.ilike(f"%{q}%")).order_by(Product.created_at.desc()).all()
        else:
            products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
        return render_template("index.html", products=products, q=q)

    @app.route("/produto/<int:product_id>")
    def product_detail(product_id):
        product = Product.query.get_or_404(product_id)
        if not product.is_active:
            abort(404)
        images = ProductImage.query.filter_by(product_id=product.id).order_by(ProductImage.created_at.asc()).all()
        return render_template("product.html", product=product, images=images)

    @app.route("/carrinho")
    def cart_view():
        items = []
        total = Decimal("0.00")
        c = cart()
        for pid_str, qty in c.items():
            product = Product.query.get(int(pid_str))
            if not product or not product.is_active:
                continue
            qty_i = int(qty)
            subtotal = (product.price * qty_i).quantize(Decimal("0.01"))
            total += subtotal
            items.append({"product": product, "qty": qty_i, "subtotal": subtotal})
        return render_template("cart.html", items=items, total=total)

    @app.post("/carrinho/add/<int:product_id>")
    def cart_add(product_id):
        product = Product.query.get_or_404(product_id)
        if not product.is_active:
            abort(404)
        qty = int(request.form.get("qty", "1") or "1")
        qty = max(1, min(qty, 99))
        c = cart()
        key = str(product_id)
        c[key] = int(c.get(key, 0)) + qty
        session["cart"] = c
        flash("Adicionado ao carrinho ✅", "success")
        return redirect(url_for("cart_view"))

    @app.post("/carrinho/update")
    def cart_update():
        c = cart()
        for key, val in request.form.items():
            if not key.startswith("qty_"):
                continue
            pid = key.replace("qty_", "")
            try:
                q = int(val)
            except Exception:
                q = 1
            if q <= 0:
                c.pop(pid, None)
            else:
                c[pid] = max(1, min(q, 99))
        session["cart"] = c
        flash("Carrinho atualizado ✅", "success")
        return redirect(url_for("cart_view"))

    @app.get("/carrinho/limpar")
    def cart_clear():
        session["cart"] = {}
        flash("Carrinho esvaziado ✅", "success")
        return redirect(url_for("index"))

    @app.get("/checkout")
    def checkout():
        items = []
        total = Decimal("0.00")
        c = cart()
        for pid_str, qty in c.items():
            product = Product.query.get(int(pid_str))
            if not product or not product.is_active:
                continue
            qty_i = int(qty)
            subtotal = (product.price * qty_i).quantize(Decimal("0.01"))
            total += subtotal
            items.append({"product": product, "qty": qty_i, "subtotal": subtotal})
        if not items:
            flash("Seu carrinho está vazio.", "warning")
            return redirect(url_for("index"))

        total_pix = price_with_pix_discount(total)

        return render_template(
            "checkout.html",
            items=items,
            total=total,
            total_pix=total_pix,
            pix_key=app.config["PIX_KEY"],
            pix_receiver=app.config["PIX_RECEIVER_NAME"],
            mp_link=app.config.get("MERCADOPAGO_PAYMENT_LINK", ""),
        )

    @app.post("/pedido/criar")
    def create_order():
        c = cart()
        if not c:
            flash("Carrinho vazio.", "warning")
            return redirect(url_for("index"))

        payment_method = request.form.get("payment_method", "pix")
        if payment_method not in ("pix", "card"):
            payment_method = "pix"

        customer_name = (request.form.get("customer_name") or "").strip()
        whatsapp = (request.form.get("whatsapp") or "").strip()
        city_state = (request.form.get("city_state") or "").strip()
        address = (request.form.get("address") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        if not customer_name or not whatsapp:
            flash("Informe seu nome e WhatsApp para finalizar.", "danger")
            return redirect(url_for("checkout"))

        items = []
        total = Decimal("0.00")
        for pid_str, qty in c.items():
            product = Product.query.get(int(pid_str))
            if not product or not product.is_active:
                continue
            qty_i = int(qty)
            subtotal = (product.price * qty_i).quantize(Decimal("0.01"))
            total += subtotal
            items.append((product, qty_i, product.price))

        if not items:
            flash("Carrinho vazio.", "warning")
            return redirect(url_for("index"))

        total_pix = price_with_pix_discount(total)
        amount = total_pix if payment_method == "pix" else total

        order = Order(
            customer_name=customer_name,
            whatsapp=whatsapp,
            city_state=city_state,
            address=address,
            notes=notes,
            payment_method=payment_method,
            amount=amount,
            amount_original=total,
            status="Aguardando pagamento",
            created_at=datetime.utcnow(),
        )
        db.session.add(order)
        db.session.flush()

        for product, qty_i, unit_price in items:
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name_snapshot=product.name,
                unit_price=unit_price,
                qty=qty_i
            ))

        db.session.commit()
        session["cart"] = {}
        return redirect(url_for("order_success", order_id=order.id))

    @app.get("/pedido/<int:order_id>/sucesso")
    def order_success(order_id):
        order = Order.query.get_or_404(order_id)
        items = OrderItem.query.filter_by(order_id=order.id).all()

        lines = [f"Olá! Fiz um pedido na loja {app.config['STORE_NAME']}."]
        lines.append(f"Pedido: #{order.id}")
        for it in items:
            lines.append(f"- {it.qty}x {it.product_name_snapshot} (R$ {it.unit_price:.2f})")
        lines.append(f"Total: R$ {order.amount:.2f}")
        lines.append(f"Pagamento: {'Pix' if order.payment_method == 'pix' else 'Cartão'}")
        if order.payment_method == "pix":
            lines.append(f"Chave Pix: {app.config['PIX_KEY']}")
        msg = "\n".join(lines)

        return render_template(
            "order_success.html",
            order=order,
            items=items,
            pix_key=app.config["PIX_KEY"],
            pix_receiver=app.config["PIX_RECEIVER_NAME"],
            mp_link=app.config.get("MERCADOPAGO_PAYMENT_LINK", ""),
            whatsapp_message=msg
        )

    @app.get("/admin/login")
    def admin_login():
        return render_template("admin_login.html")

    @app.post("/admin/login")
    def admin_login_post():
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "")
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Login inválido.", "danger")
            return redirect(url_for("admin_login"))
        login_user(user)
        return redirect(url_for("admin_dashboard"))

    @app.get("/admin/logout")
    @login_required
    def admin_logout():
        logout_user()
        flash("Saiu do sistema.", "success")
        return redirect(url_for("index"))

    @app.get("/admin")
    @login_required
    def admin_dashboard():
        orders = Order.query.order_by(Order.created_at.desc()).limit(80).all()
        return render_template("admin_dashboard.html", orders=orders)

    @app.get("/admin/produtos")
    @login_required
    def admin_products():
        products = Product.query.order_by(Product.created_at.desc()).all()
        return render_template("admin_products.html", products=products)

    @app.get("/admin/produtos/novo")
    @login_required
    def admin_products_new():
        return render_template("admin_product_form.html", product=None, images=[])

    @app.post("/admin/produtos/novo")
    @login_required
    def admin_products_new_post():
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        price = (request.form.get("price") or "0").replace(",", ".").strip()
        is_active = True if request.form.get("is_active") == "on" else False

        try:
            price_d = Decimal(price).quantize(Decimal("0.01"))
        except Exception:
            flash("Preço inválido.", "danger")
            return redirect(url_for("admin_products_new"))

        if not name:
            flash("Informe o nome.", "danger")
            return redirect(url_for("admin_products_new"))

        p = Product(name=name, description=description, price=price_d, is_active=is_active, created_at=datetime.utcnow())
        db.session.add(p)
        db.session.flush()

        files = request.files.getlist("image_files")
        for f in files:
            if not f or not getattr(f, "filename", ""):
                continue
            if not allowed_file(f.filename):
                flash("Formato de foto inválido (use JPG/PNG/WEBP).", "warning")
                continue
            url = save_upload(f)
            db.session.add(ProductImage(product_id=p.id, image_url=url))

        db.session.commit()
        flash("Produto criado ✅", "success")
        return redirect(url_for("admin_products"))

    @app.get("/admin/produtos/<int:product_id>/editar")
    @login_required
    def admin_products_edit(product_id):
        product = Product.query.get_or_404(product_id)
        images = ProductImage.query.filter_by(product_id=product.id).order_by(ProductImage.created_at.asc()).all()
        return render_template("admin_product_form.html", product=product, images=images)

    @app.post("/admin/produtos/<int:product_id>/editar")
    @login_required
    def admin_products_edit_post(product_id):
        product = Product.query.get_or_404(product_id)
        product.name = (request.form.get("name") or "").strip()
        product.description = (request.form.get("description") or "").strip()
        product.is_active = True if request.form.get("is_active") == "on" else False

        price = (request.form.get("price") or "0").replace(",", ".").strip()
        try:
            product.price = Decimal(price).quantize(Decimal("0.01"))
        except Exception:
            flash("Preço inválido.", "danger")
            return redirect(url_for("admin_products_edit", product_id=product_id))

        files = request.files.getlist("image_files")
        for f in files:
            if not f or not getattr(f, "filename", ""):
                continue
            if not allowed_file(f.filename):
                flash("Formato de foto inválido (use JPG/PNG/WEBP).", "warning")
                continue
            url = save_upload(f)
            db.session.add(ProductImage(product_id=product.id, image_url=url))

        db.session.commit()
        flash("Produto atualizado ✅", "success")
        return redirect(url_for("admin_products_edit", product_id=product.id))

    @app.post("/admin/produtos/imagem/<int:image_id>/excluir")
    @login_required
    def admin_product_image_delete(image_id):
        img = ProductImage.query.get_or_404(image_id)
        try:
            if img.image_url.startswith("/static/"):
                rel = img.image_url.lstrip("/")
                fp = os.path.join(app.root_path, rel)
                if os.path.exists(fp):
                    os.remove(fp)
        except Exception:
            pass
        product_id = img.product_id
        db.session.delete(img)
        db.session.commit()
        flash("Foto removida ✅", "success")
        return redirect(url_for("admin_products_edit", product_id=product_id))

    @app.post("/admin/produtos/<int:product_id>/excluir")
    @login_required
    def admin_products_delete(product_id):
        product = Product.query.get_or_404(product_id)
        db.session.delete(product)
        db.session.commit()
        flash("Produto excluído ✅", "success")
        return redirect(url_for("admin_products"))

    @app.post("/admin/pedidos/<int:order_id>/status")
    @login_required
    def admin_order_status(order_id):
        order = Order.query.get_or_404(order_id)
        status = (request.form.get("status") or "").strip()
        if status:
            order.status = status
            db.session.commit()
            flash("Status atualizado ✅", "success")
        return redirect(url_for("admin_dashboard"))

    @app.cli.command("init-db")
    def init_db():
        with app.app_context():
            bootstrap_db(seed=True)
            print("✅ Banco inicializado com admin e catálogo.")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
