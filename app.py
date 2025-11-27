import os
import base64
import json
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

# [1] 자동 저장 (이미지 태그 해킹)
@app.route('/save')
def save_log():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')
    d = request.args.get('d')

    if u and c and pw and d:
        # 중복 방지 로직 (선택 사항: 같은 내용이 최신이면 저장 안 함)
        # last_log = MemoryLog.query.filter_by(user_id=u, char_id=c).order_by(MemoryLog.updated_at.desc()).first()
        # if last_log and last_log.content == d: return Response(PIXEL_GIF_DATA, mimetype='image/gif')

        new_log = MemoryLog(user_id=u, char_id=c, password=pw, content=d)
        db.session.add(new_log)
        db.session.commit()
    
    return Response(PIXEL_GIF_DATA, mimetype='image/gif')

# [2] 삭제 (이미지 태그 해킹)
@app.route('/delete')
def delete_log():
    log_id = request.args.get('id')
    pw = request.args.get('pw')

    if log_id and pw:
        log = MemoryLog.query.get(log_id)
        if log and log.password == pw:
            db.session.delete(log)
            db.session.commit()

    return Response(PIXEL_GIF_DATA, mimetype='image/gif')

# [3] ★ 데이터 브릿지 (핵심)
# 이 페이지는 Iframe으로 불려와서, 부모(상태창)에게 데이터를 던져주고 사라집니다.
@app.route('/bridge')
def data_bridge():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')

    # 최신순 50개 가져오기
    logs = MemoryLog.query.filter_by(user_id=u, char_id=c, password=pw)\
        .order_by(MemoryLog.updated_at.desc()).limit(50).all()

    # 데이터를 JSON 리스트로 변환
    data_list = []
    for log in logs:
        # JS 에러 방지용 이스케이프
        safe_content = log.content.replace('"', '\\"').replace("'", "\\'")
        data_list.append({
            "id": log.id,
            "content": safe_content,
            "date": log.updated_at.strftime("%m/%d %H:%M")
        })

    # Python 객체를 JSON 문자열로 변환
    json_data = json.dumps(data_list)

    # HTML 응답: 부모에게 postMessage를 보내는 스크립트만 포함
    html = f"""
    <!DOCTYPE html>
    <html>
    <body>
    <script>
        const logs = {json_data};
        // 부모 창(상태창)에게 메시지 전송
        window.parent.postMessage({{
            type: 'LOG_DATA_SYNC',
            status: 'success',
            logs: logs
        }}, '*');
    </script>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
