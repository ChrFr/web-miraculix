from django.db import models
from django.core.validators import int_list_validator
from django.urls import reverse
from django.conf import settings
import ast

from orcaserver.management import OrcaManager, OrcaTypeMap


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
    docstring = models.TextField(null=True, blank=True)
    module = models.TextField(null=True, blank=True)
    groupname = models.TextField(null=False, blank=False, default='')
    order = models.IntegerField(null=False, default=1)
    datatype = models.TextField(null=True, blank=True)
    data_class = models.TextField(null=True, blank=True)
    valid = models.BooleanField(null=False, default=True)
    parent_injectables = models.TextField(
        validators=[int_list_validator], default='[]')
    choices = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.scenario} - {self.name}'

    @property
    def can_be_changed(self):
        if self.parent_injectable_values:
            return False
        conv = OrcaTypeMap.get(self.data_class)
        # only data types with an implemented converter should be changable
        # via UI, the default converter has no datatype
        if not conv.data_type:
            return False
        return True

    @property
    def calculated_value(self):
        """The calculated value"""
        if self.can_be_changed:
            return self.value
        orca = OrcaManager().get(self.scenario.id,
                                 module=self.scenario.project.module)
        return orca.get_injectable(self.name)

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

    @property
    def validated_value(self):
        # ToDo: some validation
        value = self.value
        if self.can_be_changed:
            conv = OrcaTypeMap.get(self.data_class)
            value = conv.to_value(value)
        return value

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

    def save(self, **kwargs):
        if self.value is not None and not isinstance(self.value, str):
            conv = OrcaTypeMap.get(self.data_class)
            self.value = conv.to_str(self.value)
        super().save(**kwargs)

    def get_form_field(self):
        converter = OrcaTypeMap.get(self.data_class)
        if self.choices:
            choices = self.choices.split(',')
            choices = tuple(zip(choices, choices))
            field = converter.get_choice_field(
                value=self.validated_value, choices=choices)
        else:
            field = converter.get_form_field(value=self.validated_value,
                                             label=f'Value')
            field.widget.attrs['placeholder'] = self.docstring
        return field


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


class Run(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    models.OneToOneField(Scenario, on_delete=models.CASCADE)
    started = models.DateTimeField(null=True)
    finished = models.DateTimeField(null=True)
    success = models.BooleanField(default=False)
    run_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                               on_delete=models.SET_NULL, null=True)
