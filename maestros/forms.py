from django import forms
from django.utils import timezone

from .chile import COMUNA_REGION, COMUNAS_CHOICES, comunas_de_region
from .models import Especialidad, PerfilMaestro, TrabajoRealizado


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        clean_one = super().clean
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        cleaned = [clean_one(item, initial) for item in files]
        for image in cleaned:
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Cada imagen debe pesar como máximo 5 MB.")
        return cleaned


class ComunaMultipleSelect(forms.SelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        option["attrs"]["data-region"] = COMUNA_REGION.get(str(value), "")
        return option


class PerfilMaestroForm(forms.ModelForm):
    comunas_trabajo = forms.MultipleChoiceField(
        choices=COMUNAS_CHOICES,
        widget=ComunaMultipleSelect(attrs={"size": 8}),
        label="Comunas donde trabajas",
        help_text="Marca todas las comunas de la región en las que puedes trabajar.",
    )

    class Meta:
        model = PerfilMaestro
        fields = (
            "foto",
            "descripcion_profesional",
            "anos_experiencia",
            "especialidades",
            "region",
            "comunas_trabajo",
            "disponible",
        )
        widgets = {
            "descripcion_profesional": forms.Textarea(attrs={"rows": 5}),
            "especialidades": forms.CheckboxSelectMultiple,
        }
        labels = {
            "descripcion_profesional": "Descripción profesional",
            "anos_experiencia": "Años de experiencia",
            "region": "Región donde trabajas",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["especialidades"].queryset = Especialidad.objects.filter(activa=True)
        self.fields["especialidades"].required = True
        self.fields["foto"].help_text = "JPG, PNG o WebP. Máximo 5 MB."
        self.fields["foto"].widget.attrs["accept"] = "image/jpeg,image/png,image/webp"
        if self.instance and self.instance.pk:
            actuales = [zona.strip() for zona in self.instance.zonas_trabajo.split(",") if zona.strip()]
            self.initial["comunas_trabajo"] = actuales or [self.instance.comuna]
            if self.instance.foto:
                self.fields["foto"].widget.attrs["data-current-url"] = self.instance.foto.url
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.setdefault("class", "form-control" if name not in {"disponible"} else "form-check-input")

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        if foto and hasattr(foto, "size") and foto.size > 5 * 1024 * 1024:
            raise forms.ValidationError("La foto debe pesar como máximo 5 MB.")
        return foto

    def clean(self):
        cleaned_data = super().clean()
        region = cleaned_data.get("region")
        comunas = cleaned_data.get("comunas_trabajo") or []
        permitidas = set(comunas_de_region(region))
        if region and (not comunas or any(comuna not in permitidas for comuna in comunas)):
            self.add_error("comunas_trabajo", "Selecciona una o más comunas pertenecientes a la región indicada.")
        return cleaned_data

    def save(self, commit=True):
        perfil = super().save(commit=False)
        comunas = self.cleaned_data.get("comunas_trabajo", [])
        perfil.comuna = comunas[0] if comunas else ""
        perfil.zonas_trabajo = ", ".join(comunas)
        if commit:
            perfil.save()
            self.save_m2m()
        return perfil


class EspecialidadForm(forms.ModelForm):
    class Meta:
        model = Especialidad
        fields = ("nombre", "descripcion")
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class TrabajoRealizadoForm(forms.ModelForm):
    imagenes = MultipleImageField(required=False, label="Nuevas imágenes")

    class Meta:
        model = TrabajoRealizado
        fields = ("titulo", "descripcion", "especialidades", "comuna", "fecha", "publicado")
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 5}),
            "especialidades": forms.CheckboxSelectMultiple,
            "fecha": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        self.maestro = kwargs.pop("maestro", None)
        super().__init__(*args, **kwargs)
        especialidades = Especialidad.objects.filter(activa=True)
        if self.maestro:
            especialidades = especialidades.filter(maestros=self.maestro)
        self.fields["especialidades"].queryset = especialidades.distinct()
        self.fields["especialidades"].required = True
        hoy = timezone.localdate()
        anos = max(1, self.maestro.anos_experiencia if self.maestro else 60)
        fecha_minima = hoy.replace(year=hoy.year - min(anos, 60), month=1, day=1)
        self.fields["fecha"].widget.attrs.update(
            {"max": hoy.isoformat(), "min": fecha_minima.isoformat()}
        )
        self.fields["fecha"].help_text = (
            f"Debe estar entre {fecha_minima.strftime('%d/%m/%Y')} y hoy."
        )
        self.fields["imagenes"].widget.attrs.update({"accept": "image/jpeg,image/png,image/webp"})
        self.fields["imagenes"].help_text = "Puedes seleccionar varias imágenes. Máximo 5 MB por archivo."
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.setdefault("class", "master-checkbox-group")
            elif name != "publicado":
                field.widget.attrs.setdefault("class", "form-control")
            else:
                field.widget.attrs.setdefault("class", "form-check-input")

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")
        if not fecha:
            return fecha
        hoy = timezone.localdate()
        anos = max(1, self.maestro.anos_experiencia if self.maestro else 60)
        fecha_minima = hoy.replace(year=hoy.year - min(anos, 60), month=1, day=1)
        if fecha > hoy:
            raise forms.ValidationError("La fecha del trabajo no puede estar en el futuro.")
        if fecha < fecha_minima:
            raise forms.ValidationError(
                "La fecha no coincide con los años de experiencia indicados en tu perfil."
            )
        return fecha
