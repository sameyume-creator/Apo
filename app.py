import os
import base64
import json
from datetime import datetime
from flask import Flask, request, Response, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- 1. 데이터베이스 설정 (Railway PostgreSQL 대응) ---
# Railway는 'postgres://'를 줄 때가 있는데, 최신 라이브러리는 'postgresql://'을 원해서 바꿔줘야 함
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 2. 데이터 모델 (테이블 설계) ---
class MemoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), index=True)
    char_id = db.Column(db.String(100), index=True)
    content = db.Column(db.Text)
    password = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

# 앱 시작 시 테이블 생성 (Railway 배포 시 자동 실행됨)
with app.app_context():
    db.create_all()

# --- 3. 유틸리티 ---
# 1x1 투명 픽셀 (이미지 해킹 응답용)
PIXEL_GIF_DATA = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

# --- 4. API 엔드포인트 ---

@app.route('/')
def index():
    return "Memory Server is Running!"

# [기능 1] 로그 저장 (이미지 태그 호출용)
@app.route('/save')
def save_log():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')
    d = request.args.get('d')

    if u and c and pw and d:
        new_log = MemoryLog(user_id=u, char_id=c, password=pw, content=d)
        db.session.add(new_log)
        db.session.commit()
    
    return Response(PIXEL_GIF_DATA, mimetype='image/gif')

# [기능 2] 로그 삭제 (개별 삭제)
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

# [기능 3] 로그 불러오기 (JSONP 방식)
# 상태창 노드(샌드박스)에서 데이터를 받아가기 위한 핵심 기능
@app.route('/load_jsonp')
def load_jsonp():
    u = request.args.get('u')
    c = request.args.get('c')
    pw = request.args.get('pw')
    callback = request.args.get('callback', 'handleServerData')

    # 최신순으로 50개 가져오기
    logs = MemoryLog.query.filter_by(user_id=u, char_id=c, password=pw)\
        .order_by(MemoryLog.updated_at.desc())\
        .limit(50).all()

    if not logs:
        # 로그 없음
        js_code = f"{callback}({{ 'status': 'empty', 'message': '저장된 기록이 없습니다.' }});"
    else:
        # 데이터 리스트 변환
        logs_list = []
        for log in logs:
            # JS 문자열 깨짐 방지
            safe_content = log.content.replace("`", "").replace("\\", "\\\\").replace("'", "\\'")
            logs_list.append(f"{{ 'id': {log.id}, 'content': '{safe_content}', 'date': '{log.updated_at}' }}")
        
        logs_json_str = "[" + ",".join(logs_list) + "]"
        js_code = f"{callback}({{ 'status': 'success', 'logs': {logs_json_str} }});"

    return Response(js_code, mimetype='application/javascript')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
