# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
import os

from flask import flash, current_app

def validate_form(form_handler):
    """Decorator to help call validation on form."""
    def _validate_before_handler(current_form, *args, **kwargs):
        if not current_form.validate_on_submit():
            return False, current_form
        else:
            return True, form_handler(current_form, *args, **kwargs)
    return _validate_before_handler

def flash_errors(form, category='warning'):
    """Flash all errors for a form."""
    for field, errors in form.errors.items():
        for error in errors:
            flash('{0} - {1}'.format(getattr(form, field).label.text, error), category)


def get_config_file_path(config_file_name):
    config_file_path = os.path.join(current_app.config['UPLOADED_CONFIG_FILE_DIR'],
                                    config_file_name)
    return config_file_path
