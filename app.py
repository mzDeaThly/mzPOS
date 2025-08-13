from dotenv import load_dotenv
import os
load_dotenv()

\
import os
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from models import db, User, Shop, Category, MenuItem, Table, Order, OrderItem, Ingredient, Recipe, Inventory, Member, Payment, Subscription
from utils.promptpay import build_promptpay_qr_png, PromptPayIDType
import qrcode, io, base64

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "pos.db"))
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()
    return app

app = create_app()

# ---- System owner config (from .env) ----
SYSTEM_PROMPTPAY_ID = os.getenv("SYSTEM_PROMPTPAY_ID", "0812345678")
SYSTEM_PROMPTPAY_KIND = os.getenv("SYSTEM_PROMPTPAY_KIND", "PHONE")
SYSTEM_MERCHANT_NAME = os.getenv("SYSTEM_MERCHANT_NAME", "UNIVERSAL POS")
SYSTEM_MERCHANT_CITY = os.getenv("SYSTEM_MERCHANT_CITY", "BANGKOK")
SUBSCRIPTION_MONTHLY = float(os.getenv("SUBSCRIPTION_MONTHLY", "299.00"))
SUBSCRIPTION_YEARLY = float(os.getenv("SUBSCRIPTION_YEARLY", "2990.00"))


def shop_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        if not current_user.shop_id:
            flash("กรุณาสร้าง/เข้าร่วมร้านค้าก่อน", "warning")
            return redirect(url_for("register"))
        # check subscription valid
        shop = Shop.query.get(current_user.shop_id)
        if shop.plan_expiry and shop.plan_expiry < datetime.utcnow().date():
            allowed = {"subscriptions", "logout", "set_subscription_paid"}
            if request.endpoint not in allowed:
                flash("แพ็กเกจหมดอายุ กรุณาต่ออายุการใช้งาน", "danger")
                return redirect(url_for("subscriptions"))
        return fn(*args, **kwargs)
    return wrapper

def _rand_token(n=16):
    import secrets, string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def ensure_table_token(table):
    try:
        if not getattr(table, "token", None):
            table.token = _rand_token(16)
            db.session.commit()
        elif not table.token:
            table.token = _rand_token(16)
            db.session.commit()
    except Exception:
        pass
    return table.token

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        shop_name = request.form["shop_name"].strip()
        if User.query.filter_by(email=email).first():
            flash("อีเมลนี้ถูกใช้แล้ว", "danger")
            return redirect(url_for("register"))
        user = User(email=email, password_hash=generate_password_hash(password))
        db.session.add(user); db.session.commit()
        shop = Shop(name=shop_name, owner_user_id=user.id)
        db.session.add(shop); db.session.commit()
        user.shop_id = shop.id; db.session.commit()
        login_user(user)
        flash("สมัครสมาชิกและสร้างร้านสำเร็จ", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("อีเมลหรือรหัสผ่านไม่ถูกต้อง", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
@shop_required
def dashboard():
    shop = Shop.query.get(current_user.shop_id)
    today = datetime.utcnow().date()
    orders = Order.query.filter_by(shop_id=shop.id, status="PAID").all()
    day_sales = sum([o.total_amount for o in orders if o.closed_at and o.closed_at.date() == today])
    week_sales = sum([o.total_amount for o in orders if o.closed_at and (today - o.closed_at.date()).days <= 7])
    month_sales = sum([o.total_amount for o in orders if o.closed_at and o.closed_at.date().month == today.month and o.closed_at.date().year == today.year])
    top = {}
    for o in orders:
        for it in o.items:
            top[it.menu_item.name] = top.get(it.menu_item.name, 0) + it.quantity
    top_items = sorted(top.items(), key=lambda x: x[1], reverse=True)[:5]
    return render_template("dashboard.html", shop=shop, day_sales=day_sales, week_sales=week_sales, month_sales=month_sales, top_items=top_items)

# Subscriptions
@app.route("/subscriptions", methods=["GET","POST"])
@login_required
def subscriptions():
    shop = Shop.query.get(current_user.shop_id)
    plans = [
        {"code":"MONTHLY","name":"รายเดือน","days":30,"price":299.0},
        {"code":"ANNUAL","name":"รายปี","days":365,"price":2990.0},
    ]
    if request.method == "POST":
        code = request.form["plan_code"]
        plan = next((p for p in plans if p["code"]==code), None)
        if not plan: 
            flash("แพ็กเกจไม่ถูกต้อง","danger"); return redirect(url_for("subscriptions"))
        sub = Subscription(shop_id=shop.id, plan_code=plan["code"], price=plan["price"], days=plan["days"], status="PENDING", created_at=datetime.utcnow())
        db.session.add(sub); db.session.commit()
        return redirect(url_for("pay_subscription", sub_id=sub.id))
    return render_template("subscriptions.html", shop=shop, plans=plans)

@app.route("/subscriptions/<int:sub_id>/pay")
@login_required
def pay_subscription(sub_id):
    shop = Shop.query.get(current_user.shop_id)
    sub = Subscription.query.get_or_404(sub_id)
    if sub.shop_id != shop.id: 
        flash("ไม่พบรายการของร้านคุณ","danger"); return redirect(url_for("subscriptions"))
    receiver = SYSTEM_PROMPTPAY_ID
    kind = SYSTEM_PROMPTPAY_KIND
    amount = float(sub.price)
    png_bytes = build_promptpay_qr_png(
        receiver, PromptPayIDType[kind], amount,
        merchant_name=SYSTEM_MERCHANT_NAME, merchant_city=SYSTEM_MERCHANT_CITY,
        reference=f"SUB{sub.id}", dynamic=True
    )
    return render_template("subscription_pay.html", shop=shop, sub=sub, qr_png=b"data:image/png;base64,"+png_bytes.encode())

@app.route("/subscriptions/<int:sub_id>/mark_paid", methods=["POST"])
@login_required
def set_subscription_paid(sub_id):
    shop = Shop.query.get(current_user.shop_id)
    sub = Subscription.query.get_or_404(sub_id)
    if sub.shop_id != shop.id: 
        flash("ไม่พบรายการของร้านคุณ","danger"); return redirect(url_for("subscriptions"))
    sub.status = "PAID"; db.session.commit()
    start_date = max(datetime.utcnow().date(), shop.plan_expiry or datetime.utcnow().date())
    shop.plan_expiry = start_date + timedelta(days=sub.days)
    db.session.commit()
    flash("ต่ออายุแพ็กเกจสำเร็จ", "success")
    return redirect(url_for("dashboard"))

# Settings
@app.route("/settings", methods=["GET","POST"])
@login_required
@shop_required
def settings():
    shop = Shop.query.get(current_user.shop_id)
    if request.method == "POST":
        shop.name = request.form["name"]
        shop.promptpay_id = request.form.get("promptpay_id","").strip()
        shop.promptpay_kind = request.form.get("promptpay_kind","PHONE")
        shop.point_rate = float(request.form.get("point_rate", "1.0"))
        db.session.commit()
        flash("บันทึกการตั้งค่าแล้ว","success")
        return redirect(url_for("settings"))
    return render_template("settings.html", shop=shop)

# Categories & Menu
@app.route("/categories", methods=["GET","POST"])
@login_required
@shop_required
def categories():
    shop = Shop.query.get(current_user.shop_id)
    if request.method == "POST":
        name = request.form["name"]
        db.session.add(Category(shop_id=shop.id, name=name)); db.session.commit()
        return redirect(url_for("categories"))
    cats = Category.query.filter_by(shop_id=shop.id).all()
    return render_template("categories.html", cats=cats)

@app.route("/categories/<int:cat_id>/delete", methods=["POST"])
@login_required
def del_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    if cat.shop_id != current_user.shop_id: 
        flash("ไม่พบหมวดหมู่ของร้านคุณ","danger"); return redirect(url_for("categories"))
    db.session.delete(cat); db.session.commit()
    return redirect(url_for("categories"))

@app.route("/menu", methods=["GET","POST"])
@login_required
@shop_required
def menu():
    shop = Shop.query.get(current_user.shop_id)
    cats = Category.query.filter_by(shop_id=shop.id).all()
    if request.method == "POST"]:
        name = request.form["name"]; price = float(request.form["price"]); cat_id = int(request.form["category_id"])
        img = request.files.get("image")
        img_path = None
        if img and img.filename:
            fname = datetime.utcnow().strftime("%Y%m%d%H%M%S_") + secure_filename(img.filename)
            img.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
            img_path = f"/static/uploads/{fname}"
        db.session.add(MenuItem(shop_id=shop.id, name=name, price=price, category_id=cat_id, image_url=img_path))
        db.session.commit()
        return redirect(url_for("menu"))
    items = MenuItem.query.filter_by(shop_id=shop.id).all()
    return render_template("menu.html", items=items, cats=cats)

@app.route("/menu/<int:item_id>/delete", methods=["POST"])
@login_required
def del_menu_item(item_id):
    it = MenuItem.query.get_or_404(item_id)
    if it.shop_id != current_user.shop_id: 
        flash("ไม่พบเมนูของร้านคุณ","danger"); return redirect(url_for("menu"))
    db.session.delete(it); db.session.commit()
    return redirect(url_for("menu"))

# Tables & Orders
@app.route("/tables", methods=["GET","POST"])
@login_required
@shop_required
def tables():
    shop = Shop.query.get(current_user.shop_id)
    if request.method == "POST":
        name = request.form["name"]
        db.session.add(Table(shop_id=shop.id, name=name, status="FREE")); db.session.commit()
        return redirect(url_for("tables"))
    ts = Table.query.filter_by(shop_id=shop.id).all()
    return render_template("tables.html", tables=ts)

@app.route("/tables/<int:table_id>/qr")
@login_required
@shop_required
def table_qr(table_id):
    shop = Shop.query.get(current_user.shop_id)
    table = Table.query.get_or_404(table_id)
    if table.shop_id != shop.id:
        flash("ไม่พบโต๊ะของร้านคุณ","danger"); return redirect(url_for("tables"))
    token = ensure_table_token(table)
    public_url = url_for("public_order", token=token, _external=True)
    img = qrcode.make(public_url)
    bio = io.BytesIO(); img.save(bio, format="PNG")
    b64 = base64.b64encode(bio.getvalue()).decode("utf-8")
    return render_template("table_qr.html", table=table, public_url=public_url, qr_png=b64)

@app.route("/orders/new/<int:table_id>", methods=["GET","POST"])
@login_required
@shop_required
def new_order(table_id):
    shop = Shop.query.get(current_user.shop_id)
    table = Table.query.get_or_404(table_id)
    if table.shop_id != shop.id: 
        flash("ไม่พบโต๊ะของร้านคุณ","danger"); return redirect(url_for("tables"))
    if request.method == "POST":
        item_id = int(request.form["item_id"]); qty = int(request.form["qty"])
        order = Order.query.filter_by(shop_id=shop.id, table_id=table.id, status="OPEN").first()
        if not order:
            order = Order(shop_id=shop.id, table_id=table.id, status="OPEN", created_at=datetime.utcnow(), total_amount=0.0)
            db.session.add(order); db.session.commit()
            table.status="BUSY"; db.session.commit()
        menu_item = MenuItem.query.get(item_id)
        db.session.add(OrderItem(order_id=order.id, menu_item_id=item_id, quantity=qty, unit_price=menu_item.price)); db.session.commit()
        order.total_amount = sum([it.quantity*it.unit_price for it in order.items]); db.session.commit()
        flash("เพิ่มรายการแล้ว","success")
        return redirect(url_for("new_order", table_id=table.id))
    items = MenuItem.query.filter_by(shop_id=shop.id).all()
    order = Order.query.filter_by(shop_id=shop.id, table_id=table.id, status="OPEN").first()
    return render_template("order_new.html", table=table, items=items, order=order)

@app.route("/kitchen")
@login_required
@shop_required
def kitchen():
    shop = Shop.query.get(current_user.shop_id)
    orders = Order.query.filter_by(shop_id=shop.id, status="OPEN").all()
    return render_template("kitchen.html", orders=orders)

@app.route("/orders/<int:order_id>/close", methods=["GET","POST"])
@login_required
@shop_required
def close_order(order_id):
    shop = Shop.query.get(current_user.shop_id)
    order = Order.query.get_or_404(order_id)
    if order.shop_id != shop.id:
        flash("ไม่พบออเดอร์ของร้านคุณ","danger"); return redirect(url_for("tables"))
    if request.method == "POST":
        method = request.form["method"]
        member_phone = request.form.get("member_phone","").strip()
        if member_phone:
            member = Member.query.filter_by(shop_id=shop.id, phone=member_phone).first()
            if not member:
                member = Member(shop_id=shop.id, name=member_phone, phone=member_phone, points=0)
                db.session.add(member); db.session.commit()
            earn = int(order.total_amount // shop.point_rate) if shop.point_rate else 0
            member.points += earn; db.session.commit()
        if method == "PROMPTPAY":
            return redirect(url_for("pay_order_promptpay", order_id=order.id))
        _finalize_order(order)
        flash("รับเงินสดและปิดบิลแล้ว","success")
        return redirect(url_for("receipt", order_id=order.id))
    return render_template("close_order.html", order=order, shop=shop)

def _finalize_order(order: Order):
    for it in order.items:
        recipes = Recipe.query.filter_by(menu_item_id=it.menu_item_id).all()
        for r in recipes:
            inv = Inventory.query.filter_by(shop_id=order.shop_id, ingredient_id=r.ingredient_id).first()
            if inv:
                inv.quantity -= (r.quantity * it.quantity)
    order.status = "PAID"
    order.closed_at = datetime.utcnow()
    db.session.commit()

@app.route("/orders/<int:order_id>/pay_promptpay")
@login_required
@shop_required
def pay_order_promptpay(order_id):
    shop = Shop.query.get(current_user.shop_id)
    order = Order.query.get_or_404(order_id)
    if order.shop_id != shop.id:
        flash("ไม่พบออเดอร์ของร้านคุณ","danger"); return redirect(url_for("tables"))
    receiver = shop.promptpay_id or "0812345678"
    kind = shop.promptpay_kind or "PHONE"
    png_b64 = build_promptpay_qr_png(
        receiver, PromptPayIDType[kind], float(order.total_amount),
        merchant_name=shop.name, merchant_city="BANGKOK",
        reference=f"ORDER{order.id}", dynamic=True
    )
    return render_template("pay_promptpay.html", order=order, qr_png=b"data:image/png;base64,"+png_b64.encode())

@app.route("/orders/<int:order_id>/mark_paid", methods=["POST"])
@login_required
@shop_required
def mark_paid(order_id):
    shop = Shop.query.get(current_user.shop_id)
    order = Order.query.get_or_404(order_id)
    if order.shop_id != shop.id:
        flash("ไม่พบออเดอร์ของร้านคุณ","danger"); return redirect(url_for("tables"))
    _finalize_order(order)
    flash("ทำเครื่องหมายชำระเงินแล้ว","success")
    return redirect(url_for("receipt", order_id=order.id))

@app.route("/receipt/<int:order_id>")
@login_required
@shop_required
def receipt(order_id):
    order = Order.query.get_or_404(order_id)
    shop = Shop.query.get(current_user.shop_id)
    return render_template("receipt.html", order=order, shop=shop)

# Inventory & Recipes
@app.route("/inventory", methods=["GET","POST"])
@login_required
@shop_required
def inventory():
    shop = Shop.query.get(current_user.shop_id)
    if request.method == "POST":
        name = request.form["name"]; qty = float(request.form["quantity"]); unit = request.form["unit"]
        ing = Ingredient(shop_id=shop.id, name=name, unit=unit)
        db.session.add(ing); db.session.commit()
        db.session.add(Inventory(shop_id=shop.id, ingredient_id=ing.id, quantity=qty)); db.session.commit()
        return redirect(url_for("inventory"))
    invs = db.session.query(Inventory, Ingredient).join(Ingredient, Inventory.ingredient_id==Ingredient.id).filter(Inventory.shop_id==shop.id).all()
    return render_template("inventory.html", invs=invs)

@app.route("/recipes/<int:menu_id>", methods=["GET","POST"])
@login_required
@shop_required
def recipes(menu_id):
    shop = Shop.query.get(current_user.shop_id)
    item = MenuItem.query.get_or_404(menu_id)
    if item.shop_id != shop.id: 
        flash("ไม่พบเมนูของร้านคุณ","danger"); return redirect(url_for("menu"))
    if request.method == "POST":
        ing_id = int(request.form["ingredient_id"]); qty = float(request.form["quantity"])
        db.session.add(Recipe(menu_item_id=item.id, ingredient_id=ing_id, quantity=qty)); db.session.commit()
        return redirect(url_for("recipes", menu_id=item.id))
    ings = Ingredient.query.filter_by(shop_id=shop.id).all()
    recs = db.session.query(Recipe, Ingredient).join(Ingredient, Recipe.ingredient_id==Ingredient.id).filter(Recipe.menu_item_id==item.id).all()
    return render_template("recipes.html", item=item, ings=ings, recs=recs)

# Members
@app.route("/members", methods=["GET","POST"])
@login_required
@shop_required
def members():
    shop = Shop.query.get(current_user.shop_id)
    if request.method == "POST":
        name = request.form["name"]; phone = request.form["phone"]
        db.session.add(Member(shop_id=shop.id, name=name, phone=phone, points=0)); db.session.commit()
        return redirect(url_for("members"))
    ms = Member.query.filter_by(shop_id=shop.id).all()
    return render_template("members.html", members=ms)

# Reports
@app.route("/reports")
@login_required
@shop_required
def reports():
    shop = Shop.query.get(current_user.shop_id)
    orders = Order.query.filter_by(shop_id=shop.id, status="PAID").all()
    total = sum([o.total_amount for o in orders])
    today = datetime.utcnow().date()
    daily = sum([o.total_amount for o in orders if o.closed_at and o.closed_at.date()==today])
    weekly = sum([o.total_amount for o in orders if o.closed_at and (today - o.closed_at.date()).days <= 7])
    monthly = sum([o.total_amount for o in orders if o.closed_at and o.closed_at.date().month==today.month and o.closed_at.date().year==today.year])
    return render_template("reports.html", total=total, daily=daily, weekly=weekly, monthly=monthly)

# Public ordering
@app.route("/p/<token>", methods=["GET","POST"])
def public_order(token):
    table = Table.query.filter_by(token=token).first()
    if not table:
        return "Invalid table token", 404
    shop = Shop.query.get(table.shop_id)
    cart_key = f"cart_{token}"
    cart = session.get(cart_key, {})
    if request.method == "POST":
        item_id = int(request.form["item_id"]); qty = int(request.form.get("qty", 1))
        cart[str(item_id)] = cart.get(str(item_id), 0) + qty
        session[cart_key] = cart
        session.modified = True
        flash("เพิ่มรายการแล้ว", "success")
        return redirect(url_for("public_order", token=token))
    categories = Category.query.filter_by(shop_id=shop.id).all()
    items = MenuItem.query.filter_by(shop_id=shop.id).all()
    items_by_cat = {}
    for c in categories:
        items_by_cat[c.id] = []
    for it in items:
        items_by_cat.setdefault(it.category_id, []).append(it)
    cart_items, total = [], 0.0
    for k,v in cart.items():
        it = MenuItem.query.get(int(k))
        if not it: continue
        cart_items.append({"name":it.name, "qty":v, "subtotal":it.price*v, "price":it.price, "id":it.id})
        total += it.price * v
    return render_template("public_order.html", shop=shop, table=table, categories=categories, items_by_cat=items_by_cat, cart_items=cart_items, total=total)

@app.route("/p/<token>/remove/<int:item_id>")
def public_remove(token, item_id):
    cart_key = f"cart_{token}"
    cart = session.get(cart_key, {})
    if str(item_id) in cart:
        cart.pop(str(item_id))
        session[cart_key] = cart
        session.modified = True
    return redirect(url_for("public_order", token=token))

@app.route("/p/<token>/checkout", methods=["POST"])
def public_checkout(token):
    table = Table.query.filter_by(token=token).first()
    if not table:
        return "Invalid table token", 404
    shop = Shop.query.get(table.shop_id)
    cart_key = f"cart_{token}"
    cart = session.get(cart_key, {})
    if not cart:
        flash("ตะกร้าว่างเปล่า", "warning")
        return redirect(url_for("public_order", token=token))
    order = Order.query.filter_by(shop_id=shop.id, table_id=table.id, status="OPEN").first()
    if not order:
        order = Order(shop_id=shop.id, table_id=table.id, status="OPEN", created_at=datetime.utcnow(), total_amount=0.0)
        db.session.add(order); db.session.commit()
        table.status = "BUSY"; db.session.commit()
    for k,qty in cart.items():
        it = MenuItem.query.get(int(k))
        if not it: continue
        db.session.add(OrderItem(order_id=order.id, menu_item_id=it.id, quantity=int(qty), unit_price=it.price))
    db.session.commit()
    order.total_amount = sum([it.quantity*it.unit_price for it in order.items]); db.session.commit()
    session.pop(cart_key, None)
    flash("ส่งออเดอร์เข้าครัวแล้ว! แจ้งพนักงานเมื่อพร้อมชำระเงิน", "success")
    return redirect(url_for("public_order", token=token))

# Static uploads
@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True)
