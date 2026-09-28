# Exports the active SeedHammer design as STEP to ~/SeedHammer/outbox, where scripts/publish.py picks it up.
# Refuses unsaved designs (the file is named after the saved version) and designs with hidden geometry (Fusion leaves
# hidden components and bodies out of the STEP).
import adsk.core, adsk.fusion, os, traceback

MODELS = {'Hammer_V3P': 'Hammer', 'seed_v4': 'Seed'}
OUTBOX = os.path.expanduser('~/SeedHammer/outbox')


def hidden_geometry(design):
    found = [b.name for b in design.rootComponent.bRepBodies if not b.isVisible]
    for o in design.rootComponent.allOccurrences:
        parent = o.assemblyContext
        if not o.isVisible:
            # Report the topmost hidden occurrence that has geometry; its children are hidden with it.
            has_bodies = o.bRepBodies.count or any(c.bRepBodies.count for c in o.component.allOccurrences)
            if has_bodies and (parent is None or parent.isVisible):
                found.append(o.fullPathName)
            continue
        found += [f'{o.fullPathName}/{b.name}' for b in o.bRepBodies if not b.isVisible]
    return found


def export(app):
    doc = app.activeDocument
    if doc is None or doc.name not in MODELS:
        return f'Open {" or ".join(MODELS)} first.'
    if doc.isModified or not doc.isSaved:
        return f'Save {doc.name} first; the file is named after the saved version.'
    data = doc.dataFile
    if data.versionNumber != data.latestVersionNumber:
        return f'{doc.name} is at version {data.versionNumber}, but version {data.latestVersionNumber} exists. Open the latest.'
    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    hidden = hidden_geometry(design)
    if hidden:
        return 'These are hidden and would be left out of the STEP. Show them (or delete them) and save:\n\n' + '\n'.join(hidden[:20])

    name = f'{MODELS[doc.name]}-v{data.versionNumber}.step'
    tmp = os.path.join(OUTBOX, '.tmp')
    os.makedirs(tmp, exist_ok=True)
    # Export beside the outbox, then move it in whole, so the publisher never reads a half-written file.
    options = design.exportManager.createSTEPExportOptions(os.path.join(tmp, name), design.rootComponent)
    if not design.exportManager.execute(options):
        return 'Fusion could not export the STEP.'
    os.replace(os.path.join(tmp, name), os.path.join(OUTBOX, name))
    return f'Queued {name}. A notification tells you when it is published, or why not.'


def run(_context):
    app = adsk.core.Application.get()
    try:
        message = export(app)
    except Exception:
        message = 'Export failed:\n' + traceback.format_exc()[-1500:]
    app.userInterface.messageBox(message, 'SeedHammer export')
