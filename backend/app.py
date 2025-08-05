"""
Court Data Fetcher & Mini-Dashboard - Main Flask Application
Target: Delhi High Court (https://delhihighcourt.nic.in/)
"""

import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import logging
from scraper import CourtDataFetcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../frontend', static_folder='../frontend/static')
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Database configuration
DATABASE = os.path.join('database', 'court_data.db')

def init_database():
    """Initialize SQLite database"""
    # Ensure database directory exists
    os.makedirs('database', exist_ok=True)
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create query logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_type TEXT NOT NULL,
            case_number TEXT NOT NULL,
            filing_year TEXT NOT NULL,
            query_timestamp TEXT NOT NULL,
            response_data TEXT,
            success BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create case cache table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS case_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_key TEXT UNIQUE NOT NULL,
            case_data TEXT NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create statistics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS query_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            total_queries INTEGER DEFAULT 0,
            successful_queries INTEGER DEFAULT 0,
            failed_queries INTEGER DEFAULT 0,
            unique_cases INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

def log_query(case_type, case_number, filing_year, response_data, success=True):
    """Log query and response to database"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO query_logs (case_type, case_number, filing_year, 
                                  query_timestamp, response_data, success)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            case_type, case_number, filing_year,
            datetime.now().isoformat(),
            json.dumps(response_data),
            success
        ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error logging query: {str(e)}")

# Initialize database and fetcher
init_database()
fetcher = CourtDataFetcher()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/case-types')
def get_case_types():
    """API endpoint to get available case types"""
    try:
        case_types = fetcher.get_case_types()
        return jsonify({
            'success': True,
            'data': case_types
        })
    except Exception as e:
        logger.error(f"Error fetching case types: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch case types'
        }), 500

@app.route('/api/fetch-case', methods=['POST'])
def fetch_case():
    """API endpoint to fetch case data"""
    try:
        data = request.get_json()
        
        case_type = data.get('case_type', '').strip()
        case_number = data.get('case_number', '').strip()
        filing_year = data.get('filing_year', '').strip()
        
        # Validate inputs
        if not all([case_type, case_number, filing_year]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
        
        # Validate year
        try:
            year = int(filing_year)
            current_year = datetime.now().year
            if year < 2000 or year > current_year:
                raise ValueError("Invalid year")
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Filing year must be between 2000 and {datetime.now().year}'
            }), 400
        
        # Validate case number (basic validation)
        if not case_number.isdigit() or len(case_number) > 10:
            return jsonify({
                'success': False,
                'error': 'Case number must be a valid number'
            }), 400
        
        # Fetch case data
        result = fetcher.fetch_case_data(case_type, case_number, filing_year)
        
        # Log the query
        log_query(case_type, case_number, filing_year, result, result.get('success', False))
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error in fetch_case endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/query-history')
def query_history():
    """Get query history"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        offset = (page - 1) * per_page
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute('SELECT COUNT(*) FROM query_logs')
        total_count = cursor.fetchone()[0]
        
        # Get paginated results
        cursor.execute('''
            SELECT case_type, case_number, filing_year, query_timestamp, success
            FROM query_logs 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        ''', (per_page, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            history.append({
                'case_type': row[0],
                'case_number': row[1],
                'filing_year': row[2],
                'timestamp': row[3],
                'success': bool(row[4])
            })
        
        return jsonify({
            'success': True, 
            'data': history,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': (total_count + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching query history: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get dashboard statistics"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Total queries
        cursor.execute('SELECT COUNT(*) FROM query_logs')
        total_queries = cursor.fetchone()[0]
        
        # Successful queries
        cursor.execute('SELECT COUNT(*) FROM query_logs WHERE success = 1')
        successful_queries = cursor.fetchone()[0]
        
        # Failed queries
        cursor.execute('SELECT COUNT(*) FROM query_logs WHERE success = 0')
        failed_queries = cursor.fetchone()[0]
        
        # Unique cases
        cursor.execute('SELECT COUNT(DISTINCT case_type || case_number || filing_year) FROM query_logs')
        unique_cases = cursor.fetchone()[0]
        
        # Recent activity (last 7 days)
        cursor.execute('''
            SELECT DATE(query_timestamp) as date, COUNT(*) as count
            FROM query_logs 
            WHERE query_timestamp >= datetime('now', '-7 days')
            GROUP BY DATE(query_timestamp)
            ORDER BY date
        ''')
        recent_activity = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_queries': total_queries,
                'successful_queries': successful_queries,
                'failed_queries': failed_queries,
                'unique_cases': unique_cases,
                'success_rate': round((successful_queries / total_queries * 100) if total_queries > 0 else 0, 2),
                'recent_activity': [{'date': row[0], 'count': row[1]} for row in recent_activity]
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Mock PDF download endpoint"""
    try:
        import tempfile
        
        # Create a temporary file with mock content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(f"DELHI HIGH COURT\n")
            f.write(f"{'='*50}\n\n")
            f.write(f"Document: {filename}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("This is a demonstration document.\n")
            f.write("In a real implementation, this would be an actual court document.\n\n")
            f.write("CAPTCHA Strategy Notes:\n")
            f.write("- Use headless browser automation (Playwright/Selenium)\n")
            f.write("- Implement OCR for CAPTCHA solving\n")
            f.write("- Consider third-party CAPTCHA solving services\n")
            f.write("- Implement retry mechanisms with exponential backoff\n")
            f.write("- Cache session tokens to minimize CAPTCHA encounters\n")
            temp_path = f.name
        
        return send_file(temp_path, as_attachment=True, download_name=filename.replace('.txt', '.pdf'))
        
    except Exception as e:
        logger.error(f"Error serving file {filename}: {str(e)}")
        return jsonify({'error': 'File not found'}), 404

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Court Data Fetcher on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Database: {DATABASE}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
