# Generated by Django 4.2.7 on 2025-04-12 10:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0006_question_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='description',
            field=models.TextField(blank=True, verbose_name='Description'),
        ),
    ]
