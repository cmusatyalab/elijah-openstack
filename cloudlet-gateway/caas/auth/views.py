# -*- coding: utf-8 -*-
"""app views."""
import os
import pdb

from flask import Blueprint, render_template, request, flash, url_for, redirect, current_app, send_from_directory, \
    make_response, jsonify
from flask_jwt_extended import create_access_token
from flask_restful import Api, Resource, reqparse

from caas.extensions import csrf_protect, bcrypt
from caas.provider.models import User

blueprint = Blueprint('auth', __name__, url_prefix='/auth')
api = Api(blueprint)
csrf_protect.exempt(blueprint)

class LoginAPI(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, location='json')
        parser.add_argument('password', type=str, required=True, location='json')
        args = parser.parse_args(strict=True)
        username, password = args['username'], args['password']
        user = User.query.filter_by(
            username=username
        ).first()
        if user and bcrypt.check_password_hash(
                user.password, password):
            ret = {
                'status': 'success',
                'access_token': create_access_token(identity=user.id)
            }
            return ret, 200
        else:
            ret = {
                'status': 'failed',
            }
            return ret, 401
api.add_resource(LoginAPI, '/login')
