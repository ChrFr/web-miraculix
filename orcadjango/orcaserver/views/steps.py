from collections import OrderedDict
from django.views.generic import ListView
from django.views.generic.edit import BaseFormView
from django.shortcuts import render, HttpResponseRedirect
import orca
from orcaserver.views import ScenarioMixin
from orcaserver.models import Step
from orcaserver.forms import StepsPopulateForm, StepsForm


def select_steps(request):
    """select some steps"""
    if request.method == 'POST':
        form = StepsForm(request.POST, request.FILES)
        if form.is_valid():
            steps = form.cleaned_data['steps']
            orca.run(steps)
            return HttpResponseRedirect('/orca/selectsteps')
    else:
        form = StepsForm()
    return render(request, 'orcaserver/step_selection.html', {'form': form})


class StepsView(BaseFormView, ListView, ScenarioMixin):
    model = Step
    template_name = 'orcaserver/steps.html'
    context_object_name = 'step_dict'
    form_class = StepsPopulateForm
    success_url = '/orca/steps'

    def get_queryset(self):
        """Return the steps with their values."""
        qs = OrderedDict(((name, orca.get_step(name))
                          for name in orca.list_steps()))
        return qs

    def form_valid(self, form):
        action = self.request.POST.get('action')
        scenario = self.get_scenario()
        if action == 'Populate':
            #  enter to model
            for name in orca.list_steps():
                step, created = Step.objects.get_or_create(
                    name=name,
                    scenario=scenario)
                step.value = orca.get_step(name)
                step.changed = False
                step.save()
        if action == 'Save':
            #  save values for scenario
            for name in orca.list_steps():
                step, created = Step.objects.get_or_create(
                    name=name,
                    scenario=scenario)
                step.value = orca.get_step(name)
                step.save()

        if action == 'Load':
            #  save values for scenario
            for name in orca.list_steps():
                step, created = Step.objects.get_or_create(
                    name=name,
                    scenario=scenario)

        return super().form_valid(form)
