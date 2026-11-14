#!/usr/bin/env python3
"""
Assemble notebook_part1.py and notebook_part2.py into a single .ipynb file.
Parses Jupyter percent-script format (# %% markers) into notebook JSON.
"""

import json
import re
import sys
import os

def parse_percent_script(filepath):
    """Parse a Jupyter percent-script .py file into a list of cells."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split on cell markers
    # Match: # %% [markdown] or # %%
    cell_pattern = re.compile(r'^# %%\s*(?:\[markdown\])?\s*$', re.MULTILINE)
    
    # Find all cell boundaries
    parts = []
    last_end = 0
    for match in cell_pattern.finditer(content):
        if last_end > 0:
            parts.append({
                'marker': content[last_marker_start:last_marker_end],
                'content': content[last_marker_end:match.start()]
            })
        last_marker_start = match.start()
        last_marker_end = match.end()
        last_end = match.end()
    
    # Don't forget the last cell
    if last_end > 0:
        parts.append({
            'marker': content[last_marker_start:last_marker_end],
            'content': content[last_end:]
        })
    
    cells = []
    for part in parts:
        marker = part['marker'].strip()
        raw_content = part['content']
        
        is_markdown = '[markdown]' in marker
        
        # Clean up the content
        lines = raw_content.split('\n')
        
        # Remove leading/trailing empty lines
        while lines and lines[0].strip() == '':
            lines.pop(0)
        while lines and lines[-1].strip() == '':
            lines.pop()
        
        if not lines:
            continue
        
        if is_markdown:
            # Strip '# ' prefix from markdown lines
            md_lines = []
            for line in lines:
                if line.startswith('# '):
                    md_lines.append(line[2:])
                elif line.strip() == '#':
                    md_lines.append('')
                else:
                    # If it doesn't start with #, include as-is (might be a blank line)
                    md_lines.append(line)
            
            source = []
            for i, line in enumerate(md_lines):
                if i < len(md_lines) - 1:
                    source.append(line + '\n')
                else:
                    source.append(line)
            
            cells.append({
                'cell_type': 'markdown',
                'metadata': {},
                'source': source
            })
        else:
            # Code cell
            source = []
            for i, line in enumerate(lines):
                if i < len(lines) - 1:
                    source.append(line + '\n')
                else:
                    source.append(line)
            
            cells.append({
                'cell_type': 'code',
                'metadata': {},
                'source': source,
                'outputs': [],
                'execution_count': None
            })
    
    return cells


def create_notebook(cells, output_path):
    """Create a .ipynb notebook from a list of cells."""
    notebook = {
        'nbformat': 4,
        'nbformat_minor': 5,
        'metadata': {
            'kernelspec': {
                'display_name': 'Python 3',
                'language': 'python',
                'name': 'python3'
            },
            'language_info': {
                'name': 'python',
                'version': '3.10.0',
                'mimetype': 'text/x-python',
                'file_extension': '.py',
                'codemirror_mode': {
                    'name': 'ipython',
                    'version': 3
                }
            },
            'colab': {
                'provenance': [],
                'toc_visible': True
            }
        },
        'cells': cells
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    
    print(f"✅ Notebook created: {output_path}")
    print(f"   Total cells: {len(cells)}")
    md_cells = sum(1 for c in cells if c['cell_type'] == 'markdown')
    code_cells = sum(1 for c in cells if c['cell_type'] == 'code')
    print(f"   Markdown cells: {md_cells}")
    print(f"   Code cells: {code_cells}")


def main():
    build_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(build_dir)
    
    part1_path = os.path.join(build_dir, 'notebook_part1.py')
    part2_path = os.path.join(build_dir, 'notebook_part2.py')
    output_path = os.path.join(project_dir, 'notebooks', 'Automated_CRM_Data_Filler_Agent.ipynb')
    
    print("🔧 Parsing Part 1...")
    cells_part1 = parse_percent_script(part1_path)
    print(f"   Found {len(cells_part1)} cells")
    
    print("🔧 Parsing Part 2...")
    cells_part2 = parse_percent_script(part2_path)
    print(f"   Found {len(cells_part2)} cells")
    
    # Combine cells
    all_cells = cells_part1 + cells_part2
    
    print(f"\n📓 Assembling notebook with {len(all_cells)} total cells...")
    create_notebook(all_cells, output_path)
    print("✅ Done!")


if __name__ == '__main__':
    main()
