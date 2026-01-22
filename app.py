import pymysql
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, join_room, leave_room, emit
import psycopg2



def get_db_connection():
    return pymysql.connect(host="localhost", user="root", password="", database="tutoring" )

app = Flask(__name__)
app.secret_key = "your_secret_key" 
socketio = SocketIO(app) 

@app.route("/")
def index():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        connection = get_db_connection()
        cursor = connection.cursor()

        print(f"Attempting login for email: {email}")
        try:
            query = "SELECT s_id, email, password,department FROM student WHERE email = %s"
            cursor.execute(query, (email,))
            student = cursor.fetchone()

            if student:
                print("User found in the database.")
                stored_password = student[2]

                if stored_password == password:
                    session['role'] = "student"
                    session['email'] = email
                    session['s_id'] = student[0]
                    session['user_id'] = student[0]  
                    session['user_name'] = student[1]
                    session['dept'] = student[3]
                    return redirect(url_for("home1")) 
                else:
                    flash("Invalid password", "error")
                    return render_template("login.html")
            else:
                query = "SELECT t_id, name, email, password, department, per_hour_charge, available_slot FROM tutor WHERE email = %s "
                cursor.execute(query,(email,))
                tutor = cursor.fetchone()
                if tutor:
                    t_id, t_name, t_email, t_pass, t_dept,t_per_hour_charge, t_available_slot = tutor
                    if t_pass == password:
                        session["role"] = "tutor"
                        session["email"] = t_email
                        session["t_id"] = t_id
                        session["user_id"] = t_id
                        session["user_name"] = t_name
                        session["dept"] = t_dept
                        session['per_hour_charge'] = t_per_hour_charge
                        session["available_slot"] = t_available_slot
                        return redirect(url_for("tutor_home"))
                    else:
                        flash("Invalid password", "error")
                        return render_template("login.html")
        finally:
            cursor.close()
            connection.close()

    return render_template("login.html")

@app.route("/tutor_home")
def tutor_home():
    if 'user_id' not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))
    return render_template("tutor_home.html")

@app.route("/home1")
def home1():
    if 'user_id' not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))
    
    
    return render_template("home1.html")

@app.route('/logout')
def logout():
    session.pop('user_id', None) 
    session.pop('user_name', None)  
    
    return redirect(url_for('login'))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user_type      = request.form.get("user")
        name           = request.form.get("name")
        email          = request.form.get("email")
        department     = request.form.get("department")
        password       = request.form.get("password")
        cgpa_raw       = (request.form.get("cgpa") or "").strip()
        charge_raw     = (request.form.get("charge") or "").strip()
        available_slot = (request.form.get("available_slot") or "").strip()
        offered_raw    = (request.form.get("offered_courses") or "").strip()

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            if user_type == "Student":
                cursor.execute(
                    """
                    INSERT INTO student (name, email, department, password)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (name, email, department, password)
                )

            elif user_type == "Tutor":
                if not all([cgpa_raw, charge_raw, available_slot]):
                    flash("CGPA, Charge, and Available Slot are required for teachers.", "error")
                    return render_template("register.html")

                try:
                    cgpa = float(cgpa_raw)
                    charge = float(charge_raw)
                except ValueError:
                    flash("Invalid CGPA or Charge value.", "error")
                    return render_template("register.html")

                cursor.execute(
                    """
                    INSERT INTO tutor (name, email, department, password, cgpa, per_hour_charge, available_slot)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (name, email, department, password, cgpa, charge, available_slot)
                )

                t_id = cursor.lastrowid

                if not t_id:
                    cursor.execute("SELECT t_id FROM tutor WHERE email = %s ORDER BY t_id DESC LIMIT 1", (email,))
                    row = cursor.fetchone()
                    if not row:
                        raise Exception("Could not retrieve tutor id after insert.")
                    t_id = row[0]

                if offered_raw:
                    courses = [c.strip() for c in offered_raw.split(",") if c.strip()]
                    seen = set()
                    courses = [c for c in courses if not (c in seen or seen.add(c))]
                    if courses:
                        cursor.executemany(
                            "INSERT INTO offers (t_id, course_code) VALUES (%s, %s)",
                            [(t_id, oc) for oc in courses]
                        )

            else:
                flash("Unknown user type.", "error")
                return render_template("register.html")

            conn.commit()
            flash("Registration successful!", "success")
            return redirect(url_for("login"))

        except Exception as e:
            conn.rollback()
            flash(f"Registration failed: {str(e)}", "error")
            return render_template("register.html")
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html")





@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if session["role"] == "student":
        s_id = session['s_id']
        print(f"Session student_id: {s_id}") 

        if not s_id:
            print("No student is logged in.")
            return redirect(url_for('login'))

        print(f"Fetching profile for student ID: {s_id}")


        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM student WHERE s_id = %s', (s_id,))
        student = cursor.fetchone()
        cursor.close()
        conn.close()

        if student:

            if request.method == 'POST':
                name = request.form.get('name')
                department = request.form.get('department')
                email = request.form.get('email')
                password = request.form.get('password')

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE student 
                    SET name = %s, department = %s, email = %s,password = %s
                    WHERE s_id = %s
                ''', (name, department, email, password, s_id))
                conn.commit()
                cursor.close()
                conn.close()

                flash("Profile updated successfully!", "success")
                return redirect(url_for('profile'))  

            return render_template('profile.html', student=student)
        else:
            flash("Student not found.", "error")
            return redirect(url_for('login'))


    elif session["role"] == "tutor":
        t_id = session['t_id']
        print(f"Session student_id: {t_id}") 

        if not t_id:
            print("No student is logged in.")
            return redirect(url_for('login'))

        print(f"Fetching profile for student ID: {t_id}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tutor WHERE t_id = %s', (t_id,))
        tutor = cursor.fetchone()
        cursor.close()
        conn.close()
        if tutor:
            if request.method == 'POST':
                name = request.form.get('name')
                department = request.form.get('department')
                email = request.form.get('email')
                password = request.form.get('password')
                cgpa = request.form.get('cgpa')
                per_hour_charge = request.form.get('per_hour_charge')
                available_slot = request.form.get('available_slot')

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE tutor 
                    SET name = %s, department = %s, email = %s,password = %s, cgpa = %s, per_hour_charge = %s,available_slot = %s
                    WHERE t_id = %s
                ''', (name, department, email, password, cgpa, per_hour_charge, available_slot, t_id))
                conn.commit()
                cursor.close()
                conn.close()

                flash("Profile updated successfully!", "success")
                return redirect(url_for('profile'))
            return render_template('profile.html', tutor=tutor)
        else:
            flash("Student not found.", "error")
            return redirect(url_for('login'))


@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    if session["role"] == "student":
        s_id = session['s_id']
        if not s_id:
            flash("You must be logged in to delete your profile.", "error")
            return redirect(url_for('login'))

        try:

            conn = get_db_connection()
            cursor = conn.cursor()


            cursor.execute('DELETE FROM student WHERE s_id = %s', (s_id,))
            conn.commit()
            cursor.close()
            conn.close()

            session.clear()
            flash("Your profile has been deleted.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for('profile'))
    
    elif session["role"] == "tutor":
        t_id = session['t_id']
        if not t_id:
            flash("You must be logged in to delete your profile.", "error")
            return redirect(url_for('login'))

        try:

            conn = get_db_connection()
            cursor = conn.cursor()


            cursor.execute('DELETE FROM tutor WHERE t_id = %s', (t_id,))
            conn.commit()
            cursor.close()
            conn.close()

            session.clear()
            flash("Your profile has been deleted.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for('profile'))






@app.route('/book_tutor_page', methods=['POST'])
def book_tutor_page():
    print("book_tutor route accessed!")  

    if 'email' not in session:
        print("User not logged in")
        return redirect(url_for('login'))

    s_id = session.get('s_id')
    t_id = request.form.get('t_id')
    status = "Pending"

    print(f"Student ID: {s_id}, Tutor ID: {t_id}")

    if not s_id or not t_id:
        print("Missing s_id or t_id")
        return "Invalid request", 400

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = "INSERT INTO book (s_id, t_id ,status) VALUES (%s,%s, %s);"
            cursor.execute(query, (s_id, t_id, status))
            connection.commit()
            print("Booking inserted into database")
    except Exception as e:
        print(f"Database error: {e}")
        return "Database error", 500
    finally:
        connection.close()

    return redirect(url_for('tutor'))






@app.route('/tutor')
def tutor():
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT t1.name,t1.t_id, t1.department,t1.cgpa,t1.email,t1.per_hour_charge,t1.available_slot,o.course_code
        from tutor t1 JOIN offers o ON t1.t_id = o.t_id
    """
    cursor.execute(query)
    tutor= cursor.fetchall()  
    cursor.close()
    conn.close()

    return render_template('tutor.html', tutor=tutor)




@app.route("/view_booking")
def view_booking():
    if 't_id' not in session:
        return redirect(url_for('login'))

    t_id = session['t_id']
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)  # ✅ return dicts

    query = """
        SELECT student.name, student.department, student.email, 
               book.booking_date, book.status, book.id AS booking_id
        FROM student 
        JOIN book ON student.s_id = book.s_id 
        JOIN tutor ON book.t_id = tutor.t_id 
        WHERE book.t_id = %s;
    """
    cursor.execute(query, (t_id,))
    tutors = cursor.fetchall()
    connection.close()

    return render_template("view_booking.html", tutors=tutors)


@app.route('/accept_booking/<id>', methods=['GET'])
def accept_booking(id):
    t_id = session["t_id"]
    status = "Accepted"
    connection = get_db_connection()
    cursor = connection.cursor()
    query =  "UPDATE book SET status = %s WHERE t_id = %s AND id = %s"
    cursor.execute(query,(status,t_id,id))
    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("view_booking"))

@app.route('/cancel_booking/<id>', methods=['GET'])
def cancel_booking(id):
    t_id = session["t_id"]
    status = "Cancelled"
    connection = get_db_connection()
    cursor = connection.cursor()
    query =  "UPDATE book SET status = %s WHERE t_id = %s AND id = %s"
    cursor.execute(query,(status,t_id,id))
    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("view_booking"))


@app.route("/view_course/id/<int:id>")
def view_course_by_id(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT c.course_code, c.name, d.name
            FROM course AS c
            JOIN department AS d ON c.d_id = d.d_id
            WHERE c.d_id = %s
            ORDER BY c.course_code
            """,
            (id,)
        )
        rows = cursor.fetchall()

        if not rows:
            cursor.execute("SELECT name FROM department WHERE d_id = %s", (id,))
            dep_row = cursor.fetchone()
            dept_name = dep_row[0] if dep_row else f"Department #{id}"
            courses = []
        else:
            dept_name = rows[0][2]
            course = [{"course_code": r[0], "name": r[1]} for r in rows]

        return render_template("view_course.html", dept=dept_name, course=course)
    finally:
        cursor.close()
        conn.close()


########################################## Fariha ######################################


@app.route('/student_cancel_booking/<id>', methods=['GET'])
def student_cancel_booking(id):
    s_id = session["s_id"]
    status = "Cancelled"
    connection = get_db_connection()
    cursor = connection.cursor()
    query =  "UPDATE book SET status = %s WHERE s_id = %s AND id = %s"
    cursor.execute(query,(status,s_id,id))
    connection.commit()
    cursor.close()
    connection.close()
    return redirect(url_for("booking"))

@app.route("/booking")
def booking():
    if 's_id' not in session:
        return redirect(url_for('login'))

    s_id = session['s_id']
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)   # ✅ Dicts instead of tuples

    query = """
        SELECT tutor.name, tutor.per_hour_charge, tutor.t_id, 
               book.booking_date, book.status, book.id AS booking_id
        FROM tutor 
        JOIN book ON tutor.t_id = book.t_id 
        WHERE book.s_id = %s
    """
    cursor.execute(query, (s_id,))
    tutors = cursor.fetchall()
    connection.close()
    return render_template("booking.html", tutors=tutors)



@app.route('/book_tutor', methods=['POST'])
def book_tutor():
    print("book_tutor route accessed!")  

    if 'email' not in session:
        print("User not logged in")
        return redirect(url_for('login'))

    s_id = session.get('s_id')
    t_id = request.form.get('t_id')
    status = "Pending"

    print(f"Student ID: {s_id}, Tutor ID: {t_id}")

    if not s_id or not t_id:
        print("Missing s_id or t_id")
        return "Invalid request", 400

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = "INSERT INTO book (s_id, t_id ,status) VALUES (%s,%s, %s);"
            cursor.execute(query, (s_id, t_id, status))
            connection.commit()
            print("Booking inserted into database")
    except Exception as e:
        print(f"Database error: {e}")
        return "Database error", 500
    finally:
        connection.close()

    return redirect(url_for('course'))



################################################################### SOHAN #####################################################
@app.route('/available_tutor/<course_code>', methods=['GET'])
def available_tutor(course_code):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        query = """
            SELECT tutor.name, tutor.t_id, tutor.department, tutor.cgpa, tutor.email, tutor.per_hour_charge, 
                   tutor.available_slot, offers.course_code
            FROM tutor
            JOIN offers ON tutor.t_id = offers.t_id
            WHERE offers.course_code = %s
        """
        cursor.execute(query, (course_code,))
        tutors = cursor.fetchall()
    connection.close()
    return render_template('available_tutor.html', course_code=course_code, tutors=tutors)

@app.route('/course')
def course():
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT course_code, name from course
    """
    cursor.execute(query)
    course = cursor.fetchall()  
    cursor.close()
    conn.close()

    return render_template('course.html', course=course)  


@app.route("/search_tutors", methods=["GET"])
def search_tutors():
    query = request.args.get("q")

    connection = get_db_connection()
    cursor = connection.cursor()

    # Search tutors by name (case-insensitive)
    sql = """
        SELECT t1.name,t1.t_id, t1.department,t1.cgpa,t1.email,t1.per_hour_charge,t1.available_slot,o.course_code
        from tutor t1 JOIN offers o ON t1.t_id = o.t_id
    WHERE name LIKE %s OR o.course_code LIKE %s"""
    like = "%" + query + "%"
    cursor.execute(sql, (like,like))
    tutors = cursor.fetchall()

    connection.close()

    return render_template("tutor.html", tutor=tutors)


@app.route('/dept')
def dept():
    # Check if the user is an admin
    if 'role' not in session or session['role'] != 'student':
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))
    
    # Retrieve all departments from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT d_id, name, description, image_path FROM department")
    departments = cursor.fetchall()
    
    cursor.close()
    conn.close()

    # Pass department data to the template
    return render_template('dept.html', departments=departments)


@app.route("/adminlogin", methods=["GET", "POST"])
def adminlogin():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        connection = get_db_connection()
        cursor = connection.cursor()

        print(f"Attempting admin login for email: {email}")
        try:
            # Check the admin credentials
            query = "SELECT id, email, password, name FROM admin WHERE email = %s"
            cursor.execute(query, (email,))
            admin = cursor.fetchone()

            if admin:
                stored_password = admin[2]

                if stored_password == password:
                    # Admin login successful, set session variables
                    session['role'] = "admin"
                    session['email'] = email
                    session['admin_id'] = admin[0]
                    session['admin_name'] = admin[3]
                    return redirect(url_for("admin_home"))
                else:
                    flash("Invalid password", "error")
                    return render_template("adminlogin.html")
            else:
                flash("Admin not found", "error")
                return render_template("adminlogin.html")
        finally:
            cursor.close()
            connection.close()

    return render_template("adminlogin.html")

@app.route("/admin_home")
def admin_home():
    if 'role' not in session or session['role'] != 'admin':
        flash("Please log in to continue.", "error")
        return redirect(url_for("adminlogin"))
    return render_template("admin_home.html")

@app.route('/admin_course')
def admin_course():
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT course_code, name from course
    """
    cursor.execute(query)
    course = cursor.fetchall()  
    cursor.close()
    conn.close()

    return render_template('admin_course.html', course=course) 

@app.route('/add_course', methods=["POST"])
def add_course():
    if 'role' not in session or session['role'] != 'admin':
        flash("Please log in to continue.", "error")
        return redirect(url_for("adminlogin"))
    

    course_code = request.form.get("course_code")
    course_name = request.form.get("course_name")
    dept_id = request.form.get("dept_name")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO course (course_code, name, d_id)
            VALUES (%s, %s, %s)
        """, (course_code, course_name, dept_id))
        conn.commit()
        flash("Course added successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error adding course: {e}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("admin_course"))



@app.route('/admin_dept')
def admin_dept():
    # Check if the user is an admin
    if 'role' not in session or session['role'] != 'admin':
        flash("Please log in to continue.", "error")
        return redirect(url_for("adminlogin"))
    
    # Retrieve all departments from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT d_id, name, description, image_path FROM department")
    departments = cursor.fetchall()
    
    cursor.close()
    conn.close()


    return render_template('admin_dept.html', departments=departments)

@app.route('/add_department', methods=["POST"])
def add_department():

    if 'role' not in session or session['role'] != 'admin':
        flash("Please log in to continue.", "error")
        return redirect(url_for("adminlogin"))
    

    department_name = request.form.get("department_name")
    department_description = request.form.get("department_description")
    image_path = request.form.get("image_path")
    dept_id = request.form.get("department_id")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO department (d_id, name, description, image_path)
            VALUES (%s, %s, %s, %s)
        """, (dept_id, department_name, department_description, image_path))

        conn.commit()
        flash("Department added successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error adding department: {e}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("admin_dept"))


####################################################################### extra ###################################

# review

@app.route("/review", methods=["GET", "POST"])
def review():
    if 's_id' not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))
    
    # Get the list of tutors from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT t_id, name FROM tutor")
    tutors = cursor.fetchall()

    # Get the filter parameter for tutor reviews
    filter_tutor = request.args.get("filter_tutor")  # Get the selected tutor ID for filtering

    # Handle review submission
    if request.method == "POST":
        tutor_id = request.form.get("tutor_id")
        review_text = request.form.get("review")

        # Fetch the student's name from the database using the session's student ID
        cursor.execute("SELECT name FROM student WHERE s_id = %s", (session['s_id'],))
        student_name = cursor.fetchone()[0]  # Get the student's name

        if tutor_id and review_text:
            try:
                cursor.execute(
                    """
                    INSERT INTO review (student_id, tutor_id, review, student_name)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (session['s_id'], tutor_id, review_text, student_name)
                )
                conn.commit()
                flash("Review submitted successfully!", "success")
                return redirect(url_for("review"))
            except Exception as e:
                flash(f"Error submitting review: {str(e)}", "error")
                return render_template("review.html", tutors=tutors)

    # Fetch reviews, optionally filtered by tutor
    if filter_tutor:
        cursor.execute(
            """
            SELECT student.name, review.review, tutor.name 
            FROM review
            JOIN student ON review.student_id = student.s_id
            JOIN tutor ON review.tutor_id = tutor.t_id
            WHERE review.tutor_id = %s
            """, 
            (filter_tutor,)
        )
    else:
        cursor.execute(
            """
            SELECT student.name, review.review, tutor.name 
            FROM review
            JOIN student ON review.student_id = student.s_id
            JOIN tutor ON review.tutor_id = tutor.t_id
            """
        )

    reviews = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("review.html", tutors=tutors, reviews=reviews, filter_tutor=filter_tutor)

# dashboard

@app.route("/dashboard")
def dashboard():
    # Make sure the user is logged in and is a student
    if 'role' not in session or session['role'] != 'student':
        flash("You are not authorized to view this page.", "error")
        return redirect(url_for("login"))

    # Get the number of tutors
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the number of tutors
    cursor.execute("SELECT COUNT(*) FROM tutor")
    num_tutors = cursor.fetchone()[0]

    # Get the number of courses
    cursor.execute("SELECT COUNT(*) FROM course")
    num_courses = cursor.fetchone()[0]

    # Get the number of departments
    cursor.execute("SELECT COUNT(*) FROM department")
    num_departments = cursor.fetchone()[0]

    # Get the number of students
    cursor.execute("SELECT COUNT(*) FROM student")
    num_students = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    # Render the student dashboard with the stats
    return render_template("dashboard.html", num_tutors=num_tutors, num_courses=num_courses, num_departments=num_departments, num_students=num_students)



###########################Chat###############################


# API to fetch old messages
@app.route("/chat_history/<int:booking_id>")
def chat_history(booking_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT sender_type, message, timestamp FROM messages WHERE booking_id=%s ORDER BY timestamp", (booking_id,))
    rows = cur.fetchall()
    conn.close()

    # Convert tuples → dicts
    msgs = [
        {"sender_type": row[0], "message": row[1], "timestamp": row[2]} 
        for row in rows
    ]
    return {"messages": msgs}

# WebSocket events
@socketio.on("join")
def handle_join(data):
    booking_id = str(data["booking_id"])
    join_room(booking_id)  # student+tutor with same booking_id join same room

@socketio.on("message")
def handle_message(data):
    booking_id = str(data["booking_id"])
    sender_type = data["sender_type"]
    msg = data["msg"]

    # save to DB
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (booking_id, sender_type, message) VALUES (%s, %s, %s)", 
                (booking_id, sender_type, msg))
    conn.commit()
    conn.close()

    # include booking_id so frontend knows which box to update
    emit("new_message", {
    "booking_id": booking_id,
    "sender_type": sender_type,
    "message": msg
}, room=booking_id, include_self=True)


@app.route('/pay_booking/<int:id>', methods=['GET'])
def pay_booking(id):
    if 's_id' not in session:
        return redirect(url_for('login'))

    s_id = session["s_id"]
    connection = get_db_connection()
    cursor = connection.cursor()

    # Update status to Accepted
    query = "UPDATE book SET status = %s WHERE id = %s AND s_id = %s"
    cursor.execute(query, ("Paid", id, s_id))
    connection.commit()
    cursor.close()
    connection.close()

    flash("Payment successful! Booking Accepted.", "success")
    return redirect(url_for("booking"))






if __name__ == "__main__":
    socketio.run(app, debug=True)
