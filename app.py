import os
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash
import json

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

def get_db():
    required_vars = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306))
        )
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        raise

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/student', methods=['GET', 'POST'])
def student():
    if request.method == 'POST':
        name = request.form['name'].strip()
        regno = request.form['regno'].strip()
        course = request.form['course'].strip()
        department = request.form['department'].strip()
        provider = request.form['provider'].strip()
        email = request.form['email'].strip()
        certificate_links = [link.strip() for link in request.form.getlist('certificate_links') if link.strip()]

        if not (name and regno and course and department and provider and email and certificate_links):
            flash("Please fill all fields and provide at least one certificate link.", "error")
            return redirect(url_for('student'))

        try:
            db = get_db()
            with db.cursor() as cursor:
                # Check if student exists
                cursor.execute("SELECT * FROM students WHERE regno = %s AND email = %s", (regno, email))
                student = cursor.fetchone()

                if not student:
                    flash("You are not a registered student. Submission denied.", "error")
                    return redirect(url_for('student'))

                # Convert certificate_links to a JSON string
                links_json = json.dumps(certificate_links)

                # Insert all data into a single row
                cursor.execute("""
                    INSERT INTO student_certificates 
                    (name, regno, course, department, provider, email, certificate_links)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (name, regno, course, department, provider, email, links_json))

                db.commit()
                flash("Your certificate submission was successful!", "success")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
            return redirect(url_for('student'))
        finally:
            db.close()

    return render_template("student.html")

@app.route('/studentview', methods=['GET', 'POST'])
def studentview():
    student_data = []
    if request.method == 'POST':
        regno = request.form['regno'].strip().lower()
        name = request.form['name'].strip().lower()
        email = request.form['email'].strip().lower()

        try:
            db = get_db()
            with db.cursor() as cursor:
                cursor.execute("""
                    SELECT name, regno, course, department, provider, email, certificate_links
                    FROM student_certificates
                    WHERE LOWER(name) = %s AND LOWER(regno) = %s AND LOWER(email) = %s
                """, (name, regno, email))
                student_data = cursor.fetchall()
                
                # Parse JSON links
                for i, row in enumerate(student_data):
                    row = list(row)
                    try:
                        row[6] = json.loads(row[6])  # Convert JSON string back to list
                    except json.JSONDecodeError:
                        row[6] = []
                    student_data[i] = row
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            db.close()

        if not student_data:
            flash("No submissions found for the given details.", "error")

    return render_template("studentview.html", student=student_data)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        try:
            db = get_db()
            with db.cursor() as cur:
                cur.execute("SELECT * FROM admin_users WHERE username = %s AND password = %s", (username, password))
                admin = cur.fetchone()
                
                if admin:
                    session['admin_logged_in'] = True
                    return redirect(url_for('adminview'))
                else:
                    flash("Invalid username or password.", "error")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            db.close()

    return render_template("admin.html")

@app.route('/adminview')
def adminview():
    if not session.get('admin_logged_in'):
        flash("Please log in as admin to access this page.", "error")
        return redirect(url_for('admin'))

    parsed_data = []
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("""
                SELECT name, regno, course, department, provider, email, certificate_links
                FROM student_certificates ORDER BY department
            """)
            all_data = cur.fetchall()
            # Parse JSON links
            for row in all_data:
                row = list(row)
                try:
                    row[6] = json.loads(row[6])  # Convert JSON string to list
                except json.JSONDecodeError:
                    row[6] = []  # Fallback to empty list if JSON is invalid
                parsed_data.append(row)
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
    finally:
        db.close()
    
    return render_template("adminview.html", submissions=parsed_data)

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash("Logged out successfully.", "success")
    return redirect(url_for('home'))
