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

# --- 모델 1: 누적 로그 (History) ---
class MemoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), index=True)
    char_id = db.Column(db.String(100), index=True)
    content = db.Column(db.Text) # 로그 내용
    password = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- 모델 2: 현재 상태 (Snapshot) ---
# 50개의 변수를 매번 컬럼으로 만들지 않고, 통째로 JSON으로 저장합니다.
class CurrentState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), index=True)
    char_id = db.Column(db.String(100), index=True)
    json_data = db.Column(db.Text) # 50개 변수가 담긴 JSON 문자열
    password = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

PIXEL_GIF_DATA = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

# [보안] Iframe 허용
@app.after_request
def add_header(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "frame-ancestors *"
    return response

# [기능 1] 통합 저장 (로그 + 상태)
@app.route('/save')
def save_data():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')
    
    log_text = request.args.get('d')      # 누적할 로그 (없을 수도 있음)
    state_json = request.args.get('s')    # 50개 변수 JSON (없을 수도 있음)

    if not u or not c or not pw: return Response(PIXEL_GIF_DATA, mimetype='image/gif')

    # 1. 로그가 있으면 누적 저장
    if log_text:
        db.session.add(MemoryLog(user_id=u, char_id=c, password=pw, content=log_text))

    # 2. 상태값이 있으면 덮어쓰기 (Upsert)
    if state_json:
        # 기존 상태 찾기
        state_record = CurrentState.query.filter_by(user_id=u, char_id=c, password=pw).first()
        if state_record:
            state_record.json_data = state_json
            state_record.updated_at = datetime.utcnow()
        else:
            db.session.add(CurrentState(user_id=u, char_id=c, password=pw, json_data=state_json))

    db.session.commit()
    return Response(PIXEL_GIF_DATA, mimetype='image/gif')

# [기능 2] 로그 삭제
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
            
    return redirect(url_for('manager_view', u=u, c=c, pw=pw))

# [기능 3] ★ 대시보드 뷰 (디자인 리메이크)
@app.route('/manager')
def manager_view():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')

    # 1. 로그 가져오기 (최신 30개)
    logs = MemoryLog.query.filter_by(user_id=u, char_id=c, password=pw)\
        .order_by(MemoryLog.updated_at.desc()).limit(30).all()

    # 2. 상태 가져오기
    state_record = CurrentState.query.filter_by(user_id=u, char_id=c, password=pw).first()
    state_data = {}
    if state_record and state_record.json_data:
        try:
            state_data = json.loads(state_record.json_data)
        except:
            state_data = {"Error": "JSON 파싱 실패"}

    # HTML 템플릿 (CSS Grid & Glassmorphism)
    html = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Memory Dashboard</title>
        <style>
            :root {{
                --bg-color: #0f172a;
                --card-bg: #1e293b;
                --accent: #6366f1;
                --text-main: #f1f5f9;
                --text-sub: #94a3b8;
                --border: #334155;
            }}
            body {{
                background-color: var(--bg-color); color: var(--text-main);
                font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
                margin: 0; padding: 20px;
                display: flex; flex-direction: column; gap: 20px;
            }}
            /* 그리드 레이아웃 */
            .dashboard-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
            }}
            
            /* 카드 스타일 */
            .card {{
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}
            .card-header {{
                font-size: 1.1em; font-weight: bold; color: var(--accent);
                margin-bottom: 15px; border-bottom: 2px solid var(--border);
                padding-bottom: 10px; display: flex; justify-content: space-between;
            }}

            /* 상태 변수 리스트 */
            .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em; }}
            .stat-item {{ display: flex; justify-content: space-between; padding: 5px; border-bottom: 1px dashed var(--border); }}
            .stat-key {{ color: var(--text-sub); }}
            .stat-val {{ font-weight: bold; color: #fff; text-align: right; }}

            /* 로그 리스트 */
            .log-list {{ max-height: 400px; overflow-y: auto; }}
            .log-item {{ 
                display: flex; gap: 10px; padding: 10px; 
                background: #0f172a; border-radius: 6px; margin-bottom: 8px; border: 1px solid var(--border);
            }}
            .chk {{ transform: scale(1.2); margin-top: 4px; cursor: pointer; }}
            .log-content {{ flex: 1; font-size: 0.9em; line-height: 1.4; }}
            .log-date {{ font-size: 0.75em; color: var(--text-sub); margin-bottom: 4px; }}
            .btn-del {{ 
                color: #ef4444; border: 1px solid #ef4444; background: transparent;
                padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8em; height: fit-content; text-decoration: none;
            }}
            .btn-del:hover {{ background: #ef4444; color: #fff; }}

            /* 하단 플로팅 바 */
            .floating-bar {{
                position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
                background: rgba(30, 41, 59, 0.9); backdrop-filter: blur(10px);
                padding: 10px 20px; border-radius: 50px; border: 1px solid var(--accent);
                display: flex; gap: 15px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
                width: max-content;
            }}
            .btn-float {{
                background: var(--accent); color: white; border: none;
                padding: 10px 20px; border-radius: 20px; font-weight: bold; cursor: pointer;
            }}
            .btn-float:hover {{ filter: brightness(1.1); }}
        </style>
        <script>
            function copyChecked() {{
                const chks = document.querySelectorAll('.chk:checked');
                if(chks.length === 0) return alert("선택된 로그가 없습니다.");
                let text = "";
                chks.forEach(c => text += "- " + c.value + "\\n");
                navigator.clipboard.writeText(text).then(() => alert("📋 복사 완료! 상태창에 붙여넣으세요."))
                .catch(() => prompt("Ctrl+C로 복사하세요:", text));
            }}
        </script>
    </head>
    <body>
        <div style="font-size:1.5em; font-weight:bold; text-align:center; margin-bottom:10px;">
            🧬 {c} <span style="font-size:0.6em; color:#64748b;">(User: {u})</span>
        </div>

        <div class="dashboard-grid">
            <div class="card">
                <div class="card-header">👤 User Info</div>
                <div class="stat-grid" style="grid-template-columns: 1fr;">
                    {''.join([f'<div class="stat-item"><span class="stat-key">{k}</span><span class="stat-val">{v}</span></div>' 
                              for k, v in state_data.get('user_info', {{}}).items()])}
                    
                    <div style="margin-top:10px; color:var(--accent); font-weight:bold;">⚔️ Skills</div>
                    {''.join([f'<div class="stat-item"><span class="stat-key">Skill</span><span class="stat-val">{v}</span></div>' 
                              for v in state_data.get('skills', [])])}
                </div>
            </div>

            <div class="card">
                <div class="card-header">🌍 Reputation</div>
                <div class="stat-grid">
                     {''.join([f'<div class="stat-item"><span class="stat-key">{k}</span><span class="stat-val">{v}</span></div>' 
                              for k, v in state_data.get('reputation', {{}}).items()])}
                </div>
            </div>

            <div class="card" style="grid-column: span 2;">
                <div class="card-header">📊 Character Status</div>
                <div class="stat-grid" style="grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));">
                     {''.join([f'<div class="stat-item"><span class="stat-key">{k}</span><span class="stat-val">{v}</span></div>' 
                              for k, v in state_data.get('status', {{}}).items()])}
                </div>
            </div>

            <div class="card" style="grid-column: span 2;">
                <div class="card-header">
                    📜 Memory Log ({len(logs)})
                </div>
                <div class="log-list">
                    {''.join([f'''
                    <div class="log-item">
                        <input type="checkbox" class="chk" value="{l.content.replace('"', '&quot;')}">
                        <div class="log-content">
                            <div class="log-date">{l.updated_at.strftime("%m/%d %H:%M")}</div>
                            {l.content}
                        </div>
                        <a href="/delete_action?id={l.id}&pw={pw}&u={u}&c={c}" class="btn-del" onclick="return confirm('삭제?')">DEL</a>
                    </div>
                    ''' for l in logs])}
                </div>
            </div>
        </div>

        <div style="height: 60px;"></div> <div class="floating-bar">
            <button onclick="location.reload()" class="btn-float" style="background:#334155;">🔄 Refresh</button>
            <button onclick="copyChecked()" class="btn-float">📋 Copy Selected</button>
        </div>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
