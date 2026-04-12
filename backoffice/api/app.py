import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def get_db_connection():
    return psycopg2.connect(
        host="database-moodiot",
        database="mood_iot",
        user="admin",
        password="admin",
        cursor_factory=RealDictCursor
    )

@app.route('/getUserData', methods=['POST'])
def get_user_data():
    data = request.json
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({"error": "L'identifiant 'user_id' est requis"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = """
            SELECT u.firstname, l.lat, l.lon, l.recorded_at, l.altitude
            FROM users u
            JOIN locations l ON u.id = l.user_id
            WHERE u.id = %s
            ORDER BY l.recorded_at DESC;
        """
        cur.execute(query, (user_id,))
        results = cur.fetchall()
        
        cur.close()
        return jsonify(results), 200

    except Exception as e:
        print(f"Erreur SQL: {e}")
        return jsonify({"error": "Erreur lors de la récupération des données"}), 500
    
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("Application Mood IoT API is running...")
    app.run(host='0.0.0.0', port=5000, debug=True)