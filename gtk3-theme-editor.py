#!/usr/bin/env python3
"""GTK3 Theme Editor - A GUI tool for configuring GTK themes on XFCE."""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, Pango, GLib
import os
import re
import copy
import shutil
from datetime import datetime


class ThemeParser:
    """Parse and modify GTK theme files."""

    @staticmethod
    def _extract_css_props(block_text):
        """Extract property: value pairs from a CSS declaration block."""
        props = {}
        # Split on ; and parse each declaration
        for decl in block_text.split(';'):
            decl = decl.strip()
            if ':' not in decl:
                continue
            prop, _, val = decl.partition(':')
            prop = prop.strip()
            val = val.strip()
            props[prop] = val
        return props

    @staticmethod
    def parse_gtk3_css_colors(css_text):
        """Extract color values from GTK3 CSS."""
        colors = {}
        hex_re = r'#[0-9a-fA-F]{3,8}'

        # Parse specific CSS rule blocks for their color properties
        block_patterns = [
            ('background', r'\.background\s*\{([^}]+)\}'),
            ('background_backdrop', r'\.background:backdrop\s*\{([^}]+)\}'),
            ('view', r'\.view,\s*iconview[^{]*\{([^}]+)\}'),
            ('selected', r'\.gtkstyle-fallback:selected[^{]*\{([^}]+)\}'),
            ('disabled', r'\.gtkstyle-fallback:disabled[^{]*\{([^}]+)\}'),
            ('entry', r'spinbutton:not\(\.vertical\),\s*entry\s*\{([^}]+)\}'),
            ('entry_focus', r'spinbutton:focus:not\(\.vertical\),\s*entry:focus\s*\{([^}]+)\}'),
            ('entry_error', r'spinbutton\.error:not\(\.vertical\),\s*entry\.error\s*\{([^}]+)\}'),
            ('entry_warning', r'spinbutton\.warning:not\(\.vertical\),\s*entry\.warning\s*\{([^}]+)\}'),
            ('entry_drop', r'spinbutton:drop\(active\):not\(\.vertical\),\s*entry:drop\(active\)[^{]*\{([^}]+)\}'),
            ('osd', r'\.osd\s*\{([^}]+)\}'),
            ('textview_border', r'textview\s+border\s*\{([^}]+)\}'),
            ('global', r'^\*[^{]*\{([^}]+)\}'),
        ]

        blocks = {}
        for name, pattern in block_patterns:
            m = re.search(pattern, css_text, re.MULTILINE)
            if m:
                blocks[name] = ThemeParser._extract_css_props(m.group(1))

        def get_hex(props, prop_name):
            val = props.get(prop_name, '')
            m = re.search(hex_re, val)
            return m.group(0) if m else None

        def get_rgba_hex(props, prop_name):
            val = props.get(prop_name, '')
            m = re.search(r'rgba\((\d+),\s*(\d+),\s*(\d+)', val)
            if m:
                return '#{:02x}{:02x}{:02x}'.format(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return get_hex(props, prop_name)

        # Extract colors from parsed blocks
        if 'background' in blocks:
            v = get_hex(blocks['background'], 'background-color')
            if v:
                colors['bg_color'] = {'value': v, 'label': 'Window Background'}
            v = get_hex(blocks['background'], 'color')
            if v:
                colors['fg_color'] = {'value': v, 'label': 'Window Foreground'}

        if 'view' in blocks:
            v = get_hex(blocks['view'], 'background-color')
            if v:
                colors['base_color'] = {'value': v, 'label': 'View/Input Background'}
            # text_color may be a named color like "white"
            val = blocks['view'].get('color', '').strip()
            if val:
                rgba = Gdk.RGBA()
                if rgba.parse(val):
                    colors['text_color'] = {
                        'value': '#{:02x}{:02x}{:02x}'.format(
                            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)),
                        'label': 'View/Input Text'
                    }

        if 'selected' in blocks:
            v = get_hex(blocks['selected'], 'background-color')
            if v:
                colors['selected_bg_color'] = {'value': v, 'label': 'Selection Background'}
            v = get_hex(blocks['selected'], 'color')
            if v:
                colors['selected_fg_color'] = {'value': v, 'label': 'Selection Foreground'}

        if 'global' in blocks:
            v = get_hex(blocks['global'], '-gtk-secondary-caret-color')
            if v:
                colors['link_color'] = {'value': v, 'label': 'Accent/Link Color'}

        if 'entry' in blocks:
            v = get_hex(blocks['entry'], 'border-color')
            if v:
                colors['entry_border'] = {'value': v, 'label': 'Entry Border'}
            v = get_hex(blocks['entry'], 'background-color')
            if v:
                colors['entry_bg'] = {'value': v, 'label': 'Entry Background'}

        if 'entry_focus' in blocks:
            v = get_hex(blocks['entry_focus'], 'border-color')
            if v:
                colors['focus_color'] = {'value': v, 'label': 'Focus Border'}

        if 'entry_error' in blocks:
            v = get_hex(blocks['entry_error'], 'border-color')
            if v:
                colors['error_color'] = {'value': v, 'label': 'Error Color'}

        if 'entry_warning' in blocks:
            v = get_hex(blocks['entry_warning'], 'border-color')
            if v:
                colors['warning_color'] = {'value': v, 'label': 'Warning Color'}

        if 'entry_drop' in blocks:
            v = get_hex(blocks['entry_drop'], 'border-color')
            if v:
                colors['success_color'] = {'value': v, 'label': 'Success Color'}

        if 'osd' in blocks:
            v = get_rgba_hex(blocks['osd'], 'background-color')
            if v:
                colors['osd_bg'] = {'value': v, 'label': 'OSD Background'}
            v = get_hex(blocks['osd'], 'color')
            if v:
                colors['osd_fg'] = {'value': v, 'label': 'OSD Foreground'}

        if 'textview_border' in blocks:
            v = get_hex(blocks['textview_border'], 'background-color')
            if v:
                colors['tooltip_border'] = {'value': v, 'label': 'Textview Border BG'}

        if 'background_backdrop' in blocks:
            v = get_hex(blocks['background_backdrop'], 'color')
            if v:
                colors['backdrop_fg'] = {'value': v, 'label': 'Backdrop Foreground'}

        if 'disabled' in blocks:
            v = get_hex(blocks['disabled'], 'color')
            if v:
                colors['disabled_fg'] = {'value': v, 'label': 'Disabled Foreground'}
            v = get_hex(blocks['disabled'], 'background-color')
            if v:
                colors['disabled_bg'] = {'value': v, 'label': 'Disabled Background'}

        return colors

    @staticmethod
    def parse_gtk2_colors(gtkrc_text):
        """Extract color-scheme values from GTK2 gtkrc."""
        colors = {}
        color_labels = {
            'bg_color': 'Background',
            'selected_bg_color': 'Selection Background',
            'base_color': 'View Background',
            'fg_color': 'Foreground',
            'selected_fg_color': 'Selection Foreground',
            'text_color': 'Text',
            'tooltip_bg_color': 'Tooltip Background',
            'tooltip_fg_color': 'Tooltip Foreground',
            'link_color': 'Link',
            'panel_bg': 'Panel Background',
            'fm_color': 'File Manager',
            'bg_color_dark': 'Dark Background',
            'text_color_dark': 'Dark Text',
        }

        for match in re.finditer(r'gtk-color-scheme\s*=\s*"([^"]*)"', gtkrc_text):
            scheme = match.group(1)
            for pair in scheme.split('\\n'):
                pair = pair.strip()
                if ':' in pair:
                    name, value = pair.split(':', 1)
                    name = name.strip()
                    value = value.strip()
                    if value.startswith('#'):
                        label = color_labels.get(name, name.replace('_', ' ').title())
                        colors[name] = {'value': value, 'label': label}
        return colors

    @staticmethod
    def parse_murrine_settings(gtkrc_text):
        """Extract murrine engine settings from GTK2 gtkrc default style."""
        settings = {}
        # Find the default style's murrine engine block - handle nested { } in values
        m = re.search(r'style\s+"default"\s*\{.*?engine\s+"murrine"\s*\{', gtkrc_text, re.DOTALL)
        if not m:
            return settings

        # Find the matching closing brace, accounting for nested braces
        start = m.end()
        depth = 1
        pos = start
        while pos < len(gtkrc_text) and depth > 0:
            if gtkrc_text[pos] == '{':
                depth += 1
            elif gtkrc_text[pos] == '}':
                depth -= 1
            pos += 1
        block = gtkrc_text[start:pos - 1]
        setting_defs = {
            'roundness': ('Roundness', 'int', 0, 20),
            'contrast': ('Contrast', 'float', 0.0, 2.0),
            'highlight_shade': ('Highlight Shade', 'float', 0.5, 1.5),
            'lightborder_shade': ('Light Border Shade', 'float', 0.5, 2.0),
            'glazestyle': ('Glaze Style', 'int', 0, 4),
            'glowstyle': ('Glow Style', 'int', 0, 4),
            'glow_shade': ('Glow Shade', 'float', 0.5, 2.0),
            'menubarstyle': ('Menubar Style', 'int', 0, 3),
            'menuitemstyle': ('Menu Item Style', 'int', 0, 2),
            'menustyle': ('Menu Stripe', 'int', 0, 1),
            'reliefstyle': ('Relief Style', 'int', 0, 3),
            'scrollbarstyle': ('Scrollbar Style', 'int', 0, 6),
            'separatorstyle': ('Separator Style', 'int', 0, 1),
            'sliderstyle': ('Slider Style', 'int', 0, 1),
            'stepperstyle': ('Stepper Style', 'int', 0, 2),
            'progressbarstyle': ('Progress Bar Style', 'int', 0, 2),
            'toolbarstyle': ('Toolbar Style', 'int', 0, 2),
            'arrowstyle': ('Arrow Style', 'int', 0, 2),
            'textstyle': ('Text Style', 'int', 0, 1),
            'focusstyle': ('Focus Style', 'int', 0, 3),
            'prelight_shade': ('Prelight Shade', 'float', 0.5, 1.5),
            'animation': ('Animation', 'bool', None, None),
            'colorize_scrollbar': ('Colorize Scrollbar', 'bool', None, None),
            'rgba': ('RGBA', 'bool', None, None),
        }

        for key, (label, vtype, vmin, vmax) in setting_defs.items():
            pattern = rf'{key}\s*=\s*([^\s#]+)'
            m = re.search(pattern, block, re.IGNORECASE)
            if m:
                raw = m.group(1).strip()
                settings[key] = {
                    'value': raw,
                    'label': label,
                    'type': vtype,
                    'min': vmin,
                    'max': vmax,
                }
        return settings

    @staticmethod
    def parse_xfwm4_themerc(text):
        """Parse xfwm4 themerc key=value pairs."""
        settings = {}
        setting_defs = {
            'active_text_color': ('Active Title Color', 'color'),
            'inactive_text_color': ('Inactive Title Color', 'color'),
            'title_shadow_active': ('Active Title Shadow', 'bool'),
            'title_shadow_inactive': ('Inactive Title Shadow', 'bool'),
            'full_width_title': ('Full Width Title', 'bool'),
            'title_vertical_offset_active': ('Active Title V-Offset', 'int'),
            'title_vertical_offset_inactive': ('Inactive Title V-Offset', 'int'),
            'button_offset': ('Button Offset', 'int'),
            'button_spacing': ('Button Spacing', 'int'),
            'shadow_delta_height': ('Shadow Delta Height', 'int'),
            'shadow_delta_width': ('Shadow Delta Width', 'int'),
            'shadow_delta_x': ('Shadow Delta X', 'int'),
            'shadow_delta_y': ('Shadow Delta Y', 'int'),
            'shadow_opacity': ('Shadow Opacity', 'int'),
            'frame_border_top': ('Frame Border Top', 'int'),
        }
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip()
            if key in setting_defs:
                label, vtype = setting_defs[key]
                settings[key] = {'value': val, 'label': label, 'type': vtype}
        return settings

    @staticmethod
    def parse_index_theme(text):
        """Parse index.theme metadata."""
        meta = {}
        fields = {
            'Name': 'Theme Name',
            'Comment': 'Comment',
            'GtkTheme': 'GTK Theme',
            'MetacityTheme': 'Metacity Theme',
            'IconTheme': 'Icon Theme',
            'CursorTheme': 'Cursor Theme',
            'ButtonLayout': 'Button Layout',
        }
        for line in text.splitlines():
            line = line.strip()
            if '=' not in line or line.startswith('['):
                continue
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip()
            if key in fields:
                meta[key] = {'value': val, 'label': fields[key]}
        return meta


class ThemeWriter:
    """Write modified values back to theme files."""

    @staticmethod
    def update_gtk2_color_scheme(gtkrc_text, colors):
        """Update color-scheme values in gtkrc."""
        for name, data in colors.items():
            new_val = data['value']
            # Match name:#color within gtk-color-scheme strings
            pattern = rf'({name}\s*:\s*)#[0-9a-fA-F]+'
            gtkrc_text = re.sub(pattern, rf'\g<1>{new_val}', gtkrc_text)
        return gtkrc_text

    @staticmethod
    def update_murrine_default(gtkrc_text, settings):
        """Update murrine engine settings in the default style."""
        for key, data in settings.items():
            val = data['value']
            # Replace within the file
            pattern = rf'({key}\s*=\s*)[^\s#]+'
            gtkrc_text = re.sub(pattern, rf'\g<1>{val}', gtkrc_text, count=1)
        return gtkrc_text

    @staticmethod
    def update_gtk3_css_color(css_text, old_color, new_color):
        """Replace a specific color value throughout GTK3 CSS."""
        if old_color and new_color and old_color != new_color:
            css_text = css_text.replace(old_color, new_color)
        return css_text

    @staticmethod
    def update_xfwm4_themerc(text, settings):
        """Update xfwm4 themerc values."""
        for key, data in settings.items():
            val = data['value']
            pattern = rf'^({key}\s*=\s*).*$'
            text = re.sub(pattern, rf'\g<1>{val}', text, flags=re.MULTILINE)
        return text

    @staticmethod
    def update_index_theme(text, meta):
        """Update index.theme metadata."""
        for key, data in meta.items():
            val = data['value']
            pattern = rf'^({key}\s*=\s*).*$'
            text = re.sub(pattern, rf'\g<1>{val}', text, flags=re.MULTILINE)
        return text


class ColorButton(Gtk.ColorButton):
    """Color button that tracks a key name."""

    def __init__(self, key, hex_color, callback):
        super().__init__()
        self.key = key
        rgba = Gdk.RGBA()
        rgba.parse(hex_color)
        self.set_rgba(rgba)
        self.set_use_alpha(False)
        self.connect('color-set', callback)


class ThemeEditorWindow(Gtk.Window):
    """Main application window."""

    def __init__(self):
        super().__init__(title="GTK3 Theme Editor")
        self.set_default_size(900, 700)
        self.set_border_width(6)

        self.theme_dir = None
        self.gtk3_css_text = None
        self.gtk3_dark_css_text = None
        self.gtk2_gtkrc_text = None
        self.xfwm4_text = None
        self.index_text = None

        self.gtk3_colors = {}
        self.gtk3_colors_orig = {}
        self.gtk2_colors = {}
        self.murrine_settings = {}
        self.xfwm4_settings = {}
        self.index_meta = {}

        self._build_ui()

    def _build_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_bottom(6)

        open_btn = Gtk.Button(label="Open Theme")
        open_btn.connect('clicked', self._on_open)
        toolbar.pack_start(open_btn, False, False, 0)

        save_btn = Gtk.Button(label="Save Theme")
        save_btn.get_style_context().add_class('suggested-action')
        save_btn.connect('clicked', self._on_save)
        toolbar.pack_start(save_btn, False, False, 0)

        save_as_btn = Gtk.Button(label="Save As...")
        save_as_btn.connect('clicked', self._on_save_as)
        toolbar.pack_start(save_as_btn, False, False, 0)

        self.theme_label = Gtk.Label(label="No theme loaded")
        self.theme_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.theme_label.set_xalign(1.0)
        toolbar.pack_end(self.theme_label, True, True, 0)

        vbox.pack_start(toolbar, False, False, 0)

        # Notebook tabs
        self.notebook = Gtk.Notebook()
        vbox.pack_start(self.notebook, True, True, 0)

        # Placeholder pages - populated on theme load
        self.gtk3_page = self._make_scrolled_page("GTK3 Colors")
        self.gtk2_page = self._make_scrolled_page("GTK2 Colors")
        self.murrine_page = self._make_scrolled_page("Murrine Engine")
        self.xfwm4_page = self._make_scrolled_page("XFWM4 Window Manager")
        self.meta_page = self._make_scrolled_page("Theme Metadata")
        self.preview_page = self._make_scrolled_page("Preview")

    def _make_scrolled_page(self, title):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        viewport = Gtk.Viewport()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        viewport.add(box)
        scroll.add(viewport)
        self.notebook.append_page(scroll, Gtk.Label(label=title))
        return box

    def _clear_page(self, page):
        for child in page.get_children():
            page.remove(child)

    def _on_open(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select Theme Directory",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        # Default to system themes or user themes
        for d in [os.path.expanduser('~/.themes'), '/usr/share/themes']:
            if os.path.isdir(d):
                dialog.set_current_folder(d)
                break

        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            self._load_theme(dialog.get_filename())
        dialog.destroy()

    def _load_theme(self, theme_dir):
        self.theme_dir = theme_dir
        name = os.path.basename(theme_dir)
        self.theme_label.set_text(f"Theme: {name}  ({theme_dir})")

        # Read files
        self.gtk3_css_text = self._read_file(os.path.join(theme_dir, 'gtk-3.0', 'gtk.css'))
        self.gtk3_dark_css_text = self._read_file(os.path.join(theme_dir, 'gtk-3.0', 'gtk-dark.css'))
        self.gtk2_gtkrc_text = self._read_file(os.path.join(theme_dir, 'gtk-2.0', 'gtkrc'))
        self.xfwm4_text = self._read_file(os.path.join(theme_dir, 'xfwm4', 'themerc'))
        self.index_text = self._read_file(os.path.join(theme_dir, 'index.theme'))

        # Parse
        if self.gtk3_css_text:
            self.gtk3_colors = ThemeParser.parse_gtk3_css_colors(self.gtk3_css_text)
            self.gtk3_colors_orig = {k: v['value'] for k, v in self.gtk3_colors.items()}
        if self.gtk2_gtkrc_text:
            self.gtk2_colors = ThemeParser.parse_gtk2_colors(self.gtk2_gtkrc_text)
            self.murrine_settings = ThemeParser.parse_murrine_settings(self.gtk2_gtkrc_text)
        if self.xfwm4_text:
            self.xfwm4_settings = ThemeParser.parse_xfwm4_themerc(self.xfwm4_text)
        if self.index_text:
            self.index_meta = ThemeParser.parse_index_theme(self.index_text)

        # Build UI
        self._populate_gtk3_page()
        self._populate_gtk2_page()
        self._populate_murrine_page()
        self._populate_xfwm4_page()
        self._populate_meta_page()
        self._populate_preview_page()

        self.show_all()

    def _read_file(self, path):
        if os.path.isfile(path):
            with open(path, 'r', errors='replace') as f:
                return f.read()
        return None

    # ── GTK3 Colors ──────────────────────────────────────────

    def _populate_gtk3_page(self):
        self._clear_page(self.gtk3_page)
        if not self.gtk3_colors:
            self.gtk3_page.pack_start(Gtk.Label(label="No GTK3 CSS found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>GTK3 CSS Colors</b>  (gtk-3.0/gtk.css)")
        header.set_xalign(0)
        self.gtk3_page.pack_start(header, False, False, 4)

        note = Gtk.Label(label="Changes replace the color globally in the CSS file.")
        note.set_xalign(0)
        note.get_style_context().add_class('dim-label')
        self.gtk3_page.pack_start(note, False, False, 0)

        grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        grid.set_margin_top(8)
        self.gtk3_page.pack_start(grid, False, False, 0)

        row = 0
        for key, data in self.gtk3_colors.items():
            label = Gtk.Label(label=data['label'])
            label.set_xalign(0)
            grid.attach(label, 0, row, 1, 1)

            hex_label = Gtk.Label(label=data['value'])
            hex_label.set_xalign(0)
            hex_label.set_name(f'gtk3_hex_{key}')
            grid.attach(hex_label, 2, row, 1, 1)

            btn = ColorButton(key, data['value'], self._on_gtk3_color_changed)
            btn.hex_label = hex_label
            grid.attach(btn, 1, row, 1, 1)

            row += 1

    def _on_gtk3_color_changed(self, btn):
        rgba = btn.get_rgba()
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
        self.gtk3_colors[btn.key]['value'] = hex_color
        btn.hex_label.set_text(hex_color)

    # ── GTK2 Colors ──────────────────────────────────────────

    def _populate_gtk2_page(self):
        self._clear_page(self.gtk2_page)
        if not self.gtk2_colors:
            self.gtk2_page.pack_start(Gtk.Label(label="No GTK2 gtkrc found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>GTK2 Color Scheme</b>  (gtk-2.0/gtkrc)")
        header.set_xalign(0)
        self.gtk2_page.pack_start(header, False, False, 4)

        grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        grid.set_margin_top(8)
        self.gtk2_page.pack_start(grid, False, False, 0)

        row = 0
        for key, data in self.gtk2_colors.items():
            label = Gtk.Label(label=data['label'])
            label.set_xalign(0)
            grid.attach(label, 0, row, 1, 1)

            hex_label = Gtk.Label(label=data['value'])
            hex_label.set_xalign(0)
            grid.attach(hex_label, 2, row, 1, 1)

            btn = ColorButton(key, data['value'], self._on_gtk2_color_changed)
            btn.hex_label = hex_label
            grid.attach(btn, 1, row, 1, 1)

            row += 1

    def _on_gtk2_color_changed(self, btn):
        rgba = btn.get_rgba()
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
        self.gtk2_colors[btn.key]['value'] = hex_color
        btn.hex_label.set_text(hex_color)

    # ── Murrine Engine ───────────────────────────────────────

    def _populate_murrine_page(self):
        self._clear_page(self.murrine_page)
        if not self.murrine_settings:
            self.murrine_page.pack_start(Gtk.Label(label="No murrine engine settings found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>Murrine Engine Settings</b>  (gtk-2.0/gtkrc default style)")
        header.set_xalign(0)
        self.murrine_page.pack_start(header, False, False, 4)

        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        grid.set_margin_top(8)
        self.murrine_page.pack_start(grid, False, False, 0)

        row = 0
        for key, data in self.murrine_settings.items():
            label = Gtk.Label(label=data['label'])
            label.set_xalign(0)
            label.set_tooltip_text(key)
            grid.attach(label, 0, row, 1, 1)

            vtype = data['type']
            if vtype == 'bool':
                widget = Gtk.Switch()
                val = data['value'].upper() in ('TRUE', '1', 'YES')
                widget.set_active(val)
                widget.key = key
                widget.connect('notify::active', self._on_murrine_bool_changed)
                grid.attach(widget, 1, row, 1, 1)
            elif vtype == 'float':
                adj = Gtk.Adjustment(
                    value=float(data['value']),
                    lower=data['min'],
                    upper=data['max'],
                    step_increment=0.05,
                    page_increment=0.1,
                )
                widget = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
                widget.set_digits(2)
                widget.set_hexpand(True)
                widget.set_size_request(200, -1)
                widget.key = key
                widget.connect('value-changed', self._on_murrine_float_changed)
                grid.attach(widget, 1, row, 2, 1)
            elif vtype == 'int':
                adj = Gtk.Adjustment(
                    value=int(data['value']),
                    lower=data['min'],
                    upper=data['max'],
                    step_increment=1,
                    page_increment=1,
                )
                widget = Gtk.SpinButton(adjustment=adj)
                widget.set_numeric(True)
                widget.key = key
                widget.connect('value-changed', self._on_murrine_int_changed)
                grid.attach(widget, 1, row, 1, 1)
            row += 1

    def _on_murrine_bool_changed(self, switch, pspec):
        val = 'TRUE' if switch.get_active() else 'FALSE'
        self.murrine_settings[switch.key]['value'] = val

    def _on_murrine_float_changed(self, scale):
        self.murrine_settings[scale.key]['value'] = f'{scale.get_value():.2f}'

    def _on_murrine_int_changed(self, spin):
        self.murrine_settings[spin.key]['value'] = str(int(spin.get_value()))

    # ── XFWM4 ───────────────────────────────────────────────

    def _populate_xfwm4_page(self):
        self._clear_page(self.xfwm4_page)
        if not self.xfwm4_settings:
            self.xfwm4_page.pack_start(Gtk.Label(label="No xfwm4 themerc found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>XFWM4 Window Manager</b>  (xfwm4/themerc)")
        header.set_xalign(0)
        self.xfwm4_page.pack_start(header, False, False, 4)

        grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        grid.set_margin_top(8)
        self.xfwm4_page.pack_start(grid, False, False, 0)

        row = 0
        for key, data in self.xfwm4_settings.items():
            label = Gtk.Label(label=data['label'])
            label.set_xalign(0)
            grid.attach(label, 0, row, 1, 1)

            vtype = data['type']
            if vtype == 'color':
                hex_label = Gtk.Label(label=data['value'])
                hex_label.set_xalign(0)
                grid.attach(hex_label, 2, row, 1, 1)

                btn = ColorButton(key, data['value'], self._on_xfwm4_color_changed)
                btn.hex_label = hex_label
                grid.attach(btn, 1, row, 1, 1)
            elif vtype == 'bool':
                widget = Gtk.Switch()
                widget.set_active(data['value'].lower() == 'true')
                widget.key = key
                widget.connect('notify::active', self._on_xfwm4_bool_changed)
                grid.attach(widget, 1, row, 1, 1)
            elif vtype == 'int':
                adj = Gtk.Adjustment(value=int(data['value']), lower=-100, upper=200, step_increment=1)
                widget = Gtk.SpinButton(adjustment=adj)
                widget.set_numeric(True)
                widget.key = key
                widget.connect('value-changed', self._on_xfwm4_int_changed)
                grid.attach(widget, 1, row, 1, 1)
            row += 1

    def _on_xfwm4_color_changed(self, btn):
        rgba = btn.get_rgba()
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
        self.xfwm4_settings[btn.key]['value'] = hex_color
        btn.hex_label.set_text(hex_color)

    def _on_xfwm4_bool_changed(self, switch, pspec):
        self.xfwm4_settings[switch.key]['value'] = 'true' if switch.get_active() else 'false'

    def _on_xfwm4_int_changed(self, spin):
        self.xfwm4_settings[spin.key]['value'] = str(int(spin.get_value()))

    # ── Metadata ─────────────────────────────────────────────

    def _populate_meta_page(self):
        self._clear_page(self.meta_page)
        if not self.index_meta:
            self.meta_page.pack_start(Gtk.Label(label="No index.theme found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>Theme Metadata</b>  (index.theme)")
        header.set_xalign(0)
        self.meta_page.pack_start(header, False, False, 4)

        grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        grid.set_margin_top(8)
        self.meta_page.pack_start(grid, False, False, 0)

        row = 0
        for key, data in self.index_meta.items():
            label = Gtk.Label(label=data['label'])
            label.set_xalign(0)
            grid.attach(label, 0, row, 1, 1)

            entry = Gtk.Entry()
            entry.set_text(data['value'])
            entry.set_hexpand(True)
            entry.set_size_request(300, -1)
            entry.key = key
            entry.connect('changed', self._on_meta_changed)
            grid.attach(entry, 1, row, 1, 1)
            row += 1

    def _on_meta_changed(self, entry):
        self.index_meta[entry.key]['value'] = entry.get_text()

    # ── Preview ──────────────────────────────────────────────

    def _populate_preview_page(self):
        self._clear_page(self.preview_page)

        header = Gtk.Label()
        header.set_markup("<b>Widget Preview</b>  (uses current system theme)")
        header.set_xalign(0)
        self.preview_page.pack_start(header, False, False, 4)

        note = Gtk.Label(label="To see your changes, save the theme and switch to it in XFCE Appearance Settings.")
        note.set_xalign(0)
        note.set_line_wrap(True)
        note.get_style_context().add_class('dim-label')
        self.preview_page.pack_start(note, False, False, 0)

        # Sample widgets
        frame1 = Gtk.Frame(label="Buttons")
        box1 = Gtk.Box(spacing=6)
        box1.set_margin_start(8)
        box1.set_margin_end(8)
        box1.set_margin_top(8)
        box1.set_margin_bottom(8)
        box1.pack_start(Gtk.Button(label="Normal"), False, False, 0)
        btn_sugg = Gtk.Button(label="Suggested")
        btn_sugg.get_style_context().add_class('suggested-action')
        box1.pack_start(btn_sugg, False, False, 0)
        btn_dest = Gtk.Button(label="Destructive")
        btn_dest.get_style_context().add_class('destructive-action')
        box1.pack_start(btn_dest, False, False, 0)
        btn_dis = Gtk.Button(label="Disabled")
        btn_dis.set_sensitive(False)
        box1.pack_start(btn_dis, False, False, 0)
        frame1.add(box1)
        self.preview_page.pack_start(frame1, False, False, 4)

        frame2 = Gtk.Frame(label="Inputs")
        box2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box2.set_margin_start(8)
        box2.set_margin_end(8)
        box2.set_margin_top(8)
        box2.set_margin_bottom(8)
        entry = Gtk.Entry()
        entry.set_text("Text entry")
        box2.pack_start(entry, False, False, 0)
        combo = Gtk.ComboBoxText()
        combo.append_text("Combo box item 1")
        combo.append_text("Combo box item 2")
        combo.set_active(0)
        box2.pack_start(combo, False, False, 0)
        spin = Gtk.SpinButton.new_with_range(0, 100, 1)
        spin.set_value(42)
        box2.pack_start(spin, False, False, 0)
        frame2.add(box2)
        self.preview_page.pack_start(frame2, False, False, 4)

        frame3 = Gtk.Frame(label="Toggles & Selection")
        box3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box3.set_margin_start(8)
        box3.set_margin_end(8)
        box3.set_margin_top(8)
        box3.set_margin_bottom(8)
        hbox = Gtk.Box(spacing=12)
        check1 = Gtk.CheckButton(label="Check 1")
        check1.set_active(True)
        hbox.pack_start(check1, False, False, 0)
        hbox.pack_start(Gtk.CheckButton(label="Check 2"), False, False, 0)
        radio1 = Gtk.RadioButton.new_with_label(None, "Radio A")
        radio2 = Gtk.RadioButton.new_with_label_from_widget(radio1, "Radio B")
        hbox.pack_start(radio1, False, False, 0)
        hbox.pack_start(radio2, False, False, 0)
        switch = Gtk.Switch()
        switch.set_active(True)
        hbox.pack_start(switch, False, False, 0)
        box3.pack_start(hbox, False, False, 0)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_value(65)
        box3.pack_start(scale, False, False, 0)

        progress = Gtk.ProgressBar()
        progress.set_fraction(0.7)
        progress.set_text("70%")
        progress.set_show_text(True)
        box3.pack_start(progress, False, False, 0)
        frame3.add(box3)
        self.preview_page.pack_start(frame3, False, False, 4)

        frame4 = Gtk.Frame(label="Text View")
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(80)
        tv = Gtk.TextView()
        buf = tv.get_buffer()
        buf.set_text("Sample text in a text view.\nThis shows the view/base colors of the theme.\nYou can type here to test the cursor color too.")
        scroll.add(tv)
        frame4.add(scroll)
        self.preview_page.pack_start(frame4, False, False, 4)

        # Color summary
        if self.gtk2_colors or self.gtk3_colors:
            frame5 = Gtk.Frame(label="Current Color Summary")
            summary_grid = Gtk.Grid(column_spacing=12, row_spacing=4)
            summary_grid.set_margin_start(8)
            summary_grid.set_margin_end(8)
            summary_grid.set_margin_top(8)
            summary_grid.set_margin_bottom(8)

            colors_to_show = self.gtk2_colors if self.gtk2_colors else self.gtk3_colors
            r = 0
            for key, data in colors_to_show.items():
                lbl = Gtk.Label(label=data['label'])
                lbl.set_xalign(0)
                summary_grid.attach(lbl, 0, r, 1, 1)

                swatch = Gtk.DrawingArea()
                swatch.set_size_request(60, 20)
                color_val = data['value']
                swatch.connect('draw', self._draw_swatch, color_val)
                summary_grid.attach(swatch, 1, r, 1, 1)

                hex_lbl = Gtk.Label(label=color_val)
                hex_lbl.set_xalign(0)
                summary_grid.attach(hex_lbl, 2, r, 1, 1)
                r += 1

            frame5.add(summary_grid)
            self.preview_page.pack_start(frame5, False, False, 4)

    def _draw_swatch(self, widget, cr, color_str):
        rgba = Gdk.RGBA()
        rgba.parse(color_str)
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1.0)
        alloc = widget.get_allocation()
        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.fill()
        # border
        cr.set_source_rgba(0.5, 0.5, 0.5, 1.0)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, alloc.width - 1, alloc.height - 1)
        cr.stroke()

    # ── Save ─────────────────────────────────────────────────

    def _on_save(self, button):
        if not self.theme_dir:
            self._show_message("No theme loaded", Gtk.MessageType.WARNING)
            return
        self._save_to_dir(self.theme_dir)

    def _on_save_as(self, button):
        if not self.theme_dir:
            self._show_message("No theme loaded", Gtk.MessageType.WARNING)
            return

        dialog = Gtk.FileChooserDialog(
            title="Save Theme As (select destination directory)",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )

        # Suggest saving into ~/.themes
        themes_dir = os.path.expanduser('~/.themes')
        if os.path.isdir(themes_dir):
            dialog.set_current_folder(themes_dir)

        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            dest = dialog.get_filename()
            # If the selected dir doesn't look like a theme, ask for a name
            if not os.path.exists(os.path.join(dest, 'gtk-3.0')) and not os.path.exists(os.path.join(dest, 'gtk-2.0')):
                name_dialog = Gtk.Dialog(
                    title="Theme Name",
                    parent=self,
                    flags=Gtk.DialogFlags.MODAL,
                )
                name_dialog.add_buttons(
                    Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OK, Gtk.ResponseType.OK,
                )
                box = name_dialog.get_content_area()
                box.set_spacing(8)
                box.set_margin_start(12)
                box.set_margin_end(12)
                box.set_margin_top(12)
                lbl = Gtk.Label(label="Enter new theme name:")
                box.pack_start(lbl, False, False, 0)
                name_entry = Gtk.Entry()
                name_entry.set_text(os.path.basename(self.theme_dir) + "-custom")
                box.pack_start(name_entry, False, False, 0)
                name_dialog.show_all()
                name_resp = name_dialog.run()
                new_name = name_entry.get_text().strip()
                name_dialog.destroy()

                if name_resp != Gtk.ResponseType.OK or not new_name:
                    dialog.destroy()
                    return

                dest = os.path.join(dest, new_name)
                # Copy original theme as base
                if not os.path.exists(dest):
                    shutil.copytree(self.theme_dir, dest)

            self._save_to_dir(dest)
            self.theme_dir = dest
            self.theme_label.set_text(f"Theme: {os.path.basename(dest)}  ({dest})")

        dialog.destroy()

    def _save_to_dir(self, dest_dir):
        try:
            # GTK3 CSS
            if self.gtk3_css_text and self.gtk3_colors:
                css = self.gtk3_css_text
                for key, orig_val in self.gtk3_colors_orig.items():
                    new_val = self.gtk3_colors[key]['value']
                    css = ThemeWriter.update_gtk3_css_color(css, orig_val, new_val)
                self._write_file(os.path.join(dest_dir, 'gtk-3.0', 'gtk.css'), css)

                # Also update gtk-dark.css if it exists
                if self.gtk3_dark_css_text:
                    dark_css = self.gtk3_dark_css_text
                    for key, orig_val in self.gtk3_colors_orig.items():
                        new_val = self.gtk3_colors[key]['value']
                        dark_css = ThemeWriter.update_gtk3_css_color(dark_css, orig_val, new_val)
                    self._write_file(os.path.join(dest_dir, 'gtk-3.0', 'gtk-dark.css'), dark_css)

            # GTK2 gtkrc
            if self.gtk2_gtkrc_text:
                gtkrc = self.gtk2_gtkrc_text
                if self.gtk2_colors:
                    gtkrc = ThemeWriter.update_gtk2_color_scheme(gtkrc, self.gtk2_colors)
                if self.murrine_settings:
                    gtkrc = ThemeWriter.update_murrine_default(gtkrc, self.murrine_settings)
                self._write_file(os.path.join(dest_dir, 'gtk-2.0', 'gtkrc'), gtkrc)

            # xfwm4
            if self.xfwm4_text and self.xfwm4_settings:
                xfwm4 = ThemeWriter.update_xfwm4_themerc(self.xfwm4_text, self.xfwm4_settings)
                self._write_file(os.path.join(dest_dir, 'xfwm4', 'themerc'), xfwm4)

            # index.theme
            if self.index_text and self.index_meta:
                index = ThemeWriter.update_index_theme(self.index_text, self.index_meta)
                self._write_file(os.path.join(dest_dir, 'index.theme'), index)

            # Update originals so subsequent saves work correctly
            self.gtk3_colors_orig = {k: v['value'] for k, v in self.gtk3_colors.items()}
            # Re-read the saved files as the new base
            self.gtk3_css_text = self._read_file(os.path.join(dest_dir, 'gtk-3.0', 'gtk.css'))
            self.gtk3_dark_css_text = self._read_file(os.path.join(dest_dir, 'gtk-3.0', 'gtk-dark.css'))
            self.gtk2_gtkrc_text = self._read_file(os.path.join(dest_dir, 'gtk-2.0', 'gtkrc'))
            self.xfwm4_text = self._read_file(os.path.join(dest_dir, 'xfwm4', 'themerc'))
            self.index_text = self._read_file(os.path.join(dest_dir, 'index.theme'))

            self._show_message(f"Theme saved to:\n{dest_dir}", Gtk.MessageType.INFO)

        except Exception as e:
            self._show_message(f"Error saving theme:\n{e}", Gtk.MessageType.ERROR)

    def _write_file(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)

    def _show_message(self, text, msg_type):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=msg_type,
            buttons=Gtk.ButtonsType.OK,
            text=text,
        )
        dialog.run()
        dialog.destroy()


def main():
    win = ThemeEditorWindow()
    win.connect('destroy', Gtk.main_quit)
    win.show_all()

    # Auto-load theme if passed as argument
    import sys
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        win._load_theme(sys.argv[1])

    Gtk.main()


if __name__ == '__main__':
    main()
