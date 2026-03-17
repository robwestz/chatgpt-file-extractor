#!/usr/bin/env python3
"""
CLI version: pipe or paste ChatGPT output, get a ZIP.

Usage:
    python cli.py input.txt -o output.zip
    python cli.py input.txt -d ./output-folder
    cat chatgpt-output.txt | python cli.py - -o output.zip
"""

import argparse
import sys
from src.parser import parse
from src.zipper import create_zip_file, extract_to_folder


def main():
    ap = argparse.ArgumentParser(description='Extract files from ChatGPT output')
    ap.add_argument('input', help='Input file path, or "-" for stdin')
    ap.add_argument('-o', '--output-zip', help='Output ZIP path')
    ap.add_argument('-d', '--output-dir', help='Output directory (extract files)')
    ap.add_argument('-r', '--root', default='', help='Root folder name in ZIP')
    args = ap.parse_args()

    # Read input
    if args.input == '-':
        text = sys.stdin.read()
    else:
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()

    files = parse(text)
    print(f'Found {len(files)} files:')
    for f in files:
        print(f'  {f.path} ({len(f.content)} chars)')

    if not files:
        print('No files detected.')
        sys.exit(1)

    if args.output_zip:
        create_zip_file(files, args.output_zip, args.root)
        print(f'Saved ZIP to {args.output_zip}')
    elif args.output_dir:
        extract_to_folder(files, args.output_dir, args.root)
        print(f'Extracted to {args.output_dir}/')
    else:
        print('Specify -o (ZIP) or -d (directory) to save.')


if __name__ == '__main__':
    main()
