from django import forms

from .models import Proveedor


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ('nombre', 'nombre_contacto', 'email', 'telefono')

    def clean_nombre(self):
        return self.cleaned_data['nombre'].strip()

    def clean_nombre_contacto(self):
        return self.cleaned_data['nombre_contacto'].strip()

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_telefono(self):
        return self.cleaned_data['telefono'].strip()
