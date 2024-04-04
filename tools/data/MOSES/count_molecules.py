def count_molecules_in_smi_file(file_path):
    try:
        with open(file_path, 'r') as file:
            molecules = file.readlines()
            return len(molecules)
    except FileNotFoundError:
        return "File not found. Please check the file path."

# Replace 'path_to_your_file.smi' with the actual path to your .smi file
file_path = 'train.smi'
number_of_molecules = count_molecules_in_smi_file(file_path)
print(f'Number of molecules in the file: {number_of_molecules} in {file_path}')

