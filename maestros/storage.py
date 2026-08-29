from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class DocumentosPrivadosStorage(FileSystemStorage):
    """Almacena antecedentes fuera de MEDIA_ROOT y sin una URL pública directa."""

    @property
    def base_location(self):
        return str(
            Path(
                getattr(
                    settings,
                    "PRIVATE_DOCUMENTS_ROOT",
                    settings.BASE_DIR / "private_uploads",
                )
            )
        )

    @property
    def location(self):
        return str(Path(self.base_location).resolve())

    def url(self, name):
        raise ValueError("Los documentos privados no tienen una URL pública.")


documentos_privados_storage = DocumentosPrivadosStorage()
