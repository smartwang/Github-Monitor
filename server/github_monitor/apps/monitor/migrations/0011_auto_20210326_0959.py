# Generated by Django 2.1.5 on 2021-03-26 01:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('monitor', '0010_task_match_method'),
    ]

    operations = [
        migrations.CreateModel(
            name='Processor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=20, unique=True, verbose_name='name')),
                ('backend', models.CharField(choices=[('github', 'github')], default='github', max_length=16, verbose_name='backend')),
                ('config', models.TextField(blank=True, default='', verbose_name='config')),
            ],
        ),
        migrations.AlterField(
            model_name='task',
            name='match_method',
            field=models.IntegerField(choices=[(0, '模糊匹配'), (1, '精确匹配'), (2, '单词匹配')], default=0),
        ),
        migrations.AddField(
            model_name='task',
            name='processor',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='monitor.Processor', verbose_name='processor'),
        ),
    ]
