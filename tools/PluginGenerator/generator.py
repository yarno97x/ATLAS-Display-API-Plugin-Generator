import argparse
import os


def run(args=None):
	parser = argparse.ArgumentParser(description='Generate an ATLAS display plugin.')
	parser.add_argument('name', nargs='?', help='plugin name; omit to open the GUI')
	parser.add_argument('--output', help='parent folder for the generated plugin')
	parser.add_argument('--no-view', action='store_true', help='omit the WPF view files')
	parser.add_argument('--no-parameters', action='store_true', help='omit dynamic parameter support')
	parser.add_argument('--max-parameters', type=int, default=100, help='maximum number of display parameters')
	options = parser.parse_args(args)

	from .gui import default_output_folder, generate_plugin, main

	if not options.name:
		main()
		return

	output = options.output or default_output_folder()
	target = generate_plugin(
		options.name,
		output,
		include_view=not options.no_view,
		include_parameters=not options.no_parameters,
		parameter_max_count=options.max_parameters,
		workspace_root=os.getcwd(),
	)
	print(f'Plugin created at: {target}')


if __name__ == '__main__':
	run()
