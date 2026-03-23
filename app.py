from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cok-gizli-bir-anahtar-buraya' # Güvenlik için şart

# Veritabanı
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'butce.db')
db = SQLAlchemy(app)

# Login Yönetimi
login_manager = LoginManager()
login_manager.login_view = 'login' # Giriş yapmamışları buraya yönlendir
login_manager.init_app(app)

# VERİTABANI MODELLERİ
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    # Bir kullanıcının birden fazla işlemi olabilir (İlişki kuruyoruz)
    islemler = db.relationship('Islem', backref='sahibi', lazy=True)

class Islem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    miktar = db.Column(db.Float, nullable=False)
    kategori = db.Column(db.String(50), nullable=False)
    tip = db.Column(db.String(10), default='Gider')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Kime ait?

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTALAR (ROUTES) ---

@app.route('/')
@login_required # Sadece giriş yapanlar görebilir
def ana_sayfa():
    # Sadece GİRİŞ YAPAN KULLANICININ verilerini çek (Filtreleme!)
    tum_islemler = Islem.query.filter_by(user_id=current_user.id).order_by(Islem.id.desc()).all()
    
    toplam_gelir = db.session.query(func.sum(Islem.miktar)).filter(Islem.user_id == current_user.id, Islem.tip == 'Gelir').scalar() or 0
    toplam_gider = db.session.query(func.sum(Islem.miktar)).filter(Islem.user_id == current_user.id, Islem.tip == 'Gider').scalar() or 0
    bakiye = toplam_gelir - toplam_gider

    gider_sorgusu = db.session.query(Islem.kategori, func.sum(Islem.miktar)).filter(Islem.user_id == current_user.id, Islem.tip == 'Gider').group_by(Islem.kategori).all()
    labels = [row[0] for row in gider_sorgusu]
    values = [row[1] for row in gider_sorgusu]

    uyari_mesaji = ""
    if toplam_gelir > 0:
        oran = (toplam_gider / toplam_gelir) * 100
        if oran >= 100: uyari_mesaji = "🚨 Bütçeni aştın!"
        elif oran >= 80: uyari_mesaji = "⚠️ Gelirinin %80'ini harcadın!"

    return render_template('index.html', islemler=tum_islemler, labels=labels, values=values, 
                           gelir=toplam_gelir, gider=toplam_gider, bakiye=bakiye, uyari=uyari_mesaji, 
                           name=current_user.username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('ana_sayfa'))
        flash('Kullanıcı adı veya şifre hatalı!')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_password = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
        new_user = User(username=request.form.get('username'), password=hashed_password)
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        except:
            flash('Bu kullanıcı adı zaten alınmış!')
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/ekle', methods=['POST'])
@login_required
def ekle():
    miktar = request.form.get('miktar')
    kategori = request.form.get('kategori')
    tip = request.form.get('tip')
    if miktar:
        yeni_islem = Islem(miktar=float(miktar), kategori=kategori, tip=tip, user_id=current_user.id)
        db.session.add(yeni_islem)
        db.session.commit()
    return redirect(url_for('ana_sayfa'))

@app.route('/sil/<int:id>')
@login_required
def sil(id):
    islem = Islem.query.get_or_404(id)
    if islem.user_id == current_user.id: # Güvenlik: Başkasının verisini silemesin
        db.session.delete(islem)
        db.session.commit()
    return redirect(url_for('ana_sayfa'))

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)