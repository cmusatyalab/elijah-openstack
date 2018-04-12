# -*- coding: utf-8 -*-
from caas.database import Column, Model, SurrogatePK, db, reference_col, relationship
from caas.provider.models import App as AppModel

class Customer(SurrogatePK, Model):
    """An instance of an app for a customer."""

    __tablename__ = 'customers'
    name = Column(db.String(80), unique=True, nullable=False)
    instance = relationship('Instance', backref='customer')

    def __init__(self, name, **kwargs):
        """Create instance."""
        db.Model.__init__(self, name=name, **kwargs)

    def __repr__(self):
        """Represent instance as a unique string."""
        return '<Customer({name})>'.format(name=self.name)


class Instance(SurrogatePK, Model):
    """An instance of an app for a customer."""

    __tablename__ = 'instances'
    vm_stack_id = Column(db.String(200), unique=False, nullable=True)
    ct_stack_id = Column(db.String(200), unique=False, nullable=True)
    name = Column(db.String(80), nullable=False)
    app_id = reference_col('apps', nullable=True)
    customer_id = reference_col('customers', nullable=True)

    def __init__(self, name, app_id, customer_id, **kwargs):
        """Create instance."""
        db.Model.__init__(self, name=name, app_id=app_id, customer_id=customer_id, **kwargs)

    def __repr__(self):
        """Represent instance as a unique string."""
        return '<Instance({name})>'.format(name=self.name)

    @property
    def stack_ids(self):
        return {
            AppModel.APP_TYPE.VMs: self.vm_stack_id,
            AppModel.APP_TYPE.Containers: self.ct_stack_id
        }
