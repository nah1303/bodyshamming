from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
import hashlib

app = Flask(__name__)
app.secret_key = 'tram_tru_an_secret_key_2026'

# Đường dẫn tới cơ sở dữ liệu SQLite trong thư mục BODY_SAFE_AI/data/
DB_PATH = os.path.join('BODY_SAFE_AI', 'data', 'database.db')

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Khởi tạo cơ sở dữ liệu và các bảng cần thiết
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Bảng lưu thông tin tài khoản người dùng
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Bảng lưu bài viết trên diễn đàn chữa lành
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS forum_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL,
            time_str TEXT NOT NULL,
            text_content TEXT NOT NULL,
            img_url TEXT,
            hugs INTEGER DEFAULT 0,
            hearts INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. Bảng lưu bình luận cho từng bài viết
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS post_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            author TEXT NOT NULL,
            comment_text TEXT NOT NULL,
            FOREIGN KEY (post_id) REFERENCES forum_posts (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# Chạy khởi tạo database khi khởi động ứng dụng
init_db()

@app.route('/')
def index():
    # Trỏ trực tiếp đến file index1.html của bạn (đặt trong thư mục templates nếu dùng render_template, hoặc cùng cấp)
    return render_template('index1.html')

# --- API ĐĂNG NHẬP / ĐĂNG KÝ TÀI KHOẢN ---
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    if not email or not password:
        return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ thông tin!"}), 400
        
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ? AND password_hash = ?', (email, password_hash))
    user = cursor.fetchone()
    
    if not user:
        # Tự động tạo tài khoản mới nếu chưa tồn tại để tối ưu trải nghiệm nhanh
        try:
            username = email.split('@')[0]
            cursor.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)', 
                           (username, email, password_hash))
            conn.commit()
            cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
            user = cursor.fetchone()
        except Exception as e:
            conn.close()
            return jsonify({"status": "error", "message": "Lỗi xác thực tài khoản!"}), 400
            
    conn.close()
    
    session['user_id'] = user['id']
    session['username'] = user['username']
    
    return jsonify({
        "status": "success", 
        "message": "Đăng nhập thành công!", 
        "username": user['username']
    })

# --- API LẤY DANH SÁCH BÀI VIẾT DIỄN ĐÀN ---
@app.route('/api/posts', methods=['GET'])
def get_posts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM forum_posts ORDER BY id DESC')
    posts = cursor.fetchall()
    
    result = []
    for p in posts:
        post_dict = dict(p)
        cursor.execute('SELECT author, comment_text as text FROM post_comments WHERE post_id = ?', (post_dict['id'],))
        comments = [dict(c) for c in cursor.fetchall()]
        post_dict['comments'] = comments
        result.append(post_dict)
        
    conn.close()
    return jsonify(result)

# --- API ĐĂNG BÀI VIẾT MỚI ---
@app.route('/api/posts', methods=['POST'])
def create_post():
    data = request.json
    author = data.get('author', 'Thành viên ẩn danh')
    text_content = data.get('text', '').strip()
    img_url = data.get('img', '')
    
    if not text_content:
        return jsonify({"status": "error", "message": "Nội dung bài viết không được trống!"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO forum_posts (author, time_str, text_content, img_url, hugs, hearts)
        VALUES (?, ?, ?, ?, 0, 0)
    ''', (author, 'Vừa xong', text_content, img_url))
    
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": "Đăng bài thành công!"})

# --- API TƯƠNG TÁC (THẢ TIM / ÔM CÁI NHẸ) ---
@app.route('/api/posts/<int:post_id>/react', methods=['POST'])
def react_post(post_id):
    data = request.json
    reaction_type = data.get('type') # 'hug' hoặc 'heart'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if reaction_type == 'hug':
        cursor.execute('UPDATE forum_posts SET hugs = hugs + 1 WHERE id = ?', (post_id,))
    elif reaction_type == 'heart':
        cursor.execute('UPDATE forum_posts SET hearts = hearts + 1 WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success"})

# --- API THÊM BÌNH LUẬN ---
@app.route('/api/posts/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    data = request.json
    author = data.get('author', 'Thành viên')
    comment_text = data.get('text', '').strip()
    
    if not comment_text:
        return jsonify({"status": "error", "message": "Bình luận trống!"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO post_comments (post_id, author, comment_text) VALUES (?, ?, ?)',
                   (post_id, author, comment_text))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": "Đã thêm bình luận!"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
