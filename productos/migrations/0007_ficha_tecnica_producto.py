from decimal import Decimal

from django.db import migrations, models
import django.core.validators


def completar_datos_conocidos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')

    marcas = {
        'Taladro Bauker': ('Bauker', ''),
        'Stanley Sierra Circular': ('Stanley', ''),
        'Taladro Bosch Professional GSB 450 RE': ('Bosch Professional', 'GSB 450 RE'),
        'Combinación lavaplatos Arizona': ('Arizona', ''),
    }
    for nombre, (marca, modelo) in marcas.items():
        Producto.objects.filter(nombre=nombre).update(marca=marca, modelo=modelo)

    Producto.objects.filter(nombre__icontains='Pintura').update(
        unidad_venta='envase',
        tipo_calculo='pintura',
        unidad_contenido='l',
        porcentaje_desperdicio=Decimal('10.00'),
    )
    Producto.objects.filter(nombre='Pintura Látex Extracubriente').update(
        contenido=Decimal('3.785'),
    )
    Producto.objects.filter(nombre__icontains='Clavo corriente 4').update(
        unidad_venta='paquete',
        contenido=Decimal('1.000'),
        unidad_contenido='kg',
        tipo_calculo='peso',
    )
    Producto.objects.filter(nombre='Tabla 2 x 2').update(
        contenido=Decimal('3.200'),
        unidad_contenido='m',
        tipo_calculo='longitud',
    )


class Migration(migrations.Migration):
    dependencies = [('productos', '0006_alter_producto_imagen')]

    operations = [
        migrations.AlterModelOptions(
            name='producto',
            options={'ordering': ['nombre', 'id']},
        ),
        migrations.AlterField(
            model_name='producto',
            name='categoria',
            field=models.CharField(
                choices=[
                    ('General', 'General'),
                    ('Herramientas', 'Herramientas'), ('Construcción', 'Construcción'),
                    ('Electricidad', 'Electricidad'), ('Pinturas', 'Pinturas'),
                    ('Gasfitería', 'Gasfitería'), ('Adhesivos', 'Adhesivos'),
                    ('Iluminación', 'Iluminación'), ('Ferretería', 'Ferretería'),
                    ('Seguridad', 'Seguridad'), ('Otra', 'Otra'),
                ],
                default='Otra', max_length=100,
            ),
        ),
        migrations.AddField(model_name='producto', name='marca', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='producto', name='modelo', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(
            model_name='producto', name='unidad_venta',
            field=models.CharField(
                choices=[('unidad', 'Unidad'), ('envase', 'Envase'), ('paquete', 'Paquete'),
                         ('caja', 'Caja'), ('saco', 'Saco'), ('rollo', 'Rollo'), ('juego', 'Juego')],
                default='unidad', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='producto', name='contenido',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True,
                                      validators=[django.core.validators.MinValueValidator(Decimal('0.001'))]),
        ),
        migrations.AddField(
            model_name='producto', name='unidad_contenido',
            field=models.CharField(blank=True,
                choices=[('unidad', 'unidad(es)'), ('ml', 'mL'), ('l', 'L'), ('g', 'g'), ('kg', 'kg'),
                         ('m', 'm'), ('m2', 'm²'), ('m3', 'm³')], max_length=20),
        ),
        migrations.AddField(
            model_name='producto', name='tipo_calculo',
            field=models.CharField(
                choices=[('ninguno', 'Sin cálculo automático'), ('pintura', 'Pintura por superficie'),
                         ('superficie', 'Cobertura por superficie'), ('longitud', 'Material por longitud'),
                         ('peso', 'Material por peso'), ('unidad', 'Material por unidades')],
                default='ninguno', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='producto', name='rendimiento',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True,
                                      validators=[django.core.validators.MinValueValidator(Decimal('0.001'))]),
        ),
        migrations.AddField(
            model_name='producto', name='unidad_rendimiento',
            field=models.CharField(blank=True,
                choices=[('', 'No aplica'), ('m2_l', 'm² por litro'), ('m2_kg', 'm² por kilogramo'),
                         ('m2_unidad', 'm² por unidad'), ('m_unidad', 'metros por unidad'),
                         ('unidad_m2', 'unidades por m²')], max_length=30),
        ),
        migrations.AddField(
            model_name='producto', name='capas_recomendadas',
            field=models.PositiveSmallIntegerField(blank=True, null=True,
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)]),
        ),
        migrations.AddField(
            model_name='producto', name='porcentaje_desperdicio',
            field=models.DecimalField(decimal_places=2, default=Decimal('10.00'), max_digits=5,
                validators=[django.core.validators.MinValueValidator(Decimal('0')),
                            django.core.validators.MaxValueValidator(Decimal('50'))]),
        ),
        migrations.AddField(model_name='producto', name='uso_recomendado', field=models.TextField(blank=True)),
        migrations.AddField(model_name='producto', name='especificaciones', field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='producto', name='informacion_tecnica_verificada', field=models.BooleanField(default=False)),
        migrations.AddConstraint(
            model_name='producto',
            constraint=models.CheckConstraint(
                condition=models.Q(contenido__isnull=True) | models.Q(contenido__gt=0),
                name='producto_contenido_positivo',
            ),
        ),
        migrations.AddConstraint(
            model_name='producto',
            constraint=models.CheckConstraint(
                condition=models.Q(rendimiento__isnull=True) | models.Q(rendimiento__gt=0),
                name='producto_rendimiento_positivo',
            ),
        ),
        migrations.AddConstraint(
            model_name='producto',
            constraint=models.CheckConstraint(
                condition=models.Q(porcentaje_desperdicio__gte=0, porcentaje_desperdicio__lte=50),
                name='producto_desperdicio_valido',
            ),
        ),
        migrations.RunPython(completar_datos_conocidos, migrations.RunPython.noop),
    ]
