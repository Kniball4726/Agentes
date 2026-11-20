"""Descriptor reutilizable de delegación por composición para fachadas y almacenes."""

from __future__ import annotations

from typing import Any


class DelegadoAtributo:
    """Descriptor no-datos que delega el acceso a un método o atributo de un componente interno.

    Al ser un descriptor no-datos (solo define ``__get__``), permite que las pruebas unitarias
    sobrescriban métodos en la instancia (``obj.metodo = MagicMock()``) o en la clase
    (``patch.object(Clase, 'metodo', ...)``) sin fricción.
    """

    def __init__(
        self,
        attr_name: str,
        target_cls: type | None = None,
        target_name: str | None = None,
    ) -> None:
        self.attr_name = attr_name
        self.target_cls = target_cls
        self.target_name = target_name

    def __set_name__(self, owner: type, name: str) -> None:
        if self.target_name is None:
            self.target_name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            if self.target_cls is not None and self.target_name is not None:
                return getattr(self.target_cls, self.target_name)
            return self
        component = getattr(instance, self.attr_name)
        return getattr(component, self.target_name)  # type: ignore[arg-type]
