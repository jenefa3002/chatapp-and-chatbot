# Generated by Django 5.1.5 on 2025-02-07 06:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0007_alter_privatemessage_content'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='privatemessage',
            name='deleted',
        ),
    ]
