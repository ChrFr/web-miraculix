from django import forms
from django.conf import settings
import time
import json

from orcaserver.models import Step, InjectableConversionError
from orcaserver.management import OrcaManager, parse_injectables

TYPE_FORM_MAP = {
    'float': forms.FloatField,
    'int': forms.IntegerField,
    'bool': forms.BooleanField,
    'str': forms.CharField,
    #'dict': forms.MultiValueDict,
    'list': forms.MultiValueField
}


def get_python_module():
    """return the currently set python module"""
    return OrcaManager().default_module

def get_available_modules():
    available = settings.ORCA_MODULES.get('available', {})
    return [(v.get('path'),
             k + f" - {v['description']} " if 'description' in v else '')
            for k, v in available.items()]


class OrcaSettingsForm(forms.Form):
    choices = forms.ChoiceField(
        widget=forms.Select(
        attrs={'onchange': "document.querySelector('input[name=\"module\"]').value=this.value;"}),
        choices=get_available_modules(),
        label='Available modules',
        initial=get_python_module,
    )
    module = forms.CharField(
        max_length=100,
        widget=forms.widgets.TextInput(
            attrs={'size': 100, }),
        label='Python module with orca imports',
        initial=get_python_module,
    )


class InjectableValueForm(forms.Form):
    value = forms.CharField(label='Value', max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        self.injectable = kwargs.pop('injectable', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        value = self.cleaned_data['value']

        try:
            _ = self.injectable.validate_value(value=value)
        except InjectableConversionError as e:
            self.add_error('value', str(e))
            raise forms.ValidationError(str(e))


class ProjectForm(forms.Form):
    name = forms.CharField(label='Project name', max_length=255)
    description = forms.CharField(label='Description')

    def __init__(self, *args, **kwargs):
        active_mod = kwargs.pop('module')
        project_name = kwargs.pop('project_name', '')
        project_description = kwargs.pop('project_description', '')
        initial_values = json.loads(kwargs.pop('init', '{}'))
        super().__init__(*args, **kwargs)
        self.fields['name'].initial = project_name
        self.fields['description'].initial = project_description
        available_mods = settings.ORCA_MODULES.get('available')

        mod_descs = list(filter(lambda mod: mod['path'] == active_mod,
                                available_mods.values()))
        if len(mod_descs) > 1:
            raise Exception('more than one module defined with same path in '
                            'settings')
        if len(mod_descs) == 0:
            return kwargs

        module_name = mod_descs[0]['path']
        initial = mod_descs[0].get('init')
        manager = OrcaManager()
        uid = str(time.time())
        orca = manager.get(uid , module=module_name)
        meta = parse_injectables(orca)
        for injectable in initial:
            desc = meta[injectable]
            value = initial_values.get(injectable, desc['value'])
            typ = desc['data_class'].replace('builtins.', '')
            field_form = TYPE_FORM_MAP.get(typ, forms.CharField)
            field = field_form(
                label=f'initial value for "{injectable}" - {desc["docstring"]}',
                initial=value)
            self.fields[injectable] = field
        manager.remove(uid)


class StepForm(forms.ModelForm):
    class Meta:
        model = Step
        exclude = ()
        widgets={
            'is_active': forms.RadioSelect(
                attrs={
                    'class':'custom-control-input custom-control-label',
                }
            ),
        }
