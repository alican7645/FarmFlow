import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, date

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "sera-yonetim-secret-key")

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

    # İşçilik Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS iscilik (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        isci_adi TEXT NOT NULL,
        gorev TEXT NOT NULL,
        tarih TEXT NOT NULL,
        baslangic_saati TEXT,
        bitis_saati TEXT,
        sure REAL,
        saatlik_ucret REAL DEFAULT 0,
        toplam_ucret REAL DEFAULT 0,
        sera_adi TEXT,
        durum TEXT DEFAULT 'Tamamlandı',
        notlar TEXT
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

# Initialize database on startup
init_db()

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
    
    # Bu ayki toplam işçilik maliyeti
    bu_ay = datetime.now().strftime('%Y-%m')
    aylik_iscilik = conn.execute(
        "SELECT COALESCE(SUM(toplam_ucret), 0) as total FROM iscilik WHERE tarih LIKE ?",
        (f"{bu_ay}%",)
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
        'aylik_iscilik': aylik_iscilik,
        'sera_sayisi': sera_sayisi,
        'bu_ay_hasat': bu_ay_hasat
    }

# --- ROTALAR ---

@app.route("/")
def index():
    return redirect(url_for('dashboard'))

@app.route("/dashboard")
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
    
    son_iscilik = conn.execute(
        "SELECT * FROM iscilik ORDER BY tarih DESC LIMIT 5"
    ).fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         stats=stats,
                         son_uretim=son_uretim,
                         son_stok=son_stok,
                         son_iscilik=son_iscilik)

@app.route("/uretim", methods=["GET", "POST"])
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

@app.route("/iscilik", methods=["GET", "POST"])
def iscilik():
    conn = get_db_connection()
    
    if request.method == "POST":
        try:
            isci_adi = request.form['isci_adi'].strip()
            gorev = request.form['gorev'].strip()
            tarih = request.form['tarih']
            baslangic_saati = request.form.get('baslangic_saati', '').strip()
            bitis_saati = request.form.get('bitis_saati', '').strip()
            saatlik_ucret = float(request.form.get('saatlik_ucret', 0) or 0)
            sera_adi = request.form.get('sera_adi', '').strip()
            notlar = request.form.get('notlar', '').strip()
            
            # Çalışma süresini hesapla
            sure = 0
            toplam_ucret = 0
            
            if baslangic_saati and bitis_saati:
                try:
                    baslangic = datetime.strptime(baslangic_saati, '%H:%M')
                    bitis = datetime.strptime(bitis_saati, '%H:%M')
                    sure = (bitis - baslangic).total_seconds() / 3600
                    if sure < 0:
                        sure += 24  # Gece vardiyası için
                except ValueError:
                    flash('Saat formatı hatalı! (HH:MM)', 'error')
                    sure = 0
            else:
                sure = float(request.form.get('sure', 0) or 0)
            
            toplam_ucret = sure * saatlik_ucret
            
            if not isci_adi or not gorev or not tarih:
                flash('İşçi adı, görev ve tarih zorunludur!', 'error')
            else:
                conn.execute("""
                    INSERT INTO iscilik (isci_adi, gorev, tarih, baslangic_saati, bitis_saati,
                                       sure, saatlik_ucret, toplam_ucret, sera_adi, notlar) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (isci_adi, gorev, tarih, baslangic_saati, bitis_saati, sure, 
                      saatlik_ucret, toplam_ucret, sera_adi, notlar))
                conn.commit()
                flash('İşçilik kaydı başarıyla eklendi!', 'success')
                return redirect(url_for('iscilik'))
                
        except ValueError:
            flash('Lütfen sayısal değerleri doğru formatta girin!', 'error')
        except Exception as e:
            flash(f'Bir hata oluştu: {str(e)}', 'error')
    
    # İşçilik kayıtları ve istatistikler
    iscilikler = conn.execute("SELECT * FROM iscilik ORDER BY tarih DESC, isci_adi").fetchall()
    
    # Bu ayki toplam maliyet
    bu_ay = datetime.now().strftime('%Y-%m')
    bu_ay_toplam = conn.execute(
        "SELECT COALESCE(SUM(toplam_ucret), 0) as total FROM iscilik WHERE tarih LIKE ?",
        (f"{bu_ay}%",)
    ).fetchone()['total']
    
    # İşçi bazında özetler
    isci_ozetleri = conn.execute("""
        SELECT isci_adi, 
               COUNT(*) as gorev_sayisi,
               SUM(sure) as toplam_sure,
               SUM(toplam_ucret) as toplam_kazanc
        FROM iscilik 
        WHERE tarih LIKE ?
        GROUP BY isci_adi
        ORDER BY toplam_kazanc DESC
    """, (f"{bu_ay}%",)).fetchall()
    
    conn.close()
    
    return render_template("iscilik.html", 
                         iscilikler=iscilikler,
                         bu_ay_toplam=bu_ay_toplam,
                         isci_ozetleri=isci_ozetleri)

@app.route("/hasat", methods=["GET", "POST"])
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
    
    # İşçilik maliyeti trendi
    iscilik_raporu = conn.execute("""
        SELECT strftime('%Y-%m', tarih) as ay,
               COUNT(DISTINCT isci_adi) as isci_sayisi,
               SUM(sure) as toplam_sure,
               SUM(toplam_ucret) as toplam_maliyet
        FROM iscilik 
        WHERE tarih >= date('now', '-12 months')
        GROUP BY strftime('%Y-%m', tarih)
        ORDER BY ay DESC
    """).fetchall()
    
    conn.close()
    
    return render_template('rapor.html',
                         uretim_raporu=uretim_raporu,
                         stok_raporu=stok_raporu,
                         iscilik_raporu=iscilik_raporu)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
