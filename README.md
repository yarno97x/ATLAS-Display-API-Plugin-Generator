ATLAS Display Plugin Generator

Usage:

Run the GUI generator with Python from the workspace root:

```powershell
python -m tools.PluginGenerator.generator
```

To generate directly without the GUI:

```powershell
python -m tools.PluginGenerator.generator MyPlugin
```

The plugin name is used as the C# namespace. In the GUI, enter one custom parameter identifier per line to generate `DisplayParameterService.AddParameterContainer(...)` calls in `OnInitialised()`, and choose the maximum parameter count. Use `--output C:\path\to\folder` to choose the parent folder, `--no-view` to omit the WPF view, `--no-parameters` to generate a basic display without dynamic parameter support, or `--max-parameters 2` to set the generated limit. Generated parameter displays use `DisplayPluginLibrary` to discover configured parameters, request throttled cursor samples, and show live parameter values and ranges in the WPF view.

The GUI will prompt for a plugin name, namespace, and output folder. It creates a minimal `.csproj`, `PluginModule.cs`, and a `ViewModel` plus an optional WPF view.

Notes:
- This is a lightweight starter generator. You can extend templates in `gui.py`.
- Ensure you have .NET SDK installed to build the generated project.
