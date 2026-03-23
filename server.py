from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
import os, re

app = Flask(__name__, static_folder='.')
CORS(app)

# ✅ Railway MySQL Config (AUTO from environment)
DB_CONFIG = {
    'host': os.getenv('MYSQLHOST'),
    'port': int(os.getenv('MYSQLPORT', 3306)),
    'user': os.getenv('MYSQLUSER'),
    'password': os.getenv('MYSQLPASSWORD'),
    'database': os.getenv('MYSQLDATABASE'),
    'autocommit': True
}

def get_connection(database=None):
    cfg = DB_CONFIG.copy()
    if database:
        cfg['database'] = database
    return mysql.connector.connect(**cfg)

# Serve frontend
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# Health check
@app.route('/api/ping')
def ping():
    try:
        conn = get_connection()
        conn.close()
        return jsonify({'connected': True})
    except Exception as e:
        return jsonify({'connected': False, 'error': str(e)})

# Run SQL queries
@app.route('/api/query', methods=['POST'])
def run_query():
    body = request.get_json()
    sql = body.get('sql', '').strip()

    if not sql:
        return jsonify({'error': True, 'message': 'No SQL provided'})

    statements = split_sql(sql)
    results = []

    try:
        conn = get_connection()
        cursor = conn.cursor()

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue

            try:
                cursor.execute(stmt)

                if cursor.description:
                    cols = [col[0] for col in cursor.description]
                    rows = cursor.fetchall()

                    results.append({
                        'type': 'SELECT',
                        'columns': cols,
                        'rows': [[str(v) if v is not None else 'NULL' for v in row] for row in rows],
                        'rowCount': len(rows)
                    })
                else:
                    results.append({
                        'type': 'OK',
                        'affectedRows': cursor.rowcount if cursor.rowcount >= 0 else 0
                    })

            except mysql.connector.Error as e:
                results.append({
                    'type': 'ERROR',
                    'message': str(e)
                })

        cursor.close()
        conn.close()
        return jsonify({'success': True, 'results': results})

    except Exception as e:
        return jsonify({'error': True, 'message': str(e)})

# Split SQL
def split_sql(sql):
    sql = re.sub(r'DELIMITER\s+//\s*', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'DELIMITER\s+;\s*', '', sql, flags=re.IGNORECASE)
    sql = sql.replace('//', ';')
    return [s.strip() for s in sql.split(';') if s.strip()]

# ✅ Railway PORT FIX
if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=PORT)