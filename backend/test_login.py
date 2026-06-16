import logging
from database import SessionLocal
import models
from auth_utils import verify_password, get_password_hash
db = SessionLocal()
try:
    user = db.query(models.User).filter(models.User.username == "alex_dance").first()
    print("User found:", user.username)
    print("Hashed password type:", type(user.hashed_password))
    print("Hashed password val:", user.hashed_password)
    res = verify_password("password123", user.hashed_password)
    print("Verify result:", res)
except Exception as e:
    logging.exception("Error during login:")
