import os
import base64
import json
from datetime import datetime
from flask import Flask, request, Response, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- DB 설정 ---
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 모델 ---
class MemoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), index=True)
    char_id = db.Column(db.String(100), index=True)
    content = db.Column(db.Text)
    password = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class CurrentState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), index=True)
    char_id = db.Column(db.String(100), index=True)
    json_data = db.Column(db.Text)
    password = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

# 테이블 생성 시도
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"DB Error: {e}")

PIXEL_GIF_DATA = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

@app.after_request
def add_header(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "frame-ancestors *"
    return response

@app.route('/')
def index():
    return "Memory Server Running OK"

@app.route('/save')
def save_data():
    try:
        u = request.args.get('u')
        c = request.args.get('c')
        pw = request.args.get('pw')
        d = request.args.get('d')
        s = request.args.get('s')

        if not u or not c or not pw: 
            return Response(PIXEL_GIF_DATA, mimetype='image/gif')

        if d:
            db.session.add(MemoryLog(user_id=u, char_id=c, password=pw, content=d))

        if s:
            state_record = CurrentState.query.filter_by(user_id=u, char_id=c, password=pw).first()
            if state_record:
                state_record.json_data = s
                state_record.updated_at = datetime.utcnow()
            else:
                db.session.add(CurrentState(user_id=u, char_id=c, password=pw, json_data=s))

        db.session.commit()
    except Exception as e:
        print(f"Save Error: {e}")
    
    return Response(PIXEL_GIF_DATA, mimetype='image/gif')

@app.route('/delete_action')
def delete_action():
    try:
        log_id = request.args.get('id')
        pw = request.args.get('pw')
        u = request.args.get('u')
        c = request.args.get('c')

        if log_id and pw:
            log = MemoryLog.query.get(log_id)
            if log and log.password == pw:
                db.session.delete(log)
                db.session.commit()
        return redirect(url_for('manager_view', u=u, c=c, pw=pw))
    except:
        return "Delete Error"

# ★ 안전하게 수정한 관리자 페이지 코드
@app.route('/manager')
def manager_view():
    try:
        u = request.args.get('u')
        c = request.args.get('c')
        pw = request.args.get('pw')

        # 1. 로그 데이터 준비
        logs = MemoryLog.query.filter_by(user_id=u, char_id=c, password=pw)\
            .order_by(MemoryLog.updated_at.desc()).limit(30).all()

        log_html = ""
        for l in logs:
            safe_content = l.content.replace('"', '&quot;')
            date_str = l.updated_at.strftime("%m/%d %H:%M")
            log_html += f'''
            <div class="log-item">
                <input type="checkbox" class="chk" value="{safe_content}">
                <div class="log-content">
                    <div class="log-date">{date_str}</div>
                    {l.content}
                </div>
                <a href="/delete_action?id={l.id}&pw={pw}&u={u}&c={c}" class="btn-del" onclick="return confirm('삭제?')">DEL</a>
            </div>
            '''

        # 2. 상태 데이터 준비
        state_record = CurrentState.query.filter_by(user_id=u, char_id=c, password=pw).first()
        user_info_html = ""
        skills_html = ""
        reputation_html = ""
        status_html = ""

        if state_record and state_record.json_data:
            try:
                data = json.loads(state_record.json_data)
                
                # 유저 정보
                for k, v in data.get('user_info', {}).items():
                    user_info_html += f'<div class="stat-item"><span class="stat-key">{k}</span><span class="stat-val">{v}</span></div>'
                
                # 스킬
                for v in data.get('skills', []):
                    skills_html += f'<div class="stat-item"><span class="stat-key">Skill</span><span class="stat-val">{v}</span></div>'
                
                # 평판
                for k, v in data.get('reputation', {}).items():
                    reputation_html += f'<div class="stat-item"><span class="stat-key">{k}</span><span class="stat-val">{v}</span></div>'
                
                # 상태
                for k, v in data.get('status', {}).items():
                    status_html += f'<div class="stat-item"><span class="stat-key">{k}</span><span class="stat-val">{v}</span></div>'
            except:
                user_info_html = "<div>JSON Error</div>"

        # 3. HTML 조립 (안전한 방식)
        html = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard</title>
            <style>
                body {{ background: #0f172a; color: #f1f5f9; font-family: sans-serif; padding: 20px; margin: 0; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
                .card {{ background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; }}
                .header {{ color: #6366f1; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #334155; padding-bottom: 5px; }}
                .stat-item {{ display: flex; justify-content: space-between; border-bottom: 1px dashed #334155; padding: 4px 0; font-size: 0.9em; }}
                .stat-val {{ font-weight: bold; }}
                .log-item {{ background: #0f172a; padding: 10px; margin-bottom: 8px; border-radius: 6px; display: flex; gap: 10px; }}
                .btn-del {{ color: #ef4444; font-size: 0.8em; text-decoration: none; border: 1px solid #ef4444; padding: 2px 5px; height: fit-content; }}
                .float-bar {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: #334155; padding: 10px 20px; border-radius: 30px; display: flex; gap: 10px; }}
                button {{ background: #6366f1; border: none; color: white; padding: 8px 16px; border-radius: 20px; cursor: pointer; font-weight: bold; }}
            </style>
            <script>
                function copyChecked() {{
                    const chks = document.querySelectorAll('.chk:checked');
                    let text = "";
                    chks.forEach(c => text += "- " + c.value + "\\n");
                    if(!text) return alert("선택된 항목 없음");
                    navigator.clipboard.writeText(text).then(() => alert("복사 완료")).catch(() => prompt("복사하세요:", text));
                }}
            </script>
        </head>
        <body>
            <h2 style="text-align:center;">User: {u} / Char: {c}</h2>
            <div class="grid">
                <div class="card">
                    <div class="header">User Info</div>
                    {user_info_html}
                    <div class="header" style="margin-top:10px;">Skills</div>
                    {skills_html}
                </div>
                <div class="card">
                    <div class="header">Reputation</div>
                    {reputation_html}
                </div>
                <div class="card" style="grid-column: span 2;">
                    <div class="header">Character Status</div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px;">
                        {status_html}
                    </div>
                </div>
                <div class="card" style="grid-column: span 2;">
                    <div class="header">History Logs</div>
                    {log_html}
                </div>
            </div>
            <div style="height:60px;"></div>
            <div class="float-bar">
                <button onclick="location.reload()">Refresh</button>
                <button onclick="copyChecked()">Copy Selected</button>
            </div>
        </body>
        </html>
        """
        return Response(html, mimetype='text/html')
    
    except Exception as e:
        return f"<h1>Error: {e}</h1>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
