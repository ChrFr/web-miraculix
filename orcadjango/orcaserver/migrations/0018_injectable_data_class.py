# Generated by Django 3.0 on 2020-02-07 00:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orcaserver', '0017_injectable_valid'),
    ]

    operations = [
        migrations.AddField(
            model_name='injectable',
            name='data_class',
            field=models.TextField(blank=True, null=True),
        ),
    ]
