# Imports modules which handles the database
import json
import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")  # Holds the database's URL


# Establishes connection between the program and the database
def get_connection():
    return psycopg2.connect(DATABASE_URL)


# Ensures the structure of the database is in the desired form and establishes it newly if it's missing 1610390844
def ensure_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_details (
                    user_id BIGINT PRIMARY KEY,
                    gender VARCHAR(1),
                    age INTEGER,
                    country VARCHAR(25),
                    reports INTEGER,
                    reporters TEXT,
                    vote_up INTEGER,
                    vote_down INTEGER,
                    voters TEXT,
                    feedback_track JSONB,
                    partner_id BIGINT
            )
        """)
        conn.commit()


# Function which stores the details of the users in the database
def save_user_data(data: dict, dirty_user: set):
    ensure_db()

    QUERY = """
            INSERT INTO user_details (
                user_id, gender, age, country, reports, reporters, 
                vote_up, vote_down, voters, feedback_track, partner_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                gender = EXCLUDED.gender,
                age = EXCLUDED.age,
                country = EXCLUDED.country,
                reports = EXCLUDED.reports,
                reporters = EXCLUDED.reporters,
                vote_up = EXCLUDED.vote_up,
                vote_down = EXCLUDED.vote_down,
                voters = EXCLUDED.voters,
                feedback_track = EXCLUDED.feedback_track,
                partner_id = EXCLUDED.partner_id
    """

    with get_connection() as conn:
        cursor = conn.cursor()

        values = []

        for user_id in list(dirty_user):
            details = data.get(user_id)
            if details is None:
                continue

            values.append((
                user_id,
                details.get("gender"),
                details.get("age"),
                details.get("country"),
                details.get("reports", 0),
                json.dumps(details.get("reporters", [])),
                details.get("votes", {}).get("up", 0),
                details.get("votes", {}).get("down", 0),
                json.dumps(details.get("voters", [])),
                json.dumps(details.get("feedback_track", {})),
                details.get("partner_id", None)
            ))

        if values:
            cursor.executemany(QUERY, values)

        conn.commit()
        dirty_user.clear()

        print("✅ User Data Saved to Drive Successfully.")


# Function which returns the users' details it read from the database
def load_user_data() -> dict:
    ensure_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_details")
        rows = cursor.fetchall()

        data = {}
        for row in rows:
            user_id = row[0]
            data[user_id] = {
                "gender": row[1],
                "age": row[2],
                "country": row[3],
                "reports": row[4],
                "reporters": json.loads(row[5]),
                "votes": {
                    "up": row[6],
                    "down": row[7],
                },
                "voters": json.loads(row[8]),
                "feedback_track": row[9],
                "partner_id": row[10],
            }
        return data
