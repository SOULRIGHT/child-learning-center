"""Flask 확장 객체. app.py와 feature 모듈이 순환 import 없이 공유한다."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
