import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "tiktok.db")

def seed():
    if not os.path.exists(db_path):
        print("Database file not found yet. Running startup first or check path.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Xóa tất cả video cũ để tránh lỗi link Mixkit bị Access Denied
        cursor.execute("DELETE FROM comments")
        cursor.execute("DELETE FROM likes")
        cursor.execute("DELETE FROM videos")
        conn.commit()
        print("Cleared old mock videos.")

        # Lấy danh sách users
        cursor.execute("SELECT id FROM users LIMIT 2")
        users = cursor.fetchall()
        
        if not users:
            # Hash passwords before seeding
            from auth_utils import get_password_hash
            hashed_pwd = get_password_hash("hashedpassword123")
            
            # Nếu chưa có user nào, tạo mới
            cursor.execute("INSERT INTO users (username, hashed_password, display_name, avatar_url, bio) VALUES (?, ?, ?, ?, ?)",
                           ("alex_dance", hashed_pwd, "Alex Dance", "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150", "Dancing is my life! 💃"))
            cursor.execute("INSERT INTO users (username, hashed_password, display_name, avatar_url, bio) VALUES (?, ?, ?, ?, ?)",
                           ("neon_vibes", hashed_pwd, "Neon Vibes", "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150", "Capturing lights 🌃"))
            conn.commit()
            cursor.execute("SELECT id FROM users LIMIT 2")
            users = cursor.fetchall()

        user1_id = users[0][0]
        user2_id = users[1][0] if len(users) > 1 else user1_id

        # Thêm 3 video local mới
        videos = [
            ("Big Buck Bunny Short #bunny #classic", "http://localhost:8000/static/uploads/short1.mp4", "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=400", user1_id),
            ("Bear Video Short #nature #animal", "http://localhost:8000/static/uploads/short2.mp4", "https://images.unsplash.com/photo-1500485035595-cbe6f645feb1?w=400", user2_id),
            ("People Detection Short #ai #technology", "http://localhost:8000/static/uploads/short3.mp4", "https://images.unsplash.com/photo-1518770660439-4636190af475?w=400", user1_id)
        ]

        for title, url, cover, uid in videos:
            cursor.execute("INSERT INTO videos (title, video_url, cover_url, user_id) VALUES (?, ?, ?, ?)",
                           (title, url, cover, uid))
        
        conn.commit()
        print("Successfully seeded local videos to database!")
        
    except Exception as e:
        print(f"Error seeding DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed()
