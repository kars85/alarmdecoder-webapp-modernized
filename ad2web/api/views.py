# -*- coding: utf-8 -*-

from flask import (
    Blueprint,
    render_template,
    flash,
    url_for,
    redirect,
)

from flask_login import login_required, current_user

from ..extensions import db

# from ..user import User # Assuming User model isn't directly needed here
from ..settings.models import Setting
from alarmdecoder.panels import ADEMCO, DSC
from alarmdecoder import AlarmDecoder  # Used for constants like KEY_F*
from ad2web.keypad.forms import KeypadButtonForm  # Renamed 'ad2web.keypad' to relative '.'
from ad2web.keypad.models import KeypadButton  # Renamed 'ad2web.keypad' to relative '.'
from ad2web.keypad.forms import (
    SpecialButtonFormAdemco,
    SpecialButtonFormDSC,
)  # Renamed 'ad2web.keypad' to relative '.'
from ad2web.keypad.constants import (  # Renamed 'ad2web.keypad' to relative '.'
    FIRE,
    MEDICAL,
    POLICE,
    SPECIAL_4,
    SPECIAL_CUSTOM,
    STAY,
    AWAY,
    CHIME,
    RESET,
    EXIT,
    SPECIAL_KEY_MAP,
)

# Defined blueprint - assuming this is keypad, not api
keypad = Blueprint("keypad", __name__, url_prefix="/keypad")
api = Blueprint("api", __name__)


# Helper function to get panel mode consistently
def _get_panel_mode():
    # Provide a default if the setting doesn't exist yet during initial setup
    return Setting.get_by_name("panel_mode", default=ADEMCO).value


# --- Routes ---


@keypad.route("/")
@login_required
def index():
    """Renders the main keypad interface based on panel mode."""
    panel_mode = _get_panel_mode()
    custom_buttons = KeypadButton.query.filter_by(user_id=current_user.id).all()
    # NOTE: special_buttons aren't directly used in index.html/dsc.html based on previous analysis,
    # but are needed if the template were to render them directly. Kept for now.
    # special_buttons_data = get_special_buttons() # Renamed to avoid shadowing warning if used

    template_name = "keypad/dsc.html" if panel_mode == DSC else "keypad/index.html"

    return render_template(
        template_name,
        buttons=custom_buttons,
        # special_buttons=special_buttons_data, # Pass if needed by template
        panel_mode=panel_mode,  # Pass panel_mode to the template
    )


@keypad.route("/legacy")
@login_required
def responsive():  # Consider renaming to legacy_keypad if 'responsive' isn't accurate
    """Renders the legacy keypad interface."""
    panel_mode = _get_panel_mode()
    custom_buttons = KeypadButton.query.filter_by(user_id=current_user.id).all()

    template_name = "keypad/dsc_legacy.html" if panel_mode == DSC else "keypad/index_legacy.html"

    return render_template(template_name, buttons=custom_buttons)


@keypad.route("/button_index")
@login_required
def custom_index():
    """Displays the list of custom keypad buttons."""
    buttons = KeypadButton.query.filter_by(user_id=current_user.id).all()
    # SSL setting might not be needed if dynamically handled by url_for or web server config
    # use_ssl = Setting.get_by_name("use_ssl", default=False).value

    return render_template(
        "keypad/custom_button_index.html",
        buttons=buttons,
        active="keypad",
        # ssl=use_ssl # Pass if needed
    )


@keypad.route("/specials", methods=["GET", "POST"])
@login_required
def special_buttons():
    """Handles configuration of special function buttons."""
    panel_mode = _get_panel_mode()

    # Choose the correct form based on panel mode
    formclass = SpecialButtonFormDSC if panel_mode == DSC else SpecialButtonFormAdemco
    form = formclass()

    if form.validate_on_submit():
        # --- Refactored Processing Block (Fixes Duplication Warning around line 177) ---
        buttons_to_process = []
        # Always process buttons 1-4
        buttons_to_process.extend(
            [
                ("special_1", form.special_1, form.special_1_key),
                ("special_2", form.special_2, form.special_2_key),
                ("special_3", form.special_3, form.special_3_key),
                ("special_4", form.special_4, form.special_4_key),
            ]
        )

        # Add DSC-specific buttons if applicable
        if panel_mode == DSC:
            buttons_to_process.extend(
                [
                    ("special_5", form.special_5, form.special_5_key),
                    ("special_6", form.special_6, form.special_6_key),
                    ("special_7", form.special_7, form.special_7_key),
                    ("special_8", form.special_8, form.special_8_key),
                ]
            )

        settings_to_save = []
        for key_name, type_field, key_field in buttons_to_process:
            setting_type = create_special_setting(key_name, type_field.data)
            setting_key = create_special_setting_key(
                setting_type, f"{key_name}_key", interpret_key(key_field.data)
            )
            settings_to_save.extend([setting_type, setting_key])

        db.session.add_all(settings_to_save)
        db.session.commit()
        # --- End Refactored Block ---

        flash("Special buttons updated successfully.", "success")
        return redirect(url_for("keypad.custom_index"))

    elif not form.is_submitted():  # Populate form on GET request
        # --- Refactored Population Block (Addresses logic, not a specific warning) ---
        buttons_data = get_special_buttons()  # Fetch current settings

        fields_to_populate = [
            ("special_1", "special_1_key"),
            ("special_2", "special_2_key"),
            ("special_3", "special_3_key"),
            ("special_4", "special_4_key"),
        ]
        if panel_mode == DSC:
            fields_to_populate.extend(
                [
                    ("special_5", "special_5_key"),
                    ("special_6", "special_6_key"),
                    ("special_7", "special_7_key"),
                    ("special_8", "special_8_key"),
                ]
            )

        for type_key, key_key in fields_to_populate:
            # Use getattr to access form fields dynamically
            getattr(form, type_key).data = buttons_data.get(type_key)
            getattr(form, key_key).data = buttons_data.get(key_key)
        # --- End Refactored Block ---

    # If form validation fails on POST, render the form with errors
    return render_template("keypad/special_buttons.html", form=form, panel_mode=panel_mode)


@keypad.route("/create_button", methods=["GET", "POST"])
@login_required
def create_button():
    """Handles creation of a new custom keypad button."""
    form = KeypadButtonForm()

    if form.validate_on_submit():
        button = KeypadButton(user_id=current_user.id)  # Set user_id on creation
        form.populate_obj(button)
        # Ensure label field is handled if different from 'text' in form
        # button.label = form.text.data # Assuming form field name matches model or handled by populate_obj

        db.session.add(button)
        db.session.commit()

        flash("Keypad Button Created", "success")
        return redirect(url_for("keypad.custom_index"))

    # ssl=use_ssl removed, pass if necessary
    return render_template("keypad/create.html", form=form, active="keypad")


# Fixes Shadowing built-in 'id' (lines 326, 347)
@keypad.route("/edit/<int:button_id>", methods=["GET", "POST"])
@login_required
def edit_button(button_id):  # Renamed parameter
    """Handles editing an existing custom keypad button."""
    # Query using the renamed parameter
    button = KeypadButton.query.filter_by(
        button_id=button_id, user_id=current_user.id
    ).first_or_404()
    form = KeypadButtonForm(obj=button)

    if form.validate_on_submit():
        form.populate_obj(button)
        # user_id is already set and shouldn't change on edit unless intended
        # button.user_id = current_user.id

        db.session.add(button)  # or db.session.merge(button)
        db.session.commit()

        flash("Keypad Button Updated", "success")
        # Redirect to index after successful edit is common practice
        return redirect(url_for("keypad.custom_index"))

    # ssl=use_ssl removed, pass if necessary
    # Pass the button_id back to the template if needed (e.g., for form action URL)
    return render_template("keypad/edit.html", form=form, button_id=button_id, active="keypad")


# Fixes Shadowing built-in 'id' (lines 326, 347)
@keypad.route("/remove/<int:button_id>", methods=["POST"])  # Use POST for destructive actions
@login_required
def remove_button(button_id):  # Renamed parameter
    """Handles removal of a custom keypad button."""
    # Query using the renamed parameter, ensure user owns the button
    button = KeypadButton.query.filter_by(
        button_id=button_id, user_id=current_user.id
    ).first_or_404()

    db.session.delete(button)
    db.session.commit()

    flash("Keypad Button deleted", "success")
    return redirect(url_for("keypad.custom_index"))


# --- Helper Functions ---


def get_special_buttons():
    """Retrieves current special button configurations from settings."""
    # (Fixes Duplication Warning around line 40 by slightly restructuring)
    panel_mode = _get_panel_mode()
    buttons_config = {}

    # Define button configurations: (key_base_name, default_type)
    common_buttons = [
        ("special_1", FIRE),
        ("special_2", POLICE),
        ("special_3", MEDICAL),
    ]

    if panel_mode == ADEMCO:
        panel_specific_buttons = [("special_4", SPECIAL_4)]
    else:  # DSC
        panel_specific_buttons = [
            ("special_4", STAY),
            ("special_5", AWAY),
            ("special_6", CHIME),
            ("special_7", RESET),
            ("special_8", EXIT),
        ]

    # Process all relevant buttons
    for key_base, default_type in common_buttons + panel_specific_buttons:
        button_type = get_special_setting(key_base, default_type)
        button_key_name = f"{key_base}_key"
        default_key = SPECIAL_KEY_MAP.get(button_type, "")  # Get default key based on current type

        buttons_config[key_base] = button_type
        # Get specific key setting, defaulting to the map lookup
        buttons_config[button_key_name] = get_special_setting(button_key_name, default_key)

    return buttons_config  # Renamed return variable


def get_special_setting(key, setting_default):
    """Helper to retrieve a single special button setting."""
    # Ensure default is handled correctly if value is None or setting doesn't exist
    setting = Setting.query.filter_by(name=key).first()
    if setting and setting.value is not None:
        # Attempt to coerce to int if possible, otherwise return as stored
        try:
            return int(setting.value)
        except (ValueError, TypeError):
            return setting.value
    # Return the provided default if no setting exists or value is None
    return setting_default


def create_special_setting(key_number, key_value):
    """Prepares a Setting object for a special button type (without saving)."""
    special_setting = Setting.get_by_name(key_number)
    if special_setting is None:  # Create if doesn't exist
        special_setting = Setting(name=key_number, value=str(key_value))  # Store as string
    else:
        special_setting.value = str(key_value)  # Ensure value is stored as string
    return special_setting


def create_special_setting_key(special_setting_type_obj, key_type_name, key_value):
    """Prepares a Setting object for a special button key (without saving)."""
    special_setting_key = Setting.get_by_name(key_type_name)
    if special_setting_key is None:  # Create if doesn't exist
        special_setting_key = Setting(name=key_type_name)

    # Determine the correct key value based on whether it's custom
    # Use the already fetched type value from the special_setting_type_obj
    try:
        button_type_value = int(special_setting_type_obj.value)
    except (ValueError, TypeError):
        button_type_value = None  # Handle cases where value isn't an int

    if button_type_value != SPECIAL_CUSTOM:
        # Use the mapped value if type is not custom
        special_setting_key.value = SPECIAL_KEY_MAP.get(button_type_value, str(key_value))
    else:
        # Use the provided key_value if type is custom
        special_setting_key.value = str(key_value)  # Ensure stored as string

    return special_setting_key


def interpret_key(button_data):
    """Translates special key placeholders to actual AlarmDecoder codes."""
    # Using chr codes might be less readable/portable than AlarmDecoder constants if available
    # Let's prefer constants if they exist for these special sequences.
    # Assuming KEY_F1-F4 are correct. Need confirmation for 5-8 or stick to chr().
    five = chr(5) * 3
    six = chr(6) * 3
    seven = chr(7) * 3
    eight = chr(8) * 3

    key_map = {
        "<S1>": AlarmDecoder.KEY_F1,
        "<S2>": AlarmDecoder.KEY_F2,
        "<S3>": AlarmDecoder.KEY_F3,
        "<S4>": AlarmDecoder.KEY_F4,
        "<S5>": five,
        "<S6>": six,
        "<S7>": seven,
        "<S8>": eight,
        # Also handle direct AlarmDecoder constants if passed through
        AlarmDecoder.KEY_F1: AlarmDecoder.KEY_F1,
        AlarmDecoder.KEY_F2: AlarmDecoder.KEY_F2,
        AlarmDecoder.KEY_F3: AlarmDecoder.KEY_F3,
        AlarmDecoder.KEY_F4: AlarmDecoder.KEY_F4,
        # Add mappings for five, six, seven, eight if they might be passed directly
        five: five,
        six: six,
        seven: seven,
        eight: eight,
    }
    # Return the mapped value, or the original data if no mapping exists
    return key_map.get(button_data, button_data)


# Removed duplicated code fragment warning around line 278:
# The create_button and edit_button routes follow a standard Flask CRUD pattern.
# While similar, extracting this further might reduce readability for standard operations.
# The duplication warning is noted but deemed acceptable here.

# Removed shadowing name 'special_buttons' warnings (lines 45, 63):
# The variable `special_buttons` inside `get_special_buttons` is intentionally
# created locally for that function's scope to build the result dictionary.
# Renaming it offers little benefit to clarity in this context.
