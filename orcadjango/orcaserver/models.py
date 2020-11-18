from django.db import models
from django.contrib.gis.db.models import MultiPolygonField
from django.core.validators import int_list_validator
from django.urls import reverse
import pandas as pd
import xarray as xr
import ast
import importlib

from orcaserver.management import OrcaManager


class NameModel(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Project(NameModel):
    name = models.TextField()
    description = models.TextField()
    module = models.TextField(default='')
    # ToDo: saved as plain text, maybe custom field here so that you don't need
    # to dump/load outside
    init = models.TextField(default='{}')


class Scenario(NameModel):
    """Scenario"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    name = models.TextField()


class InjectableConversionError(ValueError):
    """exception raised when the conversion of an injectable fails"""


class Injectable(NameModel):
    name = models.TextField()
    scenario = models.ForeignKey(Scenario,
                                 on_delete=models.CASCADE,
                                 null=True)
    value = models.TextField(null=True)
    changed = models.BooleanField(default=False)
    can_be_changed = models.BooleanField(default=True)
    docstring = models.TextField(null=True, blank=True)
    module = models.TextField(null=True, blank=True)
    groupname = models.TextField(null=False, blank=False, default='')
    order = models.IntegerField(null=False, default=1)
    datatype = models.TextField(null=True, blank=True)
    data_class = models.TextField(null=True, blank=True)
    valid = models.BooleanField(null=False, default=True)
    parent_injectables = models.TextField(
        validators=[int_list_validator], default='[]')

    def __str__(self):
        return f'{self.scenario} - {self.name}'

    @property
    def calculated_value(self):
        """The calculated value"""
        if self.can_be_changed:
            return self.value
        orca = OrcaManager().get(self.scenario.id)
        return orca.get_injectable(self.name)

    @property
    def valid_value(self) -> bool:
        """The calculated value"""
        if self.can_be_changed:
            return self.valid
        orca = OrcaManager().get(self.scenario.id)
        try:
            orca.get_injectable(self.name)
        except Exception as e:
            return False
        return True

    @property
    def repr_html(self) -> str:
        """HTML-representation of the value according to the type"""
        try:
            if self.datatype == 'DataFrame':
                ret = self.calculated_value.to_html()
            if self.datatype in ['DataArray', 'Dataset']:
                ret = self.calculated_value._repr_html_()
            ret = str(self.calculated_value)
        except Exception as e:
            ret = repr(e)
        return ret

    # ToDo: move validation to form
    def validate_value(self, value=None):
        """validate the value of the injectable"""
        #  get original type of injectable value (if not available, use string)
        module_class = self.data_class.split('.')
        module_name = '.'.join(module_class[:-1])
        classname = module_class[-1]
        original_type = getattr(importlib.import_module(module_name),
                                classname, str)
        if value is None:
            value = self.value
        # compare to evaluation or value
        if value is None:
            orca = OrcaManager().get(self.scenario.id)
            func = orca._injectable_function.get(self.name)
            if func:
                converted_value = func()
            else:
                converted_value = orca.get_injectable(self.name)
        elif issubclass(original_type, str):
            converted_value = value
        else:
            try:
                converted_value = ast.literal_eval(value)
                if not isinstance(converted_value, original_type):
                    #  try to cast the value using the original type
                    converted_value = original_type(value)
            except (SyntaxError, ValueError, TypeError) as e:

                # if casting does not work, raise warning
                # and use original value
                msg = (f'Injectable `{self.name}` with value `{value}` '
                       f'could not be casted to type `{original_type.__name__}`.'
                       f'Injectable Value was not overwritten.'
                       f'Error message: {repr(e)}')
                raise InjectableConversionError(msg)
        return converted_value

    @property
    def parent_injectable_values(self):
        parent_injectables = ast.literal_eval(self.parent_injectables)
        injectables = Injectable.objects.filter(id__in=parent_injectables)
        inj_names = injectables.values_list('name', flat=True)
        return ','.join(inj_names)

    @property
    def parent_injectable_urls(self):
        reverse_url = reverse('injectables')
        return {name: f'{reverse_url}{name}'
                for name in self.parent_injectable_values.split(',')}


class Step(NameModel):
    name = models.TextField()
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    started = models.DateTimeField(null=True)
    finished = models.DateTimeField(null=True)
    success = models.BooleanField(default=False)
    order = models.IntegerField(null=True)
    active = models.BooleanField(default=True)
    docstring = models.TextField(null=True, blank=True)


class LogEntry(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    message = models.TextField(blank=True)
    level = models.TextField(default='INFO')
    timestamp = models.DateTimeField()