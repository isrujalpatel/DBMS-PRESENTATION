# ============================================================
#  OPD Query Runner — Python Backend Server
#  
#  SETUP:
#  1. pip install flask flask-cors mysql-connector-python
#  2. Edit your MySQL password below (line ~25)
#  3. python server.py
#  4. Open http://localhost:3000 in browser
# ============================================================

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
import os, re

app = Flask(__name__, static_folder='.')
CORS(app)

# ── MySQL config — EDIT YOUR PASSWORD HERE ────────────────
DB_CONFIG = {
    'host'    : 'localhost',
    'port'    : 3306,
    'user'    : 'root',       # ✏️ your MySQL username
    'password': '',           # ✏️ your MySQL password (leave '' if none)
    'autocommit': True
}

def get_connection(database=None):
    cfg = DB_CONFIG.copy()
    if database:
        cfg['database'] = database
    return mysql.connector.connect(**cfg)

# ── Serve frontend HTML ───────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# ── Health check ──────────────────────────────────────────
@app.route('/api/ping')
def ping():
    try:
        conn = get_connection()
        conn.close()
        return jsonify({'connected': True})
    except Exception as e:
        return jsonify({'connected': False, 'error': str(e)})

# ── Execute SQL ───────────────────────────────────────────
@app.route('/api/query', methods=['POST'])
def run_query():
    body = request.get_json()
    sql  = body.get('sql', '').strip()

    if not sql:
        return jsonify({'error': True, 'message': 'No SQL provided'})

    # Split multi-statement SQL into individual statements
    # Handle DELIMITER // blocks (stored procedures, triggers)
    statements = split_sql(sql)

    results = []
    current_db = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue

            # Track USE statements so we reconnect to correct DB
            use_match = re.match(r'^USE\s+(\w+)', stmt, re.IGNORECASE)
            if use_match:
                current_db = use_match.group(1)
                try:
                    cursor.execute(stmt)
                    results.append({'type': 'OK', 'affectedRows': 0, 'message': f'Database changed to {current_db}'})
                except Exception as e:
                    results.append({'type': 'OK', 'affectedRows': 0, 'message': f'Database changed to {current_db}'})
                continue

            # Reconnect with correct database after CREATE DATABASE
            if re.match(r'^CREATE\s+DATABASE', stmt, re.IGNORECASE):
                try:
                    cursor.execute(stmt)
                    results.append({'type': 'OK', 'affectedRows': 0, 'message': 'Database created successfully'})
                except mysql.connector.Error as e:
                    if e.errno == 1007:  # DB already exists
                        results.append({'type': 'OK', 'affectedRows': 0, 'message': 'Database already exists (OK)'})
                    else:
                        results.append({'type': 'ERROR', 'message': str(e)})
                continue

            try:
                cursor.execute(stmt)

                # SELECT / SHOW / EXPLAIN — fetch rows
                if cursor.description:
                    cols = [col[0] for col in cursor.description]
                    rows = cursor.fetchall()
                    # Convert all values to strings
                    str_rows = []
                    for row in rows:
                        str_row = []
                        for val in row:
                            if val is None:
                                str_row.append('NULL')
                            else:
                                str_row.append(str(val))
                        str_rows.append(str_row)

                    results.append({
                        'type'    : 'SELECT',
                        'columns' : cols,
                        'rows'    : str_rows,
                        'rowCount': len(str_rows)
                    })

                else:
                    # DDL / DML
                    affected = cursor.rowcount if cursor.rowcount >= 0 else 0
                    results.append({
                        'type'        : 'OK',
                        'affectedRows': affected,
                        'message'     : f'Query OK, {affected} row(s) affected'
                    })

            except mysql.connector.Error as e:
                results.append({
                    'type'   : 'ERROR',
                    'message': f'{e.msg}' if hasattr(e, 'msg') else str(e)
                })

        cursor.close()
        conn.close()
        return jsonify({'success': True, 'results': results})

    except Exception as e:
        return jsonify({'error': True, 'message': str(e)})


def split_sql(sql):
    """
    Splits a multi-statement SQL string into individual statements.
    Handles DELIMITER // blocks for procedures and triggers by
    collapsing them into a single statement.
    """
    statements = []

    # Remove DELIMITER lines and join procedure/trigger bodies
    # Strategy: collapse everything between DELIMITER // and DELIMITER ;
    # into one statement (mysql-connector-python handles it directly)
    sql = re.sub(r'DELIMITER\s+//\s*', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'DELIMITER\s+;\s*', '', sql, flags=re.IGNORECASE)
    sql = sql.replace('//', ';')

    # Now split on semicolons, but be smart about BEGIN...END blocks
    current   = []
    depth     = 0    # nesting depth for BEGIN/END

    lines = sql.split('\n')
    for line in lines:
        stripped = line.strip()

        # Skip pure comment lines
        if stripped.startswith('--') or stripped.startswith('#'):
            continue

        # Remove inline comments
        line_clean = re.sub(r'--[^\n]*', '', line)

        current.append(line_clean)

        # Track BEGIN/END depth
        depth += len(re.findall(r'\bBEGIN\b', line_clean, re.IGNORECASE))
        depth -= len(re.findall(r'\bEND\b',   line_clean, re.IGNORECASE))
        depth  = max(depth, 0)

        # Split on semicolon only when not inside a BEGIN/END block
        if depth == 0 and ';' in line_clean:
            stmt = ' '.join(current).strip()
            stmt = stmt.rstrip(';').strip()
            if stmt:
                statements.append(stmt)
            current = []

    # Flush anything remaining
    remaining = ' '.join(current).strip().rstrip(';').strip()
    if remaining:
        statements.append(remaining)

    return statements


if __name__ == '__main__':
    print('\n🏥  OPD Token System — Python Backend')
    print('─' * 40)

    # Test MySQL connection on startup
    try:
        conn = get_connection()
        conn.close()
        print('✅  MySQL connected successfully!')
    except Exception as e:
        print(f'❌  MySQL connection failed: {e}')
        print('   → Edit DB_CONFIG in server.py with your credentials')

    print('🌐  Open http://localhost:3000 in your browser\n')
    app.run(host='0.0.0.0', port=3000, debug=False)
