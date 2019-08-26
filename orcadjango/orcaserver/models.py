from django.db import models


class NameModel(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Scenario(NameModel):
    """Scenario"""
    name = models.TextField()
    module = models.TextField(default='')


class Injectable(NameModel):
    name = models.TextField()
    scenario = models.ForeignKey(Scenario,
                                 on_delete=models.CASCADE,
                                 null=True)
    value = models.TextField(null=True)
    changed = models.BooleanField(default=False)
    can_be_changed = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.scenario} - {self.name}'


class Step(NameModel):
    name = models.TextField()
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    started = models.DateTimeField(null=True)
    finished = models.DateTimeField(null=True)
    success = models.BooleanField(default=False)
    order = models.IntegerField(null=True)
    active = models.BooleanField(default=True)
