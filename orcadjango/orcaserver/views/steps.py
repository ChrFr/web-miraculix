import logging
import json
from inspect import signature
from django.views.generic import TemplateView
from django.shortcuts import HttpResponseRedirect
from django.http import HttpResponse
from django.http import JsonResponse, HttpResponseNotFound
from collections import OrderedDict

from orcaserver.management import OrcaManager
from orcaserver.views import ProjectMixin, apply_injectables
from orcaserver.models import Step, Injectable, Scenario
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
import json

logger = logging.getLogger('OrcaLog')
manager = OrcaManager()


class StepsView(ProjectMixin, TemplateView):
    template_name = 'orcaserver/steps.html'

    @property
    def id(self):
        return self.kwargs.get('id')

    def get(self, request, *args, **kwargs):
        if not self.get_scenario():
            return  HttpResponseRedirect(reverse('scenarios'))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        scenario = self.get_scenario()
        orca = self.get_orca()
        steps_grouped = {}
        for name in orca.list_steps():
            wrapper = orca.get_step(name)
            group = getattr(wrapper, 'groupname', '-')
            order = getattr(wrapper, 'order', 1)
            steps_grouped.setdefault(group, []).append({
                'name': name,
                'description': wrapper._func.__doc__ or '',
                'order': order,
                'module': wrapper._func.__module__,
            })
        # order the steps inside the groups
        for group, steps_group in steps_grouped.items():
            steps_grouped[group] = sorted(steps_group, key=lambda x: x['order'])

        steps_grouped = OrderedDict(sorted(steps_grouped.items()))
        steps_scenario = Step.objects.filter(
            scenario=scenario).order_by('order')
        kwargs = super().get_context_data(**kwargs)
        kwargs['steps_available'] = steps_grouped if scenario else []
        kwargs['steps_scenario'] = steps_scenario
        return kwargs

    @staticmethod
    def list(request):
        if request.method == 'POST':
            body = json.loads(request.body)
            for item in body:
                step = Step.objects.get(id=item['id'])
                step.order = item['order']
                step.save()
        scenario_id = request.session.get('scenario')
        orca = manager.get(scenario_id)
        if scenario_id is None:
            return HttpResponseNotFound('scenario not found')
        scenario = Scenario.objects.get(id=scenario_id)
        steps_scenario = Step.objects.filter(
            scenario=scenario).order_by('order')
        steps_json = []
        injectables_available = orca.list_injectables()
        for step in steps_scenario:
            func = orca.get_step(step.name)
            sig = signature(func._func)
            inj_parameters = sig.parameters
            injectables = []
            for name in inj_parameters:
                if name not in injectables_available:
                    continue
                try:
                    inj = Injectable.objects.get(name=name, scenario=scenario)
                    injectables.append({
                        'id': inj.id,
                        'name': name,
                        'value': repr(inj.value),
                        'url': f"{reverse('injectables')}{name}",
                        'valid': True
                    })
                except ObjectDoesNotExist:
                    injectables.append({
                        'id': -1,
                        'name': name,
                        'value': 'Injectable not found',
                        'url': f"{reverse('injectables')}{name}",
                        'valid': False
                    })
            started = step.started
            finished = step.finished
            if started:
                started = started.strftime("%a %b %d %H:%M:%S %Z %Y")
            if finished:
                finished = finished.strftime("%a %b %d %H:%M:%S %Z %Y")
            steps_json.append({
                'id': step.id,
                'name': step.name,
                'started': started,
                'finished': finished,
                'success': step.success,
                'order': step.order,
                'is_active': step.active,
                'injectables': injectables,
                'module': func._func.__module__,
            })
        return JsonResponse(steps_json, safe=False)

    def post(self, request, *args, **kwargs):
        scenario = self.get_scenario()
        if request.POST.get('add'):
            steps = request.POST.get('steps', '').split(',')
            for step in steps:
                if not step:
                    continue
                Step.objects.create(scenario=scenario,
                                    name=step, order=10000)
        elif request.POST.get('remove'):
            step_id = request.POST.get('step')
            step = Step.objects.get(id=step_id)
            step.delete()
        elif request.POST.get('run'):
            pass
        return HttpResponseRedirect(request.path_info)

    # to do for updating is_active
    @staticmethod
    def detail(request, *args, **kwargs):
        step_id = kwargs.get('id')
        if request.method == 'PATCH':
            try:
                step = Step.objects.get(id=step_id)
            except ObjectDoesNotExist:
                return JsonResponse({}, safe=False)
            body = json.loads(request.body)
            is_active = body.get('is_active')
            step.active = is_active
            step.save()
            return JsonResponse({}, safe=False)

    @classmethod
    def status(cls, request):
        #manager = OrcaManager()
        #status_text = f'currently run by user "{manager.user}"'\
            #if manager.is_running else 'not in use'
        status = {
            'running': '',# manager.is_running,
            'text': '', # status_text,
            'last_user': '', # manager.user,
            'last_start': '' # manager.start_time,
        }
        return JsonResponse(status)

    @classmethod
    def run(cls, request):
        scenario_id = request.session.get('scenario')
        if not scenario_id:
            return
        orca = manager.get(scenario_id)
        scenario = Scenario.objects.get(id=scenario_id)
        message = f'Running Steps for scenario "{scenario.name}"'

        logger.info(message)

        active_steps = Step.objects.filter(scenario=scenario, active=True)
        if len(active_steps) == 0:
            logger.error('No steps selected.')
            return HttpResponse(status=400)
        steps = active_steps.order_by('order')
        # check if all injectables are available
        injectables_available = orca.list_injectables()
        for step in steps:
            func = orca.get_step(step.name)
            sig = signature(func._func)
            inj_parameters = sig.parameters
            required = list(set(inj_parameters) & set(injectables_available))
            inj_db = Injectable.objects.filter(name__in=required,
                                               scenario=scenario)
            if len(required) > len(inj_db):
                logger.error(
                    'Steps contain injectables that can not be found. '
                    'Your project seems not to be up to date '
                    'with the module.<br>Please refresh the injectables!')
                return HttpResponse(status=400)
        for step in steps:
            step.started = None
            step.finished = None
            step.success = False
            step.save()
        apply_injectables(scenario)
        if manager.is_running(scenario.id):
            logger.error('Orca is already running. Please wait for it to '
                         'finish or abort it.')
            return HttpResponse(status=400)
        manager.start(scenario.id, steps=steps, user=request.user)
        return HttpResponse(status=200)

    @classmethod
    def abort(cls, request):
        scenario_id = request.session.get('scenario')
        manager = OrcaManager()
        manager.abort(scenario_id)
        return HttpResponse(status=200)


class StatusView(ProjectMixin, TemplateView):
    template_name = 'orcaserver/status.html'
