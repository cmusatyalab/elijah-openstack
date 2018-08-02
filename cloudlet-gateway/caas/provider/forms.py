# -*- coding: utf-8 -*-
"""User forms."""
import wtforms
from flask_login import current_user
from flask_wtf import FlaskForm, Form
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import validators

from caas.provider.models import App, Cluster, User


class RegisterForm(Form):
    """Register form."""

    username = wtforms.StringField('Username',
                           validators=[validators.DataRequired(), validators.Length(min=3, max=25)])
    email = wtforms.StringField('Email',
                        validators=[validators.DataRequired(), validators.Email(), validators.Length(min=6, max=40)])
    password = wtforms.PasswordField('Password',
                             validators=[validators.DataRequired(), validators.Length(min=6, max=40)])
    confirm = wtforms.PasswordField('Verify password',
                            [validators.DataRequired(), validators.EqualTo('password', message='Passwords must match')])

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(RegisterForm, self).__init__(*args, **kwargs)
        self.user = None

    def validate(self):
        """Validate the form."""
        initial_validation = super(RegisterForm, self).validate()
        if not initial_validation:
            return False
        user = User.query.filter_by(username=self.username.data).first()
        if user:
            self.username.errors.append('Username already registered')
            return False
        user = User.query.filter_by(email=self.email.data).first()
        if user:
            self.email.errors.append('Email already registered')
            return False
        return True


class NewAppForm(FlaskForm):
    """Register form."""
    appname = wtforms.StringField('Name', validators=[validators.DataRequired(), validators.Length(min=1, max=40)])
    clustername = wtforms.SelectField('Cluster', validators=[validators.DataRequired()])
    config_file = FileField(validators=[FileRequired(),
                                        FileAllowed(['yml', 'yaml'], 'YAML files only')
                                        ])

    def __init__(self, selection_choices):
        super(NewAppForm, self).__init__()
        self.clustername.choices = selection_choices

    def validate(self):
        """Validate the form."""
        initial_validation = super(NewAppForm, self).validate()
        if not initial_validation:
            return False
        app = App.query.filter_by(name=self.appname.data, user_id=current_user.id).first()
        if app:
            self.appname.errors.append('App name already registered')
            return False
        cluster = Cluster.query.filter_by(name=self.clustername.data, user_id=current_user.id).first()
        if not cluster:
            self.clustername.errors.append('No such cluster')
            return False
        return True

class NewClusterForm(FlaskForm):
    """Register form."""
    clustername = wtforms.StringField('Name', validators=[validators.DataRequired(), validators.Length(min=1, max=40)])
    vCPUs = wtforms.IntegerField('vCPUs', validators=[validators.DataRequired()])
    vMem = wtforms.IntegerField('vMem', validators=[validators.DataRequired()])
    network = wtforms.SelectField('Network', validators=[validators.DataRequired()])
    network_bridge_name = wtforms.StringField('Bridge Name', validators=[validators.DataRequired()])
    acceleration = wtforms.SelectField('Acceleration', validators=[validators.DataRequired()])
    clustertype = wtforms.SelectField('Type', validators=[validators.DataRequired()])

    def __init__(self):
        super(NewClusterForm, self).__init__()
        self.acceleration.choices = [("", "---"), ('GPU', 'GPU')]
        self.clustertype.choices = [('Kubernetes', 'Kubernetes')]
        self.network.choices = [("", "---"), ('Bridge', 'Bridge')]

    def validate(self):
        """Validate the form."""
        initial_validation = super(NewClusterForm, self).validate()
        if not initial_validation:
            return False
        app = App.query.filter_by(name=self.appname.data, user_id=current_user.id).first()
        if app:
            self.appname.errors.append('App name already registered')
            return False
        cluster = Cluster.query.filter_by(name=self.clustername.data, user_id=current_user.id).first()
        if not cluster:
            self.clustername.errors.append('No such cluster')
            return False
        return True
