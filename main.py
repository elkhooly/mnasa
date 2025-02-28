from flask import Flask, render_template, request, redirect,jsonify, abort, url_for, session, flash, make_response
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from werkzeug.security import generate_password_hash
import os
from werkzeug.utils import secure_filename

import pdfkit

from werkzeug.utils import secure_filename
import os



from werkzeug.utils import secure_filename
import os


app = Flask(__name__)
app.secret_key = '1a2b3c4d5e6d7g8h9i10'

# إعدادات الاتصال بقاعدة البيانات
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # ضع كلمة مرور قاعدة البيانات هنا
app.config['MYSQL_DB'] = 'loginapp'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

mysql = MySQL(app)



# إعداد الاتصال بقاعدة البيانات
db = MySQLdb.connect(host="localhost", user="root", passwd="", db="loginapp", charset="utf8")
cursor = db.cursor()


from werkzeug.security import check_password_hash


@app.route('/pythonlogin/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT id, username, password, role FROM accounts WHERE username = %s', (username,))
        account = cursor.fetchone()

        if account and check_password_hash(account['password'], password):
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['role'] = account['role']  # تخزين نوع المستخدم

            flash("تم تسجيل الدخول بنجاح!", "success")
            return redirect(url_for('home'))
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة!", "danger")

        cursor.close()

    return render_template('auth/login.html', title="تسجيل الدخول")

def is_teacher():
    return 'loggedin' in session and session.get('role') == 'teacher'

def is_admin():
    return 'loggedin' in session and session.get('role') == 'admin'


@app.route('/admin/manage_users', methods=['GET', 'POST'])
def manage_users():
    if not is_admin():
        flash("ليس لديك الصلاحيات للوصول إلى هذه الصفحة!", "danger")
        return redirect(url_for('home'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        user_id = request.form['user_id']
        new_role = request.form['role']
        cursor.execute("UPDATE accounts SET role = %s WHERE id = %s", (new_role, user_id))
        mysql.connection.commit()
        flash("تم تحديث صلاحيات المستخدم بنجاح!", "success")

    cursor.execute("SELECT id, username, role FROM accounts")
    users = cursor.fetchall()
    cursor.close()

    return render_template('manage_users.html', users=users)



@app.route('/pythonlogin/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # التحقق مما إذا كان اسم المستخدم أو البريد الإلكتروني موجود بالفعل
        cursor.execute("SELECT * FROM accounts WHERE username = %s OR email = %s", (username, email))
        account = cursor.fetchone()

        if account:
            flash("Username or email already exists!", "danger")
        elif not re.match(r'^[A-Za-z0-9]+$', username):
            flash("Username must contain only letters and numbers!", "danger")
        elif not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            flash("Invalid email address!", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters long!", "danger")
        else:
            # تشفير كلمة المرور قبل التخزين
            hashed_password = generate_password_hash(password)

            # إدخال المستخدم الجديد إلى قاعدة البيانات
            cursor.execute('INSERT INTO accounts (username, email, password) VALUES (%s, %s, %s)',
                           (username, email, hashed_password))
            mysql.connection.commit()

            # تسجيل النشاط في activity_logs
            cursor.execute("INSERT INTO activity_logs (activity, username, user_id) VALUES (%s, %s, LAST_INSERT_ID())",
                           ("New user registered", username))
            mysql.connection.commit()

            flash("You have successfully registered! Please log in.", "success")
            return redirect(url_for('login'))

    return render_template('auth/register.html', title="Register")
@app.route('/')
def home():
    if 'loggedin' not in session:
        return redirect(url_for('login'))  # توجيه المستخدم إلى صفحة تسجيل الدخول إذا لم يكن مسجلاً

    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT posts.id, posts.content, posts.timestamp, accounts.username, accounts.profile_picture "
        "FROM posts JOIN accounts ON posts.user_id = accounts.id ORDER BY posts.timestamp DESC"
    )
    posts_data = cursor.fetchall()

    posts_list = []
    for row in posts_data:
        post_id = row[0]
        cursor.execute("SELECT COUNT(*) FROM likes WHERE post_id = %s", (post_id,))
        likes_count = cursor.fetchone()[0]

        cursor.execute("SELECT comments.content, comments.timestamp, accounts.username, accounts.profile_picture "
                       "FROM comments JOIN accounts ON comments.user_id = accounts.id WHERE comments.post_id = %s ORDER BY comments.timestamp DESC", (post_id,))
        comments_data = cursor.fetchall()

        posts_list.append({
            'id': post_id,
            'content': row[1],
            'timestamp': row[2],
            'username': row[3],
            'profile_picture': row[4],  # إضافة صورة المستخدم
            'likes_count': likes_count,
            'comments': [{'content': comment[0], 'timestamp': comment[1], 'username': comment[2], 'profile_picture': comment[3]} for comment in comments_data]
        })

    cursor.close()
    return render_template('home/home.html', username=session['username'], title="Home", posts=posts_list)
@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    # التحقق من وجود تفاعل سابق
    cursor.execute("SELECT * FROM likes WHERE user_id = %s AND post_id = %s", (session['id'], post_id))
    existing_like = cursor.fetchone()

    if existing_like:
        # إذا كان المستخدم قد أعجب بالمنشور بالفعل، قم بإزالة الإعجاب
        cursor.execute("DELETE FROM likes WHERE user_id = %s AND post_id = %s", (session['id'], post_id))
        mysql.connection.commit()
    else:
        # إذا لم يكن هناك تفاعل سابق، قم بإضافة إعجاب جديد
        cursor.execute("INSERT INTO likes (user_id, post_id) VALUES (%s, %s)", (session['id'], post_id))
        mysql.connection.commit()

    cursor.close()
    return redirect(url_for('home'))
@app.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    content = request.form['content']
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO comments (user_id, post_id, content) VALUES (%s, %s, %s)", (session['id'], post_id, content))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('home'))


@app.route('/add_friend', methods=['GET', 'POST'])
def add_friend():
    if 'id' not in session:
        flash("يجب تسجيل الدخول أولاً!", "danger")
        return redirect(url_for('login'))

    current_user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # جلب قائمة الأصدقاء الحاليين
    cursor.execute("""
        SELECT a.id FROM accounts a
        JOIN friends f ON (a.id = f.user_id OR a.id = f.friend_id)
        WHERE (f.user_id = %s OR f.friend_id = %s) AND f.status = 'accepted'
    """, (current_user_id, current_user_id))

    friend_ids = [row['id'] for row in cursor.fetchall()]
    friend_ids.append(current_user_id)  # استبعاد المستخدم الحالي نفسه

    query = "SELECT id, username, profile_picture FROM accounts WHERE id NOT IN %s"
    params = (tuple(friend_ids),)

    # البحث حسب اسم المستخدم إذا تم إدخال بحث
    if request.method == 'POST' and 'username' in request.form:
        search_username = f"%{request.form['username']}%"
        query += " AND username LIKE %s"
        params += (search_username,)

    cursor.execute(query, params)
    users = cursor.fetchall()

    return render_template('add_friend.html', users=users)


@app.route('/send_friend_request/<int:user_id>', methods=['POST'])
def send_friend_request(user_id):
    if 'id' not in session:
        flash("يجب تسجيل الدخول أولاً!", "danger")
        return redirect(url_for('login'))

    current_user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # التأكد من عدم إرسال طلب مكرر
    cursor.execute("SELECT * FROM friends WHERE user_id = %s AND friend_id = %s", (current_user_id, user_id))
    existing_request = cursor.fetchone()

    if not existing_request:
        cursor.execute("INSERT INTO friends (user_id, friend_id, status) VALUES (%s, %s, 'pending')",
                       (current_user_id, user_id))
        mysql.connection.commit()
        flash("تم إرسال طلب الصداقة بنجاح!", "success")
    else:
        flash("تم إرسال طلب الصداقة مسبقاً!", "warning")

    return redirect(url_for('add_friend'))


@app.route('/friend_requests', methods=['GET', 'POST'])
def friend_requests():
    if 'id' not in session:
        flash("يجب تسجيل الدخول أولاً!", "danger")
        return redirect(url_for('login'))

    current_user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # جلب طلبات الصداقة مع اسم المرسل وصورة الملف الشخصي
    cursor.execute("""
        SELECT friends.id, accounts.username, accounts.profile_picture, friends.user_id 
        FROM friends 
        JOIN accounts ON friends.user_id = accounts.id 
        WHERE friends.friend_id = %s AND friends.status = 'pending'
    """, [current_user_id])

    requests = cursor.fetchall()

    if request.method == 'POST':
        action = request.form['action']
        request_id = request.form['request_id']

        if action == 'accept':
            cursor.execute("UPDATE friends SET status = 'accepted' WHERE id = %s", [request_id])
            flash("تم قبول طلب الصداقة!", "success")
        elif action == 'reject':
            cursor.execute("DELETE FROM friends WHERE id = %s", [request_id])  # حذف الطلب بدل من تعيينه rejected
            flash("تم رفض طلب الصداقة!", "danger")

        mysql.connection.commit()
        return redirect(url_for('friend_requests'))

    return render_template('friend_requests.html', requests=requests)


@app.route('/accept_friend_request/<int:request_id>', methods=['POST'])
def accept_friend_request(request_id):
    if 'id' not in session:
        flash("يجب تسجيل الدخول أولاً!", "danger")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # تحديث الطلب إلى "مقبول"
    cursor.execute("UPDATE friends SET status = 'accepted' WHERE id = %s", [request_id])
    mysql.connection.commit()

    flash("تم قبول طلب الصداقة!", "success")
    return redirect(url_for('friend_requests'))


@app.route('/reject_friend_request/<int:request_id>', methods=['POST'])
def reject_friend_request(request_id):
    if 'id' not in session:
        flash("يجب تسجيل الدخول أولاً!", "danger")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # حذف الطلب من قاعدة البيانات
    cursor.execute("DELETE FROM friends WHERE id = %s", [request_id])
    mysql.connection.commit()

    flash("تم رفض طلب الصداقة!", "danger")
    return redirect(url_for('friend_requests'))
@app.route('/my_friends')
def my_friends():
    if 'id' not in session:
        flash("يجب تسجيل الدخول أولاً!", "danger")
        return redirect(url_for('login'))

    current_user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT a.id, a.username, a.email, a.profile_picture 
        FROM friends f
        JOIN accounts a ON a.id = f.friend_id OR a.id = f.user_id
        WHERE (f.user_id = %s OR f.friend_id = %s) 
        AND f.status = 'accepted' 
        AND a.id != %s
    """, (current_user_id, current_user_id, current_user_id))

    friends = cursor.fetchall()
    return render_template('my_friends.html', friends=friends)

@app.route('/messages')
def messages():
    if 'id' not in session:
        return redirect(url_for('login'))

    user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)


    cursor.execute("""
        SELECT accounts.id, accounts.username, 
               COALESCE(accounts.profile_picture, 'default.png') AS profile_picture,
               (SELECT MAX(messages.timestamp)
                FROM messages 
                WHERE (messages.sender_id = accounts.id AND messages.receiver_id = %s)
                   OR (messages.receiver_id = accounts.id AND messages.sender_id = %s)
               ) AS last_message_time
        FROM friends
        JOIN accounts ON (friends.friend_id = accounts.id OR friends.user_id = accounts.id)
        WHERE (friends.user_id = %s OR friends.friend_id = %s) 
          AND accounts.id != %s
        ORDER BY IFNULL(last_message_time, '1970-01-01 00:00:00') DESC
    """, (user_id, user_id, user_id, user_id, user_id))

    friends = cursor.fetchall()
    cursor.close()

    return render_template('messages.html', friends=friends)

# 📍 عرض المحادثة بين شخصين وإرسال الرسائل
@app.route('/chat/<int:friend_id>', methods=['GET', 'POST'])
def chat(friend_id):
    if 'id' not in session:
        return redirect(url_for('login'))

    user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        message = request.form['message']
        cursor.execute("INSERT INTO messages (sender_id, receiver_id, message) VALUES (%s, %s, %s)",
                       (user_id, friend_id, message))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'status': 'success'})

    cursor.execute("""
        SELECT * FROM messages 
        WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s) 
        ORDER BY timestamp
    """, (user_id, friend_id, friend_id, user_id))
    messages = cursor.fetchall()

    cursor.execute("""
        SELECT username, 
               COALESCE(profile_picture, 'default.png') AS profile_picture 
        FROM accounts WHERE id = %s
    """, (friend_id,))

    friend = cursor.fetchone()
    cursor.close()

    if not friend:
        flash("المستخدم غير موجود!", "danger")
        return redirect(url_for('messages'))

    return render_template('chat.html', messages=messages, friend=friend, friend_id=friend_id)


@app.route('/get_messages/<int:friend_id>')
def get_messages(friend_id):
    if 'id' not in session:
        return jsonify({'error': 'يجب تسجيل الدخول'}), 403

    user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT m.*, a.username AS sender_name 
        FROM messages m
        JOIN accounts a ON m.sender_id = a.id
        WHERE (m.sender_id = %s AND m.receiver_id = %s) 
           OR (m.sender_id = %s AND m.receiver_id = %s) 
        ORDER BY m.timestamp
    """, (user_id, friend_id, friend_id, user_id))

    messages = cursor.fetchall()
    cursor.close()

    chat_html = ""
    for message in messages:
        sender = "أنت" if message['sender_id'] == user_id else message['sender_name']
        css_class = "sent" if message['sender_id'] == user_id else "received"
        chat_html += f'''
        <div class="message-container {css_class}">
            <div class="message">
                <div class="message-username">{sender}</div>
                {message["message"]}
                <div class="message-time">{message["timestamp"].strftime('%H:%M')}</div>
            </div>
        </div>
        '''

    return chat_html

@app.route('/profile')
def profile():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE id = %s', (session['id'],))
        account = cursor.fetchone()
        if account:
            return render_template('auth/profile.html', account=account, title="Profile")
    return redirect(url_for('login'))


@app.route('/info')
def info():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE id = %s', (session['id'],))
        account = cursor.fetchone()
        if account:
            return render_template('auth/info.html', account=account, title="Info")
    return redirect(url_for('login'))


@app.route('/activity')
def activity():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM activity_logs WHERE user_id = %s ORDER BY date DESC', (session['id'],))
        activities = cursor.fetchall()
        return render_template('auth/activity.html', activities=activities, title="Activity Logs")
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)

    flash("You have successfully logged out!", "success")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    return render_template('home/dashboard.html', username=session['username'])

@app.route('/blog')
def blog():
    return render_template('blog.html')


@app.route('/freinds')
def freinds():
    return render_template('freinds.html')


@app.route('/setting')
def setting():
    return render_template('setting.html')


# صفحة النشر
@app.route('/post', methods=['GET', 'POST'])
def post():
    if request.method == 'POST':
        if 'id' in session:  # تعديل التحقق من session['user_id'] إلى session['id']
            user_id = session['id']
            content = request.form['content']

            cursor = mysql.connection.cursor()  # إنشاء كيرسور جديد
            sql = "INSERT INTO posts (user_id, content) VALUES (%s, %s)"
            cursor.execute(sql, (user_id, content))
            mysql.connection.commit()
            cursor.close()  # إغلاق الكيرسور بعد الاستخدام

            return redirect(url_for('home'))
        else:
            return "يجب تسجيل الدخول أولاً"

    return render_template('post.html')


from werkzeug.utils import secure_filename
import os

# إعداد مجلد لتحميل الصور
UPLOAD_FOLDER = 'static/profile_pictures'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# دالة للتحقق من صيغة الملف
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE id = %s', (session['id'],))
        account = cursor.fetchone()

        if request.method == 'POST' and 'username' in request.form and 'email' in request.form:
            username = request.form['username']
            email = request.form['email']
            password = request.form['password'] if 'password' in request.form else None

            # تحميل صورة الملف الشخصي
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    profile_picture = filename
                else:
                    profile_picture = account['profile_picture']  # الاحتفاظ بالصورة القديمة إذا لم يتم تحميل صورة جديدة
            else:
                profile_picture = account['profile_picture']  # الاحتفاظ بالصورة القديمة إذا لم يتم تحميل صورة جديدة

            if password:  # إذا أدخل المستخدم كلمة مرور جديدة
                hashed_password = generate_password_hash(password)  # تشفير كلمة المرور
                cursor.execute('UPDATE accounts SET username = %s, email = %s, password = %s, profile_picture = %s WHERE id = %s',
                               (username, email, hashed_password, profile_picture, session['id']))
            else:  # إذا لم يُدخل كلمة مرور، يتم تحديث الاسم والبريد فقط
                cursor.execute('UPDATE accounts SET username = %s, email = %s, profile_picture = %s WHERE id = %s',
                               (username, email, profile_picture, session['id']))

            mysql.connection.commit()

            # تسجيل النشاط
            cursor.execute("INSERT INTO activity_logs (activity, username, user_id) VALUES (%s, %s, %s)",
                           ("User updated profile", username, session['id']))
            mysql.connection.commit()

            flash("تم تحديث الملف الشخصي بنجاح!", "success")
            return redirect(url_for('home'))

        return render_template('auth/edit_profile.html', account=account, title="تعديل الملف الشخصي")

    return redirect(url_for('login'))



@app.route('/add_subject', methods=['GET', 'POST'])
def add_subject():
    if not is_teacher():
        flash("ليس لديك الصلاحية لإضافة المواد الدراسية!", "danger")
        return redirect(url_for('subjects'))  # تأكد من أن المسار مسجل في Flask

    if 'username' not in session:
        flash("يجب عليك تسجيل الدخول أولاً", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        teacher = session['username']

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO subjects (name, description, teacher) VALUES (%s, %s, %s)",
                       (name, description, teacher))
        mysql.connection.commit()
        cursor.close()

        flash("تمت إضافة المادة بنجاح!", "success")
        return redirect(url_for('subjects'))  # تأكد أن `subjects` هو الاسم الصحيح

    return render_template('add_subject.html')



@app.route('/subjects')
def subjects():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    try:
        with mysql.connection.cursor(MySQLdb.cursors.DictCursor) as cursor:
            if session['role'] == 'teacher':
                cursor.execute("""
                    SELECT * 
                    FROM subjects 
                    WHERE BINARY teacher = %s
                """, (session['username'],))
            else:
                cursor.execute("SELECT * FROM subjects")

            subjects = cursor.fetchall()

        return render_template('subjects.html', subjects=subjects)

    except Exception as e:
        flash(f"حدث خطأ أثناء جلب المواد: {str(e)}", "danger")
        return redirect(url_for('subjects'))  # إعادة التوجيه إلى نفس الصفحة بدلاً من dashboard

@app.route('/subject/<int:subject_id>')
def subject_page(subject_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM subjects WHERE id = %s", (subject_id,))
    subject = cursor.fetchone()

    cursor.execute("SELECT * FROM subject_files WHERE subject_id = %s ORDER BY uploaded_at DESC", (subject_id,))
    files = cursor.fetchall()

    cursor.execute("SELECT * FROM exams WHERE subject_id = %s ORDER BY created_at DESC", (subject_id,))
    exams = cursor.fetchall()

    cursor.close()

    if not subject:
        flash("المادة غير موجودة!", "danger")
        return redirect(url_for('subjects'))
    return render_template('subject_page.html', subject=subject, files=files, exams=exams)


@app.route('/delete_subject/<int:subject_id>', methods=['POST'])
def delete_subject(subject_id):
    if 'loggedin' not in session or session['role'] != 'teacher':
        abort(403)

    try:
        # جلب المادة والتأكد من ملكيتها للمعلم
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT teacher_id 
            FROM subjects 
            WHERE id = %s
        """, (subject_id,))
        result = cursor.fetchone()

        if not result or result['teacher_id'] != session['user_id']:
            flash("غير مصرح بهذه العملية", 'danger')
            return redirect(url_for('subjects_page'))

        # حذف المادة
        cursor.execute("DELETE FROM subjects WHERE id = %s", (subject_id,))
        mysql.connection.commit()
        flash("تم حذف المادة بنجاح", 'success')

    except Exception as e:
        mysql.connection.rollback()
        flash(f"حدث خطأ أثناء الحذف: {str(e)}", 'danger')

    finally:
        cursor.close()

    return redirect(url_for('subjects_page'))

@app.route('/add_question', methods=['GET', 'POST'])
def add_question():
    if 'loggedin' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    if request.method == 'POST':
        question_text = request.form['question_text']
        question_type = request.form['question_type']
        correct_answer = request.form['correct_answer']

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO questions (subject_id, question_text, question_type, correct_answer) VALUES (%s, %s, %s, %s)",
                       (1, question_text, question_type, correct_answer))
        question_id = cursor.lastrowid

        if question_type == 'mcq':
            choices = request.form['choices'].split("\n")
            for choice in choices:
                cursor.execute("INSERT INTO choices (question_id, choice_text) VALUES (%s, %s)", (question_id, choice.strip()))

        mysql.connection.commit()
        cursor.close()
        flash("تمت إضافة السؤال بنجاح!", "success")

    return render_template('add_question.html')


@app.route('/exam')

def list_exams():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, exam_name FROM exams")  # جلب جميع الامتحانات
        exams = cursor.fetchall()
        return render_template('exams_list.html', exams=exams)  # صفحة تحتوي على روابط الامتحانات
    return redirect(url_for('login'))


@app.route('/exam/')
def exam():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM questions")
    questions = cursor.fetchall()

    for question in questions:
        if question['question_type'] == 'mcq':
            cursor.execute("SELECT * FROM choices WHERE question_id = %s", (question['id'],))
            question['choices'] = cursor.fetchall()

    cursor.close()
    return render_template('exam.html', questions=questions)





@app.route('/submit_exam', methods=['POST'])
def submit_exam():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    score = 0
    cursor.execute("SELECT * FROM questions")
    questions = cursor.fetchall()

    for question in questions:
        user_answer = request.form.get(f"q{question['id']}", None)

        if user_answer:
            is_correct = (user_answer == question['correct_answer'])
            score += 1 if is_correct else 0

            cursor.execute("INSERT INTO answers (user_id, question_id, user_answer, is_correct) VALUES (%s, %s, %s, %s)",
                           (session['id'], question['id'], user_answer, is_correct))

    mysql.connection.commit()
    cursor.close()

    flash(f"تم إرسال إجاباتك! الدرجة: {score} / {len(questions)}", "info")
    return redirect(url_for('exam'))


@app.route('/add_exam/<int:subject_id>', methods=['GET', 'POST'])
def add_exam(subject_id):
    if 'loggedin' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    if request.method == 'POST':
        exam_name = request.form.get('exam_name')
        exam_description = request.form.get('exam_description')

        # إدخال الامتحان في قاعدة البيانات
        cursor.execute(
            "INSERT INTO exams (subject_id, exam_name, description) VALUES (%s, %s, %s)",
            (subject_id, exam_name, exam_description)
        )
        exam_id = cursor.lastrowid  # الحصول على معرف الامتحان الجديد
        mysql.connection.commit()
        cursor.close()

        flash("تم إنشاء الامتحان بنجاح!", "success")
        return redirect(url_for('add_questions_to_exam', exam_id=exam_id))  # إعادة التوجيه إلى صفحة إضافة الأسئلة

    return render_template('add_exam.html', subject_id=subject_id)


@app.route('/add_questions_to_exam/<int:exam_id>', methods=['GET', 'POST'])
def add_questions_to_exam(exam_id):
    if 'loggedin' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)  # استخدام DictCursor

    if request.method == 'POST':
        question_text = request.form.get('question_text')
        question_type = request.form.get('question_type')
        correct_answer = None

        if question_type == 'mcq':
            # معالجة اختيار من متعدد
            correct_choice = request.form.get('correct_choice')
            choices = [
                request.form.get('choice1'),
                request.form.get('choice2'),
                request.form.get('choice3'),
                request.form.get('choice4')
            ]
            correct_answer = choices[int(correct_choice) - 1]  # الحصول على الإجابة الصحيحة
        elif question_type == 'true_false':
            # معالجة صح/خطأ
            correct_answer = request.form.get('correct_answer_tf')
        elif question_type == 'short_answer':
            # معالجة إجابة قصيرة
            correct_answer = request.form.get('correct_answer_short')

        # إدخال السؤال في جدول الأسئلة
        cursor.execute(
            "INSERT INTO questions (question_text, question_type, correct_answer) VALUES (%s, %s, %s)",
            (question_text, question_type, correct_answer)
        )
        question_id = cursor.lastrowid  # الحصول على معرف السؤال الجديد

        # ربط السؤال بالامتحان في جدول exam_questions
        cursor.execute(
            "INSERT INTO exam_questions (exam_id, question_id) VALUES (%s, %s)",
            (exam_id, question_id)
        )

        # إذا كان السؤال من نوع اختيار من متعدد، إضافة الاختيارات إلى جدول choices
        if question_type == 'mcq':
            for choice in choices:
                cursor.execute(
                    "INSERT INTO choices (question_id, choice_text) VALUES (%s, %s)",
                    (question_id, choice)
                )

        mysql.connection.commit()
        flash("تمت إضافة السؤال بنجاح!", "success")
        return redirect(url_for('add_questions_to_exam', exam_id=exam_id))

    # جلب الأسئلة المضافة بالفعل لهذا الامتحان
    cursor.execute("""
        SELECT q.id, q.question_text, q.question_type, q.correct_answer 
        FROM exam_questions eq
        JOIN questions q ON eq.question_id = q.id
        WHERE eq.exam_id = %s
    """, (exam_id,))
    questions = cursor.fetchall()

    # جلب الاختيارات لأسئلة "اختيار من متعدد"
    for question in questions:
        if question['question_type'] == 'mcq':  # الوصول باستخدام مفتاح نصي
            cursor.execute("SELECT choice_text FROM choices WHERE question_id = %s", (question['id'],))
            question['choices'] = cursor.fetchall()

    cursor.close()

    return render_template('add_questions_to_exam.html', exam_id=exam_id, questions=questions)


@app.route('/subject_exams/<int:subject_id>/')
def subject_exams(subject_id):
    if 'loggedin' in session:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, exam_name FROM exams WHERE subject_id = %s", (subject_id,))
        exams = cursor.fetchall()
        return render_template('subject_exams.html', exams=exams, subject_id=subject_id)
    return redirect(url_for('login'))

@app.route('/exam/<int:exam_id>/', methods=['GET', 'POST'])
def take_exam(exam_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)  # استخدام DictCursor

    try:
        # التحقق من وجود الامتحان
        cursor.execute("SELECT exam_name FROM exams WHERE id = %s", (exam_id,))
        exam = cursor.fetchone()

        if not exam:
            flash("الامتحان غير موجود!", "danger")
            return redirect(url_for('dashboard'))

        exam_name = exam['exam_name']  # اسم الامتحان

        # جلب الأسئلة الخاصة بالامتحان
        cursor.execute("""
            SELECT q.id, q.question_text, q.question_type, q.correct_answer 
            FROM exam_questions eq
            JOIN questions q ON eq.question_id = q.id
            WHERE eq.exam_id = %s
        """, (exam_id,))
        questions = cursor.fetchall()

        # جلب الاختيارات لأسئلة "اختيار من متعدد"
        for question in questions:
            if question['question_type'] == 'mcq':
                cursor.execute("SELECT choice_text FROM choices WHERE question_id = %s", (question['id'],))
                question['choices'] = cursor.fetchall()

        if request.method == 'POST':
            score = 0
            for question in questions:
                question_id = question['id']
                user_answer = request.form.get(f"q{question_id}", "")

                correct_answer = question['correct_answer']
                is_correct = (user_answer == correct_answer)

                if is_correct:
                    score += 1

                cursor.execute(
                    "INSERT INTO answers (user_id, question_id, user_answer, is_correct) VALUES (%s, %s, %s, %s)",
                    (session['id'], question_id, user_answer, is_correct)
                )

            # حفظ النتيجة في جدول student_grades
            cursor.execute(
                "INSERT INTO student_grades (user_id, exam_id, score, total_questions) VALUES (%s, %s, %s, %s)",
                (session['id'], exam_id, score, len(questions))
            )
            mysql.connection.commit()

            # إعادة توجيه المستخدم إلى صفحة النتيجة
            return redirect(url_for('exam_result', exam_id=exam_id, score=score, total=len(questions)))

        return render_template('exam.html', exam_id=exam_id, exam_name=exam_name, questions=questions)

    except Exception as e:
        flash(f"حدث خطأ: {str(e)}", "danger")
        return redirect(url_for('dashboard'))

    finally:
        cursor.close()  # إغلاق الكيرسور في النهاية

@app.route('/student_grades')
def student_grades():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        # جلب درجات الطالب
        cursor.execute("""
            SELECT sg.score, sg.total_questions, sg.grade_date, e.exam_name 
            FROM student_grades sg
            JOIN exams e ON sg.exam_id = e.id
            WHERE sg.user_id = %s
            ORDER BY sg.grade_date DESC
        """, (session['id'],))
        grades = cursor.fetchall()

        return render_template('student_grades.html', grades=grades)

    except Exception as e:
        flash(f"حدث خطأ: {str(e)}", "danger")
        return redirect(url_for('home'))

    finally:
        cursor.close()  # إغلاق الكيرسور في النهاية


@app.route('/exam_result/<int:exam_id>/<int:score>/<int:total>')
def exam_result(exam_id, score, total):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    return render_template('exam_result.html', exam_id=exam_id, score=score, total=total)

@app.route('/teacher_grades', methods=['GET'])
def teacher_grades():
    if 'loggedin' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        # جلب جميع الامتحانات التي أنشأها المعلم
        cursor.execute("""
            SELECT e.id AS exam_id, e.exam_name, s.name AS subject_name
            FROM exams e
            JOIN subjects s ON e.subject_id = s.id
            WHERE s.teacher = %s
        """, (session['username'],))
        exams = cursor.fetchall()

        # جلب الامتحان المحدد (إذا تم اختياره)
        selected_exam_id = request.args.get('exam_id')
        selected_exam = None

        if selected_exam_id:
            # جلب تفاصيل الامتحان المحدد
            cursor.execute("""
                SELECT e.id AS exam_id, e.exam_name, s.name AS subject_name
                FROM exams e
                JOIN subjects s ON e.subject_id = s.id
                WHERE e.id = %s AND s.teacher = %s
            """, (selected_exam_id, session['username']))
            selected_exam = cursor.fetchone()

            # جلب درجات الطلاب للامتحان المحدد
            if selected_exam:
                cursor.execute("""
                    SELECT a.username, sg.score, sg.total_questions, sg.grade_date
                    FROM student_grades sg
                    JOIN accounts a ON sg.user_id = a.id
                    WHERE sg.exam_id = %s
                    ORDER BY sg.grade_date DESC
                """, (selected_exam_id,))
                selected_exam['grades'] = cursor.fetchall()

        return render_template(
            'teacher_grades.html',
            exams=exams,
            selected_exam_id=selected_exam_id,
            selected_exam=selected_exam
        )

    except Exception as e:
        flash(f"حدث خطأ: {str(e)}", "danger")
        return redirect(url_for('dashboard'))

    finally:
        cursor.close()  # إغلاق الكيرسور في النهاية


@app.route('/view_student_grades', methods=['GET'])
def view_student_grades():
    if 'loggedin' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        # جلب جميع الامتحانات مع اسم المادة
        cursor.execute("""
            SELECT e.id AS exam_id, e.exam_name, s.name AS subject_name
            FROM exams e
            JOIN subjects s ON e.subject_id = s.id
        """)
        exams = cursor.fetchall()

        # جلب الامتحان المحدد (إذا تم اختياره)
        selected_exam_id = request.args.get('exam_id')
        selected_exam = None

        if selected_exam_id:
            # جلب تفاصيل الامتحان المحدد
            cursor.execute("""
                SELECT e.id AS exam_id, e.exam_name, s.name AS subject_name
                FROM exams e
                JOIN subjects s ON e.subject_id = s.id
                WHERE e.id = %s
            """, (selected_exam_id,))
            selected_exam = cursor.fetchone()

            # جلب درجات الطلاب للامتحان المحدد
            if selected_exam:
                cursor.execute("""
                    SELECT a.username, sg.score, sg.total_questions, sg.grade_date
                    FROM student_grades sg
                    JOIN accounts a ON sg.user_id = a.id
                    WHERE sg.exam_id = %s
                    ORDER BY sg.grade_date DESC
                """, (selected_exam_id,))
                selected_exam['grades'] = cursor.fetchall()

        return render_template(
            'view_student_grades.html',
            exams=exams,
            selected_exam_id=selected_exam_id,
            selected_exam=selected_exam
        )

    except Exception as e:
        flash(f"حدث خطأ: {str(e)}", "danger")
        return redirect(url_for('dashboard'))

    finally:
        cursor.close()
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'mp4', 'avi', 'mov'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_file/<int:subject_id>', methods=['POST'])
def upload_file(subject_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('لم يتم اختيار أي ملف!', 'danger')
        return redirect(url_for('subject_page', subject_id=subject_id))

    file = request.files['file']
    if file.filename == '':
        flash('لم يتم اختيار أي ملف!', 'danger')
        return redirect(url_for('subject_page', subject_id=subject_id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO subject_files (subject_id, filename, filetype) VALUES (%s, %s, %s)",
                       (subject_id, filename, file.filename.rsplit('.', 1)[1].lower()))
        mysql.connection.commit()
        cursor.close()

        flash('تم رفع الملف بنجاح!', 'success')
    else:
        flash('نوع الملف غير مدعوم! مسموح فقط PDF و MP4', 'danger')

    return redirect(url_for('subject_page', subject_id=subject_id))



# ---- Routes للتحكم في الامتحانات ----
@app.route('/edit_exam/<int:exam_id>', methods=['GET', 'POST'])
def edit_exam(exam_id):
    if 'loggedin' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        # ------ التحقق من ملكية الامتحان ------
        cursor.execute("""
            SELECT e.* 
            FROM exams e
            INNER JOIN subjects s ON e.subject_id = s.id 
            WHERE e.id = %s AND s.teacher = %s
        """, (exam_id, session['username']))
        exam = cursor.fetchone()

        if not exam:
            flash("ليس لديك صلاحية لتعديل هذا الامتحان!", "danger")
            return redirect(url_for('subjects'))  # <-- إرجاع هنا

        # ------ معالجة طلب POST ------
        if request.method == 'POST':
            new_name = request.form.get('exam_name')
            new_description = request.form.get('description')

            if not new_name or not new_description:
                flash("الرجاء ملء جميع الحقول!", "danger")
                return redirect(url_for('edit_exam', exam_id=exam_id))  # <-- إرجاع هنا

            cursor.execute("""
                UPDATE exams 
                SET exam_name = %s, description = %s 
                WHERE id = %s
            """, (new_name, new_description, exam_id))
            mysql.connection.commit()

            flash("تم تحديث الامتحان بنجاح!", "success")
            return redirect(url_for('add_questions_to_exam', exam_id=exam_id))  # إعادة التوجيه إلى صفحة إضافة الأسئلة

        # ------ عرض نموذج التعديل ------
        return render_template('edit_exam.html', exam=exam)  # <-- إرجاع هنا

    except Exception as e:
        flash(f"حدث خطأ: {str(e)}", "danger")
        return redirect(url_for('subjects'))  # <-- إرجاع هنا

    finally:
        cursor.close()


@app.route('/delete_exam/<int:exam_id>', methods=['POST'])
def delete_exam(exam_id):
    if 'loggedin' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    try:
        # التحقق من أن المعلم هو صاحب المادة
        cursor.execute("""
            SELECT e.id 
            FROM exams e
            INNER JOIN subjects s ON e.subject_id = s.id
            WHERE e.id = %s AND s.teacher = %s
        """, (exam_id, session['username']))

        if not cursor.fetchone():
            flash("ليست لديك صلاحية لهذا الإجراء", "danger")
            return redirect(url_for('subjects'))

        # حذف الدرجات المرتبطة أولاً
        cursor.execute("DELETE FROM student_grades WHERE exam_id = %s", (exam_id,))

        # حذف الامتحان
        cursor.execute("DELETE FROM exams WHERE id = %s", (exam_id,))

        mysql.connection.commit()
        flash("تم الحذف بنجاح", "success")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"خطأ في الحذف: {str(e)}", "danger")

    finally:
        cursor.close()

    return redirect(url_for('subjects'))


# حذف السؤال
@app.route('/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    if 'loggedin' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    exam_id = None  # تعريف متغير exam_id

    try:
        # جلب exam_id المرتبط بالسؤال
        cursor.execute("SELECT exam_id FROM exam_questions WHERE question_id = %s", (question_id,))
        exam_data = cursor.fetchone()
        if exam_data:
            exam_id = exam_data['exam_id']

        # حذف الاختيارات أولاً
        cursor.execute("DELETE FROM choices WHERE question_id = %s", (question_id,))
        # حذف الربط بين الامتحان والسؤال
        cursor.execute("DELETE FROM exam_questions WHERE question_id = %s", (question_id,))
        # حذف السؤال
        cursor.execute("DELETE FROM questions WHERE id = %s", (question_id,))
        mysql.connection.commit()
        flash("تم حذف السؤال بنجاح", "success")

    except Exception as e:
        flash(f"حدث خطأ أثناء الحذف: {str(e)}", "danger")

    finally:
        cursor.close()

    # التأكد من وجود exam_id قبل التوجيه
    if exam_id is not None:
        return redirect(url_for('add_questions_to_exam', exam_id=exam_id))
    else:
        flash("لم يتم العثور على الامتحان المرتبط", "danger")
        return redirect(url_for('dashboard'))

# تعديل السؤال
@app.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
def edit_question(question_id):
    if 'loggedin' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    exam_id = None

    try:
        # الحصول على exam_id من جدول الربط exam_questions
        cursor.execute("""
            SELECT exam_id FROM exam_questions 
            WHERE question_id = %s 
            LIMIT 1
        """, (question_id,))
        exam_data = cursor.fetchone()

        if not exam_data:
            flash("لم يتم ربط السؤال بأي امتحان", "warning")
            return redirect(url_for('dashboard'))

        exam_id = exam_data['exam_id']

        # جلب بيانات السؤال الأساسية
        cursor.execute("SELECT * FROM questions WHERE id = %s", (question_id,))
        question = cursor.fetchone()

        if not question:
            flash("السؤال غير موجود", "danger")
            return redirect(url_for('dashboard'))

        # جلب الاختيارات لأسئلة MCQ
        choices = []
        if question['question_type'] == 'mcq':
            cursor.execute("""
                SELECT * FROM choices 
                WHERE question_id = %s 
                ORDER BY choice_order
            """, (question_id,))
            choices = cursor.fetchall()

        if request.method == 'POST':
            # تحديث البيانات الأساسية
            new_text = request.form['question_text']
            new_type = request.form['question_type']

            # تحديد الإجابة الصحيحة حسب النوع
            new_correct = ""
            if new_type == 'mcq':
                new_correct = request.form.get('correct_choice', '')
            elif new_type == 'true_false':
                new_correct = request.form.get('correct_answer_tf', '')
            else:
                new_correct = request.form.get('correct_answer_short', '')

            # تحديث السؤال في قاعدة البيانات
            cursor.execute("""
                UPDATE questions 
                SET question_text = %s,
                    question_type = %s,
                    correct_answer = %s 
                WHERE id = %s
            """, (new_text, new_type, new_correct, question_id))

            # معالجة اختيارات MCQ
            if new_type == 'mcq':
                for i in range(1, 5):
                    choice_text = request.form.get(f'choice{i}', '')
                    if i <= len(choices):
                        # تحديث الخيارات الموجودة
                        cursor.execute("""
                            UPDATE choices 
                            SET choice_text = %s 
                            WHERE question_id = %s AND choice_order = %s
                        """, (choice_text, question_id, i))
                    else:
                        # إضافة خيارات جديدة إذا لزم الأمر
                        cursor.execute("""
                            INSERT INTO choices (question_id, choice_order, choice_text)
                            VALUES (%s, %s, %s)
                        """, (question_id, i, choice_text))
            else:
                # حذف جميع الخيارات إذا تغير النوع
                cursor.execute("DELETE FROM choices WHERE question_id = %s", (question_id,))

            mysql.connection.commit()
            flash("تم تحديث السؤال بنجاح ✅", "success")
            return redirect(url_for('add_questions_to_exam', exam_id=exam_id))

        return render_template('edit_question.html',
                               question=question,
                               choices=choices,
                               exam_id=exam_id)

    except Exception as e:
        flash(f"حدث خطأ غير متوقع: {str(e)}", "danger")
        return redirect(url_for('add_questions_to_exam', exam_id=exam_id)) if exam_id else redirect(
            url_for('dashboard'))
    finally:
        cursor.close()



@app.route('/toggle_exam_visibility/<int:exam_id>')
def toggle_exam_visibility(exam_id):
    if 'loggedin' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    try:
        # التحقق من ملكية المادة
        cursor.execute("""
            SELECT e.id 
            FROM exams e
            INNER JOIN subjects s ON e.subject_id = s.id
            WHERE e.id = %s AND s.teacher = %s
        """, (exam_id, session['username']))

        if not cursor.fetchone():
            flash("ليست لديك صلاحية لهذا الإجراء", "danger")
            return redirect(url_for('subjects'))

        # تبديل الحالة
        cursor.execute("""
            UPDATE exams 
            SET is_visible = NOT is_visible 
            WHERE id = %s
        """, (exam_id,))

        mysql.connection.commit()
        flash("تم تغيير الحالة بنجاح", "success")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"خطأ في التحديث: {str(e)}", "danger")

    finally:
        cursor.close()

    return redirect(url_for('subjects'))


@app.route('/contact')
def contact():
    return render_template('contact.html')
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
