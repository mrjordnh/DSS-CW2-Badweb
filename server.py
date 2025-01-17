import datetime
import sqlite3
import os
from functools import wraps

from flask import Flask,g,render_template,redirect,request,session,url_for

app = Flask(__name__)
app.secret_key = 'thisisabadsecretkey'

DATABASE = 'database.sqlite'
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)

    def make_dicts(cursor, row):
        return dict((cursor.description[idx][0], value)
                    for idx, value in enumerate(row))

    db.row_factory = make_dicts

    return db

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def std_context(f):
    @wraps(f)
    def wrapper(*args,**kwargs):
        context={}
        request.context = context
        if 'userid' in session:
            context['loggedin'] = True
            context['username'] = session['username']
        else:
            context['loggedin'] = False
        return f(*args,**kwargs)
    return wrapper

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route("/")
@std_context
def index():
    posts = query_db('SELECT posts.creator,posts.date,posts.title,posts.content,users.name,users.username FROM posts JOIN users ON posts.creator=users.userid ORDER BY date DESC LIMIT 10')

    def fix(item):
        item['date'] = datetime.datetime.fromtimestamp(item['date']).strftime('%Y-%m-%d %H:%M')
        item['content'] = '%s...'%(item['content'][:200])
        return item

    context = request.context
    context['posts'] = map(fix, posts)
    return render_template('index.html', **context)

@app.route("/<uname>/")
@std_context
def users_posts(uname=None):
    cid = query_db('SELECT userid FROM users WHERE username="%s"'%(uname))
    if len(cid)<1:
        return 'No such user'

    cid = cid[0]['userid']
    query = 'SELECT date,title,content FROM posts WHERE creator=%s ORDER BY date DESC'%(cid)
    
    context = request.context

    def fix(item):
        item['date'] = datetime.datetime.fromtimestamp(item['date']).strftime('%Y-%m-%d %H:%M')
        return item
    a = query_db(query)
    context['posts'] = map(fix, query_db(query))
    return render_template('user_posts.html', **context)

@app.route("/login/", methods=['GET', 'POST'])
@std_context
def login():
    username = request.form.get('username','')
    password = request.form.get('password','')
    context = request.context

    if len(username)<1 and len(password)<1:
        return render_template('login.html', **context)

    query = "SELECT userid FROM users WHERE username='%s'"%(username)
    account = query_db(query)
    user_exists = len(account)>0

    query = "SELECT userid FROM users WHERE username='%s' AND password='%s'"%(username, password)
    print(query)
    account2 = query_db(query)
    print(account)
    pass_match = len(account2)>0

    if user_exists:
        if pass_match:
            session['userid'] = account[0]['userid']
            session['username'] = username
            session['token'] = str(os.urandom(16))
            return redirect(url_for('index'))
        else:
            # Return wrong password
            return redirect(url_for('login_fail', error='Wrong password'))
    else:
        # Return no such user
        return redirect(url_for('login_fail', error='No such user'))

@app.route("/loginfail/")
@std_context
def login_fail():
    context = request.context
    context['error_msg'] = request.args.get('error','Unknown error')
    return render_template('login_fail.html',**context)

@app.route("/logout/")
def logout():
    session.pop('userid', None)
    session.pop('username', None)
    session.pop('token', None)
    return redirect('/')

@app.route("/post/", methods=['GET', 'POST'])
@std_context
def new_post():
    if 'userid' not in session:
        return redirect(url_for('login'))

    userid = session['userid']
    print(userid)
    context = request.context


    if request.method=='GET':
        session['token'] = str(os.urandom(16))
        return render_template('new_post.html', token=session.get('token'), **context)

    csrf = request.form.get('csrf')

    if csrf == session.get('token'):
        date = datetime.datetime.now().timestamp()
        title = request.form.get('title')
        content = request.form.get('content')
        query = "INSERT INTO posts (creator, date, title, content) VALUES ('%s',%d,'%s','%s')" % (
        userid, date, title, content)
        insert = query_db(query)

        get_db().commit()

    return redirect('/')

@app.route("/reset/", methods=['GET', 'POST'])
@std_context
def reset():
    context = request.context

    email = request.form.get('email','')
    if email=='':
        return render_template('reset_request.html')

    query = "SELECT email FROM users WHERE email='%s'"%(email)
    exists = query_db(query)
    if len(exists)<1:
        return render_template('no_email.html', **context)
    else:
        context['email'] = email
        return render_template('sent_reset.html', **context)

@app.route("/search/")
@std_context
def search_page():
    context = request.context
    search = request.args.get('s', '')

    #query = "SELECT posts.creator,posts.title,posts.content,users.username FROM posts JOIN users ON posts.creator=users.userid WHERE users.username LIKE '%%%s%%' ORDER BY date DESC LIMIT 10;"%(search)
    query = "SELECT username FROM users WHERE username LIKE '%%%s%%';"%(search)
    users = query_db(query)
    #for user in users:
        #post['content'] = '%s...'%(post['content'][:50])
    context['users'] = users
    context['query'] = search
    return render_template('search_results.html', **context)

# @app.route("/resetdb/<token>")
# def resetdb(token=None):
#     if token=='secret42':
#         import create_db
#         create_db.delete_db()
#         create_db.create()
#         return 'Database reset'
#     else:
#         return 'Nope',401

if __name__ == '__main__':
    app.run()
