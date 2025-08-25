from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import json
import os
import sqlite3
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import subprocess
import sys
import threading

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB limit

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(ROOT, 'public')
UPLOADS_DIR = os.path.join(ROOT, 'uploads')
CONFIG_PATH = os.path.join(ROOT, 'config.json')
DB_PATH = os.path.join(ROOT, 'scouting.db')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

def read_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS matches(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            pre_match_json TEXT NOT NULL,
            auto_json TEXT NOT NULL,
            teleop_json TEXT NOT NULL,
            endgame_json TEXT NOT NULL,
            misc_json TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            pit_json TEXT NOT NULL,
            image_path TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS checklist_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checklist_key TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            options_json TEXT NOT NULL,
            checked_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def score_obj(section, conf_section):
    if not section or not conf_section:
        return 0
    
    total = 0
    for k, v in section.items():
        if k not in conf_section:
            continue
            
        c = conf_section[k]
        
        # Handle scoring objects with Made/Missed properties
        if isinstance(v, dict) and 'Made' in v:
            if 'Value' in c and isinstance(c['Value'], (int, float)):
                total += (int(v.get('Made', 0)) * int(c['Value']))
        # Handle boolean values
        elif isinstance(v, bool):
            if isinstance(c, dict) and 'Value' in c and isinstance(c['Value'], (int, float)):
                total += int(c['Value']) if v else 0
            elif isinstance(c, (int, float)):
                total += int(c) if v else 0
                
    return total

def auto_score(data, conf):
    return score_obj(data, conf.get('match_form', {}).get('auto_period', {}))

def tele_score(data, conf):
    return score_obj(data, conf.get('match_form', {}).get('teleop_period', {}))

def endgame_score(data, conf):
    final_status_config = conf.get('match_form', {}).get('endgame', {}).get('final_status', {})
    status = data.get('final_status', '')
    
    # Handle new format with options/values
    if 'options' in final_status_config and 'values' in final_status_config:
        options = final_status_config['options']
        values = final_status_config['values']
        if status in options:
            index = options.index(status)
            return int(values[index]) if index < len(values) else 0
        return 0
    else:
        # Handle old format
        status_config = final_status_config.get(status, {})
        return int(status_config.get('Value', 0)) if status_config else 0

checklist_state = {}
checklist_lock = threading.Lock()

@app.route('/api/checklist', methods=['GET'])
def get_checklist():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM checklist_items')
        rows = cursor.fetchall()
        conn.close()
        
        print("Database checklist items:")  # Debug log
        for row in rows:
            print(f"  Key: {row['checklist_key']}, Checked: {row['checked_json']}")  # Debug log
        
        checklist_data = {}
        for row in rows:
            checklist_data[row['checklist_key']] = {
                'title': row['title'],
                'options': json.loads(row['options_json']),
                'checked': json.loads(row['checked_json'])
            }
            
        return jsonify(checklist_data)
    except Exception as e:
        print(f"Error getting checklist: {e}")  # Debug log
        return jsonify({'error': 'db', 'details': str(e)}), 500

@app.route('/api/checklist/<checklist_key>', methods=['POST'])
def update_checklist(checklist_key):
    try:
        data = request.get_json()
        checked_items = data.get('checked', [])
        
        print(f"Updating checklist {checklist_key} with checked items: {checked_items}")  # Debug log
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if checklist exists
        cursor.execute('SELECT * FROM checklist_items WHERE checklist_key = ?', (checklist_key,))
        row = cursor.fetchone()
        
        if row:
            # Update existing checklist
            cursor.execute('''
                UPDATE checklist_items 
                SET checked_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE checklist_key = ?
            ''', (json.dumps(checked_items), checklist_key))
            print(f"Updated existing checklist {checklist_key}")  # Debug log
        else:
            # Get config to create new checklist
            conf = read_config()
            home_config = conf.get('Home', {})
            body_config = home_config.get('body', {})
            
            # Find the checklist in config
            checklist_config = None
            for key, item in body_config.items():
                if key == checklist_key and item.get('type') == 'checklist':
                    checklist_config = item
                    break
            
            if not checklist_config:
                return jsonify({'error': 'Checklist not found in config'}), 404
                
            # Create new checklist
            cursor.execute('''
                INSERT INTO checklist_items (checklist_key, title, options_json, checked_json)
                VALUES (?, ?, ?, ?)
            ''', (
                checklist_key,
                checklist_config.get('title', 'Checklist'),
                json.dumps(checklist_config.get('options', [])),
                json.dumps(checked_items)
            ))
            print(f"Created new checklist {checklist_key}")  # Debug log
        
        conn.commit()
        conn.close()
        
        return jsonify({'ok': True})
    except Exception as e:
        print(f"Error updating checklist: {e}")  # Debug log
        return jsonify({'error': 'update', 'details': str(e)}), 500
    
# Serve static files
@app.route('/')
def serve_index():
    return send_from_directory(PUBLIC_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(PUBLIC_DIR, path)

@app.route('/api/config', methods=['GET'])
def get_config():
    try:
        return jsonify(read_config())
    except Exception as e:
        return jsonify({'error': 'config', 'details': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'image' not in request.files:
        return jsonify({'error': 'no file'}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'no file selected'}), 400
        
    if file:
        ext = os.path.splitext(file.filename)[1]
        filename = "upload_{}_{}{}".format(int(datetime.now().timestamp()), uuid.uuid4().hex, ext)
        filepath = os.path.join(UPLOADS_DIR, filename)
        file.save(filepath)
        return jsonify({'path': '/uploads/{}'.format(filename)})

@app.route('/api/matches', methods=['POST'])
def create_match():
    try:
        conf = read_config()
        data = request.get_json()
        
        pre = data.get('pre_match_json', {})
        auto = data.get('auto_json', {})
        tele = data.get('teleop_json', {})
        endg = data.get('endgame_json', {})
        misc = data.get('misc_json', {})
        
        auto_pts = auto_score(auto, conf)
        tele_pts = tele_score(tele, conf)
        end_pts = endgame_score(endg, conf)
        total_pts = auto_pts + tele_pts + end_pts
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO matches(pre_match_json, auto_json, teleop_json, endgame_json, misc_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (json.dumps(pre), json.dumps(auto), json.dumps(tele), json.dumps(endg), json.dumps(misc)))
        match_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'id': match_id,
            'autoPts': auto_pts,
            'telePts': tele_pts,
            'endPts': end_pts,
            'total': total_pts
        })
    except Exception as e:
        return jsonify({'error': 'insert', 'details': str(e)}), 500

@app.route('/api/matches', methods=['GET'])
def get_matches():
    try:
        conf = read_config()
        cap = conf.get('limits', {}).get('raw_table_cap', 50)
        limit = min(int(request.args.get('limit', cap)), 200)
        offset = max(0, int(request.args.get('offset', 0)))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))
        rows = cursor.fetchall()
        conn.close()
        
        matches = []
        for row in rows:
            match_data = dict(row)
            match_data['pre_match_json'] = json.loads(row['pre_match_json'])
            match_data['auto_json'] = json.loads(row['auto_json'])
            match_data['teleop_json'] = json.loads(row['teleop_json'])
            match_data['endgame_json'] = json.loads(row['endgame_json'])
            match_data['misc_json'] = json.loads(row['misc_json'])
            matches.append(match_data)
            
        return jsonify(matches)
    except Exception as e:
        return jsonify({'error': 'list', 'details': str(e)}), 500

@app.route('/api/matches/<int:match_id>', methods=['PUT'])
def update_match(match_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches WHERE id = ?', (match_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'not found'}), 404
            
        data = request.get_json()
        pre = data.get('pre_match_json', json.loads(row['pre_match_json']))
        auto = data.get('auto_json', json.loads(row['auto_json']))
        tele = data.get('teleop_json', json.loads(row['teleop_json']))
        endg = data.get('endgame_json', json.loads(row['endgame_json']))
        misc = data.get('misc_json', json.loads(row['misc_json']))
        
        cursor.execute('''
            UPDATE matches SET pre_match_json=?, auto_json=?, teleop_json=?, endgame_json=?, misc_json=?
            WHERE id=?
        ''', (json.dumps(pre), json.dumps(auto), json.dumps(tele), json.dumps(endg), json.dumps(misc), match_id))
        conn.commit()
        conn.close()
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': 'update', 'details': str(e)}), 500

@app.route('/api/matches/<int:match_id>', methods=['DELETE'])
def delete_match(match_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM matches WHERE id = ?', (match_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': 'delete', 'details': str(e)}), 500

@app.route('/api/pits', methods=['POST'])
def create_pit():
    try:
        data = request.get_json()
        pit = data.get('pit_json', {})
        image_path = data.get('image_path')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO pits(pit_json, image_path) VALUES (?, ?)', 
                      (json.dumps(pit), image_path))
        pit_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'id': pit_id})
    except Exception as e:
        return jsonify({'error': 'insert', 'details': str(e)}), 500

@app.route('/api/pits', methods=['GET'])
def get_pits():
    try:
        conf = read_config()
        cap = conf.get('limits', {}).get('raw_table_cap', 50)
        limit = min(int(request.args.get('limit', cap)), 200)
        offset = max(0, int(request.args.get('offset', 0)))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pits ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))
        rows = cursor.fetchall()
        conn.close()
        
        pits = []
        for row in rows:
            pit_data = dict(row)
            pit_data['pit_json'] = json.loads(row['pit_json'])
            pits.append(pit_data)
            
        return jsonify(pits)
    except Exception as e:
        return jsonify({'error': 'list', 'details': str(e)}), 500

@app.route('/api/pits/<int:pit_id>', methods=['PUT'])
def update_pit(pit_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pits WHERE id = ?', (pit_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'not found'}), 404
            
        data = request.get_json()
        pit = data.get('pit_json', json.loads(row['pit_json']))
        image_path = data.get('image_path', row['image_path'])
        
        cursor.execute('UPDATE pits SET pit_json=?, image_path=? WHERE id=?', 
                      (json.dumps(pit), image_path, pit_id))
        conn.commit()
        conn.close()
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': 'update', 'details': str(e)}), 500

@app.route('/api/pits/<int:pit_id>', methods=['DELETE'])
def delete_pit(pit_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM pits WHERE id = ?', (pit_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': 'delete', 'details': str(e)}), 500

@app.route('/api/team/<team>/averages', methods=['GET'])
def get_team_averages(team):
    try:
        conf = read_config()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches ORDER BY id')
        all_matches = cursor.fetchall()
        conn.close()
        team_matches = []
        for row in all_matches:
            pre_match_data = json.loads(row['pre_match_json'])
            if str(pre_match_data.get('team_number')) == str(team):
                team_matches.append(row)
        
        if not team_matches:
            return jsonify({
                'team': team, 
                'matches': 0, 
                'avg_auto': 0, 
                'avg_teleop': 0, 
                'avg_endgame': 0, 
                'avg_total': 0
            })
        auto_total, tele_total, end_total = 0, 0, 0
        for row in team_matches:
            auto_data = json.loads(row['auto_json'])
            tele_data = json.loads(row['teleop_json'])
            end_data = json.loads(row['endgame_json'])
            
            auto_total += auto_score(auto_data, conf)
            tele_total += tele_score(tele_data, conf)
            end_total += endgame_score(end_data, conf)
        n = len(team_matches)
        return jsonify({
            'team': team,
            'matches': n,
            'avg_auto': auto_total / n,
            'avg_teleop': tele_total / n,
            'avg_endgame': end_total / n,
            'avg_total': (auto_total + tele_total + end_total) / n
        })
    except Exception as e:
        return jsonify({'error': 'db', 'details': str(e)}), 500

@app.route('/api/team/<team>/matches', methods=['GET'])
def get_team_matches(team):
    try:
        conf = read_config()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches ORDER BY id')
        all_matches = cursor.fetchall()
        conn.close()
        matches = []
        for row in all_matches:
            pre_match_data = json.loads(row['pre_match_json'])
            if str(pre_match_data.get('team_number')) != str(team):
                continue
            match_data = dict(row)
            match_data['pre_match_json'] = pre_match_data
            match_data['auto_json'] = json.loads(row['auto_json'])
            match_data['teleop_json'] = json.loads(row['teleop_json'])
            match_data['endgame_json'] = json.loads(row['endgame_json'])
            match_data['misc_json'] = json.loads(row['misc_json'])
            auto_pts = auto_score(match_data['auto_json'], conf)
            tele_pts = tele_score(match_data['teleop_json'], conf)
            end_pts = endgame_score(match_data['endgame_json'], conf)
            match_data['auto_points'] = auto_pts
            match_data['teleop_points'] = tele_pts
            match_data['endgame_points'] = end_pts
            match_data['total_points'] = auto_pts + tele_pts + end_pts
            matches.append(match_data)
        return jsonify(matches)
    except Exception as e:
        return jsonify({'error': 'db', 'details': str(e)}), 500
    
@app.route('/api/team/<team>/info', methods=['GET'])
def get_team_info(team):
    try:
        year = int(request.args.get('year', 2025))
        try:
            result = subprocess.run(
                [sys.executable, 'team_name_scraper.py', team, str(year)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return jsonify(json.loads(result.stdout))
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError):
            pass  
        return jsonify({
            'name': 'Team {}'.format(team),
            'epa': None,
            'state_rank': None,
            'state_total': None,
            'country_rank': None,
            'country_total': None,
            'world_rank': None,
            'world_total': None,
            'district_rank': None,
            'district_total': None
        })
    except Exception as e:
        return jsonify({
            'name': 'Team {}'.format(team),
            'epa': None,
            'state_rank': None,
            'state_total': None,
            'country_rank': None,
            'country_total': None,
            'world_rank': None,
            'world_total': None,
            'district_rank': None,
            'district_total': None
        })

@app.route('/api/team/<team>/pit', methods=['GET'])
def get_team_pit(team):
    try:
        print(f"Looking for pit data for team: {team} (type: {type(team)})")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, pit_json FROM pits')
        all_pits = cursor.fetchall()
        print("All pit entries:")
        for pit in all_pits:
            pit_json = json.loads(pit['pit_json'])
            print(f"  ID {pit['id']}: Team {pit_json.get('team_number')} (type: {type(pit_json.get('team_number'))})")
        cursor.execute('''
            SELECT * FROM pits 
            WHERE json_extract(pit_json, '$.team_number') = ?
            ORDER BY id DESC LIMIT 1
        ''', (team,))
        row = cursor.fetchone()
        if not row:
            print("Team not found with string match, trying integer...")
            if team.isdigit():
                cursor.execute('''
                    SELECT * FROM pits 
                    WHERE json_extract(pit_json, '$.team_number') = ?
                    ORDER BY id DESC LIMIT 1
                ''', (int(team),))
                row = cursor.fetchone()
        conn.close()
        if not row:
            print(f"No pit data found for team {team}")
            return jsonify({'error': 'not found'}), 404
        pit_data = dict(row)
        pit_data['pit_json'] = json.loads(row['pit_json'])
        print(f"Found pit data: {pit_data}")
        return jsonify(pit_data)
    except Exception as e:
        print(f"Error getting pit data: {e}")
        return jsonify({'error': 'db', 'details': str(e)}), 500

@app.route('/api/rankings', methods=['GET'])
def get_rankings():
    try:
        conf = read_config()
        option = request.args.get('option', list(conf.get('rankings_options', {}).keys())[0])
        min_matches = int(request.args.get('min_matches', 0))
        team_filter = request.args.get('team', '')
        
        spec = conf.get('rankings_options', {}).get(option)
        if not spec:
            return jsonify({'error': 'unknown option'}), 400
            
        # Get all matches
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches ORDER BY id')
        all_matches = cursor.fetchall()
        conn.close()
        
        # Group matches by team
        team_matches = {}
        for row in all_matches:
            pre_match = json.loads(row['pre_match_json'])
            team_number = str(pre_match.get('team_number'))
            
            if team_number not in team_matches:
                team_matches[team_number] = []
                
            match_data = {
                'pre_match': pre_match,
                'auto': json.loads(row['auto_json']),
                'teleop': json.loads(row['teleop_json']),
                'endgame': json.loads(row['endgame_json']),
                'misc': json.loads(row['misc_json'])
            }
            team_matches[team_number].append(match_data)
        
        # Calculate ranking for each team
        rankings = []
        for team_number, matches in team_matches.items():
            if len(matches) < min_matches:
                continue
                
            if team_filter and team_number != team_filter:
                continue
            
            # Calculate the metric based on the option
            metric_value = calculate_ranking_metric(option, matches, conf)
            rankings.append({
                'team_number': team_number,
                'matches_count': len(matches),
                'metric_value': metric_value
            })
        
        # Sort based on metric value (descending)
        rankings.sort(key=lambda x: x['metric_value'], reverse=True)
        
        return jsonify({
            'option': option,
            'description': spec.get('description', option),
            'rows': rankings[:100]
        })
            
    except Exception as e:
        return jsonify({'error': 'db', 'details': str(e)}), 500

def calculate_ranking_metric(option, matches, conf):
    """Calculate ranking metric based on the option name and config"""
    # Default implementations for common ranking types
    if option == "Average Points":
        total = 0
        for match in matches:
            auto_pts = auto_score(match['auto'], conf)
            tele_pts = tele_score(match['teleop'], conf)
            end_pts = endgame_score(match['endgame'], conf)
            total += auto_pts + tele_pts + end_pts
        return total / len(matches) if matches else 0
        
    elif option == "Average L4 Auto":
        total = sum(match['auto'].get('L4', {}).get('Made', 0) for match in matches)
        return total / len(matches) if matches else 0
        
    elif option == "Max Auto L4":
        return max(match['auto'].get('L4', {}).get('Made', 0) for match in matches) if matches else 0
        
    elif option == "Average Teleop L4":
        total = sum(match['teleop'].get('L4', {}).get('Made', 0) for match in matches)
        return total / len(matches) if matches else 0
        
    elif option == "Died %":
        died_count = sum(1 for match in matches if match['misc'].get('died', False))
        return (died_count / len(matches) * 100) if matches else 0
        
    elif option == "Tippy %":
        tippy_count = sum(1 for match in matches if match['misc'].get('tippy', False))
        return (tippy_count / len(matches) * 100) if matches else 0
        
    elif option == "Auto Coral %":
        match_accuracies = []
        for match in matches:
            match_made = 0
            match_attempted = 0
            for level in ['L1', 'L2', 'L3', 'L4']:
                if level in match['auto']:
                    match_made += match['auto'][level].get('Made', 0)
                    match_attempted += match['auto'][level].get('Made', 0) + match['auto'][level].get('Missed', 0)
            
            if match_attempted > 0:
                match_accuracies.append((match_made / match_attempted) * 100)
            else:
                match_accuracies.append(0)
        
        return sum(match_accuracies) / len(match_accuracies) if match_accuracies else 0
        
    elif option == "Teleop Coral %":
        match_accuracies = []
        for match in matches:
            match_made = 0
            match_attempted = 0
            for level in ['L1', 'L2', 'L3', 'L4']:
                if level in match['teleop']:
                    match_made += match['teleop'][level].get('Made', 0)
                    match_attempted += match['teleop'][level].get('Made', 0) + match['teleop'][level].get('Missed', 0)
            
            if match_attempted > 0:
                match_accuracies.append((match_made / match_attempted) * 100)
            else:
                match_accuracies.append(0)
        
        return sum(match_accuracies) / len(match_accuracies) if match_accuracies else 0
            
        # Default fallback - try to extract from SQL pattern or return 0
        return 0

def to_csv(rows):
    if not rows:
        return ''
    keys = list(rows[0].keys())
    header = ','.join(keys)
    def escape_value(value):
        if value is None:
            return ''
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return '"{}"'.format(str(value).replace('"', '""'))
    body = '\n'.join(
        ','.join(escape_value(row.get(key)) for key in keys)
        for row in rows
    )
    return header + '\n' + body

@app.route('/api/export/matches.csv', methods=['GET'])
def export_matches_csv():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches ORDER BY id ASC')
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        csv_data = to_csv(rows)
        return csv_data, 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename="matches.csv"'
        }
    except Exception as e:
        return 'Error: {}'.format(str(e)), 500

@app.route('/api/export/pits.csv', methods=['GET'])
def export_pits_csv():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pits ORDER BY id ASC')
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        csv_data = to_csv(rows)
        return csv_data, 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename="pits.csv"'
        }
    except Exception as e:
        return 'Error: {}'.format(str(e)), 500

@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)

@app.route('/api/upload/csv', methods=['POST'])
def upload_csv():
    try:
        if 'csv' not in request.files:
            return jsonify({'error': 'No CSV file provided'}), 400
            
        file = request.files['csv']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400
            
        # Read and parse CSV
        import csv
        from io import StringIO
        
        stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_data = csv.DictReader(stream)
        
        # Determine if it's matches or pits data
        first_row = next(csv_data, None)
        if not first_row:
            return jsonify({'error': 'Empty CSV file'}), 400
            
        stream.seek(0)  # Reset stream
        csv_data = csv.DictReader(stream)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        records_processed = 0
        errors = []
        
        # Check if it's matches data
        if 'pre_match_json' in first_row:
            for i, row in enumerate(csv_data):
                try:
                    # Convert JSON strings back to objects
                    pre_match_json = json.loads(row['pre_match_json']) if row['pre_match_json'] else {}
                    auto_json = json.loads(row['auto_json']) if row['auto_json'] else {}
                    teleop_json = json.loads(row['teleop_json']) if row['teleop_json'] else {}
                    endgame_json = json.loads(row['endgame_json']) if row['endgame_json'] else {}
                    misc_json = json.loads(row['misc_json']) if row['misc_json'] else {}
                    
                    # Check if this record already exists
                    cursor.execute('SELECT id FROM matches WHERE id = ?', (row['id'],))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing record
                        cursor.execute('''
                            UPDATE matches SET pre_match_json=?, auto_json=?, teleop_json=?, endgame_json=?, misc_json=?
                            WHERE id=?
                        ''', (json.dumps(pre_match_json), json.dumps(auto_json), json.dumps(teleop_json), 
                              json.dumps(endgame_json), json.dumps(misc_json), row['id']))
                    else:
                        # Insert new record
                        cursor.execute('''
                            INSERT INTO matches(id, created_at, pre_match_json, auto_json, teleop_json, endgame_json, misc_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (row['id'], row['created_at'], json.dumps(pre_match_json), json.dumps(auto_json),
                              json.dumps(teleop_json), json.dumps(endgame_json), json.dumps(misc_json)))
                    
                    records_processed += 1
                except Exception as e:
                    errors.append(f"Row {i+1}: {str(e)}")
        
        # Check if it's pits data
        elif 'pit_json' in first_row:
            for i, row in enumerate(csv_data):
                try:
                    # Convert JSON strings back to objects
                    pit_json = json.loads(row['pit_json']) if row['pit_json'] else {}
                    image_path = row.get('image_path', '')
                    
                    # Check if this record already exists
                    cursor.execute('SELECT id FROM pits WHERE id = ?', (row['id'],))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing record
                        cursor.execute('''
                            UPDATE pits SET pit_json=?, image_path=?
                            WHERE id=?
                        ''', (json.dumps(pit_json), image_path, row['id']))
                    else:
                        # Insert new record
                        cursor.execute('''
                            INSERT INTO pits(id, created_at, pit_json, image_path)
                            VALUES (?, ?, ?, ?)
                        ''', (row['id'], row['created_at'], json.dumps(pit_json), image_path))
                    
                    records_processed += 1
                except Exception as e:
                    errors.append(f"Row {i+1}: {str(e)}")
        else:
            conn.close()
            return jsonify({'error': 'Unknown CSV format'}), 400
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Successfully processed {records_processed} records',
            'errors': errors if errors else None
        })
        
    except Exception as e:
        return jsonify({'error': 'upload', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)