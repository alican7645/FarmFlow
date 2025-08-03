from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    ad_soyad = db.Column(db.String(100), nullable=True)
    rol = db.Column(db.String(50), default='kullanici')  # 'admin' veya 'kullanici'
    aktif = db.Column(db.Boolean, default=True)
    son_giris = db.Column(db.DateTime, nullable=True)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Şifreyi hash'leyerek kaydet"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Şifreyi kontrol et"""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Kullanıcının admin olup olmadığını kontrol et"""
        return self.rol == 'admin'
    
    def __repr__(self):
        return f'<User {self.kullanici_adi}>'

class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(80), nullable=False)
    ip_adresi = db.Column(db.String(45), nullable=True)
    basarili = db.Column(db.Boolean, default=False)
    deneme_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<LoginAttempt {self.kullanici_adi} - {self.basarili}>'