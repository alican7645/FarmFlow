import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, send_file, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, date, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import io
from functools import wraps

# Import models
from models import db, User, LoginAttempt

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "sera-yonetim-secret-key")

# PostgreSQL Database configuration
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    # Fallback to individual PostgreSQL environment variables
    host = os.environ.get('PGHOST', 'localhost')
    port = os.environ.get('PGPORT', '5432')
    database = os.environ.get('PGDATABASE', 'postgres')
    user = os.environ.get('PGUSER', 'postgres')
    password = os.environ.get('PGPASSWORD', '')
    database_url = f'postgresql://{user}:{password}@{host}:{port}/{database}'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Initialize database with app
db.init_app(app)

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Bu sayfaya erişmek için giriş yapmalısınız.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- DATABASE OLUŞTURMA ---
def init_db():
    conn = sqlite3.connect('sera.db')
    c = conn.cursor()

    # Üretim Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS uretim (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sera_adi TEXT NOT NULL,
        urun_adi TEXT NOT NULL,
        ekim_tarihi TEXT NOT NULL,
        hasat_tarihi TEXT,
        durum TEXT DEFAULT 'Ekim Yapıldı',
        alan REAL,
        beklenen_verim REAL,
        gercek_verim REAL,
        notlar TEXT,
        olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # Stok Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS stok (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        malzeme_adi TEXT NOT NULL,
        kategori TEXT,
        miktar REAL NOT NULL,
        birim TEXT,
        tarih TEXT NOT NULL,
        depo TEXT,
        min_stok REAL DEFAULT 0,
        maliyet REAL DEFAULT 0,
        notlar TEXT
    )''')

    # Personel Tablosu (Çalışan Bilgileri)
    c.execute('''CREATE TABLE IF NOT EXISTS personel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        personel_adi TEXT NOT NULL,
        pozisyon TEXT,
        aylik_maas REAL DEFAULT 0,
        ise_baslama_tarihi TEXT,
        aktif INTEGER DEFAULT 1,
        telefon TEXT,
        notlar TEXT,
        olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # Devam/Yoklama Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS devam (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        personel_id INTEGER NOT NULL,
        tarih TEXT NOT NULL,
        durum TEXT NOT NULL, -- 'Geldi', 'Gelmedi', 'İzinli', 'Rapor'
        giris_saati TEXT,
        cikis_saati TEXT,
        notlar TEXT,
        olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (personel_id) REFERENCES personel (id),
        UNIQUE(personel_id, tarih)
    )''')

    # Görev Tablosu (İşçilik yerine)
    c.execute('''CREATE TABLE IF NOT EXISTS gorevler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        personel_id INTEGER NOT NULL,
        gorev TEXT NOT NULL,
        tarih TEXT NOT NULL,
        sera_adi TEXT,
        durum TEXT DEFAULT 'Tamamlandı',
        notlar TEXT,
        olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (personel_id) REFERENCES personel (id)
    )''')

    # Hasat Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS hasat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uretim_id INTEGER,
        hasat_tarihi TEXT NOT NULL,
        parsil_alan TEXT NOT NULL,
        hasat_miktari REAL NOT NULL,
        hasat_eden TEXT NOT NULL,
        teslim_edilen TEXT,
        notlar TEXT,
        olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (uretim_id) REFERENCES uretim (id)
    )''')

    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('sera.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize databases on startup
init_db()

# Create PostgreSQL tables and default admin user
with app.app_context():
    db.create_all()
    
    # Create default admin user if not exists
    admin_user = User.query.filter_by(kullanici_adi='admin').first()
    if not admin_user:
        admin_user = User(
            kullanici_adi='admin',
            email='admin@sera.com',
            ad_soyad='Sistem Yöneticisi',
            rol='admin'
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user created: admin / admin123")

# --- YARDIMCI FONKSİYONLAR ---
def get_dashboard_stats():
    conn = get_db_connection()
    
    # Aktif üretim sayısı
    aktif_uretim = conn.execute(
        "SELECT COUNT(*) as count FROM uretim WHERE durum IN ('Ekim Yapıldı', 'Büyüme Döneminde', 'Çiçeklenme')"
    ).fetchone()['count']
    
    # Düşük stok uyarıları
    dusuk_stok = conn.execute(
        "SELECT COUNT(*) as count FROM stok WHERE miktar <= min_stok AND min_stok > 0"
    ).fetchone()['count']
    
    # Bu ayki toplam personel maliyeti (sadece aktif personel)
    bu_ay = datetime.now().strftime('%Y-%m')
    aylik_personel = conn.execute(
        "SELECT COALESCE(SUM(aylik_maas), 0) as total FROM personel WHERE aktif = 1"
    ).fetchone()['total']
    
    # Toplam sera sayısı
    sera_sayisi = conn.execute(
        "SELECT COUNT(DISTINCT sera_adi) as count FROM uretim"
    ).fetchone()['count']
    
    # Bu ayki toplam hasat
    bu_ay_hasat = conn.execute(
        "SELECT COALESCE(SUM(hasat_miktari), 0) as total FROM hasat WHERE hasat_tarihi LIKE ?",
        (f"{bu_ay}%",)
    ).fetchone()['total']
    
    conn.close()
    
    return {
        'aktif_uretim': aktif_uretim,
        'dusuk_stok': dusuk_stok,
        'aylik_personel': aylik_personel,
        'sera_sayisi': sera_sayisi,
        'bu_ay_hasat': bu_ay_hasat
    }

# --- YARDIMCI DECORATORLER ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Bu sayfaya erişmek için admin yetkisine sahip olmalısınız.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROTALAR ---

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        kullanici_adi = request.form['kullanici_adi'].strip()
        password = request.form['password']
        remember = bool(request.form.get('remember'))
        
        # Login attempt kaydı
        attempt = LoginAttempt(
            kullanici_adi=kullanici_adi,
            ip_adresi=request.remote_addr
        )
        
        user = User.query.filter_by(kullanici_adi=kullanici_adi, aktif=True).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            user.son_giris = datetime.utcnow()
            attempt.basarili = True
            db.session.add(attempt)
            db.session.commit()
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            flash(f'Hoş geldiniz, {user.ad_soyad or user.kullanici_adi}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            attempt.basarili = False
            db.session.add(attempt)
            db.session.commit()
            flash('Kullanıcı adı veya şifre hatalı!', 'error')
    
    return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('login'))

@app.route("/admin")
@login_required
@admin_required
def admin_panel():
    # Kullanıcı listesi
    users = User.query.order_by(User.olusturma_tarihi.desc()).all()
    
    # Son giriş denemeleri
    recent_attempts = LoginAttempt.query.order_by(LoginAttempt.deneme_tarihi.desc()).limit(20).all()
    
    # İstatistikler
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(aktif=True).count(),
        'admin_users': User.query.filter_by(rol='admin').count(),
        'failed_attempts_today': LoginAttempt.query.filter(
            LoginAttempt.deneme_tarihi >= datetime.utcnow().date(),
            LoginAttempt.basarili == False
        ).count()
    }
    
    return render_template('admin.html', users=users, recent_attempts=recent_attempts, stats=stats)

@app.route("/admin/user/add", methods=["POST"])
@login_required
@admin_required
def admin_add_user():
    try:
        kullanici_adi = request.form['kullanici_adi'].strip()
        password = request.form['password']
        ad_soyad = request.form['ad_soyad'].strip()
        email = request.form.get('email', '').strip()
        rol = request.form['rol']
        
        # Kullanıcı adı kontrolü
        if User.query.filter_by(kullanici_adi=kullanici_adi).first():
            flash('Bu kullanıcı adı zaten kullanımda!', 'error')
            return redirect(url_for('admin_panel'))
        
        # Email kontrolü
        if email and User.query.filter_by(email=email).first():
            flash('Bu e-posta adresi zaten kullanımda!', 'error')
            return redirect(url_for('admin_panel'))
        
        # Yeni kullanıcı oluştur
        new_user = User(
            kullanici_adi=kullanici_adi,
            ad_soyad=ad_soyad,
            email=email if email else None,
            rol=rol
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'Kullanıcı "{kullanici_adi}" başarıyla oluşturuldu!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Kullanıcı oluşturulurken hata: {str(e)}', 'error')
    
    return redirect(url_for('admin_panel'))

@app.route("/admin/user/toggle/<int:user_id>")
@login_required
@admin_required
def admin_toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Kendi hesabınızı devre dışı bırakamazsınız!', 'error')
    else:
        user.aktif = not user.aktif
        db.session.commit()
        
        status = 'aktif' if user.aktif else 'pasif'
        flash(f'Kullanıcı "{user.kullanici_adi}" {status} duruma getirildi.', 'success')
    
    return redirect(url_for('admin_panel'))

@app.route("/admin/user/reset-password/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def admin_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form['new_password']
    
    user.set_password(new_password)
    db.session.commit()
    
    flash(f'Kullanıcı "{user.kullanici_adi}" şifresi başarıyla güncellendi!', 'success')
    return redirect(url_for('admin_panel'))

@app.route("/dashboard")
@login_required
def dashboard():
    stats = get_dashboard_stats()
    
    conn = get_db_connection()
    
    # Son aktiviteler
    son_uretim = conn.execute(
        "SELECT * FROM uretim ORDER BY olusturma_tarihi DESC LIMIT 5"
    ).fetchall()
    
    son_stok = conn.execute(
        "SELECT * FROM stok ORDER BY tarih DESC LIMIT 5"
    ).fetchall()
    
    son_gorevler = conn.execute(
        "SELECT g.*, p.personel_adi FROM gorevler g LEFT JOIN personel p ON g.personel_id = p.id ORDER BY g.tarih DESC LIMIT 5"
    ).fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         stats=stats,
                         son_uretim=son_uretim,
                         son_stok=son_stok,
                         son_gorevler=son_gorevler)

@app.route("/uretim", methods=["GET", "POST"])
@login_required
def uretim():
    conn = get_db_connection()
    
    if request.method == "POST":
        try:
            sera_adi = request.form['sera_adi'].strip()
            urun_adi = request.form['urun_adi'].strip()
            ekim_tarihi = request.form['ekim_tarihi']
            hasat_tarihi = request.form.get('hasat_tarihi') or None
            alan = float(request.form.get('alan', 0) or 0)
            beklenen_verim = float(request.form.get('beklenen_verim', 0) or 0)
            notlar = request.form.get('notlar', '').strip()
            
            if not sera_adi or not urun_adi or not ekim_tarihi:
                flash('Sera adı, ürün adı ve ekim tarihi zorunludur!', 'error')
            else:
                conn.execute("""
                    INSERT INTO uretim (sera_adi, urun_adi, ekim_tarihi, hasat_tarihi, 
                                      alan, beklenen_verim, notlar, durum) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (sera_adi, urun_adi, ekim_tarihi, hasat_tarihi, alan, beklenen_verim, notlar, "Ekim Yapıldı"))
                conn.commit()
                flash('Üretim kaydı başarıyla eklendi!', 'success')
                return redirect(url_for('uretim'))
        except ValueError:
            flash('Lütfen sayısal değerleri doğru formatta girin!', 'error')
        except Exception as e:
            flash(f'Bir hata oluştu: {str(e)}', 'error')
    
    uretimler = conn.execute("SELECT * FROM uretim ORDER BY ekim_tarihi DESC").fetchall()
    conn.close()
    
    return render_template("uretim.html", uretimler=uretimler)

@app.route("/uretim/guncelle/<int:id>", methods=["POST"])
@login_required
def uretim_guncelle(id):
    conn = get_db_connection()
    
    try:
        durum = request.form.get('durum')
        gercek_verim = request.form.get('gercek_verim')
        notlar = request.form.get('notlar', '')
        
        if gercek_verim:
            gercek_verim = float(gercek_verim)
        else:
            gercek_verim = None
            
        conn.execute("""
            UPDATE uretim 
            SET durum = ?, gercek_verim = ?, notlar = ?
            WHERE id = ?
        """, (durum, gercek_verim, notlar, id))
        conn.commit()
        flash('Üretim kaydı güncellendi!', 'success')
    except Exception as e:
        flash(f'Güncelleme sırasında hata: {str(e)}', 'error')
    
    conn.close()
    return redirect(url_for('uretim'))

@app.route("/stok", methods=["GET", "POST"])
@login_required
def stok():
    conn = get_db_connection()
    
    if request.method == "POST":
        try:
            malzeme_adi = request.form['malzeme_adi'].strip()
            kategori = request.form.get('kategori', '').strip()
            miktar = float(request.form['miktar'])
            birim = request.form.get('birim', '').strip()
            depo = request.form.get('depo', '').strip()
            min_stok = float(request.form.get('min_stok', 0) or 0)
            maliyet = float(request.form.get('maliyet', 0) or 0)
            notlar = request.form.get('notlar', '').strip()
            islem_turu = request.form.get('islem_turu', 'ekle')
            
            if not malzeme_adi:
                flash('Malzeme adı zorunludur!', 'error')
            else:
                # Mevcut stok kontrolü
                mevcut = conn.execute(
                    "SELECT * FROM stok WHERE malzeme_adi = ? AND depo = ?", 
                    (malzeme_adi, depo)
                ).fetchone()
                
                if mevcut and islem_turu == 'cikar':
                    # Stok çıkarma
                    yeni_miktar = mevcut['miktar'] - miktar
                    if yeni_miktar < 0:
                        flash('Yetersiz stok! Mevcut miktar: {}'.format(mevcut['miktar']), 'error')
                    else:
                        conn.execute(
                            "UPDATE stok SET miktar = ? WHERE id = ?",
                            (yeni_miktar, mevcut['id'])
                        )
                        conn.commit()
                        flash('Stok çıkarıldı!', 'success')
                elif mevcut and islem_turu == 'ekle':
                    # Mevcut stoka ekleme
                    yeni_miktar = mevcut['miktar'] + miktar
                    conn.execute(
                        "UPDATE stok SET miktar = ?, maliyet = ?, min_stok = ?, notlar = ? WHERE id = ?",
                        (yeni_miktar, maliyet, min_stok, notlar, mevcut['id'])
                    )
                    conn.commit()
                    flash('Stok güncellendi!', 'success')
                else:
                    # Yeni stok kaydı
                    conn.execute("""
                        INSERT INTO stok (malzeme_adi, kategori, miktar, birim, tarih, 
                                        depo, min_stok, maliyet, notlar) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (malzeme_adi, kategori, miktar, birim, datetime.now().strftime('%Y-%m-%d'),
                          depo, min_stok, maliyet, notlar))
                    conn.commit()
                    flash('Yeni stok kaydı eklendi!', 'success')
                
                return redirect(url_for('stok'))
                
        except ValueError:
            flash('Lütfen sayısal değerleri doğru formatta girin!', 'error')
        except Exception as e:
            flash(f'Bir hata oluştu: {str(e)}', 'error')
    
    stoklar = conn.execute("SELECT * FROM stok ORDER BY malzeme_adi").fetchall()
    
    # Düşük stok uyarıları
    dusuk_stoklar = conn.execute(
        "SELECT * FROM stok WHERE miktar <= min_stok AND min_stok > 0"
    ).fetchall()
    
    conn.close()
    
    return render_template("stok.html", stoklar=stoklar, dusuk_stoklar=dusuk_stoklar)

@app.route("/personel", methods=["GET", "POST"])
@login_required
def personel():
    conn = get_db_connection()
    
    if request.method == "POST":
        action = request.form.get('action', '')
        
        if action == 'personel_ekle':
            try:
                personel_adi = request.form['personel_adi'].strip()
                pozisyon = request.form.get('pozisyon', '').strip()
                aylik_maas = float(request.form.get('aylik_maas', 0) or 0)
                ise_baslama_tarihi = request.form.get('ise_baslama_tarihi')
                telefon = request.form.get('telefon', '').strip()
                notlar = request.form.get('notlar', '').strip()
                
                if not personel_adi:
                    flash('Personel adı zorunludur!', 'error')
                else:
                    conn.execute("""
                        INSERT INTO personel (personel_adi, pozisyon, aylik_maas, ise_baslama_tarihi, telefon, notlar) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (personel_adi, pozisyon, aylik_maas, ise_baslama_tarihi, telefon, notlar))
                    conn.commit()
                    flash('Personel kaydı başarıyla eklendi!', 'success')
                    return redirect(url_for('personel'))
                    
            except ValueError:
                flash('Lütfen sayısal değerleri doğru formatta girin!', 'error')
            except Exception as e:
                flash(f'Bir hata oluştu: {str(e)}', 'error')
        
        elif action == 'gorev_ekle':
            try:
                personel_id = request.form['personel_id']
                gorev = request.form['gorev'].strip()
                tarih = request.form['tarih']
                sera_adi = request.form.get('sera_adi', '').strip()
                notlar = request.form.get('notlar', '').strip()
                
                if not personel_id or not gorev or not tarih:
                    flash('Personel, görev ve tarih zorunludur!', 'error')
                else:
                    conn.execute("""
                        INSERT INTO gorevler (personel_id, gorev, tarih, sera_adi, notlar) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (personel_id, gorev, tarih, sera_adi, notlar))
                    conn.commit()
                    flash('Görev kaydı başarıyla eklendi!', 'success')
                    return redirect(url_for('personel'))
                    
            except Exception as e:
                flash(f'Bir hata oluştu: {str(e)}', 'error')
    
    # Personel listesi
    personeller = conn.execute("SELECT * FROM personel ORDER BY aktif DESC, personel_adi").fetchall()
    
    # Görev kayıtları
    gorevler = conn.execute("""
        SELECT g.*, p.personel_adi 
        FROM gorevler g 
        LEFT JOIN personel p ON g.personel_id = p.id 
        ORDER BY g.tarih DESC
    """).fetchall()
    
    # Bu ayki toplam maliyet
    bu_ay_toplam_maas = conn.execute(
        "SELECT COALESCE(SUM(aylik_maas), 0) as total FROM personel WHERE aktif = 1"
    ).fetchone()['total']
    
    # Personel istatistikleri
    bu_ay = datetime.now().strftime('%Y-%m')
    personel_istatistik = conn.execute("""
        SELECT p.personel_adi, p.aylik_maas,
               COUNT(g.id) as gorev_sayisi
        FROM personel p 
        LEFT JOIN gorevler g ON p.id = g.personel_id AND g.tarih LIKE ?
        WHERE p.aktif = 1
        GROUP BY p.id, p.personel_adi, p.aylik_maas
        ORDER BY p.personel_adi
    """, (f"{bu_ay}%",)).fetchall()
    
    conn.close()
    
    return render_template("personel.html", 
                         personeller=personeller,
                         gorevler=gorevler,
                         bu_ay_toplam_maas=bu_ay_toplam_maas,
                         personel_istatistik=personel_istatistik)

@app.route("/devam", methods=["GET", "POST"])
@login_required
def devam():
    conn = get_db_connection()
    
    if request.method == "POST":
        try:
            tarih = request.form['tarih']
            
            # Tüm aktif personel için devam durumunu kaydet
            personeller = conn.execute("SELECT * FROM personel WHERE aktif = 1").fetchall()
            
            for personel in personeller:
                durum = request.form.get(f'durum_{personel["id"]}', 'Gelmedi')
                giris_saati = request.form.get(f'giris_{personel["id"]}', '').strip()
                cikis_saati = request.form.get(f'cikis_{personel["id"]}', '').strip()
                notlar = request.form.get(f'notlar_{personel["id"]}', '').strip()
                
                # Mevcut kaydı kontrol et
                mevcut = conn.execute(
                    "SELECT * FROM devam WHERE personel_id = ? AND tarih = ?",
                    (personel['id'], tarih)
                ).fetchone()
                
                if mevcut:
                    # Güncelle
                    conn.execute("""
                        UPDATE devam 
                        SET durum = ?, giris_saati = ?, cikis_saati = ?, notlar = ?
                        WHERE personel_id = ? AND tarih = ?
                    """, (durum, giris_saati, cikis_saati, notlar, personel['id'], tarih))
                else:
                    # Yeni kayıt
                    conn.execute("""
                        INSERT INTO devam (personel_id, tarih, durum, giris_saati, cikis_saati, notlar) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (personel['id'], tarih, durum, giris_saati, cikis_saati, notlar))
            
            conn.commit()
            flash('Devam durumu başarıyla kaydedildi!', 'success')
            return redirect(url_for('devam'))
            
        except Exception as e:
            flash(f'Bir hata oluştu: {str(e)}', 'error')
    
    # Bugünün tarihi
    bugun = datetime.now().strftime('%Y-%m-%d')
    
    # Aktif personel listesi
    personeller = conn.execute("SELECT * FROM personel WHERE aktif = 1 ORDER BY personel_adi").fetchall()
    
    # Bugünkü devam durumu
    bugun_devam = conn.execute("""
        SELECT d.*, p.personel_adi 
        FROM devam d 
        LEFT JOIN personel p ON d.personel_id = p.id 
        WHERE d.tarih = ?
    """, (bugun,)).fetchall()
    
    # Son 7 günün devam istatistikleri
    devam_istatistik = conn.execute("""
        SELECT d.tarih,
               COUNT(*) as toplam_personel,
               SUM(CASE WHEN d.durum = 'Geldi' THEN 1 ELSE 0 END) as gelenler,
               SUM(CASE WHEN d.durum = 'Gelmedi' THEN 1 ELSE 0 END) as gelmeyenler,
               SUM(CASE WHEN d.durum = 'İzinli' THEN 1 ELSE 0 END) as izinliler
        FROM devam d 
        WHERE d.tarih >= date('now', '-7 days')
        GROUP BY d.tarih
        ORDER BY d.tarih DESC
    """).fetchall()
    
    conn.close()
    
    return render_template("devam.html", 
                         personeller=personeller,
                         bugun_devam=bugun_devam,
                         devam_istatistik=devam_istatistik,
                         bugun=bugun)

@app.route("/devam/excel-export")
@login_required
def devam_excel_export():
    conn = get_db_connection()
    
    # Tarih aralığı parametreleri
    baslangic_tarihi = request.args.get('baslangic', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    bitis_tarihi = request.args.get('bitis', datetime.now().strftime('%Y-%m-%d'))
    
    # Devam kayıtlarını al
    devam_kayitlari = conn.execute("""
        SELECT d.tarih, p.personel_adi, p.pozisyon, d.durum, d.giris_saati, d.cikis_saati, d.notlar
        FROM devam d
        LEFT JOIN personel p ON d.personel_id = p.id
        WHERE d.tarih BETWEEN ? AND ?
        ORDER BY d.tarih DESC, p.personel_adi
    """, (baslangic_tarihi, bitis_tarihi)).fetchall()
    
    # Personel bazında özet istatistikler
    personel_ozet = conn.execute("""
        SELECT p.personel_adi, p.pozisyon,
               COUNT(*) as toplam_gun,
               SUM(CASE WHEN d.durum = 'Geldi' THEN 1 ELSE 0 END) as gelme_sayisi,
               SUM(CASE WHEN d.durum = 'Gelmedi' THEN 1 ELSE 0 END) as gelmeme_sayisi,
               SUM(CASE WHEN d.durum = 'İzinli' THEN 1 ELSE 0 END) as izin_sayisi,
               SUM(CASE WHEN d.durum = 'Rapor' THEN 1 ELSE 0 END) as rapor_sayisi
        FROM devam d
        LEFT JOIN personel p ON d.personel_id = p.id
        WHERE d.tarih BETWEEN ? AND ?
        GROUP BY p.personel_adi, p.pozisyon
        ORDER BY p.personel_adi
    """, (baslangic_tarihi, bitis_tarihi)).fetchall()
    
    conn.close()
    
    # Excel dosyası oluştur
    wb = Workbook()
    
    # İlk sayfa: Günlük devam kayıtları
    ws1 = wb.active
    ws1.title = "Günlük Devam Kayıtları"
    
    # Başlık stilleri
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    center_alignment = Alignment(horizontal="center", vertical="center")
    
    # Başlıklar
    headers1 = ["Tarih", "Personel Adı", "Pozisyon", "Durum", "Giriş Saati", "Çıkış Saati", "Notlar"]
    for col, header in enumerate(headers1, 1):
        cell = ws1.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_alignment
    
    # Veri satırları
    for row, devam in enumerate(devam_kayitlari, 2):
        ws1.cell(row=row, column=1, value=devam['tarih'])
        ws1.cell(row=row, column=2, value=devam['personel_adi'])
        ws1.cell(row=row, column=3, value=devam['pozisyon'] or '-')
        ws1.cell(row=row, column=4, value=devam['durum'])
        ws1.cell(row=row, column=5, value=devam['giris_saati'] or '-')
        ws1.cell(row=row, column=6, value=devam['cikis_saati'] or '-')
        ws1.cell(row=row, column=7, value=devam['notlar'] or '-')
    
    # Sütun genişliklerini ayarla
    column_widths1 = [12, 20, 15, 12, 12, 12, 30]
    for col, width in enumerate(column_widths1, 1):
        ws1.column_dimensions[chr(64 + col)].width = width
    
    # İkinci sayfa: Personel özet istatistikleri
    ws2 = wb.create_sheet(title="Personel Özet İstatistikleri")
    
    # Başlıklar
    headers2 = ["Personel Adı", "Pozisyon", "Toplam Gün", "Gelme", "Gelmeme", "İzin", "Rapor", "Devam Oranı (%)"]
    for col, header in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_alignment
    
    # Veri satırları
    for row, ozet in enumerate(personel_ozet, 2):
        devam_orani = (ozet['gelme_sayisi'] / ozet['toplam_gun'] * 100) if ozet['toplam_gun'] > 0 else 0
        
        ws2.cell(row=row, column=1, value=ozet['personel_adi'])
        ws2.cell(row=row, column=2, value=ozet['pozisyon'] or '-')
        ws2.cell(row=row, column=3, value=ozet['toplam_gun'])
        ws2.cell(row=row, column=4, value=ozet['gelme_sayisi'])
        ws2.cell(row=row, column=5, value=ozet['gelmeme_sayisi'])
        ws2.cell(row=row, column=6, value=ozet['izin_sayisi'])
        ws2.cell(row=row, column=7, value=ozet['rapor_sayisi'])
        ws2.cell(row=row, column=8, value=f"{devam_orani:.1f}%")
    
    # Sütun genişliklerini ayarla
    column_widths2 = [20, 15, 12, 8, 10, 8, 8, 15]
    for col, width in enumerate(column_widths2, 1):
        ws2.column_dimensions[chr(64 + col)].width = width
    
    # Excel dosyasını belleğe kaydet
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    # Dosya adı
    filename = f"devam_raporu_{baslangic_tarihi}_{bitis_tarihi}.xlsx"
    
    # Response oluştur
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return response

@app.route("/hasat", methods=["GET", "POST"])
@login_required
def hasat():
    conn = get_db_connection()
    
    if request.method == "POST":
        try:
            uretim_id = request.form.get('uretim_id')
            hasat_tarihi = request.form['hasat_tarihi']
            parsil_alan = request.form['parsil_alan'].strip()
            hasat_miktari = float(request.form['hasat_miktari'])
            hasat_eden = request.form['hasat_eden'].strip()
            teslim_edilen = request.form.get('teslim_edilen', '').strip()
            notlar = request.form.get('notlar', '').strip()
            
            if not parsil_alan or not hasat_eden or not hasat_tarihi:
                flash('Hasat tarihi, parsel/alan ve hasat eden kişi zorunludur!', 'error')
            else:
                conn.execute("""
                    INSERT INTO hasat (uretim_id, hasat_tarihi, parsil_alan, hasat_miktari, 
                                     hasat_eden, teslim_edilen, notlar) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (uretim_id, hasat_tarihi, parsil_alan, hasat_miktari, 
                      hasat_eden, teslim_edilen, notlar))
                conn.commit()
                flash('Hasat kaydı başarıyla eklendi!', 'success')
                return redirect(url_for('hasat'))
                
        except ValueError:
            flash('Lütfen sayısal değerleri doğru formatta girin!', 'error')
        except Exception as e:
            flash(f'Bir hata oluştu: {str(e)}', 'error')
    
    # Hasat kayıtları ve ilgili üretim bilgileri
    hasatlar = conn.execute("""
        SELECT h.*, u.sera_adi, u.urun_adi, u.ekim_tarihi
        FROM hasat h
        LEFT JOIN uretim u ON h.uretim_id = u.id
        ORDER BY h.hasat_tarihi DESC
    """).fetchall()
    
    # Aktif üretimler (hasat için)
    aktif_uretimler = conn.execute(
        "SELECT * FROM uretim WHERE durum != 'Hasat Edildi' ORDER BY sera_adi, urun_adi"
    ).fetchall()
    
    # Bu ayki hasat istatistikleri
    bu_ay = datetime.now().strftime('%Y-%m')
    bu_ay_toplam = conn.execute(
        "SELECT COALESCE(SUM(hasat_miktari), 0) as total FROM hasat WHERE hasat_tarihi LIKE ?",
        (f"{bu_ay}%",)
    ).fetchone()['total']
    
    # En çok hasat yapan kişiler
    hasat_eden_istatistik = conn.execute("""
        SELECT hasat_eden,
               COUNT(*) as hasat_sayisi,
               SUM(hasat_miktari) as toplam_miktar
        FROM hasat 
        WHERE hasat_tarihi LIKE ?
        GROUP BY hasat_eden
        ORDER BY toplam_miktar DESC
        LIMIT 5
    """, (f"{bu_ay}%",)).fetchall()
    
    conn.close()
    
    return render_template("hasat.html", 
                         hasatlar=hasatlar,
                         aktif_uretimler=aktif_uretimler,
                         bu_ay_toplam=bu_ay_toplam,
                         hasat_eden_istatistik=hasat_eden_istatistik)

@app.route("/rapor")
@login_required
def rapor():
    conn = get_db_connection()
    
    # Aylık üretim raporu
    uretim_raporu = conn.execute("""
        SELECT strftime('%Y-%m', ekim_tarihi) as ay,
               COUNT(*) as toplam_ekim,
               SUM(CASE WHEN durum = 'Hasat Edildi' THEN 1 ELSE 0 END) as hasat_edilen,
               SUM(CASE WHEN gercek_verim IS NOT NULL THEN gercek_verim ELSE 0 END) as toplam_verim
        FROM uretim 
        WHERE ekim_tarihi >= date('now', '-12 months')
        GROUP BY strftime('%Y-%m', ekim_tarihi)
        ORDER BY ay DESC
    """).fetchall()
    
    # Stok durumu
    stok_raporu = conn.execute("""
        SELECT kategori, 
               COUNT(*) as cesit_sayisi,
               SUM(miktar * maliyet) as toplam_deger
        FROM stok 
        WHERE kategori IS NOT NULL AND kategori != ''
        GROUP BY kategori
        ORDER BY toplam_deger DESC
    """).fetchall()
    
    # Personel maliyeti trendi
    personel_raporu = conn.execute("""
        SELECT strftime('%Y-%m', 'now', '-' || (t.value-1) || ' months') as ay,
               (SELECT COUNT(*) FROM personel WHERE aktif = 1) as personel_sayisi,
               (SELECT SUM(aylik_maas) FROM personel WHERE aktif = 1) as toplam_maliyet
        FROM (SELECT 1 as value UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 
              UNION SELECT 7 UNION SELECT 8 UNION SELECT 9 UNION SELECT 10 UNION SELECT 11 UNION SELECT 12) t
        ORDER BY ay DESC
    """).fetchall()
    
    conn.close()
    
    return render_template('rapor.html',
                         uretim_raporu=uretim_raporu,
                         stok_raporu=stok_raporu,
                         personel_raporu=personel_raporu)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
