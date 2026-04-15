# =========================
# TT NAMING TOOL V5
# =========================

import json
import os
import re
import subprocess

import maya.cmds as cmds
import maya.mel as mel

WINDOW_NAME = "TT_NamingTool_V5"

PART_OPTIONS = ["HEAD", "FACE", "EYE", "HAIR", "BODY", "TORSO", "ARM", "HAND", "LEG", "FOOT", "NAIL"]
CATEGORY_OPTIONS = ["Hair", "Outfit", "Armor", "Accessory", "Weapon", "Prop", "Skin", "Cloth", "HardSurface"]
TECH_TYPE_OPTIONS = ["", "HP", "LP", "UV", "TEX", "RENDER", "LOD0", "LOD1"]
MATERIAL_TYPES = ["Default", "Skin", "Metal", "Cloth", "Glass"]

MAP_ALIASES = {
    "BASECOLOR": ["BC", "ALB", "BASECOLOR", "C"],
    "ROUGHNESS": ["RGH", "ROUGHNESS", "R"],
    "SPECULAR": ["SPEC", "SPECULAR", "SPC"],
    "METALNESS": ["MTL", "METAL", "METALNESS", "M"],
    "NORMAL": ["NRM", "NORMAL", "N"],
    "BUMP": ["BMP", "BUMP"],
    "DISPLACEMENT": ["DISP", "DSP", "DISPLACEMENT"],
    "SSS_WEIGHT": ["SSS_W", "SSSW", "SUBSURFACE"],
    "SSS_COLOR": ["SSS_C", "SSSC"],
    "SSS_RADIUS": ["SSS_R", "SSSR"],
    "AO": ["AO"],
    "OPACITY": ["OPC", "ALPHA", "OPACITY", "O"],
    "EMISSION": ["EMI", "EMISSION", "E"],
    "CAVITY": ["CAV", "CAVITY"],
    "ORM": ["ORM"],
}

COLOR_MAP_TYPES = {"BASECOLOR", "EMISSION", "SSS_COLOR"}


MATERIAL_PRESET_ATTRS = [
    "base",
    "baseColor",
    "specular",
    "specularColor",
    "specularRoughness",
    "specularIOR",
    "metalness",
    "subsurface",
    "subsurfaceColor",
    "subsurfaceRadius",
    "sheen",
    "transmission",
    "emission",
    "emissionColor",
    "opacity",
]



LOOKDEV_PRESETS = {
    "GREY BALL": {
        "name": "LDV_GREY_BALL",
        "attrs": {
            "base": 1.0,
            "baseColor": (0.18, 0.18, 0.18),
            "specular": 0.35,
            "specularRoughness": 0.45,
            "metalness": 0.0,
            "subsurface": 0.0,
        },
    },
    "CHROME BALL": {
        "name": "LDV_CHROME_BALL",
        "attrs": {
            "base": 1.0,
            "baseColor": (1.0, 1.0, 1.0),
            "specular": 1.0,
            "specularRoughness": 0.05,
            "metalness": 1.0,
            "subsurface": 0.0,
        },
    },
}

STATE = {
    "selected_material": "Default",
    "texture_files": [],
    "texture_map_paths": {},
    "texture_map_enabled": {},
}


# =========================
# NAMING ENGINE
# =========================
def build_name(
    ip,
    part,
    category,
    detail,
    version,
    prefix,
    use_prefix,
    use_part,
    use_category,
    use_detail,
    use_version,
):
    parts = []

    if use_prefix and prefix:
        parts.append(prefix)

    parts.append(ip)

    if use_part and part:
        parts.append(part)

    if use_category and category:
        parts.append(category)

    if use_detail and detail:
        parts.append(detail)

    if use_version and version:
        parts.append(version)

    return "_".join([p for p in parts if p])


def format_index(i, digits):
    return str(i + 1).zfill(digits)


def get_next_version(path, base):
    if not os.path.exists(path):
        return "v01"

    versions = []
    for f in os.listdir(path):
        if base in f:
            match = re.search(r"v(\d+)", f)
            if match:
                versions.append(int(match.group(1)))

    return f"v{str((max(versions) + 1) if versions else 1).zfill(2)}"


# =========================
# MATERIAL SYSTEM
# =========================
def current_shader_model():
    if cmds.optionMenu("shader_model", exists=True):
        return cmds.optionMenu("shader_model", q=True, value=True)
    return "Arnold"


def shader_node_type():
    model = current_shader_model()
    if model == "Phong":
        return "phong"
    if model == "Blind":
        return "blinn"
    return "aiStandardSurface"


def create_material(mat_name):
    if cmds.objExists(mat_name):
        return mat_name

    mat = cmds.shadingNode(shader_node_type(), asShader=True, name=mat_name)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=mat_name + "SG")
    cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", f=True)
    return mat


def assign_material(obj, mat):
    cmds.select(obj, r=True)
    cmds.hyperShade(assign=mat)


def set_attr_if_exists(node, attr, *values, **kwargs):
    if cmds.attributeQuery(attr, node=node, exists=True):
        cmds.setAttr(node + "." + attr, *values, **kwargs)




def apply_skin_face_beauty_preset(mat):
    # Arnold aiStandardSurface face-beauty baseline
    if not cmds.attributeQuery("base", node=mat, exists=True):
        return

    set_attr_if_exists(mat, "base", 1.0)
    set_attr_if_exists(mat, "specular", 0.45)
    set_attr_if_exists(mat, "specularRoughness", 0.38)
    set_attr_if_exists(mat, "specularIOR", 1.42)
    set_attr_if_exists(mat, "metalness", 0.0)

    # SSS tuned for face beauty lookdev start point
    set_attr_if_exists(mat, "subsurface", 0.5)
    if cmds.attributeQuery("subsurfaceColor", node=mat, exists=True):
        cmds.setAttr(mat + ".subsurfaceColor", 1.0, 0.72, 0.62, type="double3")
    if cmds.attributeQuery("subsurfaceRadius", node=mat, exists=True):
        cmds.setAttr(mat + ".subsurfaceRadius", 1.0, 0.35, 0.2, type="double3")

    set_attr_if_exists(mat, "sheen", 0.0)
    set_attr_if_exists(mat, "coat", 0.0)
    set_attr_if_exists(mat, "transmission", 0.0)
    set_attr_if_exists(mat, "emission", 0.0)



def apply_attrs_dict(mat, attrs):
    for attr, value in attrs.items():
        if not cmds.attributeQuery(attr, node=mat, exists=True):
            continue
        if isinstance(value, tuple) and len(value) == 3:
            cmds.setAttr(mat + "." + attr, value[0], value[1], value[2], type="double3")
        else:
            cmds.setAttr(mat + "." + attr, value)


def apply_lookdev_material(preset_label, *_):
    if preset_label not in LOOKDEV_PRESETS:
        cmds.warning("LookDev preset not found: " + preset_label)
        return

    preset = LOOKDEV_PRESETS[preset_label]
    mat_name = preset["name"]
    mat = create_material(mat_name)
    apply_attrs_dict(mat, preset["attrs"])

    selected = cmds.ls(sl=True) or []
    for obj in selected:
        assign_material(obj, mat)

    cmds.inViewMessage(amg="LookDev Material Applied: " + preset_label, pos="topCenter", fade=True)


def apply_mat_type(mat, mat_type):
    set_attr_if_exists(mat, "base", 1)
    set_attr_if_exists(mat, "subsurface", 0)
    set_attr_if_exists(mat, "metalness", 0)
    set_attr_if_exists(mat, "sheen", 0)
    set_attr_if_exists(mat, "transmission", 0)

    if mat_type == "Skin":
        apply_skin_face_beauty_preset(mat)
    elif mat_type == "Metal":
        set_attr_if_exists(mat, "metalness", 1)
    elif mat_type == "Cloth":
        set_attr_if_exists(mat, "sheen", 1)
    elif mat_type == "Glass":
        set_attr_if_exists(mat, "transmission", 1)
        set_attr_if_exists(mat, "specularIOR", 1.5)


# =========================
# TEXTURE SYSTEM
# =========================
def detect_map_type(filename):
    name = os.path.splitext(os.path.basename(filename))[0].upper()

    for map_type, aliases in MAP_ALIASES.items():
        for alias in aliases:
            alias = alias.upper()
            if re.search(rf"(?:^|[_\-.]){re.escape(alias)}(?:$|[_\-.])", name):
                return map_type
            if name.endswith("_" + alias):
                return map_type
    return None


def set_color_space(file_node, map_type):
    color_space = "sRGB" if map_type in COLOR_MAP_TYPES else "Raw"
    cmds.setAttr(file_node + ".colorSpace", color_space, type="string")


def create_file_node(path, map_type):
    node = cmds.shadingNode("file", asTexture=True)
    cmds.setAttr(node + ".fileTextureName", path, type="string")

    if "<UDIM>" in path or re.search(r"1\d{3}", os.path.basename(path)):
        set_attr_if_exists(node, "uvTilingMode", 3)

    set_color_space(node, map_type)
    return node


def parse_texture_files(files):
    parsed = {}
    for path in files:
        map_type = detect_map_type(path)
        if map_type:
            parsed[map_type] = path
    return parsed


def rebuild_texture_state(files):
    parsed = parse_texture_files(files)
    STATE["texture_files"] = files
    STATE["texture_map_paths"] = parsed
    STATE["texture_map_enabled"] = {map_type: True for map_type in parsed}


def map_type_from_ui_line(line):
    parts = line.split(" ", 2)
    if len(parts) >= 2:
        return parts[1]
    return None


def refresh_texture_detection_ui(*_):
    if not cmds.textScrollList("tex_detect", exists=True):
        return

    cmds.textScrollList("tex_detect", e=True, ra=True)
    for map_type in sorted(STATE["texture_map_paths"].keys()):
        status = "[ON]" if STATE["texture_map_enabled"].get(map_type, True) else "[OFF]"
        path = STATE["texture_map_paths"][map_type]
        label = f"{status} {map_type}  ->  {os.path.basename(path)}"
        cmds.textScrollList("tex_detect", e=True, a=label)


def selected_map_type_from_ui():
    sel = cmds.textScrollList("tex_detect", q=True, si=True) or []
    if not sel:
        return None
    return map_type_from_ui_line(sel[0])


def toggle_selected_texture_map(*_):
    map_type = selected_map_type_from_ui()
    if not map_type:
        cmds.warning("Select a map row in Texture System first")
        return
    current = STATE["texture_map_enabled"].get(map_type, True)
    STATE["texture_map_enabled"][map_type] = not current
    refresh_texture_detection_ui()


def relink_selected_texture_map(*_):
    map_type = selected_map_type_from_ui()
    if not map_type:
        cmds.warning("Select a map row in Texture System first")
        return

    selected = cmds.fileDialog2(
        fileMode=1,
        caption="Relink Texture: " + map_type,
        fileFilter="Images (*.png *.jpg *.jpeg *.tif *.tiff *.exr *.tga *.tx)"
    )
    if selected:
        STATE["texture_map_paths"][map_type] = selected[0]
        STATE["texture_map_enabled"][map_type] = True
        refresh_texture_detection_ui()


def select_texture_files(*_):
    selected = cmds.fileDialog2(
        fileMode=4,
        caption="Select Texture Files",
        fileFilter="Images (*.png *.jpg *.jpeg *.tif *.tiff *.exr *.tga *.tx)"
    )
    if selected:
        rebuild_texture_state(selected)
        refresh_texture_detection_ui()


def connect_normal(mat, file_node):
    normal_node = cmds.shadingNode("aiNormalMap", asUtility=True)
    cmds.connectAttr(file_node + ".outColor", normal_node + ".input", f=True)
    set_attr_if_exists(normal_node, "strength", 1.0)
    cmds.connectAttr(normal_node + ".outValue", mat + ".normalCamera", f=True)


def connect_bump(mat, file_node):
    bump_node = cmds.shadingNode("bump2d", asUtility=True)
    set_attr_if_exists(bump_node, "bumpInterp", 1)
    cmds.connectAttr(file_node + ".outAlpha", bump_node + ".bumpValue", f=True)
    cmds.connectAttr(bump_node + ".outNormal", mat + ".normalCamera", f=True)


def connect_displacement(mat, file_node):
    sg_nodes = cmds.listConnections(mat, type="shadingEngine") or []
    if not sg_nodes:
        return

    disp = cmds.shadingNode("displacementShader", asShader=True, name=mat + "_disp")
    cmds.connectAttr(file_node + ".outAlpha", disp + ".displacement", f=True)
    set_attr_if_exists(disp, "scale", 0.05)
    cmds.connectAttr(disp + ".displacement", sg_nodes[0] + ".displacementShader", f=True)


def connect_ao_with_basecolor(mat, basecolor_file, ao_file):
    if not basecolor_file:
        return

    ao_blend = cmds.shadingNode("blendColors", asUtility=True, name=mat + "_AO_Blend")
    cmds.setAttr(ao_blend + ".color1", 1, 1, 1, type="double3")
    cmds.connectAttr(ao_file + ".outColor", ao_blend + ".color2", f=True)
    cmds.setAttr(ao_blend + ".blender", 0.5)

    multiply = cmds.shadingNode("multiplyDivide", asUtility=True, name=mat + "_AO_Multiply")
    cmds.connectAttr(basecolor_file + ".outColor", multiply + ".input1", f=True)
    cmds.connectAttr(ao_blend + ".output", multiply + ".input2", f=True)
    cmds.connectAttr(multiply + ".output", mat + ".baseColor", f=True)


def connect_orm(mat, orm_file, basecolor_file=None):
    # ORM: R=AO, G=Roughness, B=Metalness
    cmds.connectAttr(orm_file + ".outColorG", mat + ".specularRoughness", f=True)
    cmds.connectAttr(orm_file + ".outColorB", mat + ".metalness", f=True)
    connect_ao_with_basecolor(mat, basecolor_file, orm_file)


def connect_specular(mat, spec_file):
    # Prefer scalar specular unless source is RGB-driven workflow.
    cmds.connectAttr(spec_file + ".outAlpha", mat + ".specular", f=True)


def connect_cavity(mat, cavity_file):
    if cmds.attributeQuery("specularRoughness", node=mat, exists=True):
        mod = cmds.shadingNode("multiplyDivide", asUtility=True, name=mat + "_Cavity_Rgh")
        cmds.connectAttr(cavity_file + ".outColorR", mod + ".input1X", f=True)
        cmds.setAttr(mod + ".input2X", 0.5)
        cmds.connectAttr(mod + ".outputX", mat + ".specularRoughness", f=True)


def connect_textures(mat):
    active_maps = {
        map_type: path
        for map_type, path in STATE["texture_map_paths"].items()
        if STATE["texture_map_enabled"].get(map_type, True)
    }
    nodes = {map_type: create_file_node(path, map_type) for map_type, path in active_maps.items()}

    basecolor = nodes.get("BASECOLOR")
    if basecolor:
        cmds.connectAttr(basecolor + ".outColor", mat + ".baseColor", f=True)
        set_attr_if_exists(mat, "base", 1)

    if "ROUGHNESS" in nodes:
        cmds.connectAttr(nodes["ROUGHNESS"] + ".outAlpha", mat + ".specularRoughness", f=True)

    if "SPECULAR" in nodes:
        connect_specular(mat, nodes["SPECULAR"])

    if "METALNESS" in nodes:
        cmds.connectAttr(nodes["METALNESS"] + ".outAlpha", mat + ".metalness", f=True)

    if "NORMAL" in nodes:
        connect_normal(mat, nodes["NORMAL"])

    if "BUMP" in nodes:
        connect_bump(mat, nodes["BUMP"])

    if "DISPLACEMENT" in nodes:
        connect_displacement(mat, nodes["DISPLACEMENT"])

    if "SSS_WEIGHT" in nodes:
        cmds.connectAttr(nodes["SSS_WEIGHT"] + ".outAlpha", mat + ".subsurface", f=True)

    if "SSS_COLOR" in nodes:
        cmds.connectAttr(nodes["SSS_COLOR"] + ".outColor", mat + ".subsurfaceColor", f=True)

    if "SSS_RADIUS" in nodes:
        cmds.connectAttr(nodes["SSS_RADIUS"] + ".outColor", mat + ".subsurfaceRadius", f=True)

    if "AO" in nodes:
        connect_ao_with_basecolor(mat, basecolor, nodes["AO"])

    if "OPACITY" in nodes:
        cmds.connectAttr(nodes["OPACITY"] + ".outColor", mat + ".opacity", f=True)

    if "EMISSION" in nodes:
        cmds.connectAttr(nodes["EMISSION"] + ".outColor", mat + ".emissionColor", f=True)
        set_attr_if_exists(mat, "emission", 1)

    if "CAVITY" in nodes:
        connect_cavity(mat, nodes["CAVITY"])

    if "ORM" in nodes:
        connect_orm(mat, nodes["ORM"], basecolor)


# =========================
# MATERIAL UI
# =========================
def select_material_type(mat_type):
    STATE["selected_material"] = mat_type
    for candidate in MATERIAL_TYPES:
        button = "mat_btn_" + candidate
        if cmds.button(button, exists=True):
            color = (0.35, 0.55, 0.35) if candidate == mat_type else (0.2, 0.2, 0.2)
            cmds.button(button, e=True, bgc=color)




def materials_from_selected_objects():
    mats = []
    selected = cmds.ls(sl=True, long=True) or []

    for obj in selected:
        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
        for shape in shapes:
            sgs = cmds.listConnections(shape, type="shadingEngine") or []
            for sg in sgs:
                shaders = cmds.listConnections(sg + ".surfaceShader") or []
                for shader in shaders:
                    if shader not in mats:
                        mats.append(shader)
    return mats


def collect_material_preset_data(mat):
    data = {
        "material": mat,
        "shaderType": cmds.nodeType(mat),
        "attributes": {},
    }

    for attr in MATERIAL_PRESET_ATTRS:
        if not cmds.attributeQuery(attr, node=mat, exists=True):
            continue

        value = cmds.getAttr(mat + "." + attr)
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        data["attributes"][attr] = value

    return data


def apply_material_preset_data(mat, data):
    attrs = data.get("attributes", {})
    for attr, value in attrs.items():
        if not cmds.attributeQuery(attr, node=mat, exists=True):
            continue

        if isinstance(value, (list, tuple)):
            if len(value) == 3 and all(isinstance(v, (int, float)) for v in value):
                cmds.setAttr(mat + "." + attr, value[0], value[1], value[2], type="double3")
            else:
                try:
                    cmds.setAttr(mat + "." + attr, *value)
                except Exception:
                    pass
        else:
            try:
                cmds.setAttr(mat + "." + attr, value)
            except Exception:
                pass


def export_material_preset(*_):
    mats = materials_from_selected_objects()
    if not mats:
        cmds.warning("Select mesh with assigned material to export preset")
        return

    path = cmds.fileDialog2(fileMode=0, caption="Export Material Preset", fileFilter="JSON (*.json)")
    if not path:
        return

    data = collect_material_preset_data(mats[0])
    with open(path[0], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    cmds.inViewMessage(amg="Material Preset Exported", pos="topCenter", fade=True)


def import_material_preset(*_):
    mats = materials_from_selected_objects()
    if not mats:
        cmds.warning("Select mesh with assigned material to import preset")
        return

    path = cmds.fileDialog2(fileMode=1, caption="Import Material Preset", fileFilter="JSON (*.json)")
    if not path:
        return

    with open(path[0], "r", encoding="utf-8") as f:
        data = json.load(f)

    for mat in mats:
        apply_material_preset_data(mat, data)

    cmds.inViewMessage(amg="Material Preset Imported", pos="topCenter", fade=True)


# =========================
# EXPORT / IMPORT
# =========================
def browse_export_path(*_):
    selected = cmds.fileDialog2(fileMode=3, caption="Select Export Folder")
    if selected:
        cmds.textField("export_path", e=True, text=selected[0])


def export_selected(*_):
    export_path = cmds.textField("export_path", q=True, text=True).strip()
    if not export_path:
        cmds.warning("Export path is empty")
        return

    if not os.path.exists(export_path):
        os.makedirs(export_path)

    fmt = "FBX" if cmds.radioButton("fmt_fbx", q=True, sl=True) else "OBJ"
    selected = cmds.ls(sl=True, long=False) or []
    if not selected:
        cmds.warning("No objects selected for export")
        return

    for obj in selected:
        output = os.path.join(export_path, obj.replace("|", "_") + (".fbx" if fmt == "FBX" else ".obj"))
        cmds.select(obj, r=True)
        if fmt == "FBX":
            cmds.file(output, force=True, options="v=0;", type="FBX export", exportSelected=True)
        else:
            cmds.file(
                output,
                force=True,
                options="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1",
                type="OBJexport",
                exportSelected=True,
            )

    cmds.inViewMessage(amg="Export DONE", pos="topCenter", fade=True)


def import_batch(*_):
    files = cmds.fileDialog2(fileMode=4, caption="Import Batch Files", fileFilter="Maya/Geo (*.ma *.mb *.fbx *.obj)")
    if not files:
        return

    for path in files:
        ext = os.path.splitext(path)[1].lower()
        file_type = "FBX" if ext == ".fbx" else "OBJ" if ext == ".obj" else None
        if file_type:
            cmds.file(path, i=True, type=file_type, ignoreVersion=True, ra=True, mergeNamespacesOnClash=False, namespace=":")
        else:
            cmds.file(path, i=True, ignoreVersion=True, ra=True, mergeNamespacesOnClash=False, namespace=":")

    cmds.inViewMessage(amg="Import Batch DONE", pos="topCenter", fade=True)


# =========================
# MAIN ACTIONS
# =========================
def collect_naming_inputs():
    return {
        "ip": cmds.textField("ip", q=True, text=True).strip(),
        "part": cmds.optionMenu("part", q=True, value=True),
        "category": cmds.optionMenu("cat", q=True, value=True),
        "detail_custom": cmds.textField("detail", q=True, text=True).strip(),
        "version": cmds.textField("ver", q=True, text=True).strip(),
        "prefix": cmds.optionMenu("prefix", q=True, value=True),
        "use_prefix": cmds.checkBox("use_prefix", q=True, v=True),
        "use_part": cmds.checkBox("use_part", q=True, v=True),
        "use_category": cmds.checkBox("use_category", q=True, v=True),
        "use_detail": cmds.checkBox("use_detail", q=True, v=True),
        "use_version": cmds.checkBox("use_version", q=True, v=True),
        "use_index": cmds.checkBox("use_index", q=True, v=True),
        "digits": 2 if cmds.radioButton("d2", q=True, sl=True) else 3,
    }


def build_material_name(obj_name):
    clean = "_".join(obj_name.split("_")[1:]) if "_" in obj_name else obj_name
    return "M_" + clean


def rename_selected(*_):
    values = collect_naming_inputs()
    detail = values["detail_custom"]
    selected = cmds.ls(sl=True) or []

    for i, obj in enumerate(selected):
        name = build_name(
            values["ip"],
            values["part"],
            values["category"],
            detail,
            values["version"],
            values["prefix"],
            values["use_prefix"],
            values["use_part"],
            values["use_category"],
            values["use_detail"],
            values["use_version"],
        )
        if values["use_index"] and len(selected) > 1:
            name += "_" + format_index(i, values["digits"])

        cmds.rename(obj, name)

    cmds.inViewMessage(amg="Rename DONE", pos="topCenter", fade=True)


def add_material_selected(*_):
    use_tex = cmds.checkBox("use_tex", q=True, v=True)
    selected = cmds.ls(sl=True) or []

    for obj in selected:
        mat_name = build_material_name(obj)
        mat = create_material(mat_name)
        apply_mat_type(mat, STATE["selected_material"])
        assign_material(obj, mat)

        if use_tex:
            connect_textures(mat)

    cmds.inViewMessage(amg="Add Material DONE", pos="topCenter", fade=True)


def apply_all(*_):
    rename_selected()
    add_material_selected()
    cmds.inViewMessage(amg="ALL DONE", pos="topCenter", fade=True)


# =========================
# UI
# =========================
def create_section_header(label, bgc):
    cmds.text(label=" " + label + " ", h=24, bgc=bgc, align="left")


def update_ui_state(*_):
    if cmds.checkBox("use_index", exists=True):
        use_index = cmds.checkBox("use_index", q=True, v=True)
        cmds.radioButton("d2", e=True, en=use_index)
        cmds.radioButton("d3", e=True, en=use_index)

    if cmds.checkBox("use_detail", exists=True):
        cmds.textField("detail", e=True, en=cmds.checkBox("use_detail", q=True, v=True))

    if cmds.checkBox("use_version", exists=True):
        cmds.textField("ver", e=True, en=cmds.checkBox("use_version", q=True, v=True))

    if cmds.checkBox("use_part", exists=True):
        cmds.optionMenu("part", e=True, en=cmds.checkBox("use_part", q=True, v=True))

    if cmds.checkBox("use_category", exists=True):
        cmds.optionMenu("cat", e=True, en=cmds.checkBox("use_category", q=True, v=True))

    if cmds.checkBox("use_tex", exists=True):
        use_tex = cmds.checkBox("use_tex", q=True, v=True)
        cmds.button("btn_select_tex", e=True, en=use_tex)
        cmds.button("btn_toggle_tex", e=True, en=use_tex)
        cmds.button("btn_relink_tex", e=True, en=use_tex)
        cmds.textScrollList("tex_detect", e=True, en=use_tex)




def add_tech_suffix(token, *_):
    selected = cmds.ls(sl=True) or []
    for obj in selected:
        short_name = obj.split("|")[-1]
        if not short_name.endswith("_" + token):
            cmds.rename(obj, short_name + "_" + token)

    cmds.inViewMessage(amg="Suffix Added: " + token, pos="topCenter", fade=True)




def del_first_char(*_):
    selected = cmds.ls(sl=True) or []
    for obj in selected:
        short_name = obj.split("|")[-1]
        if len(short_name) > 1:
            cmds.rename(obj, short_name[1:])
    cmds.inViewMessage(amg="Deleted first char", pos="topCenter", fade=True)


def del_last_char(*_):
    selected = cmds.ls(sl=True) or []
    for obj in selected:
        short_name = obj.split("|")[-1]
        if len(short_name) > 1:
            cmds.rename(obj, short_name[:-1])
    cmds.inViewMessage(amg="Deleted last char", pos="topCenter", fade=True)




def directory_upper(directory, up):
    normalized = directory.replace('\\', '/')
    parts = [p for p in normalized.split('/') if p]
    keep = max(0, len(parts) - up)
    target = '/'.join(parts[:keep])
    if normalized.startswith('/'):
        target = '/' + target
    if target and not target.endswith('/'):
        target += '/'
    return target


def open_directory_path(path):
    if not path:
        return
    norm = os.path.normpath(path)
    if os.path.isfile(norm):
        folder = os.path.dirname(norm)
        if os.name == 'nt':
            subprocess.Popen(['explorer', '/select,', norm])
        elif folder:
            subprocess.Popen(['xdg-open', folder])
    elif os.path.isdir(norm):
        if os.name == 'nt':
            os.startfile(norm)
        elif os.name == 'posix':
            subprocess.Popen(['xdg-open', norm])


def open_project_scene_directory(mode, *_):
    if mode == 0:
        path = cmds.textField('current_project', q=True, text=True)
    elif mode == 1:
        path = cmds.textField('current_scene', q=True, text=True)
        if path == 'not saved':
            return
    else:
        path = cmds.textField('target_project_path', q=True, text=True)
    open_directory_path(path)


def refresh_project_scene_info(mode=0, *_):
    current_project = cmds.workspace(q=True, rootDirectory=True)
    current_scene = cmds.file(q=True, sn=True)

    if current_scene:
        target_path = directory_upper(current_scene, 2)
    else:
        target_path = current_project
        current_scene = 'not saved'

    if cmds.textField('current_project', exists=True):
        cmds.textField('current_project', e=True, text=current_project)
    if cmds.textField('current_scene', exists=True):
        cmds.textField('current_scene', e=True, text=current_scene)

    if mode == 0 and cmds.textField('target_project_path', exists=True):
        cmds.textField('target_project_path', e=True, text=target_path)


def browse_target_project(*_):
    default_path = cmds.textField('target_project_path', q=True, text=True)
    selected = cmds.fileDialog2(fileMode=3, caption='Select Target Project Folder', dir=default_path)
    if selected and cmds.textField('target_project_path', exists=True):
        cmds.textField('target_project_path', e=True, text=selected[0])


def set_project_scene(*_):
    target = cmds.textField('target_project_path', q=True, text=True).strip()
    target = target.replace('\\', '/')
    if target and not target.endswith('/'):
        target += '/'
    cmds.textField('target_project_path', e=True, text=target)

    if not os.path.isdir(target):
        cmds.warning('Target path does not exist')
        return

    # Use Maya setProject so Save/Save As resolves under the selected target.
    mel.eval('setProject "{}"'.format(target.replace('"', '\\"')))
    cmds.workspace(target, openWorkspace=True)
    cmds.workspace(dir=target)
    if cmds.textField('current_project', exists=True):
        cmds.textField('current_project', e=True, bgc=(0.6, 0.8, 1.0))
    refresh_project_scene_info(1)
    cmds.inViewMessage(amg='Project Set -> Save As uses target path', pos='topCenter', fade=True)


def create_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(WINDOW_NAME, title="TT Naming Tool V5", w=460, h=760)
    cmds.columnLayout(adj=True, rs=8)

    tabs = cmds.tabLayout("main_tabs", innerMarginWidth=6, innerMarginHeight=6)

    # NAMING TAB (layout based on sketch)
    naming_tab = cmds.columnLayout(adj=True, rs=8)
    create_section_header("NAMING", (0.20, 0.34, 0.50))

    cmds.text(label="Character Name")
    cmds.textField("ip", text="NYX01", h=30)

    cmds.rowLayout(nc=2, adjustableColumn=1, columnWidth2=(220, 220))
    cmds.frameLayout(labelVisible=False, bgc=(0.30, 0.30, 0.30), marginHeight=6, marginWidth=6)
    cmds.rowLayout(nc=2, adjustableColumn=1)
    cmds.checkBox("use_part", label="Use Part", v=False, cc=update_ui_state)
    cmds.optionMenu("part", w=160)
    for value in PART_OPTIONS:
        cmds.menuItem(label=value)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(labelVisible=False, bgc=(0.30, 0.30, 0.30), marginHeight=6, marginWidth=6)
    cmds.rowLayout(nc=2, adjustableColumn=1)
    cmds.checkBox("use_category", label="Use Category", v=False, cc=update_ui_state)
    cmds.optionMenu("cat", w=160)
    for value in CATEGORY_OPTIONS:
        cmds.menuItem(label=value)
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(labelVisible=False, bgc=(0.18, 0.30, 0.45), marginHeight=6, marginWidth=6)
    cmds.rowLayout(nc=8, adjustableColumn=2)
    cmds.checkBox("use_prefix", label="Use Prefix", v=False)
    cmds.optionMenu("prefix", w=80)
    for pfx in ["SK", "SM", "T", "M", "GRP"]:
        cmds.menuItem(label=pfx)

    cmds.checkBox("use_detail", label="Use Detail", v=False, cc=update_ui_state)
    cmds.textField("detail", text="", w=80)

    cmds.checkBox("use_version", label="Use Version", v=False, cc=update_ui_state)
    cmds.textField("ver", text="v01", w=60)

    cmds.checkBox("use_index", label="Index", v=False, cc=update_ui_state)
    cmds.radioCollection()
    cmds.rowLayout(nc=2)
    cmds.radioButton("d2", label="01", sl=True)
    cmds.radioButton("d3", label="001")
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(labelVisible=False, bgc=(0.26, 0.26, 0.26), marginHeight=6, marginWidth=6)
    cmds.rowLayout(nc=2, adjustableColumn=1)

    cmds.columnLayout(adj=True, rs=4)
    cmds.text(label="Add Suffix")
    cmds.gridLayout(numberOfColumns=5, cellWidthHeight=(74, 26))
    for token in ["Low", "High", "CTRL", "GEO", "GRP", "L", "R", "Center", "UV", "TEX", "LOD0"]:
        cmds.button(label="+ " + token, c=lambda _, t=token: add_tech_suffix(t))
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.columnLayout(adj=True, rs=6)
    cmds.separator(h=24, style="none")
    cmds.button(label="Del First Char", h=32, c=del_first_char)
    cmds.button(label="Del Last Char", h=32, c=del_last_char)
    cmds.setParent("..")

    cmds.setParent("..")
    cmds.setParent("..")

    cmds.button(label="RENAMING", h=46, bgc=(0.45, 0.56, 0.73), c=rename_selected)
    cmds.setParent("..")

    # MATERIAL TAB
    material_tab = cmds.columnLayout(adj=True, rs=6)
    create_section_header("MATERIAL", (0.28, 0.22, 0.42))
    cmds.text(label="Shader Model")
    cmds.optionMenu("shader_model")
    for shader in ["Arnold", "Blind", "Phong"]:
        cmds.menuItem(label=shader)

    cmds.text(label="Material Library")
    cmds.text(label="Skin = Arnold Face Beauty preset", align="left")
    cmds.gridLayout(numberOfColumns=2, cellWidthHeight=(210, 32))
    for mat_type in MATERIAL_TYPES:
        cmds.button(
            "mat_btn_" + mat_type,
            label=mat_type,
            bgc=(0.35, 0.55, 0.35) if mat_type == "Default" else (0.2, 0.2, 0.2),
            c=lambda _, m=mat_type: select_material_type(m),
        )
    cmds.setParent("..")

    cmds.text(label="LookDev Material")
    cmds.gridLayout(numberOfColumns=2, cellWidthHeight=(210, 30))
    for label in ["GREY BALL", "CHROME BALL"]:
        cmds.button(label=label, c=lambda _, n=label: apply_lookdev_material(n))
    cmds.setParent("..")

    cmds.rowLayout(nc=2, adjustableColumn=1)
    cmds.button(label="Export Mat Preset", c=export_material_preset)
    cmds.button(label="Import Mat Preset", c=import_material_preset)
    cmds.setParent("..")

    cmds.button(label="ADD MATERIAL", h=42, bgc=(0.73, 0.54, 0.40), c=add_material_selected)
    cmds.setParent("..")

    # TEXTURE TAB
    texture_tab = cmds.columnLayout(adj=True, rs=6)
    create_section_header("TEXTURE", (0.45, 0.30, 0.20))
    cmds.text(label="Parse name -> map type -> color space -> connect")
    cmds.checkBox("use_tex", label="Use Texture", v=False, cc=update_ui_state)
    cmds.button("btn_select_tex", label="Select Files (Multi)", c=select_texture_files)
    cmds.rowLayout(nc=2, adjustableColumn=1)
    cmds.button("btn_toggle_tex", label="Toggle ON/OFF", c=toggle_selected_texture_map)
    cmds.button("btn_relink_tex", label="Relink Selected", c=relink_selected_texture_map)
    cmds.setParent("..")
    cmds.textScrollList("tex_detect", h=280, allowMultiSelection=False)
    cmds.setParent("..")

    # PROJECT SCENE TAB
    project_tab = cmds.columnLayout(adj=True, rs=6)
    create_section_header("PROJECT SCENE", (0.24, 0.34, 0.28))

    cmds.rowLayout(nc=2, adjustableColumn=2)
    cmds.button(label='Current Project', w=120, c=lambda *_: open_project_scene_directory(0))
    cmds.textField('current_project', editable=False)
    cmds.setParent('..')

    cmds.rowLayout(nc=2, adjustableColumn=2)
    cmds.button(label='Current Scene', w=120, c=lambda *_: open_project_scene_directory(1))
    cmds.textField('current_scene', editable=False)
    cmds.setParent('..')

    cmds.separator(h=10, style='in')

    cmds.rowLayout(nc=3, adjustableColumn=2)
    cmds.button(label='Target Path', w=120, c=lambda *_: open_project_scene_directory(2))
    cmds.textField('target_project_path', text='')
    cmds.button(label='...', w=30, c=browse_target_project)
    cmds.setParent('..')

    cmds.rowLayout(nc=2, adjustableColumn=1)
    cmds.button(label='Reload', h=34, c=lambda *_: refresh_project_scene_info(0))
    cmds.button(label='Project Set', h=34, c=set_project_scene)
    cmds.setParent('..')
    cmds.setParent('..')

    # EXPORT/IMPORT TAB
    io_tab = cmds.columnLayout(adj=True, rs=6)
    create_section_header("EXPORT / IMPORT", (0.28, 0.36, 0.36))
    cmds.radioCollection()
    cmds.rowLayout(nc=2)
    cmds.radioButton("fmt_fbx", label="FBX", sl=True)
    cmds.radioButton("fmt_obj", label="OBJ")
    cmds.setParent("..")

    cmds.text(label="Export Path")
    cmds.rowLayout(nc=2, adjustableColumn=1)
    cmds.textField("export_path", text="")
    cmds.button(label="Browse", c=browse_export_path)
    cmds.setParent("..")

    cmds.button(label="Import Batch", h=34, c=import_batch)
    cmds.button(label="Export Selected", h=34, c=export_selected)
    cmds.setParent("..")

    cmds.tabLayout(
        tabs,
        e=True,
        tabLabel=[
            (naming_tab, "Naming"),
            (material_tab, "Material"),
            (texture_tab, "Texture"),
            (io_tab, "Export/Import"),
            (project_tab, "Project Scene"),
        ],
    )

    refresh_project_scene_info(0)
    update_ui_state()
    cmds.showWindow()


create_ui()
