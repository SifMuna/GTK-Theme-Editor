#!/usr/bin/env python3
"""GTK3 Theme Editor - A GUI tool for configuring GTK themes on XFCE.

Features:
  - Live preview panel that updates in real time as you change colors
  - Hover highlighting: mouse over a color row to see which preview element it affects
  - Edit GTK3 CSS, GTK2 gtkrc, murrine engine, xfwm4, and theme metadata
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, Pango, GLib
import os
import re
import shutil
import sys


# ═══════════════════════════════════════════════════════════════
#  Parsers
# ═══════════════════════════════════════════════════════════════

class ThemeParser:
    """Parse GTK theme files."""

    @staticmethod
    def _extract_css_props(block_text):
        """Extract property: value pairs from a CSS declaration block."""
        props = {}
        for decl in block_text.split(';'):
            decl = decl.strip()
            if ':' not in decl:
                continue
            prop, _, val = decl.partition(':')
            props[prop.strip()] = val.strip()
        return props

    @staticmethod
    def parse_gtk3_css_colors(css_text):
        """Extract color values from GTK3 CSS."""
        colors = {}
        hex_re = r'#[0-9a-fA-F]{3,8}'

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

        def named_to_hex(val):
            rgba = Gdk.RGBA()
            if rgba.parse(val):
                return '#{:02x}{:02x}{:02x}'.format(
                    int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
            return None

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
            val = blocks['view'].get('color', '').strip()
            if val:
                h = named_to_hex(val)
                if h:
                    colors['text_color'] = {'value': h, 'label': 'View/Input Text'}

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
        m = re.search(r'style\s+"default"\s*\{.*?engine\s+"murrine"\s*\{', gtkrc_text, re.DOTALL)
        if not m:
            return settings

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
            m2 = re.search(pattern, block, re.IGNORECASE)
            if m2:
                settings[key] = {
                    'value': m2.group(1).strip(),
                    'label': label, 'type': vtype,
                    'min': vmin, 'max': vmax,
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
            key, val = key.strip(), val.strip()
            if key in setting_defs:
                label, vtype = setting_defs[key]
                settings[key] = {'value': val, 'label': label, 'type': vtype}
        return settings

    @staticmethod
    def parse_index_theme(text):
        """Parse index.theme metadata."""
        meta = {}
        fields = {
            'Name': 'Theme Name', 'Comment': 'Comment',
            'GtkTheme': 'GTK Theme', 'MetacityTheme': 'Metacity Theme',
            'IconTheme': 'Icon Theme', 'CursorTheme': 'Cursor Theme',
            'ButtonLayout': 'Button Layout',
        }
        for line in text.splitlines():
            line = line.strip()
            if '=' not in line or line.startswith('['):
                continue
            key, val = line.split('=', 1)
            key, val = key.strip(), val.strip()
            if key in fields:
                meta[key] = {'value': val, 'label': fields[key]}
        return meta


# ═══════════════════════════════════════════════════════════════
#  Writers
# ═══════════════════════════════════════════════════════════════

class ThemeWriter:
    """Write modified values back to theme files."""

    @staticmethod
    def update_gtk2_color_scheme(gtkrc_text, colors):
        for name, data in colors.items():
            pattern = rf'({name}\s*:\s*)#[0-9a-fA-F]+'
            gtkrc_text = re.sub(pattern, rf'\g<1>{data["value"]}', gtkrc_text)
        return gtkrc_text

    @staticmethod
    def update_murrine_default(gtkrc_text, settings):
        for key, data in settings.items():
            pattern = rf'({key}\s*=\s*)[^\s#]+'
            gtkrc_text = re.sub(pattern, rf'\g<1>{data["value"]}', gtkrc_text, count=1)
        return gtkrc_text

    @staticmethod
    def update_gtk3_css_color(css_text, old_color, new_color):
        if old_color and new_color and old_color != new_color:
            css_text = css_text.replace(old_color, new_color)
        return css_text

    @staticmethod
    def update_xfwm4_themerc(text, settings):
        for key, data in settings.items():
            pattern = rf'^({key}\s*=\s*).*$'
            text = re.sub(pattern, rf'\g<1>{data["value"]}', text, flags=re.MULTILINE)
        return text

    @staticmethod
    def update_index_theme(text, meta):
        for key, data in meta.items():
            pattern = rf'^({key}\s*=\s*).*$'
            text = re.sub(pattern, rf'\g<1>{data["value"]}', text, flags=re.MULTILINE)
        return text


# ═══════════════════════════════════════════════════════════════
#  Color-to-Preview Mapping
# ═══════════════════════════════════════════════════════════════

# Maps color keys → list of preview CSS class names that the color affects.
# Used both for live CSS generation and hover highlighting.
COLOR_PREVIEW_MAP = {
    # GTK3 color keys
    'bg_color':         ['preview-window'],
    'fg_color':         ['preview-label-normal'],
    'base_color':       ['preview-entry', 'preview-textview'],
    'text_color':       ['preview-entry', 'preview-textview'],
    'selected_bg_color': ['preview-selection'],
    'selected_fg_color': ['preview-selection'],
    'link_color':       ['preview-link'],
    'entry_border':     ['preview-entry'],
    'entry_bg':         ['preview-entry'],
    'focus_color':      ['preview-entry-focus'],
    'error_color':      ['preview-error'],
    'warning_color':    ['preview-warning'],
    'success_color':    ['preview-success'],
    'osd_bg':           ['preview-osd'],
    'osd_fg':           ['preview-osd'],
    'tooltip_border':   ['preview-tooltip'],
    'backdrop_fg':      ['preview-label-backdrop'],
    'disabled_fg':      ['preview-disabled'],
    'disabled_bg':      ['preview-disabled'],
    # GTK2 color keys (overlap with GTK3 names where applicable)
    'tooltip_bg_color': ['preview-tooltip'],
    'tooltip_fg_color': ['preview-tooltip'],
    'panel_bg':         ['preview-headerbar'],
    'fm_color':         ['preview-textview'],
    'bg_color_dark':    ['preview-headerbar'],
    'text_color_dark':  ['preview-headerbar'],
}


# ═══════════════════════════════════════════════════════════════
#  Custom Widgets
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════════

class ThemeEditorWindow(Gtk.Window):
    """Main application window with side-by-side editor + live preview."""

    def __init__(self):
        super().__init__(title="GTK3 Theme Editor")
        self.set_default_size(1200, 750)
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

        # Preview CSS provider (scoped to the preview area)
        self.preview_css_provider = Gtk.CssProvider()
        # Highlight CSS provider for hover effects
        self.highlight_css_provider = Gtk.CssProvider()

        # Track which preview widgets exist, keyed by CSS class name
        self.preview_widgets = {}

        self._build_ui()

    # ── Layout ────────────────────────────────────────────────

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

        # Horizontal paned: editor on left, preview on right
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.pack_start(self.paned, True, True, 0)

        # Left: Notebook with editor tabs
        self.notebook = Gtk.Notebook()
        self.notebook.set_size_request(550, -1)
        self.paned.pack1(self.notebook, resize=True, shrink=False)

        self.gtk3_page = self._make_scrolled_page("GTK3 Colors")
        self.gtk2_page = self._make_scrolled_page("GTK2 Colors")
        self.murrine_page = self._make_scrolled_page("Murrine Engine")
        self.xfwm4_page = self._make_scrolled_page("XFWM4")
        self.meta_page = self._make_scrolled_page("Metadata")

        # Right: Live preview
        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        preview_scroll.set_size_request(400, -1)
        self.preview_viewport = Gtk.Viewport()
        self.preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.preview_box.set_margin_start(10)
        self.preview_box.set_margin_end(10)
        self.preview_box.set_margin_top(10)
        self.preview_box.set_margin_bottom(10)
        self.preview_viewport.add(self.preview_box)
        preview_scroll.add(self.preview_viewport)
        self.paned.pack2(preview_scroll, resize=True, shrink=False)
        self.paned.set_position(580)

        # Add the CSS providers to the preview viewport's screen
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(
            screen, self.highlight_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

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

    # ── Theme Loading ─────────────────────────────────────────

    def _on_open(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select Theme Directory", parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
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

        self.gtk3_css_text = self._read_file(os.path.join(theme_dir, 'gtk-3.0', 'gtk.css'))
        self.gtk3_dark_css_text = self._read_file(os.path.join(theme_dir, 'gtk-3.0', 'gtk-dark.css'))
        self.gtk2_gtkrc_text = self._read_file(os.path.join(theme_dir, 'gtk-2.0', 'gtkrc'))
        self.xfwm4_text = self._read_file(os.path.join(theme_dir, 'xfwm4', 'themerc'))
        self.index_text = self._read_file(os.path.join(theme_dir, 'index.theme'))

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

        self._populate_gtk3_page()
        self._populate_gtk2_page()
        self._populate_murrine_page()
        self._populate_xfwm4_page()
        self._populate_meta_page()
        self._build_preview()
        self._refresh_preview_css()

        self.show_all()

    def _read_file(self, path):
        if os.path.isfile(path):
            with open(path, 'r', errors='replace') as f:
                return f.read()
        return None

    # ── Resolve active colors (GTK3 primary, GTK2 fallback) ──

    def _get_color(self, key, fallback='#888888'):
        """Get a color value from GTK3 colors first, then GTK2."""
        if key in self.gtk3_colors:
            return self.gtk3_colors[key]['value']
        if key in self.gtk2_colors:
            return self.gtk2_colors[key]['value']
        return fallback

    # ── Live Preview ──────────────────────────────────────────

    def _build_preview(self):
        """Build the preview widget tree. Called once on theme load."""
        self._clear_page(self.preview_box)
        self.preview_widgets = {}

        header = Gtk.Label()
        header.set_markup("<b>Live Preview</b>")
        header.set_xalign(0)
        self.preview_box.pack_start(header, False, False, 0)

        # ── Window area (bg_color + fg_color)
        window_frame = Gtk.Frame()
        window_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        window_box.set_margin_start(12)
        window_box.set_margin_end(12)
        window_box.set_margin_top(12)
        window_box.set_margin_bottom(12)
        self._tag(window_box, 'preview-window')
        window_frame.add(window_box)
        self.preview_box.pack_start(window_frame, False, False, 4)

        # Headerbar simulation (panel_bg / bg_color_dark)
        headerbar = Gtk.Box(spacing=8)
        headerbar.set_margin_start(4)
        headerbar.set_margin_end(4)
        headerbar.set_margin_top(4)
        headerbar.set_margin_bottom(4)
        self._tag(headerbar, 'preview-headerbar')
        hb_label = Gtk.Label(label="Window Title Bar")
        headerbar.pack_start(hb_label, True, True, 0)
        window_box.pack_start(headerbar, False, False, 0)

        # Normal label (fg_color)
        lbl_normal = Gtk.Label(label="Normal text (fg_color)")
        lbl_normal.set_xalign(0)
        self._tag(lbl_normal, 'preview-label-normal')
        window_box.pack_start(lbl_normal, False, False, 0)

        # Backdrop label
        lbl_backdrop = Gtk.Label(label="Backdrop / unfocused text")
        lbl_backdrop.set_xalign(0)
        self._tag(lbl_backdrop, 'preview-label-backdrop')
        window_box.pack_start(lbl_backdrop, False, False, 0)

        # Link label
        lbl_link = Gtk.Label()
        lbl_link.set_markup("<u>Accent / link color</u>")
        lbl_link.set_xalign(0)
        self._tag(lbl_link, 'preview-link')
        window_box.pack_start(lbl_link, False, False, 0)

        # Entry (base_color, text_color, entry_border, entry_bg)
        entry = Gtk.Entry()
        entry.set_text("Text entry (base_color + text_color)")
        entry.set_editable(False)
        self._tag(entry, 'preview-entry')
        window_box.pack_start(entry, False, False, 0)

        # Focused entry
        entry_focus = Gtk.Entry()
        entry_focus.set_text("Focused entry (focus_color border)")
        entry_focus.set_editable(False)
        self._tag(entry_focus, 'preview-entry-focus')
        window_box.pack_start(entry_focus, False, False, 0)

        # TextView (base_color, text_color)
        tv_frame = Gtk.Frame()
        tv_scroll = Gtk.ScrolledWindow()
        tv_scroll.set_min_content_height(50)
        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.get_buffer().set_text("Text view content area\n(base_color background, text_color foreground)")
        self._tag(tv, 'preview-textview')
        tv_scroll.add(tv)
        tv_frame.add(tv_scroll)
        window_box.pack_start(tv_frame, False, False, 0)

        # Selection
        sel_box = Gtk.Box(spacing=4)
        sel_label = Gtk.Label(label="  Selected item  ")
        self._tag(sel_label, 'preview-selection')
        sel_box.pack_start(sel_label, False, False, 0)
        window_box.pack_start(sel_box, False, False, 0)

        # Buttons row
        btn_box = Gtk.Box(spacing=6)
        btn_normal = Gtk.Button(label="Normal")
        btn_box.pack_start(btn_normal, False, False, 0)
        btn_suggested = Gtk.Button(label="Suggested")
        btn_suggested.get_style_context().add_class('suggested-action')
        btn_box.pack_start(btn_suggested, False, False, 0)
        btn_destructive = Gtk.Button(label="Destructive")
        btn_destructive.get_style_context().add_class('destructive-action')
        btn_box.pack_start(btn_destructive, False, False, 0)
        window_box.pack_start(btn_box, False, False, 0)

        # Disabled
        dis_box = Gtk.Box(spacing=8)
        dis_btn = Gtk.Button(label="Disabled button")
        dis_btn.set_sensitive(False)
        self._tag(dis_btn, 'preview-disabled')
        dis_box.pack_start(dis_btn, False, False, 0)
        dis_entry = Gtk.Entry()
        dis_entry.set_text("Disabled entry")
        dis_entry.set_sensitive(False)
        dis_box.pack_start(dis_entry, True, True, 0)
        window_box.pack_start(dis_box, False, False, 0)

        # Status labels (error, warning, success)
        status_box = Gtk.Box(spacing=8)
        err_lbl = Gtk.Label(label=" Error ")
        self._tag(err_lbl, 'preview-error')
        status_box.pack_start(err_lbl, False, False, 0)
        warn_lbl = Gtk.Label(label=" Warning ")
        self._tag(warn_lbl, 'preview-warning')
        status_box.pack_start(warn_lbl, False, False, 0)
        ok_lbl = Gtk.Label(label=" Success ")
        self._tag(ok_lbl, 'preview-success')
        status_box.pack_start(ok_lbl, False, False, 0)
        window_box.pack_start(status_box, False, False, 0)

        # Toggles
        toggle_box = Gtk.Box(spacing=12)
        chk = Gtk.CheckButton(label="Check")
        chk.set_active(True)
        toggle_box.pack_start(chk, False, False, 0)
        r1 = Gtk.RadioButton.new_with_label(None, "Radio A")
        r2 = Gtk.RadioButton.new_with_label_from_widget(r1, "Radio B")
        toggle_box.pack_start(r1, False, False, 0)
        toggle_box.pack_start(r2, False, False, 0)
        sw = Gtk.Switch()
        sw.set_active(True)
        toggle_box.pack_start(sw, False, False, 0)
        window_box.pack_start(toggle_box, False, False, 0)

        # Scale + Progress
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_value(65)
        window_box.pack_start(scale, False, False, 0)

        progress = Gtk.ProgressBar()
        progress.set_fraction(0.7)
        progress.set_text("70%")
        progress.set_show_text(True)
        window_box.pack_start(progress, False, False, 0)

        # OSD
        osd_box = Gtk.Box(spacing=6)
        osd_box.set_margin_top(4)
        osd_label = Gtk.Label(label="  OSD overlay area  ")
        self._tag(osd_label, 'preview-osd')
        osd_box.pack_start(osd_label, False, False, 0)
        window_box.pack_start(osd_box, False, False, 0)

        # Tooltip
        tooltip_box = Gtk.Box()
        tooltip_label = Gtk.Label(label="  Tooltip area  ")
        self._tag(tooltip_label, 'preview-tooltip')
        tooltip_box.pack_start(tooltip_label, False, False, 0)
        window_box.pack_start(tooltip_box, False, False, 0)

    def _tag(self, widget, css_class):
        """Add a CSS class to a widget and register it for highlight tracking."""
        widget.get_style_context().add_class(css_class)
        if css_class not in self.preview_widgets:
            self.preview_widgets[css_class] = []
        self.preview_widgets[css_class].append(widget)

    def _refresh_preview_css(self):
        """Regenerate and apply the preview CSS from current color values."""
        c = self._get_color  # shorthand

        css = f"""
        .preview-window {{
            background-color: {c('bg_color', '#3b3e3f')};
            border-radius: 6px;
            padding: 8px;
        }}
        .preview-headerbar {{
            background-color: {c('bg_color_dark', c('panel_bg', '#686868'))};
            color: {c('text_color_dark', '#ffffff')};
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
        }}
        .preview-headerbar label {{
            color: {c('text_color_dark', '#ffffff')};
        }}
        .preview-label-normal {{
            color: {c('fg_color', '#eeeeec')};
        }}
        .preview-label-backdrop {{
            color: {c('backdrop_fg', '#959696')};
        }}
        .preview-link {{
            color: {c('link_color', '#145ba6')};
        }}
        .preview-entry {{
            background-color: {c('entry_bg', c('base_color', '#2d2e30'))};
            color: {c('text_color', '#ffffff')};
            border: 2px solid {c('entry_border', '#1d1f1f')};
            border-radius: 3px;
            padding: 4px 6px;
        }}
        .preview-entry-focus {{
            background-color: {c('entry_bg', c('base_color', '#2d2e30'))};
            color: {c('text_color', '#ffffff')};
            border: 2px solid {c('focus_color', '#145ba6')};
            border-radius: 3px;
            padding: 4px 6px;
        }}
        .preview-textview {{
            background-color: {c('base_color', '#2d2e30')};
            color: {c('text_color', '#ffffff')};
        }}
        .preview-textview text {{
            background-color: {c('base_color', '#2d2e30')};
            color: {c('text_color', '#ffffff')};
        }}
        .preview-selection {{
            background-color: {c('selected_bg_color', '#145ba6')};
            color: {c('selected_fg_color', '#ffffff')};
            padding: 4px 12px;
            border-radius: 3px;
        }}
        .preview-error {{
            background-color: {c('error_color', '#cc0000')};
            color: #ffffff;
            padding: 3px 10px;
            border-radius: 3px;
        }}
        .preview-warning {{
            background-color: {c('warning_color', '#f57900')};
            color: #ffffff;
            padding: 3px 10px;
            border-radius: 3px;
        }}
        .preview-success {{
            background-color: {c('success_color', '#4e9a06')};
            color: #ffffff;
            padding: 3px 10px;
            border-radius: 3px;
        }}
        .preview-osd {{
            background-color: {c('osd_bg', '#222222')};
            color: {c('osd_fg', '#eeeeee')};
            padding: 6px 14px;
            border-radius: 4px;
        }}
        .preview-tooltip {{
            background-color: {c('tooltip_bg_color', c('tooltip_border', '#000000'))};
            color: {c('tooltip_fg_color', '#E1E1E1')};
            padding: 4px 12px;
            border-radius: 4px;
        }}
        .preview-disabled {{
            opacity: 0.5;
        }}

        /* Highlight ring shown on hover */
        .preview-highlight {{
            box-shadow: inset 0 0 0 3px alpha(#ff4444, 0.9);
            transition: box-shadow 150ms ease-in;
        }}
        """

        try:
            self.preview_css_provider.load_from_data(css.encode())
        except GLib.Error:
            pass

        # Ensure provider is attached to the screen
        screen = Gdk.Screen.get_default()
        # Remove and re-add to ensure fresh
        try:
            Gtk.StyleContext.remove_provider_for_screen(screen, self.preview_css_provider)
        except Exception:
            pass
        Gtk.StyleContext.add_provider_for_screen(
            screen, self.preview_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # ── Hover Highlighting ────────────────────────────────────

    def _on_color_row_enter(self, eventbox, event, color_key):
        """When mouse enters a color row, highlight corresponding preview widgets."""
        css_classes = COLOR_PREVIEW_MAP.get(color_key, [])
        for cls in css_classes:
            for widget in self.preview_widgets.get(cls, []):
                widget.get_style_context().add_class('preview-highlight')

    def _on_color_row_leave(self, eventbox, event, color_key):
        """When mouse leaves a color row, remove highlight from preview widgets."""
        css_classes = COLOR_PREVIEW_MAP.get(color_key, [])
        for cls in css_classes:
            for widget in self.preview_widgets.get(cls, []):
                widget.get_style_context().remove_class('preview-highlight')

    def _make_color_row(self, grid, row, key, data, on_changed):
        """Create a color editor row with label, button, hex display, and hover events."""
        # Wrap in EventBox for enter/leave events
        ebox = Gtk.EventBox()
        ebox.set_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        ebox.connect('enter-notify-event', self._on_color_row_enter, key)
        ebox.connect('leave-notify-event', self._on_color_row_leave, key)

        inner = Gtk.Box(spacing=12)
        inner.set_margin_top(2)
        inner.set_margin_bottom(2)

        label = Gtk.Label(label=data['label'])
        label.set_xalign(0)
        label.set_size_request(180, -1)
        inner.pack_start(label, False, False, 0)

        btn = ColorButton(key, data['value'], on_changed)
        inner.pack_start(btn, False, False, 0)

        hex_label = Gtk.Label(label=data['value'])
        hex_label.set_xalign(0)
        hex_label.set_selectable(True)
        btn.hex_label = hex_label
        inner.pack_start(hex_label, False, False, 0)

        # Small preview swatch
        swatch = Gtk.DrawingArea()
        swatch.set_size_request(40, 20)
        swatch.color_key = key
        swatch.connect('draw', self._draw_row_swatch, key)
        btn.swatch = swatch
        inner.pack_end(swatch, False, False, 0)

        ebox.add(inner)
        grid.attach(ebox, 0, row, 3, 1)
        return btn

    def _draw_row_swatch(self, widget, cr, color_key):
        """Draw a small color swatch next to the color row."""
        val = self._get_color(color_key, '#888888')
        rgba = Gdk.RGBA()
        rgba.parse(val)
        alloc = widget.get_allocation()
        # Checkerboard for visibility
        cr.set_source_rgba(0.4, 0.4, 0.4, 1.0)
        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.fill()
        # Color fill
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1.0)
        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.fill()
        # Border
        cr.set_source_rgba(0.6, 0.6, 0.6, 1.0)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, alloc.width - 1, alloc.height - 1)
        cr.stroke()

    # ── GTK3 Colors Page ──────────────────────────────────────

    def _populate_gtk3_page(self):
        self._clear_page(self.gtk3_page)
        if not self.gtk3_colors:
            self.gtk3_page.pack_start(Gtk.Label(label="No GTK3 CSS found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>GTK3 CSS Colors</b>  <small>(gtk-3.0/gtk.css)</small>")
        header.set_xalign(0)
        self.gtk3_page.pack_start(header, False, False, 4)

        note = Gtk.Label(label="Hover a color to highlight its effect in the preview.")
        note.set_xalign(0)
        note.get_style_context().add_class('dim-label')
        self.gtk3_page.pack_start(note, False, False, 0)

        grid = Gtk.Grid(row_spacing=2)
        grid.set_margin_top(8)
        self.gtk3_page.pack_start(grid, False, False, 0)

        row = 0
        for key, data in self.gtk3_colors.items():
            self._make_color_row(grid, row, key, data, self._on_gtk3_color_changed)
            row += 1

    def _on_gtk3_color_changed(self, btn):
        rgba = btn.get_rgba()
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
        self.gtk3_colors[btn.key]['value'] = hex_color
        btn.hex_label.set_text(hex_color)
        btn.swatch.queue_draw()
        self._refresh_preview_css()

    # ── GTK2 Colors Page ──────────────────────────────────────

    def _populate_gtk2_page(self):
        self._clear_page(self.gtk2_page)
        if not self.gtk2_colors:
            self.gtk2_page.pack_start(Gtk.Label(label="No GTK2 gtkrc found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>GTK2 Color Scheme</b>  <small>(gtk-2.0/gtkrc)</small>")
        header.set_xalign(0)
        self.gtk2_page.pack_start(header, False, False, 4)

        note = Gtk.Label(label="Hover a color to highlight its effect in the preview.")
        note.set_xalign(0)
        note.get_style_context().add_class('dim-label')
        self.gtk2_page.pack_start(note, False, False, 0)

        grid = Gtk.Grid(row_spacing=2)
        grid.set_margin_top(8)
        self.gtk2_page.pack_start(grid, False, False, 0)

        row = 0
        for key, data in self.gtk2_colors.items():
            self._make_color_row(grid, row, key, data, self._on_gtk2_color_changed)
            row += 1

    def _on_gtk2_color_changed(self, btn):
        rgba = btn.get_rgba()
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
        self.gtk2_colors[btn.key]['value'] = hex_color
        btn.hex_label.set_text(hex_color)
        btn.swatch.queue_draw()
        self._refresh_preview_css()

    # ── Murrine Engine Page ───────────────────────────────────

    def _populate_murrine_page(self):
        self._clear_page(self.murrine_page)
        if not self.murrine_settings:
            self.murrine_page.pack_start(Gtk.Label(label="No murrine settings found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>Murrine Engine Settings</b>  <small>(gtk-2.0/gtkrc)</small>")
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
                widget.set_active(data['value'].upper() in ('TRUE', '1', 'YES'))
                widget.key = key
                widget.connect('notify::active', self._on_murrine_bool_changed)
                grid.attach(widget, 1, row, 1, 1)
            elif vtype == 'float':
                adj = Gtk.Adjustment(
                    value=float(data['value']), lower=data['min'],
                    upper=data['max'], step_increment=0.05, page_increment=0.1)
                widget = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
                widget.set_digits(2)
                widget.set_hexpand(True)
                widget.set_size_request(200, -1)
                widget.key = key
                widget.connect('value-changed', self._on_murrine_float_changed)
                grid.attach(widget, 1, row, 2, 1)
            elif vtype == 'int':
                adj = Gtk.Adjustment(
                    value=int(data['value']), lower=data['min'],
                    upper=data['max'], step_increment=1, page_increment=1)
                widget = Gtk.SpinButton(adjustment=adj)
                widget.set_numeric(True)
                widget.key = key
                widget.connect('value-changed', self._on_murrine_int_changed)
                grid.attach(widget, 1, row, 1, 1)
            row += 1

    def _on_murrine_bool_changed(self, switch, pspec):
        self.murrine_settings[switch.key]['value'] = 'TRUE' if switch.get_active() else 'FALSE'

    def _on_murrine_float_changed(self, scale):
        self.murrine_settings[scale.key]['value'] = f'{scale.get_value():.2f}'

    def _on_murrine_int_changed(self, spin):
        self.murrine_settings[spin.key]['value'] = str(int(spin.get_value()))

    # ── XFWM4 Page ───────────────────────────────────────────

    def _populate_xfwm4_page(self):
        self._clear_page(self.xfwm4_page)
        if not self.xfwm4_settings:
            self.xfwm4_page.pack_start(Gtk.Label(label="No xfwm4 themerc found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>XFWM4 Window Manager</b>  <small>(xfwm4/themerc)</small>")
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

    # ── Metadata Page ─────────────────────────────────────────

    def _populate_meta_page(self):
        self._clear_page(self.meta_page)
        if not self.index_meta:
            self.meta_page.pack_start(Gtk.Label(label="No index.theme found"), False, False, 0)
            return

        header = Gtk.Label()
        header.set_markup("<b>Theme Metadata</b>  <small>(index.theme)</small>")
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

    # ── Save ──────────────────────────────────────────────────

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
            title="Save Theme As", parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        themes_dir = os.path.expanduser('~/.themes')
        if os.path.isdir(themes_dir):
            dialog.set_current_folder(themes_dir)

        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            dest = dialog.get_filename()
            if not os.path.exists(os.path.join(dest, 'gtk-3.0')) and \
               not os.path.exists(os.path.join(dest, 'gtk-2.0')):
                name_dialog = Gtk.Dialog(
                    title="Theme Name", parent=self, flags=Gtk.DialogFlags.MODAL)
                name_dialog.add_buttons(
                    Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OK, Gtk.ResponseType.OK)
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
                if not os.path.exists(dest):
                    shutil.copytree(self.theme_dir, dest)

            self._save_to_dir(dest)
            self.theme_dir = dest
            self.theme_label.set_text(f"Theme: {os.path.basename(dest)}  ({dest})")
        dialog.destroy()

    def _save_to_dir(self, dest_dir):
        try:
            if self.gtk3_css_text and self.gtk3_colors:
                css = self.gtk3_css_text
                for key, orig_val in self.gtk3_colors_orig.items():
                    new_val = self.gtk3_colors[key]['value']
                    css = ThemeWriter.update_gtk3_css_color(css, orig_val, new_val)
                self._write_file(os.path.join(dest_dir, 'gtk-3.0', 'gtk.css'), css)
                if self.gtk3_dark_css_text:
                    dark_css = self.gtk3_dark_css_text
                    for key, orig_val in self.gtk3_colors_orig.items():
                        new_val = self.gtk3_colors[key]['value']
                        dark_css = ThemeWriter.update_gtk3_css_color(dark_css, orig_val, new_val)
                    self._write_file(os.path.join(dest_dir, 'gtk-3.0', 'gtk-dark.css'), dark_css)

            if self.gtk2_gtkrc_text:
                gtkrc = self.gtk2_gtkrc_text
                if self.gtk2_colors:
                    gtkrc = ThemeWriter.update_gtk2_color_scheme(gtkrc, self.gtk2_colors)
                if self.murrine_settings:
                    gtkrc = ThemeWriter.update_murrine_default(gtkrc, self.murrine_settings)
                self._write_file(os.path.join(dest_dir, 'gtk-2.0', 'gtkrc'), gtkrc)

            if self.xfwm4_text and self.xfwm4_settings:
                xfwm4 = ThemeWriter.update_xfwm4_themerc(self.xfwm4_text, self.xfwm4_settings)
                self._write_file(os.path.join(dest_dir, 'xfwm4', 'themerc'), xfwm4)

            if self.index_text and self.index_meta:
                index = ThemeWriter.update_index_theme(self.index_text, self.index_meta)
                self._write_file(os.path.join(dest_dir, 'index.theme'), index)

            self.gtk3_colors_orig = {k: v['value'] for k, v in self.gtk3_colors.items()}
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
            parent=self, flags=Gtk.DialogFlags.MODAL,
            message_type=msg_type, buttons=Gtk.ButtonsType.OK, text=text)
        dialog.run()
        dialog.destroy()


def main():
    win = ThemeEditorWindow()
    win.connect('destroy', Gtk.main_quit)
    win.show_all()

    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        win._load_theme(sys.argv[1])

    Gtk.main()


if __name__ == '__main__':
    main()
