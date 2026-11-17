"""Formularios para los perfiles y las trayectorias."""

from django import forms

from .models import Egresado, Trayectoria


class EgresadoCreateForm(forms.ModelForm):
    """Formulario individual para el registro de un nuevo egresado."""

    class Meta:
        model = Egresado
        fields = [
            "document_type",
            "document_number",
            "first_name",
            "last_name",
            "email",
            "phone",
            "address",
            "municipality",
            "program",
            "center",
            "certified_on",
            "academic_status",
        ]
        widgets = {"certified_on": forms.DateInput(attrs={"type": "date"})}

    def clean_academic_status(self):
        """Impide registrar estados académicos distintos a Certificado."""
        value = self.cleaned_data["academic_status"]
        if value != Egresado.EstadoAcademico.CERTIFICADO:
            raise forms.ValidationError("El estado académico debe ser Certificado.")
        return value


class EgresadoContactForm(forms.ModelForm):
    """Permite al egresado actualizar solo contacto y situación laboral."""

    class Meta:
        model = Egresado
        fields = [
            "email",
            "phone",
            "address",
            "municipality",
            "employment_status",
            "contract_type",
            "company",
        ]


class EgresadoAdminForm(EgresadoCreateForm):
    """Permite al administrador corregir datos maestros y de contacto."""

    class Meta(EgresadoCreateForm.Meta):
        fields = EgresadoCreateForm.Meta.fields + [
            "employment_status",
            "contract_type",
            "company",
            "vulnerability",
            "status",
        ]


class TrayectoriaForm(forms.ModelForm):
    """Captura una experiencia laboral, académica o de emprendimiento."""

    class Meta:
        model = Trayectoria
        fields = [
            "kind",
            "title",
            "organization",
            "description",
            "started_on",
            "ended_on",
        ]
        widgets = {
            "started_on": forms.DateInput(attrs={"type": "date"}),
            "ended_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        """Comprueba que el período de la experiencia tenga sentido."""
        cleaned_data = super().clean()
        start = cleaned_data.get("started_on")
        end = cleaned_data.get("ended_on")
        if start and end and end < start:
            self.add_error("ended_on", "La fecha final no puede ser anterior a la inicial.")
        return cleaned_data
