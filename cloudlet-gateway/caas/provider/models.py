# -*- coding: utf-8 -*-
"""User models."""
import datetime as dt
import os
import pdb
import re

import jwt
from enum import Enum
from flask import current_app
from flask_login import UserMixin

from caas.core.openstackutils import get_fixed_ip_from_floating_ip
from caas.database import Column, Model, SurrogatePK, db, reference_col, relationship
from caas.extensions import bcrypt


class Role(SurrogatePK, Model):
    """A role for a provider."""

    __tablename__ = 'roles'
    name = Column(db.String(80), unique=True, nullable=False)
    user_id = reference_col('users', nullable=True)
    user = relationship('User', backref='roles')

    def __init__(self, name, **kwargs):
        """Create instance."""
        db.Model.__init__(self, name=name, **kwargs)

    def __repr__(self):
        """Represent instance as a unique string."""
        return '<Role({name})>'.format(name=self.name)


class User(UserMixin, SurrogatePK, Model):
    """A user of the app."""

    __tablename__ = 'users'
    username = Column(db.String(80), unique=True, nullable=False)
    email = Column(db.String(80), unique=True, nullable=False)
    #: The hashed password
    password = Column(db.Binary(128), nullable=True)
    created_at = Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    first_name = Column(db.String(30), nullable=True)
    last_name = Column(db.String(30), nullable=True)
    active = Column(db.Boolean(), default=False)
    is_admin = Column(db.Boolean(), default=False)

    clusters = relationship('Cluster', backref='user')
    apps = relationship('App', backref='user')

    def __init__(self, username, email, password=None, **kwargs):
        """Create instance."""
        db.Model.__init__(self, username=username, email=email, **kwargs)
        if password:
            self.set_password(password)
        else:
            self.password = None

    def set_password(self, password):
        """Set password."""
        self.password = bcrypt.generate_password_hash(password)

    def check_password(self, value):
        """Check password."""
        return bcrypt.check_password_hash(self.password, value)

    @property
    def full_name(self):
        """Full user name."""
        return '{0} {1}'.format(self.first_name, self.last_name)

    def __repr__(self):
        """Represent instance as a unique string."""
        return '<User({username!r})>'.format(username=self.username)

    def encode_auth_token(self, user_id):
        """
        Generates the Auth Token
        :return: string
        """
        try:
            payload = {
                'exp': dt.datetime.utcnow() + dt.timedelta(days=0, seconds=5),
                'iat': dt.datetime.utcnow(),
                'sub': user_id
            }
            return jwt.encode(
                payload,
                current_app.config.get('SECRET_KEY'),
                algorithm='HS256'
            )
        except Exception as e:
            return e

    @staticmethod
    def decode_auth_token(auth_token):
        """
        Decodes the auth token
        :param auth_token:
        :return: integer|string
        """
        try:
            payload = jwt.decode(auth_token, current_app.config.get('SECRET_KEY'))
            return payload['sub']
        except jwt.ExpiredSignatureError:
            return 'Signature expired. Please log in again.'
        except jwt.InvalidTokenError:
            return 'Invalid token. Please log in again.'


class App(SurrogatePK, Model):
    """An app of a provider."""

    class APP_TYPE(Enum):
        VMs = 'VMs'
        Containers = 'Containers'
        Mixed = 'Mixed'

    __tablename__ = 'apps'
    name = Column(db.String(80), nullable=False)
    instance = relationship('Instance', backref='app')
    cluster_id = reference_col('clusters', nullable=True)
    user_id = reference_col('users', nullable=True)
    type = Column(db.String(80), nullable=False)

    def __init__(self, name, **kwargs):
        """Create instance."""
        db.Model.__init__(self, name=name, **kwargs)

    def __repr__(self):
        """Represent instance as a unique string."""
        return '<App({name})>'.format(name=self.name)

    @property
    def config_file_name(self):
        return {
            self.APP_TYPE.Mixed: '{0}_{1}.yml'.format(self.user_id, self.name),
            self.APP_TYPE.VMs: '{0}_{1}_vm.yml'.format(self.user_id, self.name),
            self.APP_TYPE.Containers: '{0}_{1}_ct.yml'.format(self.user_id, self.name),
        }

        # @property
        # def config_file(self, storage_dir):
        #     ct = None
        #     with open(os.path.join(storage_dir, self.config_file_name[self.CONFIG_TYPE.Single])) as f:
        #         ct = f.read()
        #     return ct


class Cluster(SurrogatePK, Model):
    """An app of a provider."""

    __tablename__ = 'clusters'
    name = Column(db.String(80), unique=True, nullable=False)
    size = Column(db.Integer, nullable=False)
    nameserver_port = Column(db.String(20), nullable=True)
    app = relationship('App', backref='cluster')
    user_id = reference_col('users', nullable=True)

    def __init__(self, name, size, **kwargs):
        """Create instance."""
        if 'nameserver_port' not in kwargs:
            kwargs['nameserver_port'] = current_app.config['CLOUDLET_NAMESERVER_DEFAULT_PORT']
        db.Model.__init__(self, name=name, size=size, **kwargs)

    def __repr__(self):
        """Represent instance as a unique string."""
        return '<Cluster ({name})>'.format(name=self.name)

    @property
    def leader_ip(self):
        # private ip
        public_ip = self.leader_public_ip
        fixed_ip = None
        # parse env output
        if public_ip:
            # TODO: Using VM private ip is a fix for LEL limitation. See README.md
            # translate to private ip for LEL
            fixed_ip = get_fixed_ip_from_floating_ip(public_ip)
        return fixed_ip

    @property
    def leader_public_ip(self):
        # not requiring docker machine as a dependency
        from caas.core.machine import Machine
        dm = Machine()
        leader_env_str = dm.env(machine=self.leader_name).split('\n')
        pat = re.compile(r'export DOCKER_HOST="tcp://(.*):\d+"')
        ip = None
        # parse env output
        for env_str in leader_env_str:
            mat = pat.match(str(env_str))
            if mat:
                ip = mat.group(1)
                break
        return ip

    @property
    def leader_name(self):
        return '{}-0'.format(self.name)
