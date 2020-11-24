import json
from inspect import signature
from django.views.generic import TemplateView, ListView
from django.shortcuts import HttpResponseRedirect
from django.http import HttpResponse
from django.http import JsonResponse, HttpResponseNotFound
from collections import OrderedDict
from django.db.models import Max
from django.conf import settings
import json
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.utils import timezone

from orcaserver.management import OrcaManager
from orcaserver.views import ProjectMixin, apply_injectables
from orcaserver.models import Step, Injectable, Scenario, LogEntry, Run

manager = OrcaManager()


class StepsView(ProjectMixin, TemplateView):
    template_name = 'orcaserver/steps.html'

    @property
    def id(self):
        return self.kwargs.get('id')

    def get(self, request, *args, **kwargs):
        scenario = self.get_scenario()
        if not scenario:
            return HttpResponseRedirect(reverse('scenarios'))
        #apply_injectables(scenario)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        scenario = self.get_scenario()
        orca = self.get_orca()
        steps_grouped = {}
        steps_available = orca.list_steps()
        meta = getattr(orca, 'meta', {})
        for name in steps_available:
            _meta = meta.get(name, {})
            wrapper = orca.get_step(name)
            group = _meta.get('group', '-')
            order = _meta.get('order', 1)
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
        for step in steps_scenario:
            if step.name not in steps_available:
                step.valid = False
                step.docstring = (
                    'Step not found. Your project seems not to be up to date '
                    'with the module. Please remove this step.')
                continue
            if not step.docstring:
                step.docstring = orca.get_step(step.name)._func.__doc__
            step.valid = True
        kwargs = super().get_context_data(**kwargs)
        kwargs['steps_available'] = steps_grouped if scenario else []
        kwargs['steps_count'] = len(steps_available)
        kwargs['steps_scenario'] = steps_scenario
        logs = LogEntry.objects.filter(scenario=scenario).order_by('-timestamp')
        kwargs['logs'] = logs
        kwargs['show_status'] = True
        # ToDo: get room from handler

        prefix = 'ws' if settings.DEBUG else 'wss'
        kwargs['log_socket'] = \
            f'{prefix}://{self.request.get_host()}/ws/log/{scenario.id}/'
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
        steps_available = orca.list_steps()
        for step in steps_scenario:
            if step.name not in steps_available:
                continue
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
                        'value': repr(inj.calculated_value),
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
            existing = Step.objects.filter(scenario=scenario)
            i = 0 if len(existing) == 0 else \
                existing.aggregate(Max('order'))['order__max'] + 1
            for step in steps:
                if not step:
                    continue
                Step.objects.create(scenario=scenario,
                                    name=step, order=i)
                i += 1
        elif request.POST.get('remove'):
            step_id = request.POST.get('step')
            step = Step.objects.get(id=step_id)
            step.delete()
        elif request.POST.get('run'):
            pass
        return HttpResponseRedirect(request.path_info)

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
    def run(cls, request):
        scenario_id = request.session.get('scenario')
        if not scenario_id:
            return
        orca = manager.get(scenario_id)
        scenario = Scenario.objects.get(id=scenario_id)

        active_steps = Step.objects.filter(
            scenario=scenario, active=True).order_by('order')
        if len(active_steps) == 0:
            orca.logger.error('No steps selected.')
            return HttpResponse(status=400)
        # check if all injectables are available
        injectables_available = orca.list_injectables()
        steps_available = orca.list_steps()
        for step in active_steps:
            if step.name not in steps_available:
                orca.logger.error(
                    'There are steps selected that can not be found in the '
                    'module. Your project seems not to be up to date '
                    'with the module. Please remove those steps.')
                return HttpResponse(status=400)
            func = orca.get_step(step.name)
            sig = signature(func._func)
            inj_parameters = sig.parameters
            required = list(set(inj_parameters) & set(injectables_available))
            inj_db = Injectable.objects.filter(name__in=required,
                                               scenario=scenario)
            if len(required) > len(inj_db):
                orca.logger.error(
                    'There are steps selected that contain injectables that '
                    'not be found. Your project seems not to be up to date '
                    'with the module.<br>Please refresh the injectables '
                    '(scenario page).')
                return HttpResponse(status=400)
        for step in active_steps:
            step.started = None
            step.finished = None
            step.success = False
            step.save()
        apply_injectables(orca, scenario)
        if manager.is_running(scenario.id):
            orca.logger.error('Orca is already running. Please wait for it to '
                         'finish or abort it.')
            return HttpResponse(status=400)

        message = f'Running Steps for scenario "{scenario.name}"'
        orca.logger.info(message)

        run, created = Run.objects.get_or_create(scenario=scenario)
        run.run_by = request.user
        run.success = False
        run.started = timezone.now()
        run.finished =  None
        run.save()

        def on_success():
            run.success = True
            run.finished = timezone.now()
            run.save()
        def on_error():
            run.success = False
            run.finished = timezone.now()
            run.save()

        try:
            manager.start(scenario.id, steps=active_steps,
                          on_success=on_success, on_error=on_error)
        # ToDo: specific exceptions
        except Exception as e:
            orca.logger.error(str(e))
            return HttpResponse(status=400)
        return HttpResponse(status=200)

    @classmethod
    def abort(cls, request):
        scenario_id = request.session.get('scenario')
        manager = OrcaManager()
        manager.abort(scenario_id)
        return HttpResponse(status=200)


class LogsView(ProjectMixin, ListView):
    template_name = 'orcaserver/logs.html'
    model = LogEntry
    context_object_name = 'logs'

    def get_queryset(self):
        """Return the injectables with their values."""
        scenario_id = self.kwargs.get('id')
        logs = LogEntry.objects.filter(scenario_id=scenario_id)
        return logs