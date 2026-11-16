from django.db import migrations


GUIA_POR_CATEGORIA = {
    'Adhesivos': ('Adhesivo, sellado o terminación', 'baño, cocina, revestimientos, reparaciones'),
    'Carpintería': ('Material o accesorio de carpintería', 'muebles, puertas, tabiques, estructuras de madera'),
    'Construcción': ('Material de obra y preparación', 'radier, tabiques, techumbre, muros, terraza, quincho'),
    'Electricidad': ('Componente de instalación eléctrica', 'iluminación, enchufes, canalización, portón automático'),
    'Ferretería': ('Fijación, unión o accesorio de montaje', 'reparaciones, carpintería, estructuras, puertas'),
    'Gasfitería': ('Componente de agua, desagüe o gas', 'baño, cocina, lavaplatos, riego, bomba de agua'),
    'Herramientas': ('Herramienta para ejecución o preparación', 'reparaciones, construcción, jardín, instalación'),
    'Iluminación': ('Elemento de iluminación o control', 'iluminación interior, exterior, jardín, seguridad'),
    'Jardinería': ('Material o herramienta de jardín', 'riego, plantas, terreno, patio, huerto'),
    'Pinturas': ('Protección o terminación de superficie', 'pintura interior, exterior, madera, metal, reparación'),
    'Seguridad': ('Protección personal o prevención', 'obra, electricidad, soldadura, jardín, reparaciones'),
}


def _texto(producto):
    return ' '.join(
        str(valor or '').casefold()
        for valor in (producto.nombre, producto.descripcion, producto.uso_recomendado)
    )


def _rol_y_terminos(producto):
    texto = _texto(producto)
    reglas = (
        (('tornillo', 'perno', 'clavo', 'tarugo', 'anclaje', 'escuadra', 'abrazadera'), 'Fijación o unión', 'fijar, unir, montar, instalar'),
        (('codo', 'tee ', 'válvula', 'valvula', 'sifón', 'sifon', 'flexible', 'adaptador', 'tubo', 'ppr', 'pvc'), 'Conexión o conducción', 'conectar, unión, instalación, reparación'),
        (('pala', 'picota', 'azadón', 'azadon', 'rastrillo', 'carretilla'), 'Herramienta de preparación de terreno', 'tierra, patio, jardín, excavar, mover, nivelar'),
        (('taladro', 'sierra', 'esmeril', 'cortadora', 'martillo', 'combo', 'cincel', 'cortatubo'), 'Herramienta de trabajo', 'cortar, perforar, instalar, reparar'),
        (('guante', 'lente', 'máscara', 'mascara', 'respirador', 'extintor', 'detector'), 'Protección y seguridad', 'protección personal, seguridad, prevención'),
        (('cable', 'conduit', 'interruptor', 'enchufe', 'tablero', 'caja eléctrica', 'caja electrica'), 'Instalación eléctrica', 'electricidad, cableado, enchufe, iluminación, canalización'),
        (('ampolleta', 'foco', 'plafón', 'plafon', 'sensor', 'portalámpara', 'portalampara'), 'Iluminación o control', 'luz, iluminación, lámpara, exterior, interior'),
        (('pintura', 'barniz', 'anticorrosivo', 'protector', 'rodillo', 'brocha'), 'Preparación o terminación de superficie', 'pintar, proteger, muro, madera, metal'),
    )
    for palabras, rol, terminos in reglas:
        if any(palabra in texto for palabra in palabras):
            return rol, terminos
    return None, None


def enriquecer_guia_catalogo(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for producto in Producto.objects.filter(activo=True).order_by('pk'):
        especificaciones = producto.especificaciones if isinstance(producto.especificaciones, dict) else {}
        rol_categoria, proyectos = GUIA_POR_CATEGORIA.get(
            producto.categoria,
            ('Material o accesorio para proyecto', 'reparaciones y mantenimiento'),
        )
        rol_especifico, terminos = _rol_y_terminos(producto)
        especificaciones.setdefault('Rol en proyecto', rol_especifico or rol_categoria)
        especificaciones.setdefault('Proyectos sugeridos', proyectos)
        if terminos:
            especificaciones.setdefault('Términos relacionados', terminos)
        producto.especificaciones = especificaciones
        producto.save(update_fields=['especificaciones'])


def reversa_no_destructiva(apps, schema_editor):
    # La guía agregada es información útil del catálogo y no se elimina.
    pass


class Migration(migrations.Migration):
    dependencies = [('productos', '0045_restaurar_calculos_tecnicos_validados')]

    operations = [migrations.RunPython(enriquecer_guia_catalogo, reversa_no_destructiva)]
