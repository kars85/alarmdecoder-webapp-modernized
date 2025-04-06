# -*- coding: utf-8 -*-

from uuid import uuid4

from flask import (Blueprint, render_template, current_app, request,
                   flash, url_for, redirect, session, abort)
from flask_mail import Message
from flask_babel import gettext as _
from flask_login import login_required, login_user, current_user, logout_user, confirm_login, login_fresh

from ..user import User, UserDetail, UserHistory, FailedLogin
from ..extensions import db, mail, login_manager, oid
from .forms import SignupForm, LoginForm, RecoverPasswordForm, ReauthForm, ChangePasswordForm, OpenIDForm, CreateProfileForm, LicenseAgreementForm
from ..settings import Setting
from socket import gethostname, gethostbyname
from ..utils import user_is_authenticated

frontend = Blueprint('frontend', __name__)


#@frontend.route('/login/openid', methods=['GET', 'POST'])
#@oid.loginhandler
def login_openid():
    if user_is_authenticated(current_user):
        return redirect(url_for('user.index'))

    form = OpenIDForm()
    if form.validate_on_submit():
        openid = form.openid.data
        current_app.logger.debug('login with openid(%s)...' % openid)
        return oid.try_login(openid, ask_for=['email', 'fullname', 'nickname'])
    return render_template('frontend/login_openid.html', form=form, error=oid.fetch_error())


#@oid.after_login
def create_or_login(resp):
    user = User.query.filter_by(openid=resp.identity_url).first()
    if user and login_user(user):
        flash('Logged in', 'success')
        return redirect(oid.get_next_url() or url_for('user.index'))
    return redirect(url_for('frontend.create_profile', next=oid.get_next_url(),
            name=resp.fullname or resp.nickname, email=resp.email,
            openid=resp.identity_url))


#frontend.route('/create_profile', methods=['GET', 'POST'])
def create_profile():
    if user_is_authenticated(current_user):
        return redirect(url_for('user.index'))

    form = CreateProfileForm(name=request.args.get('name'),
            email=request.args.get('email'),
            openid=request.args.get('openid'))

    if form.validate_on_submit():
        user = User()
        form.populate_obj(user)
        db.session.add(user)
        db.session.commit()

        if login_user(user):
            return redirect(url_for('user.index'))

    return render_template('frontend/create_profile.html', form=form)


@frontend.route('/')
def index():
    if user_is_authenticated(current_user):
        return redirect(url_for('keypad.index'))

    return render_template('index.html')


#@frontend.route('/search')
def search():
    keywords = request.args.get('keywords', '').strip()
    pagination = None
    if keywords:
        page = int(request.args.get('page', 1))
        pagination = User.search(keywords).paginate(page, 1)
    else:
        flash(_('Please input keyword(s)'), 'error')
    return render_template('frontend/search.html', pagination=pagination, keywords=keywords)


def login_history_add(user, ip):
    user_history = UserHistory()
    user_history.user_id = user.id
    user_history.ip_address = ip
    userAgentString = request.headers.get('User-Agent')
    user_history.user_agent_string = userAgentString
    db.session.add(user_history)
    db.session.commit()
   

def failed_login_add(name, ip):
    failed_login = FailedLogin()
    failed_login.name = name
    failed_login.ip_address = ip
    userAgentString = request.headers.get('User-Agent')
    failed_login.user_agent_string = userAgentString

    db.session.add(failed_login)
    db.session.commit()


@frontend.route('/login', methods=['GET', 'POST'])
def login():
    if user_is_authenticated(current_user):
        return redirect(url_for('keypad.index'))

    form = LoginForm(login=request.args.get('login', None),
                     next=request.args.get('next', None))

    if form.validate_on_submit():
        user, authenticated = User.authenticate(form.login.data,
                                    form.password.data)

        if user and authenticated:
            remember = request.form.get('remember') == 'y'
            if login_user(user, remember=remember):
                flash(_("Logged in"), 'success')
                login_history_add(user, request.remote_addr)
                license = Setting.get_by_name('license_agreement', default=False).value
                if not license:
                    return redirect(url_for('frontend.license'))

            return redirect(form.next.data or url_for('keypad.index'))
        else:
            failed_login_add(form.login.data, request.remote_addr)
            flash(_('Sorry, invalid login'), 'error')

    return render_template('frontend/login.html', form=form)


@frontend.route('/reauth', methods=['GET', 'POST'])
@login_required
def reauth():
    form = ReauthForm(next=request.args.get('next'))

    if request.method == 'POST':
        user, authenticated = User.authenticate(current_user.name,
                                    form.password.data)
        if user and authenticated:
            confirm_login()
            current_app.logger.debug('reauth: %s' % session['_fresh'])
            flash(_('Reauthenticated.'), 'success')
            return redirect('/change_password')

        flash(_('Password is wrong.'), 'error')
    return render_template('frontend/reauth.html', form=form)


@frontend.route('/logout')
@login_required
def logout():
    logout_user()
    flash(_('Logged out'), 'success')
    return redirect(url_for('frontend.index'))


@frontend.route('/signup', methods=['GET', 'POST'])
def signup():
    if user_is_authenticated(current_user):
        return redirect(url_for('user.index'))

    form = SignupForm(next=request.args.get('next'))

    if form.validate_on_submit():
        user = User()
        user.user_detail = UserDetail()
        form.populate_obj(user)

        db.session.add(user)
        db.session.commit()

        if login_user(user):
            return redirect(form.next.data or url_for('user.index'))

    return render_template('frontend/signup.html', form=form)


@frontend.route('/change_password', methods=['GET', 'POST'])
def change_password():
    user = None

    if user_is_authenticated(current_user):
        if not login_fresh():
            return login_manager.needs_refresh()
        user = current_user
    elif 'activation_key' in request.values and 'email' in request.values:
        activation_key = request.values['activation_key']
        email = request.values['email']
        user = User.query.filter_by(activation_key=activation_key) \
                         .filter_by(email=email).first()
        session['password_activation_key'] = activation_key
        session['password_reset_email'] = email

    if session['password_activation_key'] is not None and session['password_reset_email'] is not None:
        user = User.query.filter_by(activation_key=session['password_activation_key']) \
                         .filter_by(email=session['password_reset_email']).first()

    if user is None:
        abort(403)

    form = ChangePasswordForm(activation_key=user.activation_key)

    if form.validate_on_submit():
        user.password = form.password.data
        user.activation_key = None
        db.session.add(user)
        db.session.commit()

        session['password_activation_key'] = None
        session['password_reset_email'] = None

        flash(_("Your password has been changed, please log in again"),
              "success")
        return redirect(url_for("frontend.login"))

    return render_template("frontend/change_password.html", form=form)


@frontend.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    form = RecoverPasswordForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            flash('Please see your email for instructions on '
                  'how to access your account', 'success')

            user.activation_key = str(uuid4())
            db.session.add(user)
            db.session.commit()
            url = url_for('frontend.change_password', email=user.email, activation_key=user.activation_key, _external=True)
            html = render_template('macros/_reset_password.html', project='AlarmDecoder Webapp', username=user.name, url=url)
            message = Message(subject='Reset your password for the AlarmDecoder Webapp', html=html, recipients=[user.email])
            mail.send(message)

            return render_template('frontend/reset_password.html', form=form)
        else:
            flash(_('Sorry, no user found for that email address'), 'error')

    return render_template('frontend/reset_password.html', form=form)


@frontend.route('/help')
def help():
    return render_template('frontend/footers/help.html', active="help")

@frontend.route('/license', methods=['GET', 'POST'])
def license():
    form = LicenseAgreementForm()
    if form.validate_on_submit():
        license = Setting.get_by_name('license_agreement', False)
        license.value = True

        db.session.add(license)
        db.session.commit()

        return redirect(url_for('keypad.index'))

    return render_template('frontend/license.html', form=form)
