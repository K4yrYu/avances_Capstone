from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def completar_fichas_pintura(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    pinturas = Producto.objects.filter(
        models.Q(categoria='Pinturas') | models.Q(tipo_calculo='pintura')
    )
    for producto in pinturas.iterator():
        texto = f'{producto.nombre} {producto.descripcion}'.casefold()
        if 'piscina' in texto:
            datos = ('caucho_clorado', 'lisa_mate', ['resistente_sanitizantes'], ['limpieza', 'lijado', 'impermeabilizacion'], 8, 24)
        elif 'fachada' in texto:
            datos = ('esmalte_agua', 'cascara_huevo', ['base_agua', 'hidrorrepelente', 'proteccion_uv', 'antihongos'], ['limpieza', 'reparacion', 'sellador'], 6, 8)
        elif 'semibrillo' in texto:
            datos = ('esmalte_agua', 'semibrillo', ['base_agua', 'lavable', 'bajo_olor', 'proteccion_uv'], ['limpieza', 'lijado', 'imprimante'], 6, 6)
        elif 'satinado' in texto:
            datos = ('esmalte_agua', 'satinado', ['base_agua', 'super_lavable', 'antihongos', 'secado_rapido'], ['limpieza', 'reparacion', 'sellador'], 3, 6)
        elif 'passol' in texto:
            datos = ('esmalte_agua', 'mate', ['base_agua', 'lavable', 'hidrorrepelente', 'antihongos'], ['limpieza', 'lijado', 'imprimante'], 4, 6)
        else:
            datos = ('latex', 'mate', ['base_agua', 'bajo_olor', 'alto_cubrimiento'], ['limpieza', 'reparacion', 'sellador'], 3, 6)
        (
            producto.tipo_pintura,
            producto.terminacion,
            producto.propiedades_pintura,
            producto.preparaciones_recomendadas,
            producto.repintado_min_horas,
            producto.repintado_max_horas,
        ) = datos
        producto.save(update_fields=[
            'tipo_pintura', 'terminacion', 'propiedades_pintura',
            'preparaciones_recomendadas', 'repintado_min_horas',
            'repintado_max_horas',
        ])


def revertir_fichas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.update(
        tipo_pintura='no_aplica',
        terminacion='no_aplica',
        propiedades_pintura=[],
        preparaciones_recomendadas=[],
        secado_tacto_horas=None,
        repintado_min_horas=None,
        repintado_max_horas=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('productos', '0012_producto_superficies_compatibles'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='tipo_pintura',
            field=models.CharField(choices=[('no_aplica', 'No aplica'), ('latex', 'L\u00e1tex al agua'), ('esmalte_agua', 'Esmalte al agua'), ('caucho_clorado', 'Caucho clorado')], default='no_aplica', max_length=20),
        ),
        migrations.AddField(
            model_name='producto',
            name='terminacion',
            field=models.CharField(choices=[('no_aplica', 'No aplica'), ('mate', 'Mate'), ('satinado', 'Satinado'), ('semibrillo', 'Semibrillo'), ('cascara_huevo', 'C\u00e1scara de huevo'), ('lisa_mate', 'Lisa y mate')], default='no_aplica', max_length=20),
        ),
        migrations.AddField(model_name='producto', name='propiedades_pintura', field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name='producto', name='preparaciones_recomendadas', field=models.JSONField(blank=True, default=list)),
        migrations.AddField(
            model_name='producto', name='secado_tacto_horas',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('168'))]),
        ),
        migrations.AddField(
            model_name='producto', name='repintado_min_horas',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('720'))]),
        ),
        migrations.AddField(
            model_name='producto', name='repintado_max_horas',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('720'))]),
        ),
        migrations.RunPython(completar_fichas_pintura, revertir_fichas),
    ]
