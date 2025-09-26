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
import hashlib
import secrets
from functools import wraps
import csv
from io import StringIO
from datetime import datetime
import secrets

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







# ==================== CONFIGURATION & DATABASE FUNCTIONS ====================

def read_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    #cursor.execute("DROP TABLE IF EXISTS batteries")
    #cursor.execute("DROP TABLE IF EXISTS battery_logs")


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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'scout',
            auth_token TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS batteries(
            id TEXT PRIMARY KEY,
            time_scanned TEXT NOT NULL,
            usage_count INTEGER DEFAULT 0,
            beakStatus TEXT NOT NULL,
            charge REAL NOT NULL,
            v0 REAL NOT NULL,
            v1 REAL NOT NULL,
            v2 REAL NOT NULL,
            rint REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS battery_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battery_id TEXT NOT NULL,
            time_scanned TEXT NOT NULL,
            status TEXT NOT NULL,
            charge REAL NOT NULL,
            beakStatus TEXT NOT NULL,
            v0 REAL NOT NULL,
            v1 REAL NOT NULL,
            v2 REAL NOT NULL,
            rint REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (battery_id) REFERENCES batteries (id)
        )
    ''')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
    admin_count = cursor.fetchone()[0]
    if admin_count == 0:
        # Default admin: username=admin, password=admin123
        password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            ('admin', password_hash, 'admin')
        )
        print("Created default admin user: admin/admin123")
    
    conn.commit()
    conn.close()
init_db()







# ==================== AUTHENTICATION & AUTHORIZATION FUNCTIONS ====================

"""Decorator function that requires user authentication with optional role-based authorization."""
def login_required(role="scout"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'error': 'Authentication required'}), 401
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE auth_token = ?', (auth_header,))
            user = cursor.fetchone()
            conn.close()
            
            if not user:
                return jsonify({'error': 'Invalid token'}), 401
            user_role = user['role']
            if role == "admin" and user_role != "admin":
                return jsonify({'error': 'Admin access required'}), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator






# ==================== BATTERY MANAGEMENT ENDPOINTS ====================

@app.route('/api/batteries', methods=['GET'])
@login_required()
def get_batteries():
    """Retrieve all batteries"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM batteries ORDER BY id')
        batteries = cursor.fetchall()
        conn.close()
        
        batteries_list = []
        for battery in batteries:
            battery_dict = dict(battery)
            # Ensure consistent field names - handle both formats
            battery_dict['timeScanned'] = battery_dict.get('time_scanned', 'Unknown')
            battery_dict['time_scanned'] = battery_dict.get('time_scanned', 'Unknown')
            battery_dict['beakStatus'] = battery_dict.get('beakStatus', 'Good')
            battery_dict['usage_count'] = battery_dict.get('usage_count', 0)
            
            # Ensure all required fields have default values
            battery_dict['charge'] = battery_dict.get('charge', 0)
            battery_dict['v0'] = battery_dict.get('v0', 0)
            battery_dict['v1'] = battery_dict.get('v1', 0)
            battery_dict['v2'] = battery_dict.get('v2', 0)
            battery_dict['rint'] = battery_dict.get('rint', 0)
            battery_dict['status'] = battery_dict.get('status', 'Unknown')
            
            batteries_list.append(battery_dict)
            
        return jsonify(batteries_list)
    except Exception as e:
        print(f"Error in get_batteries: {e}")  # Debug log
        return jsonify({'error': 'Failed to fetch batteries', 'details': str(e)}), 500

@app.route('/api/batteries/<battery_id>', methods=['GET'])
@login_required()
def get_battery(battery_id):
    """Retrieve a specific battery by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM batteries WHERE id = ?', (battery_id,))
        battery = cursor.fetchone()
        conn.close()
        # In get_batteries and get_battery functions, after fetching from database:
        battery_dict = dict(battery)
        # Ensure consistent field names
        battery_dict['timeScanned'] = battery_dict.get('time_scanned', 'Unknown')
        battery_dict['time_scanned'] = battery_dict.get('time_scanned', 'Unknown')  # Keep both for compatibility
        if not battery:
            return jsonify({'error': 'Battery not found'}), 404
            
        battery_dict = dict(battery)
        battery_dict['beakStatus'] = battery_dict.get('beakStatus', 'Good')
        battery_dict['usage_count'] = battery_dict.get('usage_count', 0)
        
        return jsonify(battery_dict)
    except Exception as e:
        return jsonify({'error': 'Failed to fetch battery', 'details': str(e)}), 500

@app.route('/api/batteries', methods=['POST'])
@login_required()
def create_battery():
    try:
        data = request.get_json()
        print(f"Creating/Updating battery with data: {data}")  # Debug log
        
        # Validate required fields
        # Handle both field names for compatibility
        time_scanned = data.get('timeScanned') or data.get('time_scanned')
        
        # If time_scanned is missing or invalid, generate current timestamp
        if not time_scanned or time_scanned == 'Unknown':
            now = datetime.now()
            time_scanned = f"{now.month}/{now.day}/{now.year}; {now.hour}:{now.minute:02d}:{now.second:02d}"
        
        required_fields = ['id', 'beakStatus', 'charge', 'v0', 'v1', 'v2', 'rint', 'status']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate battery ID format
        battery_id = data['id']
        if not battery_id.startswith('4123') or len(battery_id) != 8 or not battery_id[4:].isdigit():
            return jsonify({'error': 'Battery ID must follow pattern 4123XXXX'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if battery already exists
        cursor.execute('SELECT id FROM batteries WHERE id = ?', (battery_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Battery exists - update it instead
            conn.close()
            return update_existing_battery(battery_id, data, time_scanned)
        
        # Determine usage count - increment if status is "In Use"
        usage_count = 1 if data['status'] == 'In Use' else 0
        
        # Insert battery
        cursor.execute('''
            INSERT INTO batteries (id, time_scanned, usage_count, beakStatus, charge, v0, v1, v2, rint, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            battery_id, 
            time_scanned,
            usage_count, 
            data['beakStatus'], 
            float(data['charge']), 
            float(data['v0']), 
            float(data['v1']), 
            float(data['v2']), 
            float(data['rint']), 
            data['status']
        ))
        
        # Create log entry
        cursor.execute('''
            INSERT INTO battery_logs (battery_id, time_scanned, status, charge, beakStatus, v0, v1, v2, rint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            battery_id, 
            time_scanned,
            data['status'], 
            float(data['charge']), 
            data['beakStatus'], 
            float(data['v0']), 
            float(data['v1']), 
            float(data['v2']), 
            float(data['rint'])
        ))
        
        conn.commit()
        conn.close()
        
        print(f"Battery {battery_id} created successfully")  # Debug log
        return jsonify({'message': 'Battery created successfully', 'id': battery_id})
        
    except Exception as e:
        print(f"Error creating battery: {e}")  # Debug log
        return jsonify({'error': 'Failed to create battery', 'details': str(e)}), 500

def update_existing_battery(battery_id, data, time_scanned):
    """Helper function to update an existing battery"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current battery data
        cursor.execute('SELECT * FROM batteries WHERE id = ?', (battery_id,))
        existing_battery = cursor.fetchone()
        
        if not existing_battery:
            conn.close()
            return jsonify({'error': 'Battery not found'}), 404
        
        # Determine usage count - increment if status is changing to "In Use"
        usage_count = existing_battery['usage_count']
        new_status = data.get('status', existing_battery['status'])
        
        # Increment usage count if changing to "In Use" from any other status
        if existing_battery['status'] != 'In Use' and new_status == 'In Use':
            usage_count += 1
        
        # Update battery with new data
        cursor.execute('''
            UPDATE batteries 
            SET time_scanned = ?, usage_count = ?, beakStatus = ?, charge = ?, 
                v0 = ?, v1 = ?, v2 = ?, rint = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            time_scanned,
            usage_count,
            data.get('beakStatus', existing_battery['beakStatus']),
            float(data.get('charge', existing_battery['charge'])),
            float(data.get('v0', existing_battery['v0'])),
            float(data.get('v1', existing_battery['v1'])),
            float(data.get('v2', existing_battery['v2'])),
            float(data.get('rint', existing_battery['rint'])),
            new_status,
            battery_id
        ))
        
        # Create log entry for the update
        cursor.execute('''
            INSERT INTO battery_logs (battery_id, time_scanned, status, charge, beakStatus, v0, v1, v2, rint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            battery_id,
            time_scanned,
            new_status,
            float(data.get('charge', existing_battery['charge'])),
            data.get('beakStatus', existing_battery['beakStatus']),
            float(data.get('v0', existing_battery['v0'])),
            float(data.get('v1', existing_battery['v1'])),
            float(data.get('v2', existing_battery['v2'])),
            float(data.get('rint', existing_battery['rint']))
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Battery updated successfully', 'id': battery_id})
        
    except Exception as e:
        return jsonify({'error': 'Failed to update battery', 'details': str(e)}), 500
    
@app.route('/api/batteries/<battery_id>', methods=['PUT'])
@login_required()
def update_battery(battery_id):
    """Update an existing battery"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current battery data
        cursor.execute('SELECT * FROM batteries WHERE id = ?', (battery_id,))
        existing_battery = cursor.fetchone()
        
        if not existing_battery:
            conn.close()
            return jsonify({'error': 'Battery not found'}), 404
        
        # Determine usage count - increment if status is changing to "In Use"
        usage_count = existing_battery['usage_count']
        new_status = data.get('status', existing_battery['status'])
        
        # Increment usage count if changing to "In Use" from any other status
        if existing_battery['status'] != 'In Use' and new_status == 'In Use':
            usage_count += 1
        
        time_scanned = data.get('timeScanned') or data.get('time_scanned', existing_battery['time_scanned'])
        
        # Update battery
        cursor.execute('''
            UPDATE batteries 
            SET time_scanned = ?, usage_count = ?, beakStatus = ?, charge = ?, 
                v0 = ?, v1 = ?, v2 = ?, rint = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            time_scanned,
            usage_count,
            data.get('beakStatus', existing_battery['beakStatus']),
            float(data.get('charge', existing_battery['charge'])),
            float(data.get('v0', existing_battery['v0'])),
            float(data.get('v1', existing_battery['v1'])),
            float(data.get('v2', existing_battery['v2'])),
            float(data.get('rint', existing_battery['rint'])),
            new_status,
            battery_id
        ))
        
        # Create log entry for significant changes
        cursor.execute('''
            INSERT INTO battery_logs (battery_id, time_scanned, status, charge, beakStatus, v0, v1, v2, rint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            battery_id,
            data.get('timeScanned', existing_battery['time_scanned']),
            new_status,
            float(data.get('charge', existing_battery['charge'])),
            data.get('beakStatus', existing_battery['beakStatus']),
            float(data.get('v0', existing_battery['v0'])),
            float(data.get('v1', existing_battery['v1'])),
            float(data.get('v2', existing_battery['v2'])),
            float(data.get('rint', existing_battery['rint']))
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Battery updated successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to update battery', 'details': str(e)}), 500

@app.route('/api/batteries/<battery_id>', methods=['DELETE'])
@login_required(role="admin")
def delete_battery(battery_id):
    """Delete a battery and its logs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete logs first
        cursor.execute('DELETE FROM battery_logs WHERE battery_id = ?', (battery_id,))
        # Delete battery
        cursor.execute('DELETE FROM batteries WHERE id = ?', (battery_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Battery deleted successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to delete battery', 'details': str(e)}), 500

@app.route('/api/batteries/<battery_id>/advance-status', methods=['POST'])
@login_required()
def advance_battery_status(battery_id):
    """Advance battery to next status in the cycle"""
    try:
        status_order = [
            "Charging",
            "Cooldown to Robot", 
            "Ready for Robot",
            "In Use",
            "Cooldown to Charge",
            "Ready for Charging"
        ]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current battery data
        cursor.execute('SELECT * FROM batteries WHERE id = ?', (battery_id,))
        battery = cursor.fetchone()
        
        if not battery:
            conn.close()
            return jsonify({'error': 'Battery not found'}), 404
        
        # Determine next status
        current_status = battery['status']
        if current_status not in status_order:
            current_status = "Charging"  # Default to start
        
        current_status_index = status_order.index(current_status)
        next_status_index = (current_status_index + 1) % len(status_order)
        next_status = status_order[next_status_index]
        
        # Update usage count if advancing to "In Use"
        usage_count = battery['usage_count']
        if next_status == "In Use" and current_status != "In Use":
            usage_count += 1
        
        # Update timestamp
        now = datetime.now()
        time_scanned = f"{now.month}/{now.day}/{now.year}; {now.hour}:{now.minute:02d}:{now.second:02d}"
        
        # Update battery
        cursor.execute('''
            UPDATE batteries 
            SET time_scanned = ?, usage_count = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (time_scanned, usage_count, next_status, battery_id))
        
        # Create log entry
        cursor.execute('''
            INSERT INTO battery_logs (battery_id, time_scanned, status, charge, beakStatus, v0, v1, v2, rint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            battery_id, time_scanned, next_status, battery['charge'], 
            battery['beakStatus'], battery['v0'], battery['v1'], battery['v2'], battery['rint']
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Battery status advanced to {next_status}',
            'new_status': next_status,
            'time_scanned': time_scanned
        })
    except Exception as e:
        return jsonify({'error': 'Failed to advance battery status', 'details': str(e)}), 500
    
@app.route('/api/battery-logs', methods=['GET'])
@login_required()
def get_battery_logs():
    """Retrieve battery logs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM battery_logs 
            ORDER BY created_at DESC
        ''')
        logs = cursor.fetchall()
        conn.close()
        
        logs_list = []
        for log in logs:
            log_dict = dict(log)
            logs_list.append(log_dict)
            
        return jsonify(logs_list)
    except Exception as e:
        return jsonify({'error': 'Failed to fetch battery logs', 'details': str(e)}), 500

@app.route('/api/battery-logs/<int:log_id>', methods=['DELETE'])
@login_required(role="admin")
def delete_battery_log(log_id):
    """Delete a battery log entry"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM battery_logs WHERE id = ?', (log_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Log entry deleted successfully'})
    except Exception as e:
        return jsonify({'error': 'Failed to delete log entry', 'details': str(e)}), 500
    
@app.route('/api/debug/batteries', methods=['GET'])
@login_required()
def debug_batteries():
    """Debug endpoint to check batteries table state"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='batteries'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            conn.close()
            return jsonify({'error': 'Batteries table does not exist'}), 500
        
        # Get table schema
        cursor.execute("PRAGMA table_info(batteries)")
        schema = cursor.fetchall()
        
        # Get all batteries
        cursor.execute('SELECT * FROM batteries')
        batteries = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'table_exists': table_exists,
            'schema': [dict(col) for col in schema],
            'batteries': [dict(battery) for battery in batteries],
            'count': len(batteries)
        })
    except Exception as e:
        return jsonify({'error': 'Debug failed', 'details': str(e)}), 500
    
@app.route('/api/debug/batteries-test', methods=['GET'])
@login_required()
def debug_batteries_test():
    """Simple test endpoint to check battery data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Simple query to test
        cursor.execute('SELECT id, status, charge FROM batteries LIMIT 5')
        batteries = cursor.fetchall()
        conn.close()
        
        batteries_list = [dict(battery) for battery in batteries]
        return jsonify({'success': True, 'batteries': batteries_list, 'count': len(batteries_list)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/api/debug/batteries-table', methods=['GET'])
@login_required()
def debug_batteries_table():
    """Debug endpoint to check batteries table structure"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check table structure
        cursor.execute("PRAGMA table_info(batteries)")
        table_info = cursor.fetchall()
        
        # Check if table exists and has data
        cursor.execute("SELECT COUNT(*) as count FROM batteries")
        count = cursor.fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'table_exists': True,
            'columns': [dict(col) for col in table_info],
            'row_count': count
        })
    except Exception as e:
        return jsonify({'error': 'Debug failed', 'details': str(e)}), 500
    
    
    
        
    
    
    

# ==================== SCORING & DATA PROCESSING FUNCTIONS ====================

"""Calculates total score for a game section based on configuration values and performance data."""
def score_obj(section, conf_section):
    if not section or not conf_section:
        return 0
    total = 0
    for k, v in section.items():
        if k not in conf_section:
            continue
        c = conf_section[k]
        
        # Handle Boolean with Value fields (stored as numbers)
        if isinstance(v, (int, float)) and isinstance(c, dict) and (c.get('type') == 'Boolean with Value' or c.get('Type') == 'Boolean with Value'):
            total += int(v)
        elif isinstance(v, dict) and 'Made' in v:
            if 'Value' in c and isinstance(c['Value'], (int, float)):
                total += (int(v.get('Made', 0)) * int(c['Value']))
        elif isinstance(v, bool):
            if isinstance(c, dict) and 'Value' in c and isinstance(c['Value'], (int, float)):
                total += int(c['Value']) if v else 0
            elif isinstance(c, (int, float)):
                total += int(c) if v else 0
        # Handle regular numeric values
        elif isinstance(v, (int, float)):
            total += int(v)
    return total

"""Calculates autonomous period score using the score_obj function with auto configuration."""
def auto_score(data, conf):
    return score_obj(data, conf.get('match_form', {}).get('auto_period', {}))

"""Calculates teleoperated period score using the score_obj function with teleop configuration."""
def tele_score(data, conf):
    return score_obj(data, conf.get('match_form', {}).get('teleop_period', {}))

"""Calculates endgame score based on final robot status from configuration values."""
def endgame_score(data, conf):
    final_status_config = conf.get('match_form', {}).get('endgame', {}).get('final_status', {})
    status = data.get('final_status', '')
    if 'options' in final_status_config and 'values' in final_status_config:
        options = final_status_config['options']
        values = final_status_config['values']
        if status in options:
            index = options.index(status)
            return int(values[index]) if index < len(values) else 0
        return 0
    else:
        status_config = final_status_config.get(status, {})
        return int(status_config.get('Value', 0)) if status_config else 0

"""Converts a list of dictionaries to CSV format with proper escaping and formatting."""
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

"""Calculate ranking metric based on the option name and config"""
def calculate_ranking_metric(option, matches, conf):
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
        return 0







# ==================== USER MANAGEMENT ENDPOINTS ====================

"""Creates a new user with the specified username, password, and role (admin only)."""
@app.route('/api/users', methods=['POST'])
@login_required(role="admin")
def create_user():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'scout')
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                (username, password_hash, role)
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return jsonify({'message': 'User created successfully', 'user_id': user_id})
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'Username already exists'}), 400
    except Exception as e:
        return jsonify({'error': 'User creation failed', 'details': str(e)}), 500

"""Deletes a user by ID, preventing self-deletion (admin only)."""
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required(role="admin")
def delete_user(user_id):
    try:
        # Prevent deleting your own account
        auth_header = request.headers.get('Authorization')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE auth_token = ?', (auth_header,))
        current_user = cursor.fetchone()
        
        if current_user and current_user['id'] == user_id:
            conn.close()
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'error': 'User deletion failed', 'details': str(e)}), 500

"""Retrieves a list of all users with their basic information (admin only)."""
@app.route('/api/users', methods=['GET'])
@login_required(role="admin")
def get_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, role, created_at FROM users ORDER BY username')
        users = cursor.fetchall()
        conn.close()
        return jsonify([dict(user) for user in users])
    except Exception as e:
        return jsonify({'error': 'Failed to fetch users', 'details': str(e)}), 500







# ==================== AUTHENTICATION ENDPOINTS ====================

"""Authenticates a user with username and password, returning an auth token on success."""
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        #print(f"Login attempt: username={username}, password={password}")
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, username, role FROM users WHERE username = ? AND password_hash = ?',
            (username, password_hash)
        )
        user = cursor.fetchone()
        conn.close()
        #print(f"User found: {user}")
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        auth_token = secrets.token_hex(16)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET auth_token = ? WHERE id = ?',
            (auth_token, user['id'])
        )
        conn.commit()
        conn.close()
        #print(f"Login successful, token: {auth_token}")
        return jsonify({
            'message': 'Login successful',
            'token': auth_token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role']
            }
        })
    except Exception as e:
        #print(f"Login error: {e}")
        return jsonify({'error': 'Login failed', 'details': str(e)}), 500

"""Registers a new user (admin only endpoint)."""
@app.route('/api/register', methods=['POST'])
@login_required(role="admin")
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'scout')
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                (username, password_hash, role)
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return jsonify({'message': 'User created successfully', 'user_id': user_id})
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'Username already exists'}), 400
    except Exception as e:
        return jsonify({'error': 'Registration failed', 'details': str(e)}), 500

"""Returns information about the currently authenticated user based on their auth token."""
@app.route('/api/user', methods=['GET'])
def get_current_user():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Authorization required'}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, username, role FROM users WHERE auth_token = ?',
        (auth_header,)
    )
    user = cursor.fetchone()
    conn.close()
    if not user:
        return jsonify({'error': 'Invalid token'}), 401
    
    return jsonify(dict(user))

"""Invalidates the current user's authentication token, effectively logging them out."""
@app.route('/api/logout', methods=['POST'])
def logout():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Authorization required'}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET auth_token = NULL WHERE auth_token = ?',
        (auth_header,)
    )
    conn.commit()
    if cursor.rowcount > 0:
        conn.close()
        return jsonify({'message': 'Logged out successfully'})
    else:
        conn.close()
        return jsonify({'error': 'Invalid token or already logged out'}), 400







# ==================== DEBUG ENDPOINTS ====================

"""Debug endpoint to view all user authentication tokens."""
@app.route('/api/debug/tokens', methods=['GET'])
def debug_tokens():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, auth_token FROM users')
    users = cursor.fetchall()
    conn.close()
    return jsonify([dict(user) for user in users])

"""Debug endpoint to see all user data including passwords (admin only)."""
@app.route('/api/debug/users', methods=['GET'])
@login_required(role="admin")
def debug_users():
    """Debug endpoint to see all user data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users')
        users = cursor.fetchall()
        conn.close()
        return jsonify([dict(user) for user in users])
    except Exception as e:
        return jsonify({'error': 'Failed to fetch users', 'details': str(e)}), 500

"""Debug endpoint to check authentication status and validate tokens."""
@app.route('/api/debug/check-auth', methods=['GET'])
def debug_check_auth():
    """Debug endpoint to check authentication status"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'authenticated': False, 'message': 'No authorization header'})
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, role FROM users WHERE auth_token = ?', (auth_header,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return jsonify({'authenticated': True, 'user': dict(user)})
    else:
        return jsonify({'authenticated': False, 'message': 'Invalid token'})







# ==================== CHECKLIST MANAGEMENT ENDPOINTS ====================

checklist_state = {}
checklist_lock = threading.Lock()

"""Retrieves all checklist items from the database."""
@app.route('/api/checklist', methods=['GET'])
def get_checklist():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM checklist_items')
        rows = cursor.fetchall()
        conn.close()
       #print("Database checklist items:")
        #for row in rows:
            #print(f"  Key: {row['checklist_key']}, Checked: {row['checked_json']}")
        checklist_data = {}
        for row in rows:
            checklist_data[row['checklist_key']] = {
                'title': row['title'],
                'options': json.loads(row['options_json']),
                'checked': json.loads(row['checked_json'])
            }
        return jsonify(checklist_data)
    except Exception as e:
        print(f"Error getting checklist: {e}")
        return jsonify({'error': 'db', 'details': str(e)}), 500

"""Updates or creates a checklist item with the specified checked items."""
@app.route('/api/checklist/<path:checklist_key>', methods=['POST'])
def update_checklist(checklist_key):
    try:
        # URL decode the key if needed
        from urllib.parse import unquote
        checklist_key = unquote(checklist_key)
        
        data = request.get_json()
        checked_items = data.get('checked', [])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM checklist_items WHERE checklist_key = ?', (checklist_key,))
        row = cursor.fetchone()
        if row:
            cursor.execute('''
                UPDATE checklist_items 
                SET checked_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE checklist_key = ?
            ''', (json.dumps(checked_items), checklist_key))
        else:
            conf = read_config()
            checklist_config = None
            home_body = conf.get('Home', {}).get('body', {})
            if checklist_key in home_body and home_body[checklist_key].get('type') == 'checklist':
                checklist_config = home_body[checklist_key]
            if not checklist_config:
                pit_body = conf.get('pitProcedures', {}).get('body', {})
                if checklist_key in pit_body and pit_body[checklist_key].get('type') == 'checklist':
                    checklist_config = pit_body[checklist_key]
            if not checklist_config:
                conn.close()
                return jsonify({'error': 'Checklist not found in config'}), 404
            cursor.execute('''
                INSERT INTO checklist_items (checklist_key, title, options_json, checked_json)
                VALUES (?, ?, ?, ?)
            ''', (
                checklist_key,
                checklist_config.get('title', 'Checklist'),
                json.dumps(checklist_config.get('options', [])),
                json.dumps(checked_items)
            ))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print(f"Error updating checklist: {e}")
        return jsonify({'error': 'update', 'details': str(e)}), 500







# ==================== STATIC FILE SERVING ENDPOINTS ====================

"""Serves the main index.html file from the public directory."""
@app.route('/')
def serve_index():
    return send_from_directory(PUBLIC_DIR, 'index.html')

"""Serves static files from the public directory."""
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(PUBLIC_DIR, path)

"""Serves uploaded files from the uploads directory."""
@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)








# ==================== CONFIGURATION ENDPOINT ====================

"""Returns the current application configuration from config.json."""
@app.route('/api/config', methods=['GET'])
def get_config():
    try:
        return jsonify(read_config())
    except Exception as e:
        return jsonify({'error': 'config', 'details': str(e)}), 500







# ==================== FILE UPLOAD ENDPOINT ====================

"""Handles file uploads and stores them in the uploads directory with unique filenames."""
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







# ==================== MATCH DATA ENDPOINTS ====================

"""Creates a new match record with scoring data and calculates points based on configuration."""

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

"""Retrieves match records with pagination support and JSON parsing."""
@app.route('/api/matches', methods=['GET'])
def get_matches():
    try:
        conf = read_config()
        cap = conf.get('limits', {}).get('raw_table_cap', 50)
        limit = int(request.args.get('limit', cap))
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

"""Updates an existing match record with new data (admin only)."""
@app.route('/api/matches/<int:match_id>', methods=['PUT'])
@login_required(role="admin")
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

"""Deletes a match record by ID (admin only)."""
@app.route('/api/matches/<int:match_id>', methods=['DELETE'])
@login_required(role="admin")
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







# ==================== REINDEX ENDPOINT ====================

"""Reindexes the matches table to fix ID gaps and maintain sequential ordering"""
@app.route('/api/matches/reindex', methods=['POST'])
@login_required(role="admin")
def reindex_matches():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches ORDER BY id ASC')
        matches = cursor.fetchall()
        cursor.execute('''
            CREATE TEMPORARY TABLE matches_temp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                pre_match_json TEXT,
                auto_json TEXT,
                teleop_json TEXT,
                endgame_json TEXT,
                misc_json TEXT
            )
        ''')
        for match in matches:
            cursor.execute('''
                INSERT INTO matches_temp (created_at, pre_match_json, auto_json, teleop_json, endgame_json, misc_json)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (match['created_at'], match['pre_match_json'], match['auto_json'], 
                  match['teleop_json'], match['endgame_json'], match['misc_json']))
        cursor.execute('DROP TABLE matches')
        cursor.execute('''
            CREATE TABLE matches(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                pre_match_json TEXT NOT NULL,
                auto_json TEXT NOT NULL,
                teleop_json TEXT NOT NULL,
                endgame_json TEXT NOT NULL,
                misc_json TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            INSERT INTO matches (id, created_at, pre_match_json, auto_json, teleop_json, endgame_json, misc_json)
            SELECT id, created_at, pre_match_json, auto_json, teleop_json, endgame_json, misc_json 
            FROM matches_temp 
            ORDER BY id
        ''')
        cursor.execute('DROP TABLE matches_temp')
        conn.commit()
        conn.close()
        return jsonify({
            'message': 'Matches reindexed successfully',
            'reindexed_count': len(matches)
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': 'reindex failed', 'details': str(e)}), 500
    
    
    
    
    
    
    
# ==================== PIT SCOUTING ENDPOINTS ====================

"""Creates a new pit scouting record with optional image path."""
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

"""Retrieves pit scouting records with pagination support."""
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

"""Updates an existing pit scouting record (admin only)."""
@app.route('/api/pits/<int:pit_id>', methods=['PUT'])
@login_required(role="admin")
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

"""Deletes a pit scouting record by ID (admin only)."""
@app.route('/api/pits/<int:pit_id>', methods=['DELETE'])
@login_required(role="admin")
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







# ==================== TEAM DATA ENDPOINTS ====================

"""Calculates and returns average scores for a specific team across all their matches."""
@app.route('/api/team/<team>/averages', methods=['GET'])
def get_team_averages(team):
    try:
        conf = read_config()
        match_type_filter = request.args.get('match_type', 'all')
        event_code_filter = request.args.get('event_code', 'all')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches ORDER BY id')
        all_matches = cursor.fetchall()
        conn.close()

        team_matches = []
        for row in all_matches:
            pre_match_data = json.loads(row['pre_match_json'])
            if str(pre_match_data.get('team_number')) != str(team):
                continue

            match_type = pre_match_data.get('match_type', 'Unknown')
            event_code = pre_match_data.get('event_code', 'Unknown')

            if match_type_filter != 'all' and match_type != match_type_filter:
                continue
            if event_code_filter != 'all' and event_code != event_code_filter:
                continue

            team_matches.append(row)

        if not team_matches:
            return jsonify({
                'team': team, 'matches': 0,
                'avg_auto': 0, 'avg_teleop': 0,
                'avg_endgame': 0, 'avg_total': 0
            })

        auto_total = tele_total = end_total = 0
        for row in team_matches:
            auto_total += auto_score(json.loads(row['auto_json']), conf)
            tele_total += tele_score(json.loads(row['teleop_json']), conf)
            end_total += endgame_score(json.loads(row['endgame_json']), conf)

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


"""Retrieves all match data for a specific team with calculated scoring."""
@app.route('/api/team/<team>/matches', methods=['GET'])
def get_team_matches(team):
    try:
        conf = read_config()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches ORDER BY id ASC')
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

"""Retrieves external team information using a scraper script (team_name_scraper.py) with fallback defaults."""
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

"""Retrieves pit scouting data for a specific team."""
@app.route('/api/team/<team>/pit', methods=['GET'])
def get_team_pit(team):
    try:
       #print(f"Looking for pit data for team: {team} (type: {type(team)})")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, pit_json FROM pits')
        all_pits = cursor.fetchall()
       #print("All pit entries:")
        #for pit in all_pits:
            #pit_json = json.loads(pit['pit_json'])
            #print(f"  ID {pit['id']}: Team {pit_json.get('team_number')} (type: {type(pit_json.get('team_number'))})")
        cursor.execute('''
            SELECT * FROM pits 
            WHERE json_extract(pit_json, '$.team_number') = ?
            ORDER BY id DESC LIMIT 1
        ''', (team,))
        row = cursor.fetchone()
        if not row:
            #print("Team not found with string match, trying integer...")
            if team.isdigit():
                cursor.execute('''
                    SELECT * FROM pits 
                    WHERE json_extract(pit_json, '$.team_number') = ?
                    ORDER BY id DESC LIMIT 1
                ''', (int(team),))
                row = cursor.fetchone()
        conn.close()
        if not row:
            #print(f"No pit data found for team {team}")
            return jsonify({'error': 'not found'}), 404
        pit_data = dict(row)
        pit_data['pit_json'] = json.loads(row['pit_json'])
        #print(f"Found pit data: {pit_data}")
        return jsonify(pit_data)
    except Exception as e:
        print(f"Error getting pit data: {e}")
        return jsonify({'error': 'db', 'details': str(e)}), 500







# ==================== RANKINGS ENDPOINT ====================

"""Generates team rankings based on various statistical metrics and filtering options."""
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM matches ORDER BY id')
        all_matches = cursor.fetchall()
        conn.close()
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
        rankings = []
        for team_number, matches in team_matches.items():
            if len(matches) < min_matches:
                continue
            if team_filter and team_number != team_filter:
                continue
            metric_value = calculate_ranking_metric(option, matches, conf)
            rankings.append({
                'team_number': team_number,
                'matches_count': len(matches),
                'metric_value': metric_value
            })
        rankings.sort(key=lambda x: x['metric_value'], reverse=True)
        return jsonify({
            'option': option,
            'description': spec.get('description', option),
            'rows': rankings[:100]
        })
    except Exception as e:
        return jsonify({'error': 'db', 'details': str(e)}), 500







# ==================== DATA EXPORT ENDPOINTS ====================

"""Exports all match data as a CSV file download."""
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

"""Exports all pit scouting data as a CSV file download."""
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







# ==================== CSV UPLOAD ENDPOINT ====================

"""Handles CSV file uploads for importing match or pit data into the database."""
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
        stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_data = csv.DictReader(stream)
        first_row = next(csv_data, None)
        if not first_row:
            return jsonify({'error': 'Empty CSV file'}), 400
        stream.seek(0)
        csv_data = csv.DictReader(stream)
        conn = get_db_connection()
        cursor = conn.cursor()
        records_processed = 0
        errors = []
        if 'pre_match_json' in first_row:
            for i, row in enumerate(csv_data):
                try:
                    pre_match_json = json.loads(row['pre_match_json']) if row['pre_match_json'] else {}
                    auto_json = json.loads(row['auto_json']) if row['auto_json'] else {}
                    teleop_json = json.loads(row['teleop_json']) if row['teleop_json'] else {}
                    endgame_json = json.loads(row['endgame_json']) if row['endgame_json'] else {}
                    misc_json = json.loads(row['misc_json']) if row['misc_json'] else {}
                    cursor.execute('SELECT id FROM matches WHERE id = ?', (row['id'],))
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute('''
                            UPDATE matches SET pre_match_json=?, auto_json=?, teleop_json=?, endgame_json=?, misc_json=?
                            WHERE id=?
                        ''', (json.dumps(pre_match_json), json.dumps(auto_json), json.dumps(teleop_json), 
                              json.dumps(endgame_json), json.dumps(misc_json), row['id']))
                    else:
                        cursor.execute('''
                            INSERT INTO matches(id, created_at, pre_match_json, auto_json, teleop_json, endgame_json, misc_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (row['id'], row['created_at'], json.dumps(pre_match_json), json.dumps(auto_json),
                              json.dumps(teleop_json), json.dumps(endgame_json), json.dumps(misc_json)))
                    records_processed += 1
                except Exception as e:
                    errors.append(f"Row {i+1}: {str(e)}")
        elif 'pit_json' in first_row:
            for i, row in enumerate(csv_data):
                try:
                    pit_json = json.loads(row['pit_json']) if row['pit_json'] else {}
                    image_path = row.get('image_path', '')
                    cursor.execute('SELECT id FROM pits WHERE id = ?', (row['id'],))
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute('''
                            UPDATE pits SET pit_json=?, image_path=?
                            WHERE id=?
                        ''', (json.dumps(pit_json), image_path, row['id']))
                    else:
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

# ==================== MAIN APPLICATION ENTRY POINT ====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)