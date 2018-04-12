import os
import pdb

import ruamel.yaml
from flask import Blueprint, abort, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_restful import Resource, Api, fields, marshal_with

from caas.core.exc import UnknownFormatError
from caas.extensions import csrf_protect
from caas.provider.models import App as AppModel, Cluster
from caas.utils import get_config_file_path

blueprint = Blueprint('api', __name__, url_prefix='/api', static_folder='../static')
api = Api(blueprint, decorators=[jwt_required])
app_info = {'name': fields.String,
            'config': fields.String, }
csrf_protect.exempt(blueprint)


def parse_config_file_data(config_data, app):
    app_machine_types = []
    for app_type in AppModel.APP_TYPE:
        app_type_keyword = app_type.value
        if app_type_keyword in config_data:
            app_machine_types.append(app_type)
            part_config_data = config_data[app_type_keyword]
            with open(get_config_file_path(app.config_file_name[app_type]), 'w+') as f:
                ruamel.yaml.dump(part_config_data, stream=f, Dumper=ruamel.yaml.RoundTripDumper)

    if len(app_machine_types) < 1:
        raise UnknownFormatError("Failed to parse config file. No keywords VMs nor Containers")

    if AppModel.APP_TYPE.VMs in app_machine_types and AppModel.APP_TYPE.Containers in app_machine_types:
        return AppModel.APP_TYPE.Mixed
    else:
        return app_machine_types[0]


def rm_config_files(app):
    for app_type in AppModel.APP_TYPE:
        file_path = get_config_file_path(app.config_file_name[app_type])
        if os.path.isfile(file_path):
            os.remove(file_path)

def create_application(name, user_id, uploaded_file, cluster):
    new_app = AppModel(name, user_id=user_id, cluster_id=cluster.id)
    config_data = ruamel.yaml.load(uploaded_file.read(), ruamel.yaml.RoundTripLoader)
    app_type = parse_config_file_data(config_data, new_app)
    new_app.type = app_type.value
    new_app.save()
    cluster.app.append(new_app)
    cluster.update(app=cluster.app)

class App(Resource):
    @marshal_with(app_info)
    def get(self, name):
        app = AppModel.query.filter_by(name=name).first()
        if not app:
            abort(404)
        return app

    def put(self, name):
        current_user = get_jwt_identity()
        uploaded_file = request.files['config']
        cluster_name = request.form.get('cluster')
        cluster = Cluster.query.filter_by(name=cluster_name, user_id=current_user).first()
        if not cluster:
            abort(400, "Cluster Not Found")
        try:
            create_application(name, current_user, uploaded_file, cluster)
        except ruamel.yaml.YAMLError:
            current_app.logger.error("Invalid yaml file")
            abort(400, "Invalid YAML file")
        except UnknownFormatError:
            current_app.logger.error("Invalid configuration file")
            abort(400, "Invalid YAML file")
        return {'status': 'success'}, 200



            #     new_app = AppModel(name, user_id=current_user, cluster_id=cluster.id)
        #     config_data = ruamel.yaml.load(uploaded_file.read(), ruamel.yaml.RoundTripLoader)
        #     # don't save the original for now
        #     # with open(get_config_file_path(new_app.config_file_name[AppModel.CONFIG_TYPE.Single]), 'w+') as f:
        #     #     ruamel.yaml.dump(config_data, stream=f, Dumper=ruamel.yaml.RoundTripDumper)
        #     app_type = parse_config_file_data(config_data, new_app)
        #     new_app.type = app_type.value
        #     new_app.save()
        #     cluster.app.append(new_app)
        #     cluster.update(app=cluster.app)
        # except ruamel.yaml.YAMLError:
        #     current_app.logger.error("Invalid yaml file")
        #     abort(400, "Invalid YAML file")
        # except UnknownFormatError:
        #     current_app.logger.error("Invalid configuration file")
        #     abort(400, "Invalid YAML file")
        # return {'status': 'success'}, 200

    def delete(self, name):
        current_user = get_jwt_identity()
        new_app = AppModel.query.filter_by(name=name, user_id=current_user).first()
        if new_app:
            rm_config_files(new_app)
            new_app.delete()
            return {'status': 'success'}, 200
        else:
            return {'status': 'failed'}, 404


api.add_resource(App, '/app/<string:name>')
