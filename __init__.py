"""PluginGenerator package init.

Avoid importing submodules here to prevent circular imports when the
package is executed with `-m` or when individual modules are imported.
Import submodules lazily from the runner instead.
"""

__all__ = []
