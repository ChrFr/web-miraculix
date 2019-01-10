from collections import OrderedDict
from django.views.generic import ListView
from django.views.generic.edit import FormView, BaseFormView
import orca
from orcaserver.views import ScenarioMixin
from orcaserver.models import Injectable, Scenario
from orcaserver.forms import InjectableValueForm
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.urls import reverse


class InjectablesView(ScenarioMixin, ListView):
    model = Injectable
    template_name = 'orcaserver/injectables.html'
    context_object_name = 'injectables'

    def get_queryset(self):
        """Return the injectables with their values."""
        scenario = self.get_scenario()
        inj = orca.list_injectables()
        injectables = Injectable.objects.filter(name__in=inj, scenario=scenario)
        return injectables

    def post(self, request, *args, **kwargs):
        scenario_id = request.POST.get('scenario')
        if request.POST.get('reset'):
            for inj in self.get_queryset():
                orig_value = orca._injectable_backup[inj.name]
                inj.value = orig_value
                inj.save()
                #orca.add_injectable(inj.name, orig_value)
        return HttpResponseRedirect(request.path_info)


class InjectableView(ScenarioMixin, FormView):
    template_name = 'orcaserver/injectable.html'
    form_class = InjectableValueForm

    @property
    def name(self):
        return self.kwargs.get('name')

    def get_initial(self):
        """Return the initial data to use for forms on this view."""
        inj = Injectable.objects.get(name=self.name,
                                     scenario=self.get_scenario())
        return {'value': inj.value, }

    def post(self, request, *args, **kwargs):
        inj = Injectable.objects.get(name=self.name,
                                     scenario=self.get_scenario())
        if request.POST.get('change'):
            new_value = request.POST.get('value')
            if new_value != inj.value:
                inj.changed = True
            inj.value = new_value
            inj.save()
            #orca.add_injectable(inj.name, new_value)

        elif request.POST.get('reset'):
            orig_value = orca._injectable_backup[self.name]
            inj.value = orig_value
            inj.save()
            #orca.add_injectable(inj.name, orig_value)
            return HttpResponseRedirect(request.path_info)
        return HttpResponseRedirect(reverse('injectables'))
