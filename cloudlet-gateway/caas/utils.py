# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
import os

from flask import flash, current_app


def flash_errors(form, category='warning'):
    """Flash all errors for a form."""
    for field, errors in form.errors.items():
        for error in errors:
            flash('{0} - {1}'.format(getattr(form, field).label.text, error), category)


def get_config_file_path(config_file_name):
    config_file_path = os.path.join(current_app.config['UPLOADED_CONFIG_FILE_DIR'],
                                    config_file_name)
    return config_file_path
