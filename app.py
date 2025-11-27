import os
import base64
from datetime import datetime
from flask import Flask, request, Response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- DB 설정 ---
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- 데이터 모델 ---
class MemoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), index=True)
    char_id = db.Column(db.String(100), index=True)
    content = db.Column(db.Text)
    password = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

PIXEL_GIF_DATA = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

# --- 1. 저장 (이미지 태그 해킹 - rplay에서도 작동함) ---
@app.route('/save')
def save_log():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')
    d = request.args.get('d')

    if u and c and pw and d:
        # 무조건 추가 (Insert)
        new_log = MemoryLog(user_id=u, char_id=c, password=pw, content=d)
        db.session.add(new_log)
        db.session.commit()
    
    return Response(PIXEL_GIF_DATA, mimetype='image/gif')

# --- 2. 삭제 (관리자 페이지 내부 동작) ---
@app.route('/delete_action')
def delete_action():
    log_id = request.args.get('id')
    pw = request.args.get('pw')
    u = request.args.get('u')
    c = request.args.get('c')

    if log_id and pw:
        log = MemoryLog.query.get(log_id)
        if log and log.password == pw:
            db.session.delete(log)
            db.session.commit()
    
    # 삭제 후 다시 관리 페이지로 리다이렉트
    return f"<script>location.href='/manager?u={u}&c={c}&pw={pw}';</script>"

# --- 3. 관리자 화면 (Iframe용 HTML 반환) ---
@app.route('/manager')
def manager_view():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')

    # 최신순 50개 가져오기
    logs = MemoryLog.query.filter_by(user_id=u, char_id=c, password=pw)\
        .order_by(MemoryLog.updated_at.desc()).limit(50).all()

    # HTML 생성
    log_items = ""
    for log in logs:
        # 안전한 텍스트 처리
        safe_content = log.content.replace('"', '&quot;')
        date_str = log.updated_at.strftime("%Y-%m-%d %H:%M")
        
        log_items += f"""
        <div class="log-item">
            <div class="meta">{date_str}</div>
            <div class="content">{log.content}</div>
            <div class="actions">
                <button class="btn-copy" onclick="copyToClip('{safe_content}')">복사</button>
                <a href="/delete_action?id={log.id}&pw={pw}&u={u}&c={c}" class="btn-del" onclick="return confirm('삭제합니까?')">삭제</a>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ background: #111; color: #eee; font-family: sans-serif; margin: 0; padding: 10px; font-size: 12px; }}
            .log-item {{ background: #222; border: 1px solid #444; border-radius: 4px; padding: 8px; margin-bottom: 6px; }}
            .meta {{ color: #888; font-size: 0.8em; margin-bottom: 4px; }}
            .content {{ color: #fff; margin-bottom: 6px; word-break: break-all; }}
            .actions {{ display: flex; gap: 5px; justify-content: flex-end; }}
            button, a {{ text-decoration: none; padding: 4px 8px; border-radius: 3px; font-size: 11px; cursor: pointer; border: none; }}
            .btn-copy {{ background: #4caf50; color: white; }}
            .btn-del {{ background: #f44336; color: white; }}
            
            /* 스크롤바 */
            ::-webkit-scrollbar {{ width: 5px; }}
            ::-webkit-scrollbar-thumb {{ background: #444; border-radius: 3px; }}
        </style>
        <script>
            function copyToClip(text) {{
                navigator.clipboard.writeText(text).then(() => {{
                    alert("📋 클립보드에 복사되었습니다!\\n상태창의 '기억 주입' 칸에 붙여넣으세요.");
                }}).catch(err => {{
                    prompt("복사해서 사용하세요:", text);
                }});
            }}
        </script>
    </head>
    <body>
        <div style="text-align:center; color:#888; margin-bottom:10px;">
            ▼ {u}님의 {c} 기억 보관소 ▼
        </div>
        {log_items if logs else "<div style='text-align:center; padding:20px; color:#666;'>저장된 기록이 없습니다.</div>"}
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
