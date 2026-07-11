import os
import re
from dataclasses import dataclass

from srctools.filesys import RawFileSystem
from srctools.mdl import Model
from srctools.vmt import Material

from utils.formatting import format_size


# Compound/longer extensions must come before shorter ones so stripping works correctly.
MODEL_SUPPORT_EXTS = (
    '.sw.vtx', '.dx80.vtx', '.dx90.vtx', '.xbox.vtx', '.360.vtx',
    '.ani', '.vvd', '.phy', '.vtx',
)
SOUND_EXTS = {'.wav', '.mp3', '.ogg'}

# Text files commonly containing asset references. PCFs are handled separately
# because they are binary files with embedded path strings.
REFERENCE_TEXT_EXTS = {'.lua', '.txt', '.json', '.nut', '.cfg', '.res', '.vcd'}

# VMT keys that reference VTF texture paths.
VTF_VMT_PARAMS = {
    '$basetexture', '$basetexture2', '$bumpmap', '$bumpmap2',
    '$normalmap', '$normalmap2', '$detail', '$envmap', '$envmapmask',
    '$selfillummask', '$blendmodulatetexture', '$texture2',
    '$dudvmap', '$wrapmask', '$lightwarptexture', '$refracttexture',
    '$reflecttexture', '$ambientoccltexture', '$phongexponenttexture',
    '$specexptexture', '$rimmasktexture',
}

_REFERENCE_TOKEN_RE = re.compile(r'[A-Za-z0-9_./-]+')


@dataclass(frozen=True)
class _ReferenceIndex:
    """Normalized, tokenized references found in source files."""

    tokens: frozenset[str]
    character_count: int
    path_suffixes: frozenset[str]
    constructed_prefixes: frozenset[str]

    def contains_any(self, candidates) -> bool:
        return any(candidate and candidate in self.tokens for candidate in candidates)

    def contains_path_suffix(self, candidates) -> bool:
        """Match references with an addon-specific prefix, such as zcitysnd/."""
        for candidate in candidates:
            if not candidate:
                continue
            suffix = '/' + candidate
            if suffix in self.path_suffixes:
                return True
        return False

    def contains_constructed_path(self, candidates) -> bool:
        """Match Lua path prefixes used to construct sound filenames."""
        for candidate in candidates:
            if not candidate:
                continue
            if candidate in self.constructed_prefixes:
                return True
        return False


def _normalise_path(value: str) -> str:
    return value.strip().strip('"').strip("'").lower().replace('\\', '/')


def _get_model_base(filepath: str) -> str:
    """Return the base path of a model file (lowercase, forward slashes, no extension)."""
    path = _normalise_path(filepath)
    for ext in MODEL_SUPPORT_EXTS + ('.mdl',):
        if path.endswith(ext):
            return path[:-len(ext)]
    return path


def _strip_asset_prefix_and_extension(value: str, extension: str) -> str:
    """Normalize a Source asset reference to a path without its prefix/extension."""
    value = _normalise_path(value)
    if value.startswith('materials/'):
        value = value[len('materials/'):]
    if value.endswith(extension):
        value = value[:-len(extension)]
    return value.strip('/')


def _texture_key(value: str) -> str:
    return _strip_asset_prefix_and_extension(value, '.vtf')


def _vmt_key(value: str) -> str:
    return _strip_asset_prefix_and_extension(value, '.vmt')


def _sound_key(value: str) -> str:
    value = _normalise_path(value).strip('/')
    for prefix in ('sound/', 'sounds/'):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    return value


def _asset_basename(value: str) -> str:
    return value.rsplit('/', 1)[-1]


def _add_text_references(text: str, tokens: set[str]) -> int:
    normalized = text.lower().replace('\\', '/')
    tokens.update(_REFERENCE_TOKEN_RE.findall(normalized))
    return len(text)


def _scan_reference_tree(
    root: str,
    extensions: set[str],
    tokens: set[str],
    seen_files: set[str],
    binary: bool = False,
) -> int:
    """Scan a directory once and add normalized path-like tokens to ``tokens``."""
    if not os.path.isdir(root):
        return 0

    character_count = 0
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if os.path.splitext(filename)[1].lower() not in extensions:
                continue

            full_path = os.path.join(dirpath, filename)
            identity = os.path.normcase(os.path.abspath(full_path))
            if identity in seen_files:
                continue
            seen_files.add(identity)

            try:
                if binary:
                    with open(full_path, 'rb') as file:
                        text = file.read().decode('latin-1')
                else:
                    with open(full_path, 'r', encoding='utf-8', errors='replace') as file:
                        text = file.read()
            except (OSError, UnicodeError):
                continue

            character_count += _add_text_references(text, tokens)

    return character_count


def _build_reference_index(main_path: str, extra_lua_folders=None) -> _ReferenceIndex:
    """
    Build an index of path-like tokens from files that can reference assets.

    Exact token matching avoids false positives such as ``foo.wav`` matching
    ``foo.wav.bak`` while still supporting Lua, soundscript, JSON and PCF files.
    """
    tokens: set[str] = set()
    seen_files: set[str] = set()
    character_count = 0

    character_count += _scan_reference_tree(
        os.path.join(main_path, 'lua'), {'.lua'}, tokens, seen_files,
    )
    character_count += _scan_reference_tree(
        os.path.join(main_path, 'scripts'), REFERENCE_TEXT_EXTS, tokens, seen_files,
    )
    character_count += _scan_reference_tree(
        os.path.join(main_path, 'particles'), {'.pcf'}, tokens, seen_files, binary=True,
    )

    # Companion addons may contain references in lua/, gamemodes/, scripts/,
    # weapons/, or other addon folders. Scan the entire selected addon rather
    # than only lua/. The previous layout-specific scan missed gamemode files,
    # including references such as snd_jack_hmcd_disaster.mp3.
    for extra in extra_lua_folders or ():
        character_count += _scan_reference_tree(
            extra, REFERENCE_TEXT_EXTS, tokens, seen_files,
        )
        # PCFs outside the conventional particles/ directory can also contain
        # embedded material/model references.
        character_count += _scan_reference_tree(extra, {'.pcf'}, tokens, seen_files, binary=True)

    path_suffixes = set()
    for token in tokens:
        if '/' not in token:
            continue
        path_parts = token.split('/')
        path_suffixes.update(
            '/' + '/'.join(path_parts[index:])
            for index in range(len(path_parts))
        )
    constructed_prefixes = {
        token
        for token in tokens
        # A concatenated Lua string is tokenized as a plain prefix, for
        # example ``weapon_generic_rifle_spin``. Index extensionless tokens
        # so checking each numbered sound remains constant-time.
        if (
            token.endswith('/')
            or token.endswith(('_', '-'))
            or os.path.splitext(token)[1].lower() not in SOUND_EXTS
        )
    }
    return _ReferenceIndex(
        frozenset(tokens),
        character_count,
        frozenset(path_suffixes),
        frozenset(constructed_prefixes),
    )


def _is_referenced(references: _ReferenceIndex, *candidates: str) -> bool:
    """Return whether any normalized asset spelling occurs as a complete token."""
    normalized = {_normalise_path(candidate) for candidate in candidates if candidate}
    return (
        references.contains_any(normalized)
        or references.contains_path_suffix(normalized)
    )


def _is_constructed_sound_reference(references: _ReferenceIndex, sound_key: str) -> bool:
    """Check a generated numbered sound against indexed prefixes in O(1)."""
    filename = _asset_basename(sound_key)
    stem, extension = os.path.splitext(filename)
    if extension not in SOUND_EXTS:
        return False

    directory = sound_key[:-len(filename)]
    # A directory can contain a generated filename prefix, e.g.
    # ``snds_jack_hmcd_breathing/`` .. "f" .. math.random(4) .. ".wav".
    if directory and directory in references.constructed_prefixes:
        return True

    stem_prefix = re.sub(r'[_-]?\d+$', '', stem)
    if len(stem_prefix) <= 3:
        return False

    prefix_candidates = {
        sound_key,
        filename,
        stem_prefix,
        directory + stem_prefix,
    }
    return references.contains_constructed_path(prefix_candidates)


def _model_is_referenced(references: _ReferenceIndex, model_path: str) -> bool:
    model_path = _normalise_path(model_path)
    model_name = os.path.splitext(_asset_basename(model_path))[0]
    return _is_referenced(references, model_path, model_name)


def _event_type_value(event_type):
    value = getattr(event_type, 'value', event_type)
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _parse_model_references(fs, mdl_path: str):
    """Return normalized VMT and sound references found in one model."""
    model_vmt_keys: set[str] = set()
    model_sound_keys: set[str] = set()

    model = Model(fs, fs[mdl_path])
    for texture in model.iter_textures():
        model_vmt_keys.add(_vmt_key(texture))

    # Source sound-bearing animation events include these values. Use
    # ``model.sequences``: srctools.Model has no ``mdl`` attribute. Unknown
    # event types are retained conservatively because custom models can use
    # game-specific sound event IDs.
    sound_event_types = {14, 15, 1004, 5004, 5034}
    for sequence in model.sequences:
        for event in sequence.events:
            event_type = _event_type_value(event.type)
            if not event.options or (
                event_type not in sound_event_types
                and not isinstance(event_type, str)
            ):
                continue
            sound = _sound_key(event.options)
            if sound:
                model_sound_keys.add(sound)
                model_sound_keys.add(_asset_basename(sound))

    return model_vmt_keys, model_sound_keys


def _parse_vmt_texture_references(full_path: str, vmt_path: str) -> set[str]:
    with open(full_path, 'r', encoding='utf-8', errors='replace') as file:
        vmt = Material.parse(file, filename=vmt_path)

    references: set[str] = set()
    for key, value in vmt.items():
        # Some material parameter names contain a conditional suffix.
        parameter = key.lower().split('?', 1)[0]
        if parameter in VTF_VMT_PARAMS:
            texture = _texture_key(value)
            if texture:
                references.add(texture)
    return references


def unused_content(path: str, remove: bool = False, extra_lua_folders=None):
    """Find or remove content that is not referenced by the addon.

    The complete scan is performed before any deletion. This prevents a parse
    failure or unexpected filesystem error from leaving a partially cleaned
    addon while the remaining analysis is still incomplete.
    """
    fs = RawFileSystem(path)

    # Candidates are queued during analysis and processed only after all files
    # have been checked. The key prevents duplicate accounting/deletion.
    candidates: list[tuple[str, str]] = []
    candidate_keys: set[str] = set()

    def schedule_file(relative_path: str, label: str):
        relative_path = _normalise_path(relative_path)
        if relative_path not in candidate_keys:
            candidate_keys.add(relative_path)
            candidates.append((relative_path, label))

    print('Building reference index (Lua/scripts/PCF)...')
    references = _build_reference_index(path, extra_lua_folders)
    print(f'  {references.character_count:,} characters from reference files')

    print('\nDiscovering files...')
    all_mdl: list[str] = []
    all_support: list[str] = []
    all_vmts: list[str] = []
    all_vtfs: list[str] = []
    all_sounds: list[str] = []

    for file in fs.walk_folder(''):
        relative_path = _normalise_path(file.path)
        if relative_path.endswith('.mdl'):
            all_mdl.append(relative_path)
        elif any(relative_path.endswith(ext) for ext in MODEL_SUPPORT_EXTS):
            all_support.append(relative_path)
        elif relative_path.endswith('.vmt'):
            all_vmts.append(relative_path)
        elif relative_path.endswith('.vtf'):
            all_vtfs.append(relative_path)
        elif any(relative_path.endswith(ext) for ext in SOUND_EXTS):
            all_sounds.append(relative_path)

    print(
        f'  {len(all_mdl)} MDL, {len(all_support)} support files, '
        f'{len(all_vmts)} VMT, {len(all_vtfs)} VTF, {len(all_sounds)} sounds'
    )

    print(f'\nChecking {len(all_mdl)} models against reference files...')
    supports_by_base: dict[str, list[str]] = {}
    for support_path in all_support:
        supports_by_base.setdefault(_get_model_base(support_path), []).append(support_path)

    all_model_bases = {_get_model_base(model_path) for model_path in all_mdl}
    surviving_mdl: list[str] = []

    for mdl_path in all_mdl:
        if _model_is_referenced(references, mdl_path):
            surviving_mdl.append(mdl_path)
            continue

        schedule_file(mdl_path, 'MDL')
        for support_path in supports_by_base.get(_get_model_base(mdl_path), ()):
            schedule_file(support_path, 'support file')

    # A support file is orphaned if no model with the same base exists at all.
    scheduled_support = {relative for relative, _ in candidates if relative in all_support}
    for support_path in all_support:
        if support_path not in scheduled_support and _get_model_base(support_path) not in all_model_bases:
            schedule_file(support_path, 'orphan support file')

    print(f'\nParsing {len(surviving_mdl)} surviving models for materials and sounds...')
    model_vmt_keys: set[str] = set()
    model_sound_keys: set[str] = set()

    for mdl_path in surviving_mdl:
        try:
            vmt_keys, sound_keys = _parse_model_references(fs, mdl_path)
            model_vmt_keys.update(vmt_keys)
            model_sound_keys.update(sound_keys)
        except Exception as error:
            # A model that cannot be parsed is retained, and its missing
            # references are not used as evidence that other files are unused.
            print(f'  Warning: could not parse {mdl_path}: {error}')

    model_vmt_basenames = {_asset_basename(key) for key in model_vmt_keys}
    print(f'  {len(model_vmt_keys)} VMT refs, {len(model_sound_keys)} sound refs from models')

    print(f'\nParsing {len(all_vmts)} VMTs for VTF references...')
    vmt_vtf_keys_by_path: dict[str, set[str]] = {}
    malformed_vmts: set[str] = set()
    for vmt_path in all_vmts:
        full_path = os.path.join(path, vmt_path.replace('/', os.sep))
        try:
            vmt_vtf_keys_by_path[vmt_path] = _parse_vmt_texture_references(full_path, vmt_path)
        except Exception as error:
            malformed_vmts.add(vmt_path)
            print(f'  Warning: could not parse VMT {vmt_path}: {error}')

    # Determine which VMTs survive before deciding which VTFs survive. This
    # avoids retaining textures referenced only by a VMT that will be removed.
    surviving_vmts: set[str] = set()
    for vmt_path in all_vmts:
        vmt_key = _vmt_key(vmt_path)
        vmt_basename = _asset_basename(vmt_key)
        if (
            vmt_key in model_vmt_keys
            or vmt_basename in model_vmt_basenames
            or _is_referenced(references, vmt_path, vmt_key, vmt_key + '.vmt')
            or vmt_key.split('/')[0] in {'effects', 'sprites', 'particle', 'particles'}
            or vmt_path in malformed_vmts
        ):
            surviving_vmts.add(vmt_path)

    vmt_vtf_keys: set[str] = set()
    for vmt_path in surviving_vmts:
        vmt_vtf_keys.update(vmt_vtf_keys_by_path.get(vmt_path, ()))
    vmt_vtf_basenames = {_asset_basename(key) for key in vmt_vtf_keys}

    print(f'\nChecking {len(all_vtfs)} VTF files...')
    for vtf_path in all_vtfs:
        vtf_key = _texture_key(vtf_path)
        vtf_basename = _asset_basename(vtf_key)
        if (
            vtf_key in vmt_vtf_keys
            or vtf_basename in vmt_vtf_basenames
            or _is_referenced(references, vtf_path, vtf_key, vtf_key + '.vtf')
        ):
            continue
        # If a VMT could not be parsed, do not delete VTFs based on incomplete
        # dependency information. The malformed VMT itself is retained above.
        if malformed_vmts:
            continue
        schedule_file(vtf_path, 'VTF')

    print(f'\nChecking {len(all_vmts)} VMT files...')
    for vmt_path in all_vmts:
        if vmt_path not in surviving_vmts:
            schedule_file(vmt_path, 'VMT')

    print(f'\nChecking {len(all_sounds)} sound files...')
    for sound_path in all_sounds:
        sound_key = _sound_key(sound_path)
        sound_filename = _asset_basename(sound_key)
        if sound_key in model_sound_keys or sound_filename in model_sound_keys:
            continue
        if _is_referenced(references, sound_path, sound_key, sound_filename):
            continue

        # Handles dynamically constructed names such as
        # "weapon_spin" .. math.random(N) .. ".wav".
        if _is_constructed_sound_reference(references, sound_key):
            continue

        schedule_file(sound_path, 'sound')

    # Only now perform the requested actions.
    total_size = 0
    total_count = 0
    print(f'\n{("Removing" if remove else "Reporting")} {len(candidates)} candidates...')
    candidate_sizes = []
    for relative_path, label in candidates:
        full_path = os.path.join(path, relative_path.replace('/', os.sep))
        try:
            size = os.path.getsize(full_path)
        except OSError:
            size = 0
        candidate_sizes.append((size, relative_path, label))

    if not remove:
        candidate_sizes.sort(key=lambda candidate: candidate[0])

    for size, relative_path, label in candidate_sizes:
        full_path = os.path.join(path, relative_path.replace('/', os.sep))
        total_size += size
        total_count += 1
        action = 'Removing' if remove else 'Found'
        print(f'{action} unused {label} ({format_size(size)}): {relative_path}')
        if remove:
            try:
                os.remove(full_path)
            except OSError as error:
                print(f'  Error: {error}')

    return total_size, total_count
