from pathlib import Path
import re
from pydantic import BaseModel

class Specifications(BaseModel):
    temperature_logging_terminal_interval: int

def parse_specifications_from_readme(file_path):
    """
    Parses a README.md file to extract specifications and returns them in a dictionary,
    with keys ready for a Pydantic model.
    """
    specifications = {}
    content = file_path.read_text()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('§ '):
            spec_line = line[2:]

            # Find the start and end of the value
            value_start_index = spec_line.find('```') + 3
            value_end_index = spec_line.find('```', value_start_index)

            # Extract the name and value
            name_part = spec_line[:value_start_index - 3].strip()
            value = spec_line[value_start_index:value_end_index].strip()
            
            # Clean the name to be Pydantic-friendly (e.g., snake_case)
            name = re.sub(r'(\s\[.*?\]|\s*:)*$', '', name_part)
            cleaned_name = name.lower().replace(' ', '_').replace('-', '_')
            
            specifications[cleaned_name] = value
    validated_specifications = Specifications.model_validate(specifications)
    return validated_specifications
