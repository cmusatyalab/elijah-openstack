# -*- coding: utf-8 -*-
"""Public section, including homepage and signup."""
import pdb

from flask import Blueprint, flash, redirect, render_template, request, url_for, session, current_app
from flask_jwt_extended import create_access_token, revoke_token
from flask_login import login_required, login_user, logout_user

from caas.extensions import login_manager
from caas.public.forms import LoginForm
from caas.provider.forms import RegisterForm
from caas.provider.models import User
from caas.utils import flash_errors

blueprint = Blueprint('public', __name__, static_folder='../static')


@login_manager.user_loader
def load_user(user_id):
    """Load provider by ID."""
    return User.get_by_id(int(user_id))


@blueprint.route('/', methods=['GET', 'POST'])
def home():
    """Home page."""
    form = LoginForm(request.form)
    # Handle logging in
    if request.method == 'POST':
        if form.validate_on_submit():
            login_user(form.user)
            flash('You are logged in.', 'success')
            # acquire rest api token
            session['token'] = create_access_token(identity=form.user.id)
            current_app.logger.debug('grant user {} rest api token {}'.format(form.user, session['token']))
            redirect_url = request.args.get('next') or url_for('provider.apps')
            return redirect(redirect_url)
        else:
            flash_errors(form)
    return render_template('public/home.html', form=form)


@blueprint.route('/logout/')
@login_required
def logout():
    """Logout."""
    logout_user()
    token = session.pop('token', None)

#    if token:
#        revoke_token(token)
    flash('You are logged out.', 'info')
    return redirect(url_for('public.home'))


@blueprint.route('/register/', methods=['GET', 'POST'])
def register():
    """Register new provider."""
    form = RegisterForm(request.form)
    if form.validate_on_submit():
        User.create(username=form.username.data, email=form.email.data, password=form.password.data, active=True)
        flash('Thank you for registering. You can now log in.', 'success')
        return redirect(url_for('public.home'))
    else:
        flash_errors(form)
    return render_template('public/register.html', form=form)


@blueprint.route('/about/')
def about():
    """About page."""
    form = LoginForm(request.form)
    return render_template('public/about.html', form=form)
