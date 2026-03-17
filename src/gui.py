"""
Native GUI for ChatGPT File Extractor.
Paste ChatGPT output → see detected files → download as ZIP or extract to folder.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
from pathlib import Path

from .parser import parse, ExtractedFile
from .zipper import create_zip_file, extract_to_folder


# ──────────────────────────────────────────
# Colors (dark theme)
# ──────────────────────────────────────────
BG = '#1a1a2e'
BG_LIGHT = '#16213e'
BG_INPUT = '#0f0f23'
FG = '#e0e0e0'
FG_DIM = '#888899'
ACCENT = '#5a6af8'
ACCENT_HOVER = '#6b7af9'
RED = '#e06060'
GREEN = '#60c060'
BORDER = '#2a2a4a'


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('ChatGPT File Extractor')
        self.root.geometry('780x680')
        self.root.configure(bg=BG)
        self.root.minsize(600, 500)

        # State
        self.files: list[ExtractedFile] = []

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('.', background=BG, foreground=FG, borderwidth=0)
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=FG, font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'), foreground=ACCENT)
        style.configure('Dim.TLabel', foreground=FG_DIM, font=('Segoe UI', 9))
        style.configure('Status.TLabel', foreground=GREEN, font=('Segoe UI', 10))
        style.configure('Count.TLabel', foreground=ACCENT, font=('Segoe UI', 11, 'bold'))

        style.configure('Accent.TButton', background=ACCENT, foreground='white',
                        font=('Segoe UI', 10, 'bold'), padding=(16, 8))
        style.map('Accent.TButton', background=[('active', ACCENT_HOVER)])

        style.configure('Secondary.TButton', background=BG_LIGHT, foreground=FG,
                        font=('Segoe UI', 10), padding=(12, 6))
        style.map('Secondary.TButton', background=[('active', BORDER)])

        style.configure('Danger.TButton', background=BG_LIGHT, foreground=RED,
                        font=('Segoe UI', 10), padding=(12, 6))

        # Treeview
        style.configure('Treeview', background=BG_INPUT, foreground=FG,
                        fieldbackground=BG_INPUT, font=('Consolas', 10),
                        rowheight=24, borderwidth=0)
        style.configure('Treeview.Heading', background=BG_LIGHT, foreground=FG_DIM,
                        font=('Segoe UI', 9, 'bold'))
        style.map('Treeview', background=[('selected', ACCENT)],
                  foreground=[('selected', 'white')])

    def _build_ui(self):
        # ── Header ──
        header = ttk.Frame(self.root)
        header.pack(fill='x', padx=16, pady=(12, 6))
        ttk.Label(header, text='ChatGPT File Extractor', style='Title.TLabel').pack(side='left')
        ttk.Label(header, text='Paste output → Extract files → Download ZIP',
                  style='Dim.TLabel').pack(side='left', padx=(12, 0))

        # ── Input area ──
        input_frame = ttk.Frame(self.root)
        input_frame.pack(fill='both', expand=True, padx=16, pady=(4, 4), side='top')

        input_label = ttk.Frame(input_frame)
        input_label.pack(fill='x')
        ttk.Label(input_label, text='Paste ChatGPT output here:').pack(side='left')
        self.btn_clear = ttk.Button(input_label, text='Clear', style='Danger.TButton',
                                     command=self._clear)
        self.btn_clear.pack(side='right')
        self.btn_paste = ttk.Button(input_label, text='Paste from clipboard',
                                     style='Secondary.TButton', command=self._paste_clipboard)
        self.btn_paste.pack(side='right', padx=(0, 6))

        self.text_input = tk.Text(input_frame, bg=BG_INPUT, fg=FG, insertbackground=FG,
                                   font=('Consolas', 10), wrap='word', height=12,
                                   relief='flat', bd=0, padx=8, pady=8,
                                   selectbackground=ACCENT, selectforeground='white')
        self.text_input.pack(fill='both', expand=True, pady=(6, 0))
        self.text_input.bind('<Control-v>', lambda e: self.root.after(10, self._auto_parse))

        # ── Parse button ──
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill='x', padx=16, pady=6)
        self.btn_parse = ttk.Button(btn_frame, text='Extract Files', style='Accent.TButton',
                                     command=self._parse)
        self.btn_parse.pack(side='left')
        self.status_label = ttk.Label(btn_frame, text='', style='Status.TLabel')
        self.status_label.pack(side='left', padx=(12, 0))

        # ── File list ──
        files_frame = ttk.Frame(self.root)
        files_frame.pack(fill='both', expand=True, padx=16, pady=(0, 4))

        files_header = ttk.Frame(files_frame)
        files_header.pack(fill='x')
        ttk.Label(files_header, text='Detected files:').pack(side='left')
        self.file_count_label = ttk.Label(files_header, text='0 files', style='Count.TLabel')
        self.file_count_label.pack(side='right')

        # Treeview with columns
        tree_frame = ttk.Frame(files_frame)
        tree_frame.pack(fill='both', expand=True, pady=(4, 0))

        self.tree = ttk.Treeview(tree_frame, columns=('size', 'folder'), show='tree headings',
                                  selectmode='extended')
        self.tree.heading('#0', text='File', anchor='w')
        self.tree.heading('size', text='Size', anchor='e')
        self.tree.heading('folder', text='Folder', anchor='w')
        self.tree.column('#0', width=280, minwidth=150)
        self.tree.column('size', width=80, minwidth=60, anchor='e')
        self.tree.column('folder', width=250, minwidth=100)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        # ── Preview ──
        preview_frame = ttk.Frame(self.root)
        preview_frame.pack(fill='x', padx=16, pady=(0, 4))
        ttk.Label(preview_frame, text='Preview:', style='Dim.TLabel').pack(anchor='w')
        self.preview_text = tk.Text(preview_frame, bg=BG_INPUT, fg=FG_DIM,
                                     font=('Consolas', 9), wrap='word', height=4,
                                     relief='flat', bd=0, padx=8, pady=4, state='disabled')
        self.preview_text.pack(fill='x')

        # ── Action buttons ──
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill='x', padx=16, pady=(4, 12))

        self.btn_zip = ttk.Button(action_frame, text='Save as ZIP',
                                   style='Accent.TButton', command=self._save_zip)
        self.btn_zip.pack(side='left')
        self.btn_zip.state(['disabled'])

        self.btn_folder = ttk.Button(action_frame, text='Extract to folder',
                                      style='Secondary.TButton', command=self._extract_folder)
        self.btn_folder.pack(side='left', padx=(8, 0))
        self.btn_folder.state(['disabled'])

        # Root folder name
        ttk.Label(action_frame, text='Root folder:', style='Dim.TLabel').pack(side='left', padx=(16, 4))
        self.root_folder_var = tk.StringVar(value='project')
        self.root_entry = tk.Entry(action_frame, textvariable=self.root_folder_var,
                                    bg=BG_INPUT, fg=FG, font=('Consolas', 10),
                                    relief='flat', width=16, insertbackground=FG)
        self.root_entry.pack(side='left')

    def _paste_clipboard(self):
        try:
            text = self.root.clipboard_get()
            self.text_input.delete('1.0', 'end')
            self.text_input.insert('1.0', text)
            self._parse()
        except tk.TclError:
            messagebox.showinfo('Clipboard', 'Nothing in clipboard')

    def _auto_parse(self):
        """Auto-parse after paste."""
        content = self.text_input.get('1.0', 'end').strip()
        if content:
            self._parse()

    def _clear(self):
        self.text_input.delete('1.0', 'end')
        self.files = []
        self.tree.delete(*self.tree.get_children())
        self.file_count_label.config(text='0 files')
        self.status_label.config(text='')
        self.btn_zip.state(['disabled'])
        self.btn_folder.state(['disabled'])
        self._clear_preview()

    def _parse(self):
        content = self.text_input.get('1.0', 'end').strip()
        if not content:
            self.status_label.config(text='Nothing to parse', foreground=RED)
            return

        self.files = parse(content)

        # Populate tree
        self.tree.delete(*self.tree.get_children())
        for i, f in enumerate(self.files):
            name = Path(f.path).name
            folder = str(Path(f.path).parent) if '/' in f.path else ''
            size = f'{len(f.content)} chars'
            self.tree.insert('', 'end', iid=str(i), text=name,
                           values=(size, folder))

        count = len(self.files)
        self.file_count_label.config(text=f'{count} file{"s" if count != 1 else ""}')

        if count > 0:
            self.status_label.config(text=f'Found {count} files', foreground=GREEN)
            self.btn_zip.state(['!disabled'])
            self.btn_folder.state(['!disabled'])
        else:
            self.status_label.config(text='No files detected — check format', foreground=RED)
            self.btn_zip.state(['disabled'])
            self.btn_folder.state(['disabled'])

    def _on_select(self, event):
        sel = self.tree.selection()
        if sel:
            idx = int(sel[0])
            f = self.files[idx]
            self._show_preview(f)

    def _show_preview(self, f: ExtractedFile):
        self.preview_text.config(state='normal')
        self.preview_text.delete('1.0', 'end')
        preview = f.content[:500]
        if len(f.content) > 500:
            preview += '\n... (truncated)'
        self.preview_text.insert('1.0', preview)
        self.preview_text.config(state='disabled')

    def _clear_preview(self):
        self.preview_text.config(state='normal')
        self.preview_text.delete('1.0', 'end')
        self.preview_text.config(state='disabled')

    def _save_zip(self):
        if not self.files:
            return

        root_folder = self.root_folder_var.get().strip() or ''
        path = filedialog.asksaveasfilename(
            defaultextension='.zip',
            filetypes=[('ZIP files', '*.zip')],
            initialfile=f'{root_folder or "chatgpt-files"}.zip'
        )
        if path:
            create_zip_file(self.files, path, root_folder)
            self.status_label.config(text=f'Saved to {Path(path).name}', foreground=GREEN)

    def _extract_folder(self):
        if not self.files:
            return

        root_folder = self.root_folder_var.get().strip() or ''
        folder = filedialog.askdirectory(title='Select output folder')
        if folder:
            extract_to_folder(self.files, folder, root_folder)
            count = len(self.files)
            self.status_label.config(text=f'Extracted {count} files to {Path(folder).name}/',
                                    foreground=GREEN)

    def run(self):
        self.root.mainloop()
