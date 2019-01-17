from django.views.generic import ListView
from orcaserver.models import Scenario, Injectable, Step
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.urls import reverse
import orca
import os


class ScenarioMixin:
    _backup = {}

    def get_scenario(self):
        """get the selected scenario"""
        scenario_pk = self.request.session.get('scenario')
        try:
            scenario = Scenario.objects.get(pk=scenario_pk,
                                            module=orca._python_module)
        except Scenario.DoesNotExist:
            scenario = None
        return scenario

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        scenario = self.get_scenario()
        kwargs['scenario_name'] = scenario.name if scenario else 'none'
        kwargs['python_module'] = orca._python_module
        return kwargs


overwritable_types = (str, bytes, int, float, complex,
                      tuple, list, dict, set, bool, None.__class__)


def create_injectables(scenario):
    for name in orca.list_injectables():
        value = orca.get_injectable(name)
        inj, created = Injectable.objects.get_or_create(name=name,
                                                        scenario=scenario)
        if created:
            # for new injectables, set the initial value
            inj.value = value
            #  and check if the original type is overwritable
            inj.can_be_changed = isinstance(value, overwritable_types)
            inj.save()


def create_steps(scenario):
    for name in orca.list_steps():
        Step.objects.create(name=name, scenario=scenario)


class ScenariosView(ScenarioMixin, ListView):
    model = Scenario
    template_name = 'orcaserver/scenarios.html'
    context_object_name = 'scenarios'

    def get_queryset(self):
        """Return the injectables with their values."""
        scenarios = Scenario.objects.filter(module=orca._python_module)
        return scenarios

    def post(self, request, *args, **kwargs):
        scenario_id = request.POST.get('scenario')
        if request.POST.get('select'):
            self.request.session['scenario'] = scenario_id
        elif request.POST.get('delete'):
            Scenario.objects.get(id=scenario_id).delete()
        elif request.POST.get('refresh'):
            scenario = Scenario.objects.get(id=scenario_id)
            create_injectables(scenario)
        return HttpResponseRedirect(request.path_info)

    def create(request):
        if request.method == 'POST':
            name = request.POST.get('name')
            if not name:
                return HttpResponseBadRequest('name can not be empty')
            module = orca._python_module
            scenario = Scenario.objects.create(name=name, module=module)
            request.session['scenario'] = scenario.id
            create_injectables(scenario)
        return HttpResponseRedirect(reverse('scenarios'))
