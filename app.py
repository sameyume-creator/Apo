import os
import base64
from datetime import datetime
from flask import Flask, request, Response, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- 1. DB 설정 (Railway PostgreSQL 대응) ---
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 2. 데이터 모델 ---
class MemoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), index=True)
    char_id = db.Column(db.String(100), index=True)
    content = db.Column(db.Text)
    password = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

# 앱 시작 시 테이블 생성
with app.app_context():
    db.create_all()

# 투명 픽셀 (이미지 해킹 응답용)
PIXEL_GIF_DATA = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

@app.route('/')
def index():
    return "Memory Server is Running!"

# [기능 1] 저장 (자동 저장용)
@app.route('/save')
def save_log():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')
    d = request.args.get('d')

    if u and c and pw and d:
        # DB에 저장
        new_log = MemoryLog(user_id=u, char_id=c, password=pw, content=d)
        db.session.add(new_log)
        db.session.commit()
    
    return Response(PIXEL_GIF_DATA, mimetype='image/gif')

# [기능 2] 삭제 동작 (삭제 후 관리 페이지로 돌아감)
@app.route('/delete_action')
def delete_action():
    log_id = request.args.get('id')
    pw = request.args.get('pw')
    u = request.args.get('u') # 리다이렉트용
    c = request.args.get('c') # 리다이렉트용

    if log_id and pw:
        log = MemoryLog.query.get(log_id)
        if log and log.password == pw:
            db.session.delete(log)
            db.session.commit()
            
    # 삭제 후 다시 목록 화면으로 이동 (새로고침 효과)
    return redirect(url_for('manager_view', u=u, c=c, pw=pw))

# [기능 3] 관리자 화면 (HTML을 만들어서 줌 - Iframe용)
@app.route('/manager')
def manager_view():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')

    # 최신순 50개 조회
    logs = MemoryLog.query.filter_by(user_id=u, char_id=c, password=pw)\
        .order_by(MemoryLog.updated_at.desc()).limit(50).all()

    # HTML 조립
    rows = ""
    if not logs:
        rows = "<div class='empty'>저장된 기억이 없습니다.</div>"
    else:
        for log in logs:
            safe_content = log.content.replace("'", "&apos;").replace('"', '&quot;')
            date_str = log.updated_at.strftime("%m/%d %H:%M")
            
            rows += f"""
            <div class='row'>
                <input type='checkbox' class='chk' value='{safe_content}'>
                <div class='info'>
                    <div class='date'>{date_str}</div>
                    <div class='text'>{log.content}</div>
                </div>
                <a href='/delete_action?id={log.id}&pw={pw}&u={u}&c={c}' class='btn-del' onclick="return confirm('삭제하시겠습니까?')">삭제</a>
            </div>
            """

    # 전체 HTML 페이지 반환
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ background: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 10px; }}
            .row {{ display: flex; gap: 10px; border-bottom: 1px solid #333; padding: 10px 0; align-items: flex-start; }}
            .chk {{ transform: scale(1.5); margin-top: 5px; cursor: pointer; }}
            .info {{ flex-grow: 1; overflow: hidden; }}
            .date {{ color: #666; font-size: 12px; margin-bottom: 4px; }}
            .text {{ color: #eee; font-size: 14px; line-height: 1.4; word-break: break-all; }}
            .btn-del {{ 
                background: #330000; color: #ff5555; text-decoration: none; 
                padding: 6px 10px; border: 1px solid #550000; border-radius: 4px; 
                font-size: 12px; white-space: nowrap; height: fit-content;
            }}
            .empty {{ text-align: center; color: #666; padding: 20px; }}
            
            /* 하단 고정 바 */
            .bottom-bar {{ 
                position: fixed; bottom: 0; left: 0; right: 0; 
                background: #111; padding: 10px; border-top: 1px solid #333; 
                display: flex; gap: 10px;
            }}
            .btn {{ flex: 1; padding: 12px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; color: white; }}
            .btn-copy {{ background: #4f46e5; }}
            .btn-refresh {{ background: #333; flex: 0.3; }}
        </style>
        <script>
            function copyChecked() {{
                const chks = document.querySelectorAll('.chk:checked');
                if(chks.length === 0) return alert("선택된 항목이 없습니다.");
                
                let result = "";
                chks.forEach(c => result += "- " + c.value + "\\n");
                
                // 클립보드 복사 시도
                navigator.clipboard.writeText(result).then(() => {{
                    alert("✅ 복사 완료!\\n아래 '붙여넣기' 칸에 넣어주세요.");
                }}).catch(err => {{
                    prompt("Ctrl+C를 눌러 복사하세요:", result);
                }});
            }}
        </script>
    </head>
    <body>
        <div style="padding-bottom: 60px;"> {rows}
        </div>
        <div class="bottom-bar">
            <button onclick="location.reload()" class="btn btn-refresh">🔄</button>
            <button onclick="copyChecked()" class="btn btn-copy">📋 선택 복사</button>
        </div>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
