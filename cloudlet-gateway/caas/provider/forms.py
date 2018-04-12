# -*- coding: utf-8 -*-
"""User forms."""
from flask_login import current_user
from flask_wtf import Form, FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import PasswordField, StringField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from .models import User, App, Cluster


class RegisterForm(Form):
    """Register form."""

    username = StringField('Username',
                           validators=[DataRequired(), Length(min=3, max=25)])
    email = StringField('Email',
                        validators=[DataRequired(), Email(), Length(min=6, max=40)])
    password = PasswordField('Password',
                             validators=[DataRequired(), Length(min=6, max=40)])
    confirm = PasswordField('Verify password',
                            [DataRequired(), EqualTo('password', message='Passwords must match')])

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
    appname = StringField('Name', validators=[DataRequired(), Length(min=1, max=40)])
    clustername = SelectField('Cluster', validators=[DataRequired()])
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
