import os

def replace_required_with_data_required(directory, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = []

    # Walk through all files in the directory recursively
    for root, dirs, files in os.walk(directory):
        # Skip any directories in the exclude_dirs list
        dirs[:] = [d for d in dirs if os.path.join(root, d) not in exclude_dirs]

        for file in files:
            # Skip files in the exclude_dirs list
            if any(os.path.join(root, file).startswith(exclude_dir) for exclude_dir in exclude_dirs):
                continue

            # Only process Python files
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    lines = f.readlines()

                # Check if 'Required' is in the import line specifically
                modified = False
                for i, line in enumerate(lines):
                    # We are only targeting the specific import line
                    if 'from wtforms.validators' in line and 'DataRequired' in line:
                        lines[i] = line.replace('Required', 'DataRequired')
                        modified = True

                # If modifications were made, write the changes back to the file
                if modified:
                    with open(file_path, 'w') as f:
                        f.writelines(lines)
                    print(f"Replaced 'Required' with 'DataRequired' in: {file_path}")

# Run the script, excluding the venv directory
replace_required_with_data_required('/home/karson/alarmdecoder-webapp-modernized', exclude_dirs=['/home/karson/alarmdecoder-webapp-modernized/venv'])
