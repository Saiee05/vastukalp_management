import os
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_mysqldb import MySQL

app = Flask(__name__)
app.secret_key = 'secretkey'

# ================= CONFIG =================
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'vastukalp_db'
app.config['UPLOAD_FOLDER'] = 'uploads'

mysql = MySQL(app)
def admin_required():
    if 'user_id' not in session or session.get('role') != 'admin':
        return False
    return True

def employee_required():
    if 'user_id' not in session or session.get('role') != 'employee':
        return False
    return True
# ================= AUTH =================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cur.fetchone()
        cur.close()

        if user:
            session['user_id'] = user[0]
            session['role'] = user[4]

            if user[4] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('employee_dashboard'))

        return "Invalid Email or Password"

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ================= ADMIN =================
@app.route('/admin_dashboard')
def admin_dashboard():
    if not admin_required():
        return redirect(url_for('login'))
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM users WHERE role='employee'")
    total_employees = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM clients")
    total_clients = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM projects")
    total_projects = cur.fetchone()[0]

    cur.close()

    return render_template('admin_dashboard.html',
                           total_employees=total_employees,
                           total_clients=total_clients,
                           total_projects=total_projects)

# ---------- Employees ----------
@app.route('/employees')
def employees():
    search = request.args.get('search')
    cur = mysql.connection.cursor()

    if search:
        cur.execute("SELECT user_id, name, email, contact FROM users WHERE role='employee' AND name LIKE %s",
                    ('%' + search + '%',))
    else:
        cur.execute("SELECT user_id, name, email, contact FROM users WHERE role='employee'")

    data = cur.fetchall()
    cur.close()

    message = f"No employee found matching '{search}' 😅" if search and not data else None
    return render_template('employees.html', employees=data, message=message)


@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO users (name, email, contact, password, role)
            VALUES (%s, %s, %s, %s, 'employee')
        """, (request.form['name'], request.form['email'], request.form['contact'], request.form['password']))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('employees'))

    return render_template('add_employee.html')


@app.route('/edit_employee/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        cur.execute("""
            UPDATE users SET name=%s, email=%s, contact=%s WHERE user_id=%s
        """, (request.form['name'], request.form['email'], request.form['contact'], id))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('employees'))

    cur.execute("SELECT user_id, name, email, contact FROM users WHERE user_id=%s", (id,))
    employee = cur.fetchone()
    cur.close()

    return render_template('edit_employee.html', employee=employee)


@app.route('/delete_employee/<int:id>')
def delete_employee(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM projects WHERE assigned_to=%s", (id,))
    cur.execute("DELETE FROM users WHERE user_id=%s", (id,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('employees'))

# ---------- Clients ----------
@app.route('/clients')
def clients():
    cur = mysql.connection.cursor()
    cur.execute("SELECT client_id, name, email, contact FROM clients")
    data = cur.fetchall()
    cur.close()
    return render_template('clients.html', clients=data)


@app.route('/add_client', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO clients (name, email, contact) VALUES (%s, %s, %s)",
                    (request.form['name'], request.form['email'], request.form['contact']))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('clients'))

    return render_template('add_client.html')


@app.route('/edit_client/<int:id>', methods=['GET', 'POST'])
def edit_client(id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        cur.execute("UPDATE clients SET name=%s, email=%s, contact=%s WHERE client_id=%s",
                    (request.form['name'], request.form['email'], request.form['contact'], id))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('clients'))

    cur.execute("SELECT * FROM clients WHERE client_id=%s", (id,))
    client = cur.fetchone()
    cur.close()

    return render_template('edit_client.html', client=client)


@app.route('/delete_client/<int:id>')
def delete_client(id):
    if not admin_required():
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # first delete projects linked to this client
    cur.execute("DELETE FROM projects WHERE client_id=%s", (id,))

    # then delete client
    cur.execute("DELETE FROM clients WHERE client_id=%s", (id,))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('clients'))

# ---------- Projects ----------
@app.route('/projects')
def projects():
    if not admin_required():
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT p.project_id, p.project_name, c.name, u.name,
               p.deadline, p.status, p.pdf_file, p.cad_file
        FROM projects p
        LEFT JOIN clients c ON p.client_id = c.client_id
        LEFT JOIN users u ON p.assigned_to = u.user_id
        WHERE p.admin_id = %s
    """, (session['user_id'],))

    projects = cur.fetchall()
    cur.close()

    return render_template('projects.html', projects=projects)


@app.route('/add_project', methods=['GET', 'POST'])
def add_project():
    cur = mysql.connection.cursor()

    cur.execute("SELECT user_id, name FROM users WHERE role='employee'")
    employees = cur.fetchall()

    cur.execute("SELECT client_id, name FROM clients")
    clients = cur.fetchall()

    if request.method == 'POST':
        admin_id = session['user_id']   # ✅ inside block

        cur.execute("""
            INSERT INTO projects (project_name, client_id, assigned_to, deadline, status, admin_id)
            VALUES (%s, %s, %s, %s, 'Not Started', %s)
        """, (
            request.form['project_name'],
            request.form['client_id'],
            request.form['employee_id'],
            request.form['deadline'],
            admin_id
        ))

        # 🔔 notify employee
        cur.execute("""
            INSERT INTO notifications (message, user_id)
            VALUES (%s, %s)
        """, ("You have been assigned a new project", request.form['employee_id']))

        mysql.connection.commit()
        cur.close()

        return redirect(url_for('projects'))

    return render_template('add_project.html', employees=employees, clients=clients)
@app.route('/edit_project/<int:id>', methods=['GET', 'POST'])
def edit_project(id):
    if not admin_required():
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # get employees for dropdown
    cur.execute("SELECT user_id, name FROM users WHERE role='employee'")
    employees = cur.fetchall()

    # get clients for dropdown
    cur.execute("SELECT client_id, name FROM clients")
    clients = cur.fetchall()

    if request.method == 'POST':
        project_name = request.form['project_name']
        client_id = request.form['client_id']
        employee_id = request.form['employee_id']
        deadline = request.form['deadline']
        status = request.form['status']

        cur.execute("""
            UPDATE projects
            SET project_name=%s,
                client_id=%s,
                assigned_to=%s,
                deadline=%s,
                status=%s
            WHERE project_id=%s
        """, (project_name, client_id, employee_id, deadline, status, id))

        mysql.connection.commit()
        cur.close()
        return redirect(url_for('projects'))

    cur.execute("""
        SELECT project_id, project_name, client_id, assigned_to, deadline, status
        FROM projects
        WHERE project_id=%s
    """, (id,))
    project = cur.fetchone()
    cur.close()

    return render_template(
        'edit_project.html',
        project=project,
        employees=employees,
        clients=clients
    )

# ---------- Admin Notifications ----------
@app.route('/admin_notifications')
def admin_notifications():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT message, created_at 
        FROM notifications 
        WHERE user_id=1
        ORDER BY created_at DESC
    """)

    data = cur.fetchall()
    cur.close()

    return render_template('admin_notifications.html', notifications=data)

# ================= EMPLOYEE =================
@app.route('/employee_dashboard')
def employee_dashboard():
    user_id = session['user_id']
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM projects WHERE assigned_to=%s", (user_id,))
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM projects WHERE assigned_to=%s AND status='Not Started'", (user_id,))
    not_started = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM projects WHERE assigned_to=%s AND status='In Progress'", (user_id,))
    in_progress = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM projects WHERE assigned_to=%s AND status='Completed'", (user_id,))
    completed = cur.fetchone()[0]

    cur.close()

    return render_template('employee_dashboard.html',
                           total=total,
                           not_started=not_started,
                           in_progress=in_progress,
                           completed=completed)


@app.route('/employee_projects')
def employee_projects():
    user_id = session['user_id']
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT p.project_id, p.project_name, c.name, p.deadline, p.status, p.pdf_file, p.cad_file
        FROM projects p
        LEFT JOIN clients c ON p.client_id = c.client_id
        WHERE p.assigned_to=%s
    """, (user_id,))

    projects = cur.fetchall()
    cur.close()

    return render_template('employee_projects.html', projects=projects)

@app.route('/employee_notifications')
def employee_notifications():
    if not employee_required():
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (user_id,))

    notifications = cur.fetchall()
    cur.close()

    return render_template('employee_notifications.html', notifications=notifications)


@app.route('/update_project/<int:id>', methods=['GET', 'POST'])
def update_project(id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        status = request.form['status']
        message = request.form.get('message', '')

        # GET PROJECT NAME
        cur.execute("SELECT project_name FROM projects WHERE project_id=%s", (id,))
        project = cur.fetchone()
        project_name = project[0]

        pdf = request.files.get('pdf_file')
        cad = request.files.get('cad_file')

        pdf_name = None
        cad_name = None

        if pdf and pdf.filename:
            pdf_name = pdf.filename
            pdf.save(os.path.join(app.config['UPLOAD_FOLDER'], pdf_name))

        if cad and cad.filename:
            cad_name = cad.filename
            cad.save(os.path.join(app.config['UPLOAD_FOLDER'], cad_name))

        cur.execute("""
            UPDATE projects
            SET status=%s,
                pdf_file = COALESCE(%s, pdf_file),
                cad_file = COALESCE(%s, cad_file)
            WHERE project_id=%s
        """, (status, pdf_name, cad_name, id))

        # 🔔 BETTER NOTIFICATION
        notification_msg=f"{project_name} is now {status}"

        if message.strip():
            notification_msg += f" - {message}"

        cur.execute("""
                    INSERT INTO notifications (message,user_id)
                    VALUES(%s,%s)
                    """,(notification_msg,1))

        mysql.connection.commit()
        cur.close()

        return redirect(url_for('employee_dashboard'))

    return render_template('update_project.html')

# ================= COMMON =================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ================= RUN =================
if __name__ == '__main__':
    app.run(debug=True)