from flask import *
from flask_wtf import Form
from wtforms import StringField,FileField,SubmitField, SelectField, PasswordField, TextAreaField
from wtforms.validators import *
from flask_bootstrap import Bootstrap
from flaskext.mysql import MySQL
import html
import os
from flask import Flask, request, redirect, url_for
from werkzeug.utils import secure_filename
from flask_uploads import UploadSet, configure_uploads, IMAGES
from flask_share import Share
from bs4 import BeautifulSoup

#running of flask server virtual environment
#source /home/web/venv/bin/activate

app = Flask(__name__)
Bootstrap(app)
share = Share(app)

#wtf form for editor/writer login
class LoginForm(Form):
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=20)])

#mysql connection setup
mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = None
app.config['MYSQL_DATABASE_DB'] = 'db_news_portal'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
mysql.init_app(app)

conn = mysql.connect()
cursor =conn.cursor()

#execute sql statements
def sqlExecute(query, vals):
    cursor = conn.cursor()
    cursor.execute(query, vals)
    conn.commit()
    cursor.close()

from array import *

#returns an array of values
def sqlDatas(query, vals, i):
    cursor = conn.cursor()
    cursor.execute(query, vals)
    datas = []
    arraydata = []
    try:
        if i == 1:
            arraydata = list(cursor.fetchone())
        else:
            datas = list(cursor.fetchall())
            for data in datas:
                data = list(data)
                arraydata.append(data)
    except TypeError:
        print(TypeError)
    cursor.close()
    print("from my function: ",arraydata)
    return arraydata

#photo upload
photos = UploadSet('photos', IMAGES)
app.config['UPLOADED_PHOTOS_DEST'] = 'static/img'
configure_uploads(app, photos)

#date format
def myDate(a):
    return str(a.strftime("%I"))+":"+str(a.strftime("%M"))+" "+str(a.strftime("%p"))+" | "+str(a.strftime("%B"))+" "+str(a.strftime("%d"))

#times ago format
def pretty_date(time=False):
    from datetime import datetime
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time,datetime):
        diff = now - time
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(round(second_diff / 60)) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str(round(second_diff / 3600)) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(day_diff / 7) + " weeks ago"
    if day_diff < 365:
        return str(day_diff / 30) + " months ago"
    return str(day_diff / 365) + " years ago"


#returns the sections of the articles
def sections():
    sectionsdb = sqlDatas("select title from article_sections", None, None)
    mysec = []
    for section in sectionsdb:
        for i in section:
            mysec.append(i)
    return mysec

#returns the number of articles per section
def no_of_articles():
    num_of_article_per_section = []
    for section in sections():
        count = sqlDatas("select count(*) from tbl_articles where section=%s", section, 1)[0]
        num_of_article_per_section.append(count)

    return num_of_article_per_section


#a form using wtf for creating articles
class ArticleForm(Form):
    headline = StringField('Headline', validators=[InputRequired()])
    byline = StringField('By', validators=[InputRequired()])
    sectionsdb = sections()
    opt_Ar = []
    for i in sectionsdb:
        opt_Ar.append((i,i))

    print(opt_Ar)
    section = SelectField(
        'Section',
        choices=opt_Ar)
    body = TextAreaField('Body', validators=[Length(min=5)])
    btn_publish = SubmitField('Publish Article')
    btn_save = SubmitField('Save as draft')
    photo = FileField('Photo')
    photographer = StringField('Photograph by')
    photo_caption = TextAreaField('Photo Caption')
    status = None

#returns the position of the current user
def position(un):
    return sqlDatas("select position from tbl_admin_users where username=%s",un,1)[0]

#returns the full name of the current user
def FullName(un):
    return sqlDatas("select Name from tbl_admin_users where username=%s",un,1)[0]

#login page for editor and writer
@app.route('/login', methods=['GET','POST'])
def login():
    form1 = LoginForm()
    session['offset'] = 0
    if session.get('is_login',None) is True:
        return redirect('/admin/dashboard/'+sections()[0]+'/'+str(session['offset']))
    else:
        if request.method == 'POST':
            if form1.validate_on_submit():
                username = request.form[form1.username.name]
                password = request.form[form1.password.name]
                login_data = sqlDatas("select * from tbl_admin_users where username=%s and `Status`='Enabled'", username, 1)
                try:
                    if login_data is not None and login_data[2] == password:
                        session['is_login'] = True
                        session['username'] = username
                        session['current_section'] = sections()[0]
                        flash("Login Successful!\nWelcome "+username+"!","success")
                        return redirect('/admin/dashboard/'+sections()[0]+'/'+str(session['offset']))
                except IndexError:
                    flash("Login Failed","danger")
                else:
                    flash("Login Failed","danger")

        return render_template('login.html', form=form1)

 
#creating of articles
@app.route('/admin/create/', methods=['POST','GET'])
def admin():
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)

        form1 = ArticleForm()
        headline = form1.headline.data
        body = form1.body.data
        byline = form1.byline.data
        section = form1.section.data
        photo_caption = form1.photo_caption.data
        photographer = form1.photographer.data
        stats = ''

        ar_count = no_of_articles()
        count_data = []
        counter = 0
        for i in sections():
            count_data.append([i,ar_count[counter]])
            counter = counter + 1

        if form1.validate_on_submit():
            if form1.btn_save.data:
                stats = 'DRAFT'
            elif form1.btn_publish.data:
                stats = 'PUBLISHED'

            filename = None
            pic_file = request.files[form1.photo.name]
            if pic_file:
                filename = photos.save(pic_file)

            sql_query = "INSERT INTO `db_news_portal`.`tbl_articles` (`uploadedby`, `headline`, `byline`, `body`, `section`,`photo_filename`, `photographer`, `photo_caption`, `status`) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s);" 
            vals = (un, headline, byline, body, section, filename, photographer, photo_caption, stats)
            sqlExecute(sql_query, vals)
            last_id = str(sqlDatas("select last_insert_id();", None, 1)[0])

            if not request.form['notebox'] == "":
                sqlExecute("INSERT into tbl_article_notes (article_id, commentedby, comment, `status`, position) VALUES (%s,%s,%s,%s,%s)", (last_id, un, request.form['notebox'], 'Pending', position(un)))

            flash("Article Saved! ","success")
            return redirect(url_for('admin'))
            
        return render_template('admin.html', form=form1, sec=session['current_section'], offset=session['offset'], position=position(un), FullName=FullName(un), sections=sections(), article_counts=count_data)


#dashboard
@app.route('/admin/dashboard/<name>/<offset>', methods=['GET','POST'])
def admin_dashboard(name, offset):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        total = sqlDatas("select count(*) from tbl_articles where section=%s",name,1)[0]
        pos = position(un)

        if int(offset) == 0:
            session['offset'] = 0
        
        newb = None
        oldb = None

        if int(offset) < 5:
            newb = 'disabled'
        elif int(offset) >= total-5:
            oldb = 'disabled'

        ar_count = no_of_articles()
        count_data = []
        counter = 0
        for i in sections():
            count_data.append([i,ar_count[counter]])
            counter = counter + 1

    
        drafts = sqlDatas("select count(*) from tbl_articles where section=%s and status='DRAFT'",name,1)[0]
        published = sqlDatas("select count(*) from tbl_articles where section=%s and status='PUBLISHED'",name,1)[0]

        article_data = sqlDatas("select * from tbl_articles where section=%s order by lastEdited desc limit 5 offset "+str(offset), name, None)
        article_data_list = []
        for i in article_data:
            i[10] = pretty_date(i[10])
            i[4] = str(BeautifulSoup(i[4], "lxml").text)
            if i[1] == un and i[9] == "DRAFT":
                i.append(True)
            else:
                i.append(False)
            article_data_list.append(i)

       
        return render_template('admin_dashboard.html', sections=sections(), articles=article_data_list, sec=name, offset=offset, newb=newb, oldb=oldb, article_counts=count_data, draft=drafts, published=published, position=pos, FullName=FullName(un))



@app.route('/admin/article/read/<article_id>', methods=['GET','POST'])
def admin_readmore(article_id):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        article = sqlDatas("select * from tbl_articles where id=%s", article_id, 1)
        article[10] = myDate(article[10])

        hasAccess = None

        if position(un) == "Editor" or ( article[1] == un and article[9] == "DRAFT"):
            hasAccess = True

        ar_count = no_of_articles()
        count_data = []
        counter = 0
        for i in sections():
            count_data.append([i,ar_count[counter]])
            counter = counter + 1

        list_note = []
        notes = sqlDatas("select * from tbl_article_notes where article_id=%s order by mtimestamp desc",article_id, None)
        for note in notes:      
            note[6] = pretty_date(note[6])
            list_note.append(note)
        
        return render_template('readmore.html', article=article, sections=sections(), FullName=FullName(un), article_counts=count_data, sec=sections()[0], hasAccess=hasAccess, notes=list_note, position=position(un))


#editing of article
@app.route('/admin/article/edit/<article_id>', methods=['GET','POST'])
def admin_edit(article_id):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        list_note = []
        notes = sqlDatas("select * from tbl_article_notes where article_id=%s order by mtimestamp desc",article_id, None)
        for note in notes:   
            note[6] = pretty_date(note[6])
            list_note.append(note)

        article = sqlDatas("select * from tbl_articles where id=%s", article_id, 1)
        
        if position(un) == "Editor" or (article[1] == un and article[9] == "DRAFT"):
            article = sqlDatas("select * from tbl_articles where id=%s", article_id, 1)
            form1 = ArticleForm()
            form1.headline.data = article[2]
            form1.body.data = article[4]
            form1.byline.data = article[3]
            form1.section.data = article[5]
            form1.photo_caption.data = article[8]
            form1.photographer.data = article[7]
            stats = article[9]

            ar_count = no_of_articles()
            count_data = []
            counter = 0
            for i in sections():
                count_data.append([i,ar_count[counter]])
                counter = counter + 1


            if form1.validate_on_submit():
                if form1.btn_save.data:
                    stats = 'DRAFT'
                elif form1.btn_publish.data:
                    stats = 'PUBLISHED'

                headline = request.form[form1.headline.name]
                byline = request.form[form1.byline.name]
                section = request.form[form1.section.name]
                body = request.form[form1.body.name]
                photo_caption = request.form[form1.photo_caption.name]
                photographer = request.form[form1.photographer.name]

                filename = None
                pic_file = request.files[form1.photo.name]
                if pic_file:
                    filename = photos.save(pic_file)
                else:
                    filename = article[6]

                sql_query = "UPDATE `tbl_articles` SET `headline`=%s, `byline`=%s,`body`=%s,`section`=%s, `photo_filename`=%s, `photographer`=%s, `photo_caption`=%s, `status`=%s WHERE (`id` = %s);"
                vals = (headline, byline, body, section, filename, photographer, photo_caption, stats, article[0])
                sqlExecute(sql_query, vals)

                flash("Article Edited!","success")
                return redirect('/admin/article/edit/'+str(article[0]))

        else:
            return redirect("/admin/dashboard/"+sections()[0]+"/0")
            

        return render_template('edit_article.html', form=form1, article=article, sec=sections()[0],FullName=FullName(un), sections=sections(), article_counts=count_data,notes=list_note, position=position(un))


#deleting of article
@app.route('/admin/article/delete/<sec>/<article_id>', methods=['GET','POST'])
def admin_delete(sec, article_id):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        
        article = sqlDatas("select * from tbl_articles where id=%s", article_id,1)

        if position(un) == "Editor" or (article[1] == un and article[9] == "DRAFT"):
            sqlExecute("DELETE FROM `tbl_articles` WHERE (`id` = %s );", article_id)
            sqlExecute("delete from tbl_article_notes where article_id=%s", article_id)
            flash("Article: \""+article[2]+"\" deleted!", "success")

        return redirect('/admin/dashboard/'+sec+'/'+str(session['offset']))

#pagination for dashboard older articles
@app.route('/admin/dashboard/<section>/older', methods=['GET','POST'])
def admin_older(section):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        session['offset'] = session['offset'] + 5
        return redirect('/admin/dashboard/'+section+'/'+str(session['offset']))

#pagination for dashboard newer articles
@app.route('/admin/dashboard/<section>/newer', methods=['GET','POST'])
def admin_newer(section):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        session['offset'] = session['offset'] - 5
        return redirect('/admin/dashboard/'+section+'/'+str(session['offset']))

#logout for editor/writer
@app.route('/admin/logout', methods=['GET','POST'])
def admin_logout():
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        session['is_login'] = False
        flash("You just logout!","info")
        return redirect('/login')

#form for resetting password in profile page
class ResetPassword(Form):
    currentPassword = PasswordField("Current Password", validators=[InputRequired(), Length(min=8, max=20)])
    newPassword = PasswordField("New Password", validators=[InputRequired(), Length(min=8, max=20)])
    retypePassword = PasswordField("Confirm Password", validators=[InputRequired(), Length(min=8, max=20)])

#profile page of editor/writer
@app.route('/admin/account/<stats>', methods=['GET','POST'])
def admin_account(stats):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        form = ResetPassword()
        un = session.get('username',None)
        passw = sqlDatas("select password from tbl_admin_users where username=%s", un, 1)[0]

        ar_count = no_of_articles()
        count_data = []
        counter = 0
        for i in sections():
            count_data.append([i,ar_count[counter]])
            counter = counter + 1
        user = sqlDatas("select * from tbl_admin_users where username=%s",un, 1)
        numdraft = sqlDatas("select count(*) from tbl_articles where uploadedby=%s and `status`='DRAFT';", un,1)[0]
        numpub = sqlDatas("select count(*) from tbl_articles where uploadedby=%s and `status`='PUBLISHED';", un, 1)[0]

        article_list = []
        if stats == "all":
            article_list = sqlDatas("select headline, lastEdited, status, id from tbl_articles where uploadedby=%s order by lastEdited desc",un, None)
        else:
            article_list = sqlDatas("select headline, lastEdited, status, id from tbl_articles where uploadedby=%s and `status`=%s order by lastEdited desc",(un,stats), None)

        for i in article_list:
            i[1] = myDate(i[1])
        

        if request.method == 'POST':
            currentP = request.form[form.currentPassword.name]
            newP = request.form[form.newPassword.name]
            reP = request.form[form.retypePassword.name]

            if currentP == passw and newP == reP:
                sqlExecute("UPDATE `tbl_admin_users` SET `password` = %s WHERE (`username` = %s);",(newP, un))
                flash("Password Changed!","success")
            else:
                flash("Unable to change password","danger")

                        
            return redirect('/admin/account/all')

        return render_template('account.html',un=un, user=user, article_list=article_list, form=form, numdraft=numdraft, numpub=numpub, article_counts=count_data, FullName=FullName(un), sec=sections()[0], sections=sections())


#searching of data
@app.route('/admin/search/<query>', methods=['GET','POST'])
def admin_search(query):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)

        ar_count = no_of_articles()
        count_data = []
        counter = 0
        for i in sections():
            count_data.append([i,ar_count[counter]])
            counter = counter + 1
        

        sql_query = "SELECT * FROM tbl_articles where headline like %s or byline like %s or body like %s or section like %s or photo_filename like %s or photographer like %s or photo_caption like %s or `status` like %s or lastEdited like %s order by lastEdited desc"
        sval = "%" + query + "%"
        vals = (sval,sval,sval,sval,sval,sval,sval,sval,sval)

        article_list = sqlDatas(sql_query, vals, None)
        for i in article_list:
            i[10] = myDate(i[10])


        sql_query_draft = "SELECT count(*) FROM tbl_articles where (headline like %s or byline like %s or body like %s or section like %s or photo_filename like %s or photographer like %s or photo_caption like %s or `status` like %s or lastEdited like %s) and `status`='DRAFT'"
        sval_draft = "%" + query + "%"
        vals_draft = (sval_draft,sval_draft,sval_draft,sval_draft,sval_draft, sval_draft,sval_draft,sval_draft,sval_draft)

        draft = sqlDatas(sql_query_draft,vals_draft, 1)[0]

        sql_query_published = "SELECT count(*) FROM tbl_articles where `status`='PUBLISHED' and (headline like %s or byline like %s or body like %s or section like %s or photo_filename like %s or photographer like %s or photo_caption like %s or `status` like %s or lastEdited like %s)"
        sval_published = "%" + query + "%"
        vals_published = (sval_published,sval_published,sval_published,sval_published, sval_published,sval_published,sval_published,sval_published,sval_published)

        published = sqlDatas(sql_query_published,vals_published,1)[0]   

        return render_template('search.html', article_list=article_list, search=query, sec=sections()[0], article_counts=count_data, FullName=FullName(un), sections=sections(), draft=draft, published=published)


#dashboard for categorized articles -draft or published
@app.route('/admin/dashboard/<name>/<stats>/<offset>', methods=['GET','POST'])
def admin_dashboard_stats(name, offset, stats):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        total = sqlDatas("select count(*) from tbl_articles where section=%s and `status`=%s",(name,stats), 1)[0]

        if int(offset) == 0:
            session['offset'] = 0
        
        pos = position(un)
        newb = None
        oldb = None

        if int(offset) < 5:
            newb = 'disabled'
        elif int(offset) >= total-5:
            oldb = 'disabled'

        ar_count = no_of_articles()
        count_data = []
        counter = 0
        for i in sections():
            count_data.append([i,ar_count[counter]])
            counter = counter + 1

        drafts = sqlDatas("select count(*) from tbl_articles where section=%s and status='DRAFT'",name, 1)[0]
        published = sqlDatas("select count(*) from tbl_articles where section=%s and status='PUBLISHED'",name,1)[0]

        vals = (name, stats)
        article_data = sqlDatas("select * from tbl_articles where section=%s and status=%s order by lastEdited desc limit 5 offset "+str(offset), vals, None)
        article_data_list = []
        for i in article_data:
            i[4] = str(BeautifulSoup(i[4], "lxml").text)
            i[10] = pretty_date(i[10])
            if i[1] == un and i[9] == "DRAFT":
                i.append(True)
            else:
                i.append(False)

            article_data_list.append(i)
       
        return render_template('dashboard_stats.html', sections=sections(), articles=article_data_list, sec=name, offset=offset, newb=newb, oldb=oldb, article_counts=count_data, draft=drafts, published=published, stats=stats, position=pos, FullName=FullName(un))



#pagination for categorized article - older
@app.route('/admin/dashboard/<section>/<stats>/older', methods=['GET','POST'])
def admin_stats_older(section,stats):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        session['offset'] = session['offset'] + 5
        return redirect('/admin/dashboard/'+section+'/'+stats+'/'+str(session['offset']))


#pagination for categorized article - newer
@app.route('/admin/dashboard/<section>/<stats>/newer', methods=['GET','POST'])
def admin_stats_newer(section,stats):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        session['offset'] = session['offset'] - 5
        return redirect('/admin/dashboard/'+section+'/'+stats+'/'+str(session['offset']))


#adding notes for read page
@app.route('/admin/article/read/notes/add/<article_id>/<note>', methods=['GET','POST'])
def admin_add_notes(article_id,note):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        sqlExecute("INSERT into tbl_article_notes (article_id, commentedby, comment, `status`, position) VALUES (%s,%s,%s,%s,%s)", (article_id, un, note, 'Pending', position(un)))
        flash("Note Posted!","info")
        return redirect('/admin/article/read/'+article_id)



#modification of notes for editor role
@app.route('/admin/article/read/<article_id>/<note_id>/notes/<dowhat>', methods=['GET','POST'])
def admin_notes_do(note_id,dowhat, article_id):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:

        un = session.get('username',None)
        if position(un) == "Editor":
            if dowhat.lower() == 'delete':
                sqlExecute("delete from tbl_article_notes where id=%s", note_id)
                flash("Note deleted","success")
            elif dowhat.lower() == 'done':
                sqlExecute("UPDATE tbl_article_notes set `status`='Done' where id=%s", note_id)
                flash("Note marked as done ","success")
            elif dowhat.lower() == 'pending':
                sqlExecute("UPDATE tbl_article_notes set `status`='Pending' where id=%s", note_id)
                flash("Note marked as pending ","success")

        return redirect("/admin/article/read/"+article_id)



#adding notes for the edit page
@app.route('/admin/article/edit/notes/add/<article_id>/<note>', methods=['GET','POST'])
def admin_add_notes_edit(article_id,note):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:
        un = session.get('username',None)
        sqlExecute("INSERT into tbl_article_notes (article_id, commentedby, comment, `status`, position) VALUES (%s,%s,%s,%s,%s)", (article_id, un, note, 'Pending', position(un)))
        flash("Note Posted!","info")
        return redirect('/admin/article/edit/'+article_id)



#odification of notes in edit page for editor role
@app.route('/admin/article/edit/<article_id>/<note_id>/notes/<dowhat>', methods=['GET','POST'])
def admin_notes_do_edit(note_id,dowhat, article_id):
    if session.get('is_login',None) is not True:
        return redirect('/login')
    else:

        un = session.get('username',None)
        if position(un) == "Editor":
            if dowhat.lower() == 'delete':
                sqlExecute("delete from tbl_article_notes where id=%s", note_id)
                flash("Note deleted","success")
            elif dowhat.lower() == 'done':
                sqlExecute("UPDATE tbl_article_notes set `status`='Done' where id=%s", note_id)
                flash("Note marked as done ","success")
            elif dowhat.lower() == 'pending':
                sqlExecute("UPDATE tbl_article_notes set `status`='Pending' where id=%s", note_id)
                flash("Note marked as pending ","success")

        return redirect("/admin/article/edit/"+article_id)



#viewer part
@app.route('/', methods=['GET','POST'])
def index():
    sections1 = sections()
    subData = []
    for section in sections1:
        data = sqlDatas("select * from tbl_articles WHERE section=%s and `status`='PUBLISHED' order by lastEdited desc;", section, 1)
        if data is not None:
            data[10] = myDate(data[10])
            subData.append(data)   
    hd = []
    homeData = sqlDatas("select * from tbl_articles where`status`='PUBLISHED' order by lastEdited desc limit 5;", None, None)
    for data in homeData:
        data[4] = str(BeautifulSoup(data[4], "lxml").text)
        data[10] = myDate(data[10])
        hd.append(data)

    if request.method == "POST":
        search = request.form["search"]
        return redirect("/search/"+search)
    
    return render_template('newspaper/index.html', sections=sections1, subdata=subData, homedata=hd, active="active")


#viewer part sections
@app.route('/<sectionshere>/<offset>', methods=['GET','POST'])
def index_section(sectionshere, offset):
    if int(offset) == 0:
        session['index_offset'] = 0

    total = sqlDatas("select count(*) from tbl_articles where section=%s and `status`='PUBLISHED'",sectionshere, 1)[0]

    newer = ""
    older = ""
    if int(offset) < 5:
        newer = 'disabled'
    if int(offset) >= total-5:
        older = 'disabled'

    #category in the side
    sections1 = sections() #navigation
    subData = []
    for section in sections1:
        data = sqlDatas("select * from tbl_articles WHERE section=%s and `status`='PUBLISHED' order by lastEdited desc;", section, 1)
        if data is not None:
            data[10] = myDate(data[10])
            subData.append(data)

    hd = []
    homeData = sqlDatas("select * from tbl_articles where section=%s and `status`='PUBLISHED' order by lastEdited desc limit 5 offset "+str(session['index_offset']), sectionshere, None)
    for data in homeData:
        data[4] = str(BeautifulSoup(data[4], "lxml").text)
        data[10] = myDate(data[10])
        hd.append(data)

    if request.method == "POST":
        search = request.form["search"]
        return redirect("/search/"+search)

    return render_template('newspaper/section.html', sections=sections1, subdata=subData, homedata=hd, section_ = sectionshere, older=older, newer=newer, active="active")

#viewer part pagination
@app.route('/<sectionshere>/go/<dowhat>', methods=['GET','POST'])
def index_section_go(sectionshere, dowhat):
    if dowhat == "older":
        session['index_offset'] = session['index_offset'] + 5
    elif dowhat == "newer":
        session['index_offset'] = session['index_offset'] - 5

    return redirect("/"+sectionshere+"/"+str(session['index_offset']))


#viewer part read more
@app.route('/read/<sectionshere>/<article_id>/<article_headline>', methods=['GET','POST'])
def index_read(sectionshere, article_id,article_headline):
    #category in the side
    sections1 = sections() #navigation
    subData = []
    for section in sections1:
        data = sqlDatas("select * from tbl_articles WHERE section=%s and `status`='PUBLISHED' order by lastEdited desc;", section, 1)
        if data is not None:
            data[10] = myDate(data[10])
            subData.append(data)

    hd = sqlDatas("select * from tbl_articles where id=%s",article_id, 1)
    hd[10] = myDate(hd[10])

    if request.method == "POST":
        search = request.form["search"]
        return redirect("/search/"+search)

    return render_template('newspaper/read.html', sections=sections1, subdata=subData, homedata=hd, section_ = sectionshere)


#viewer search
@app.route('/search/<search>', methods=['GET','POST'])
def index_search(search):
    #category in the side
    sections1 = sections() #navigation
    subData = []
    for section in sections1:
        data = sqlDatas("select * from tbl_articles WHERE section=%s and `status`='PUBLISHED' order by lastEdited desc;", section,1)
        if data is not None:
            data[10] = myDate(data[10])
            subData.append(data)

    sql_query = "SELECT * FROM tbl_articles where headline like %s or byline like %s or body like %s or section like %s or photo_filename like %s or photographer like %s or photo_caption like %s or lastEdited like %s order by lastEdited desc"
    sval = "%" + search + "%"
    vals = (sval,sval,sval,sval,sval,sval,sval,sval)
    results = sqlDatas(sql_query, vals, None)
    result = []
    for hd in results:
        hd[10] = myDate(hd[10])
        result.append(hd)


    if request.method == "POST":
        search = request.form["search"]
        return redirect("/search/"+search)

    return render_template('newspaper/search.html', sections=sections1, subdata=subData, results=result, searchMo = search)


#viewer part contact page
@app.route('/contact', methods=['GET','POST'])
def index_contact():
    sections1 = sections()
    subData = []
    for section in sections1:
        data = sqlDatas("select * from tbl_articles WHERE section=%s and `status`='PUBLISHED' order by lastEdited desc;", section, 1)
        if data is not None:
            data[10] = myDate(data[10])
            subData.append(data)   

    if request.method == "POST" and "search" in request.form:
        search = request.form["search"]
        return redirect("/search/"+search)
    
    return render_template('newspaper/contact.html', sections=sections1, subdata=subData)


##my database module
dbPassword = "admin"


#login page for the db admin
@app.route('/modify/database/login', methods=['GET','POST'])
def dblogin():
    if request.method == "POST":
        passw = request.form["password"]
        if passw == dbPassword:
            session["dblogin"] = True
            return redirect("/modify/database")
        else:
            session["dblogin"] = False
            flash("Login Failed", "danger")
    return render_template('dblogin.html')

#home page for db admin
@app.route('/modify/database', methods=['GET','POST'])
def dbhome():
    if session['dblogin']:
        data = sqlDatas("select * from tbl_admin_users order by id desc", None, None)
        sec = sqlDatas("select * from article_sections", None, None)
        return render_template('dbhome.html', data=data, sections=sec)
    else:
        return redirect("/modify/database/login")

#updating of user
@app.route('/modify/database/user/update/<id>', methods=['GET','POST'])
def dbedituser(id):
    if session['dblogin']:
        if request.method == "POST":
            name = request.form["name"]
            password = request.form["password"]
            position = request.form["position"]
            sqlExecute("UPDATE tbl_admin_users set `name`=%s, `password`=%s, `position`=%s WHERE (`id`=%s)", (name, password,position, id))
            flash("Updated!","success")
            return redirect('/modify/database')
    else:
        return redirect("/modify/database/login")

#disabling/enabling of user
@app.route('/modify/database/user/<id>/<stats>', methods=['GET','POST'])
def dbedituserstats(id, stats):
    if session['dblogin']:
        sqlExecute("UPDATE tbl_admin_users set `Status`=%s WHERE (`id`=%s)", (stats, id))
        flash("Status Updated!","success")
        return redirect('/modify/database')
    else:
        return redirect("/modify/database/login")

#searchng of user account
@app.route('/modify/database/user/search', methods=['GET','POST'])
def dbsearchuser():
    if session['dblogin']:
        if request.method == "POST":
            query = request.form["search"]
            sval = "%" + query + "%"
            data = sqlDatas("select * from tbl_admin_users where username like %s or name like %s order by id desc", (sval,sval), None)
            sec = sqlDatas("select * from article_sections", None, None)
            return render_template('dbhome.html', data=data, sections=sec)
    else:
        return redirect("/modify/database/login")


#adding of user account
@app.route('/modify/database/user/add', methods=['GET','POST'])
def dbadduser():
    if session['dblogin']:
        if request.method == "POST":
            username = request.form["Username"]
            name = request.form["name"]
            password = request.form["password"]
            position = request.form["position"]
            taken = sqlDatas("select count(*) from tbl_admin_users where username=%s", username, 1)[0]
            if taken > 0:
                flash("Username: "+username+" is already taken!", "info")
            else:
                if len(password) < 8:
                    flash("Password should be greater than 8 characters!","info")
                else:
                    sqlExecute("INSERT into tbl_admin_users (`Username`,`Password`,`Position`, `Name`, `Status`) VALUES(%s,%s,%s,%s,'Enabled');",(username, password, position, name))
                    flash("User Added!","success")
        
        return redirect('/modify/database')
    else:
        return redirect("/modify/database/login")


#updating of sections
@app.route('/modify/database/section/update/<id>', methods=['GET','POST'])
def dbeditsection(id):
    if session['dblogin']:
        if request.method == "POST":
            name = request.form["sectionname"]
            sqlExecute("UPDATE article_sections set `title`=%s WHERE (`idarticle_sections`=%s)", (name, id))
            flash("Section Updated!","success")
            return redirect('/modify/database')
    else:
        return redirect("/modify/database/login")

#removing of sections
@app.route('/modify/database/section/delete/<id>', methods=['GET','POST'])
def dbdeletesection(id):
    if session['dblogin']:
        if request.method == "POST":
            sqlExecute("delete from article_sections WHERE (`idarticle_sections`=%s)", (id))
            flash("Section Deleted!","success")
            return redirect('/modify/database')
    else:
        return redirect("/modify/database/login")

#adding of sections
@app.route('/modify/database/section/add', methods=['GET','POST'])
def dbaddsection():
    if session['dblogin']:
        if request.method == "POST":
            name = request.form["sectionname"]
            sqlExecute("INSERT into article_sections (`title`) VALUES(%s)", name)
            flash("Section Added!","success")
            return redirect('/modify/database')
    else:
        return redirect("/modify/database/login")

#db admin logout
@app.route('/modify/database/logout', methods=['GET','POST'])
def dblogout():
    session['dblogin'] = False
    return redirect("/modify/database/login")

######
if __name__ == "__main__":
    app.secret_key = '1234567890'

   # app.config['SESSION_TYPE'] = 'filesystem'
    app.run(debug=True)
