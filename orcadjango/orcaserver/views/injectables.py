from django.views.generic import ListView
from django.views.generic.edit import FormView
import orca
import numpy as np
from collections import OrderedDict
from orcaserver.views import ProjectMixin
from orcaserver.models import Injectable
from orcaserver.forms import InjectableValueForm
from django.http import HttpResponseRedirect
from django.urls import reverse


class InjectablesView(ProjectMixin, ListView):
    model = Injectable
    template_name = 'orcaserver/injectables.html'
    context_object_name = 'grouped_injectables'

    def get_queryset(self):
        """Return the injectables with their values."""
        scenario = self.get_scenario()
        inj = orca.list_injectables()
        injectables = Injectable.objects.filter(name__in=inj,
                                                scenario=scenario)\
            .order_by('groupname', 'name')
        # distinct() fails here
        groups = set(injectables.values_list('groupname', flat=True))
        grouped = OrderedDict()
        for group in groups:
            grouped[group] = injectables.filter(groupname=group).order_by('order')
        return grouped

    def post(self, request, *args, **kwargs):
        if request.POST.get('reset'):
            for inj in self.get_queryset():
                orig_value = orca._injectable_backup[inj.name]
                inj.value = orig_value
                inj.save()
        return HttpResponseRedirect(request.path_info)


class InjectableView(ProjectMixin, FormView):
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

        elif request.POST.get('reset'):
            orig_value = orca._injectable_backup[self.name]
            inj.value = orig_value
            inj.save()
            return HttpResponseRedirect(request.path_info)

        elif request.POST.get('clear'):
            inj.value = None
            inj.save()

        redirect = request.GET.get('next', reverse('injectables'))
        return HttpResponseRedirect(redirect)
