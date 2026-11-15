import hashlib, hmac, secrets, time
import jwt
from src.config.settings import JWT_SECRET
def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 120000).hex()
    return salt + ':' + digest
def verify_password(password, stored):
    salt, digest = stored.split(':')
    actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 120000).hex()
    return hmac.compare_digest(actual, digest)
def token_for(user):
    return jwt.encode({'sub': str(user.id), 'exp': int(time.time()) + 28800}, JWT_SECRET, algorithm='HS256')
def decode_token(token):
    return int(jwt.decode(token, JWT_SECRET, algorithms=['HS256'])['sub'])
