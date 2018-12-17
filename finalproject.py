import os
import requests
import json
import requests_oauthlib
import webbrowser
import json
from pprint import pprint

from flask import Flask, render_template, session, redirect, request, url_for, flash
from flask_script import Manager, Shell
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FileField, PasswordField, BooleanField, SelectMultipleField, ValidationError, IntegerField
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.debug = True
app.use_reloader = True
app.config['SECRET_KEY'] = 'hard to guess string from si364'

app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://localhost/dvoorSI364FinalProjectTwitterAPI"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app)

#Association Tables
#many-to-many
tweet_to_collection = db.Table('search_tweets', db.Column('tweet_id', db.Integer, db.ForeignKey('tweet.id')), db.Column('collection_id', db.Integer, db.ForeignKey('personaltweetcollection.id')))

#one-to-many
user_to_collection = db.Table('user_collection', db.Column('tweet_id', db.Integer, db.ForeignKey('tweet.id')), db.Column('term', db.String(32), db.ForeignKey('searchterm.term')))

########################
######## Models ########
########################

#User model
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    tweets =  db.relationship('PersonalTweetCollection', backref='User')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

## DB load function
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) # returns User object or None

class Tweet(db.Model):
    __tablename__ = "tweet"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text())

    def __repr__(self):
        return "The tweet content is {}".format(self.title)

class PersonalTweetCollection(db.Model):
    __tablename__ = "personaltweetcollection"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    tweets = db.relationship('Tweet', secondary=tweet_to_collection, backref=db.backref('personaltweetcollection', lazy='dynamic'), lazy='dynamic')

class SearchTerm(db.Model):
    __tablename__ = 'searchterm'
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(256), unique=True)

    tweets = db.relationship('Tweet', secondary=user_to_collection, backref=db.backref('searchterm', lazy='dynamic'), lazy='dynamic')

    def __repr__(self):
        return "{}".format(self.term)

########################
######## Forms #########
########################
class RegistrationForm(FlaskForm):
    email = StringField('Email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Register User')

    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')

class TweetSearchForm(FlaskForm):
    search = StringField("Enter a hashtag term to search tweets (without including the #)", validators=[Required()])
    submit = SubmitField('Submit')

    def validate_search(self, field):
        if field.data.startswith('#'):
            raise ValidationError('Please do not include the #')

class CollectionCreateForm(FlaskForm):
    name = StringField('Collection Name',validators=[Required()])
    tweet_picks = SelectMultipleField('Tweets to include')
    submit = SubmitField("Create Collection")

    def validate_tweet_picks(self, field):
        print(field.data)
        if len(field.data) == 0:
            raise ValidationError("A tweet collection must contain at least one tweet.")

class UpdateButtonForm(FlaskForm):
    submit = SubmitField("Update")

class DeleteButtonForm(FlaskForm):
    submit = SubmitField('Delete')

class UpdateCollectionNameForm(FlaskForm):
    name = StringField("Please enter a new new name for the Tweet Collection", validators=[Required()])
    submit = SubmitField('Update')

# class NumberofCharactersForm(FlaskForm):
#     number_of_retweets = Int



def get_api_data(hashtag):
    f = open("creds.txt", 'r')
    (client_key, client_secret, resource_owner_key, resource_owner_secret, verifier) = json.loads(f.read())
    f.close()

    hashtag = "%23" + hashtag
    protected_url = 'https://api.twitter.com/1.1/account/settings.json'
    oauth = requests_oauthlib.OAuth1Session(client_key,client_secret=client_secret,resource_owner_key=resource_owner_key,resource_owner_secret=resource_owner_secret)

    r = oauth.get("https://api.twitter.com/1.1/search/tweets.json", params = {'q': str(hashtag), 'count' : 10})

    res = r.json()

    f = open('nested.txt', 'w')
    f.write(json.dumps(res))
    f.close()

    f = open('nested.txt', 'r')
    temp = json.loads(f.read())
    statuses = temp['statuses']


    tweets = []
    for x in statuses:
        for y in x:
            if y == 'text':
                tweets.append(x[y])


    return tweets


def get_tweet_by_id(id):
    t = Tweet.query.filter_by(id=id).first()
    return t

#################################
#### get_or_create functions ####
#################################

def get_or_create_tweet(db_session, text):
    tweet = db_session.query(Tweet).filter_by(text=text).first()
    if tweet:
        return tweet
    else:
        tweet1 = Tweet(text=text)
        db.session.add(tweet1)
        db.session.commit()
        return tweet1

def get_or_create_search_term(db_session, term, my_tweet_lst = []):
    search_term = db_session.query(SearchTerm).filter_by(term=term).first()
    if search_term:
        print("Found Term")
        return search_term
    else:
        print("Term Added")
        search_term = SearchTerm(term=term)
        api_info = get_api_data(term)
        for x in api_info:
            tweet = get_or_create_tweet(db_session, text=x)
            search_term.tweets.append(tweet)
        db_session.add(search_term)
        db_session.commit()
        return search_term


def get_or_create_collection(db_session, name, current_user, my_tweet_lst):
    collection = PersonalTweetCollection.query.filter_by(name=name, user_id=current_user.id).first()
    if collection:
        return collection
    else:
        collection = PersonalTweetCollection(name=name, user_id=current_user.id, tweets=[])
        for x in my_tweet_lst:
            collection.tweets.append(x)
        db_session.add(collection)
        db_session.commit()
        return collection

########################
#### View functions ####
########################

## Error handling routes
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html',form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('index'))

@app.route('/register',methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You can now log in!')
        return redirect(url_for('login'))
    else:
        errors = [v for v in form.errors.values()]
        if len(errors) > 0:
            flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
        return render_template('register.html',form=form)

@app.route('/secret')
@login_required
def secret():
    return "Only authenticated users can do this! Try to log in or contact the site admin."

@app.route('/', methods=["GET","POST"])
def index():
    form = TweetSearchForm()
    if request.method =="POST" and form.validate_on_submit():
        term = get_or_create_search_term(db.session, term=form.search.data)
        return redirect(url_for('search_results', search_term=form.search.data))
    else:
        errors = [v for v in form.errors.values()]
        if len(errors) > 0:
            flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
        return render_template('index.html', form=form)


@app.route('/searched_tweets/<search_term>')
def search_results(search_term):
    hashtag = SearchTerm.query.filter_by(term=search_term).first()
    my_tweets = hashtag.tweets.all()
    return render_template('searched_tweets.html', tweets=my_tweets, term=hashtag)

@app.route('/search_terms')
def search_terms():
    all_terms = SearchTerm.query.all()
    return render_template("search_terms.html", all_terms=all_terms)

@app.route('/all_tweets')
def all_tweets():
    tweets = Tweet.query.all()
    return render_template('all_tweets.html', all_tweets=tweets)

@app.route('/create_collection', methods=["GET","POST"])
@login_required
def create_collection():
    form = CollectionCreateForm()
    tweets = Tweet.query.all()
    choices = [(t.id, t.text) for t in tweets]
    form.tweet_picks.choices = choices

    if request.method == "POST":
        tweets_chosen = form.tweet_picks.data
        tweets_objects = [get_tweet_by_id(int(id)) for id in tweets_chosen]
        get_or_create_collection(db.session, name=form.name.data, current_user=current_user, my_tweet_lst=tweets_objects)
        print("Collection Created!")
        return redirect(url_for("collections"))
    else:
        errors = [v for v in form.errors.values()]
        if len(errors) > 0:
            flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
        return render_template('create_collection.html', form=form)


@app.route('/collections', methods=["GET", "POST"])
@login_required
def collections():
    form = DeleteButtonForm()
    form2 = UpdateButtonForm()
    collections = PersonalTweetCollection.query.filter_by(user_id=current_user.id).all()
    return render_template('collections.html', collections=collections, form=form, form2=form2)

@app.route('/collection/<id_number>')
def one_collection(id_number):
    id_number = int(id_number)
    collection = PersonalTweetCollection.query.filter_by(id=id_number).first()
    tweets = collection.tweets.all()
    return render_template('collection.html', collection=collection, tweets=tweets)

@app.route('/delete/<name>', methods=["GET", "POST"])
@login_required
def delete(name):
    collection = PersonalTweetCollection.query.filter_by(name=name).first()
    db.session.delete(collection)
    db.session.commit()
    flash("Collection Deleted!")
    return redirect(url_for('collections'))

@app.route('/update/<name>',methods=["GET","POST"])
def update(name):
    form = UpdateCollectionNameForm()
    if form.validate_on_submit():
        updated_name = form.name.data
        current = PersonalTweetCollection.query.filter_by(name=name).first()
        current.name = updated_name
        db.session.commit()
        flash('The name of the tweet collection {} has been changed'.format(name))
        return redirect(url_for('collections'))
    return render_template('update_item.html',name=name,form=form)



if __name__ == "__main__":
    db.create_all()
    app.run()