import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import shutil


CS_PROJ_TEMPLATE = r'''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0-windows</TargetFramework>
    <OutputType>Library</OutputType>
    <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
    <UseWindowsForms>true</UseWindowsForms>
    <UseWPF>true</UseWPF>
    <Platforms>x64</Platforms>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Atlas.DisplayAPI" Version="*" />
    <PackageReference Include="System.ComponentModel.Composition" Version="7.0.0" />
  </ItemGroup>
  <ItemGroup>
    <PackageReference Include="Autofac" Version="4.9.1" />
    <PackageReference Include="MAT.OCS.Core" Version="*" />
    <PackageReference Include="System.Reactive" Version="4.4.1" />
  </ItemGroup>
</Project>
'''

PLUGIN_MODULE_TEMPLATE = '''using System.ComponentModel.Composition;

using Autofac;
using Autofac.Core;

using MAT.Atlas.Client.Presentation.Plugins;

namespace {namespace}
{{
    [Export(typeof(IModule))]
    public sealed class PluginModule : Module
    {{
        protected override void Load(ContainerBuilder builder)
        {{
            Plugin.Register(builder);
        }}

        [DisplayPlugin(
            View = typeof({view_class}),
            ViewModel = typeof({viewmodel_class}),
            IconUri = "Resources/icon.png")]
        private sealed class Plugin : DisplayPlugin<Plugin>
        {{
        }}
    }}
}}
'''

VIEWMODEL_TEMPLATE = '''using DisplayPluginLibrary;

using MAT.Atlas.Api.Core.Diagnostics;
using MAT.Atlas.Api.Core.Signals;
using MAT.Atlas.Client.Platform.Data;
using MAT.Atlas.Client.Presentation.Plugins;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;

namespace {namespace}
{{
    [DisplayPluginSettings(ParametersMaxCount = {parameter_max_count})]
    public sealed class {viewmodel_class} : ParameterSampleDisplayViewModelBase<ParameterViewModel>
    {{
        public {viewmodel_class}(
            ISignalBus signalBus,
            IDataRequestSignalFactory dataRequestSignalFactory,
            ILogger logger) :
            base(signalBus, dataRequestSignalFactory, logger)
        {{
        }}

    {custom_parameter_setup}
        protected override ParameterViewModel OnCreateParameterViewModel() => new ParameterViewModel();
    }}
}}
'''

BASIC_VIEWMODEL_TEMPLATE = '''using MAT.Atlas.Client.Presentation.Displays;
using MAT.Atlas.Client.Presentation.Plugins;

namespace {namespace}
{{
    [DisplayPluginSettings(ParametersMaxCount = {parameter_max_count})]
    public sealed class {viewmodel_class} : DisplayPluginViewModel
    {{
    }}
}}
'''

PARAMETER_VIEWMODEL_TEMPLATE = '''using DisplayPluginLibrary;

namespace {namespace}
{{
    public sealed class ParameterViewModel : ParameterSampleViewModelBase
    {{
        private string description;
        private double displayMaximum;
        private double displayMinimum;

        public string Description
        {{
            get => this.description;
            set => this.SetProperty(ref this.description, value);
        }}

        public double DisplayMaximum
        {{
            get => this.displayMaximum;
            set => this.SetProperty(ref this.displayMaximum, value);
        }}

        public double DisplayMinimum
        {{
            get => this.displayMinimum;
            set => this.SetProperty(ref this.displayMinimum, value);
        }}

        protected override void OnUpdate()
        {{
            this.DisplayMinimum = this.DisplayParameter.SessionParameter.Minimum;
            this.DisplayMaximum = this.DisplayParameter.SessionParameter.Maximum;
        }}

        protected override bool OnValueChanged(double? oldValue, double newValue)
        {{
            this.OnUpdate();
            if (newValue < this.DisplayMinimum || newValue > this.DisplayMaximum)
            {{
                return false;
            }}

            this.Description = $"{{this.Name}}\\r{{this.Value}}";
            return true;
        }}
    }}
}}
'''

VIEW_XAML_TEMPLATE = '''<UserControl xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
             xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
             x:Class="{namespace}.{view_class}">
    <ScrollViewer HorizontalScrollBarVisibility="Auto" VerticalScrollBarVisibility="Auto">
        <ItemsControl ItemsSource="{{Binding Parameters}}">
            <ItemsControl.ItemsPanel>
                <ItemsPanelTemplate>
                    <UniformGrid Columns="2" />
                </ItemsPanelTemplate>
            </ItemsControl.ItemsPanel>
            <ItemsControl.ItemTemplate>
                <DataTemplate>
                    <Border BorderBrush="DarkGray" BorderThickness="1" Padding="12" Margin="4">
                        <StackPanel>
                            <TextBlock Text="{{Binding Name}}" FontWeight="Bold" />
                            <TextBlock Text="{{Binding Value, StringFormat=F3}}" FontSize="24" />
                            <TextBlock Text="{{Binding Description}}" />
                        </StackPanel>
                    </Border>
                </DataTemplate>
            </ItemsControl.ItemTemplate>
        </ItemsControl>
    </ScrollViewer>
</UserControl>
'''

BASIC_VIEW_XAML_TEMPLATE = '''<UserControl xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
             xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
             x:Class="{namespace}.{view_class}">
    <Grid>
        <TextBlock Text="{view_class}"
                   VerticalAlignment="Center"
                   HorizontalAlignment="Center" />
    </Grid>
</UserControl>
'''

VIEW_CODEBEHIND_TEMPLATE = '''using System.Windows.Controls;

namespace {namespace}
{{
    public partial class {view_class} : UserControl
    {{
        public {view_class}()
        {{
            InitializeComponent();
        }}
    }}
}}
'''


def default_output_folder():
    user_home = os.path.expanduser('~')
    desktop_candidates = [
        os.path.join(user_home, 'OneDrive', 'Desktop'),
        os.path.join(user_home, 'Desktop'),
    ]
    for desktop in desktop_candidates:
        if os.path.isdir(desktop):
            return os.path.join(desktop, 'ATLAS Plugins')
    return os.path.join(desktop_candidates[0], 'ATLAS Plugins')


def validate_plugin_name(name):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
        raise ValueError('Plugin name must be a valid C# identifier (letters, numbers, and underscores only).')


def parse_parameter_names(value):
    names = [line.strip() for line in value.splitlines() if line.strip()]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f'Duplicate custom parameters: {", ".join(duplicates)}')
    return names


def escape_csharp_string(value):
    return value.replace('\\', '\\\\').replace('"', '\\"')


def generate_plugin(name, base_out, include_view=True, include_parameters=True, parameter_names=None, parameter_max_count=100, workspace_root=None):
    validate_plugin_name(name)
    if not isinstance(parameter_max_count, int) or parameter_max_count < 1:
        raise ValueError('Maximum parameter count must be a positive integer.')
    parameter_names = list(parameter_names or [])
    if len(parameter_names) > parameter_max_count:
        raise ValueError('Maximum parameter count cannot be lower than the number of custom parameters.')
    namespace = name
    target = os.path.join(base_out, name)
    os.makedirs(target, exist_ok=True)
    resources_dir = os.path.join(target, 'Resources')
    os.makedirs(resources_dir, exist_ok=True)
    shutil.copyfile(os.path.join(workspace_root, 'icon.png'), os.path.join(resources_dir, 'icon.png'))

    csproj = CS_PROJ_TEMPLATE
    if include_parameters:
        library_project = os.path.join(workspace_root or '', 'DisplayPluginLibrary', 'DisplayPluginLibrary.csproj')
        if not os.path.isfile(library_project):
            raise FileNotFoundError(f'DisplayPluginLibrary project not found: {library_project}')
        library_reference = os.path.relpath(library_project, target).replace(os.sep, '/')
        csproj = csproj.replace(
            '  <ItemGroup>\n    <PackageReference Include="Atlas.DisplayAPI"',
            f'  <ItemGroup>\n    <ProjectReference Include="{library_reference}" />\n  </ItemGroup>\n  <ItemGroup>\n    <PackageReference Include="Atlas.DisplayAPI"',
        )

    viewmodel_template = VIEWMODEL_TEMPLATE if include_parameters else BASIC_VIEWMODEL_TEMPLATE
    view_template = VIEW_XAML_TEMPLATE if include_parameters else BASIC_VIEW_XAML_TEMPLATE
    parameter_setup = ''
    if include_parameters and parameter_names:
        registrations = '\n'.join(
                f'            this.DisplayParameterService.AddParameterContainer("{escape_csharp_string(parameter_name)}");'
            for parameter_name in parameter_names
        )
        parameter_setup = (
            '        protected override void OnInitialised()\n'
            '        {\n'
            '            base.OnInitialised();\n'
            f'{registrations}\n'
            '        }\n'
        )

    files = {
        f'{name}.csproj': csproj,
        'PluginModule.cs': PLUGIN_MODULE_TEMPLATE.format(
            namespace=namespace,
            view_class=f'{name}View',
            viewmodel_class=f'{name}ViewModel',
        ),
        f'{name}ViewModel.cs': viewmodel_template.format(
            namespace=namespace,
            viewmodel_class=f'{name}ViewModel',
            view_class=f'{name}View',
            custom_parameter_setup=parameter_setup,
            parameter_max_count=parameter_max_count,
        ),
    }
    if include_parameters:
        files['ParameterViewModel.cs'] = PARAMETER_VIEWMODEL_TEMPLATE.format(namespace=namespace)
    if include_view:
        os.makedirs(os.path.join(target, 'Resources'), exist_ok=True)
        files[f'{name}View.xaml'] = view_template.format(
            namespace=namespace,
            view_class=f'{name}View',
        )
        files[f'{name}View.xaml.cs'] = VIEW_CODEBEHIND_TEMPLATE.format(
            namespace=namespace,
            view_class=f'{name}View',
        )

    for filename, content in files.items():
        with open(os.path.join(target, filename), 'w', encoding='utf-8', newline='') as stream:
            stream.write(content)
    return target


class PluginGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ATLAS Display Plugin Generator')
        self.geometry('600x750')
        self.resizable(True, True)
        
        # Create main frame with scrollbar
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # === Basic Plugin Information ===
        info_frame = tk.LabelFrame(scrollable_frame, text='Basic Information', padx=8, pady=8)
        info_frame.pack(fill=tk.X, pady=8)
        
        tk.Label(info_frame, text='Plugin Name:').grid(row=0, column=0, sticky='w', pady=6)
        self.name_var = tk.StringVar()
        tk.Entry(info_frame, textvariable=self.name_var, width=45).grid(row=0, column=1, sticky='ew', padx=8)
        tk.Label(info_frame, text='(C# identifier, required)', font=('Arial', 8, 'italic')).grid(row=0, column=2, sticky='w')
        info_frame.columnconfigure(1, weight=1)

        tk.Label(info_frame, text='Description:').grid(row=1, column=0, sticky='nw', pady=6)
        self.description_var = tk.StringVar()
        tk.Entry(info_frame, textvariable=self.description_var, width=45).grid(row=1, column=1, sticky='ew', padx=8)
        tk.Label(info_frame, text='(optional)', font=('Arial', 8, 'italic')).grid(row=1, column=2, sticky='w')
        
        # === Output Location ===
        output_frame = tk.LabelFrame(scrollable_frame, text='Output Location', padx=8, pady=8)
        output_frame.pack(fill=tk.X, pady=8)
        
        tk.Label(output_frame, text='Output Folder:').grid(row=0, column=0, sticky='w', pady=6)
        atlas_plugins_default = default_output_folder()
        try:
            os.makedirs(atlas_plugins_default, exist_ok=True)
        except Exception:
            pass
        self.out_var = tk.StringVar(value=atlas_plugins_default)
        tk.Entry(output_frame, textvariable=self.out_var, width=45).grid(row=0, column=1, sticky='ew', padx=8)
        tk.Button(output_frame, text='Browse', command=self.browse).grid(row=0, column=2, padx=6)
        output_frame.columnconfigure(1, weight=1)
        
        # === View & Parameter Configuration ===
        config_frame = tk.LabelFrame(scrollable_frame, text='View & Parameter Configuration', padx=8, pady=8)
        config_frame.pack(fill=tk.X, pady=8)
        
        self.add_view_var = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text='Include simple WPF View', variable=self.add_view_var).pack(anchor='w', pady=4)
        
        self.add_parameters_var = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text='Include dynamic parameter support (uses ParameterSampleDisplayViewModelBase)', 
                       variable=self.add_parameters_var).pack(anchor='w', pady=4)
        
        # === Custom Parameters ===
        param_frame = tk.LabelFrame(scrollable_frame, text='Custom Parameters', padx=8, pady=8)
        param_frame.pack(fill=tk.BOTH, expand=True, pady=8)
        
        tk.Label(param_frame, text='Enter one parameter identifier per line (optional):', font=('Arial', 9)).pack(anchor='w', pady=4)
        self.parameter_text = tk.Text(param_frame, width=50, height=5)
        self.parameter_text.pack(fill=tk.BOTH, expand=True, pady=4)
        scrollbar_param = tk.Scrollbar(param_frame, command=self.parameter_text.yview)
        scrollbar_param.pack(side=tk.RIGHT, fill=tk.Y)
        self.parameter_text.config(yscrollcommand=scrollbar_param.set)
        
        tk.Label(param_frame, text='Example: "EngineSpeed", "BrakePressure", "Temperature"', 
                font=('Arial', 8, 'italic')).pack(anchor='w')
        
        # === Advanced Settings ===
        advanced_frame = tk.LabelFrame(scrollable_frame, text='Advanced Settings', padx=8, pady=8)
        advanced_frame.pack(fill=tk.X, pady=8)
        
        tk.Label(advanced_frame, text='Maximum parameters:').grid(row=0, column=0, sticky='w', pady=6)
        self.parameter_max_var = tk.StringVar(value='100')
        tk.Spinbox(advanced_frame, from_=1, to=1000, textvariable=self.parameter_max_var, width=10).grid(row=0, column=1, sticky='w', padx=8)
        
        self.open_folder_var = tk.BooleanVar(value=True)
        tk.Checkbutton(advanced_frame, text='Open folder after generation', variable=self.open_folder_var).grid(row=1, column=0, columnspan=2, sticky='w', pady=4)
        
        # === Action Buttons ===
        button_frame = tk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=12)
        
        tk.Button(button_frame, text='Generate Plugin', command=self.generate, 
                 bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'), padx=20, pady=10).pack(side=tk.LEFT, padx=4)
        tk.Button(button_frame, text='Reset', command=self.reset_form, 
                 bg='#2196F3', fg='white', font=('Arial', 10), padx=20, pady=10).pack(side=tk.LEFT, padx=4)
        tk.Button(button_frame, text='Exit', command=self.quit, 
                 bg='#f44336', fg='white', font=('Arial', 10), padx=20, pady=10).pack(side=tk.LEFT, padx=4)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def browse(self):
        initial = self.out_var.get()
        if not os.path.isdir(initial):
            initial = os.path.expanduser('~')
        d = filedialog.askdirectory(initialdir=initial)
        if d:
            self.out_var.set(d)

    def reset_form(self):
        self.name_var.set('')
        self.description_var.set('')
        self.parameter_text.delete('1.0', tk.END)
        self.parameter_max_var.set('100')
        self.add_view_var.set(True)
        self.add_parameters_var.set(True)
        self.open_folder_var.set(True)
        messagebox.showinfo('Reset', 'Form has been reset to default values')

    def generate(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror('Error', 'Please enter a plugin name')
            return

        base_out = self.out_var.get() or default_output_folder()
        try:
            parameter_names = parse_parameter_names(self.parameter_text.get('1.0', 'end'))
            parameter_max_count = int(self.parameter_max_var.get())
            if parameter_names and not self.add_parameters_var.get():
                raise ValueError('Enable dynamic parameter support to generate custom parameters.')
            os.makedirs(base_out, exist_ok=True)
            target = generate_plugin(
                name,
                base_out,
                include_view=self.add_view_var.get(),
                include_parameters=self.add_parameters_var.get(),
                parameter_names=parameter_names,
                parameter_max_count=parameter_max_count,
                workspace_root=os.getcwd(),
            )

            # Show success message
            success_msg = f'Plugin "{name}" created successfully at:\n{target}'
            messagebox.showinfo('Success', success_msg)
            
            # Open folder if requested
            if self.open_folder_var.get():
                import subprocess
                import platform
                if platform.system() == 'Windows':
                    os.startfile(target)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.Popen(['open', target])
                else:  # Linux
                    subprocess.Popen(['xdg-open', target])
            
            # Ask if user wants to reset form
            if messagebox.askyesno('Continue', 'Create another plugin?'):
                self.reset_form()
            else:
                self.quit()
        except Exception as ex:
            messagebox.showerror('Error', str(ex))


def main():
    app = PluginGeneratorApp()
    app.mainloop()


if __name__ == '__main__':
    main()
