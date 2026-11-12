"""Données des kits de décor (sans bpy) : palettes, habillage par défaut, repères nommés."""

PALETTES = {
    "living_room": {"wall": "#F3D9B1", "floor": "#B5835A", "accent": "#E76F51"},
    "kitchen": {"wall": "#CDEAC0", "floor": "#D9C9A3", "accent": "#F4A261"},
    "bedroom": {"wall": "#C9D7F8", "floor": "#A9744F", "accent": "#8E7DBE"},
    "bathroom": {"wall": "#9FD1F5", "floor": "#C9D6DF", "accent": "#48CAE4"},
    "office": {"wall": "#D7E3EE", "floor": "#7D8C9C", "accent": "#457B9D"},
    "street": {"wall": "#E9C46A", "floor": "#BFBFBF", "accent": "#E63946", "sky": "#8ECAE6"},
    "park": {"wall": "#8ECAE6", "floor": "#7CB518", "accent": "#FFB703", "sky": "#8ECAE6"},
    "supermarket": {"wall": "#FFE5D9", "floor": "#C9CED4", "accent": "#D62828"},
    "studio_void": {"wall": "#FFD6A5", "floor": "#FFD6A5", "accent": "#FF006E"},
    "restaurant": {"wall": "#F2CC8F", "floor": "#8D5A3B", "accent": "#9D0208"},
    "classroom": {"wall": "#FFF1B5", "floor": "#C9A27E", "accent": "#2A9D8F"},
    "beach": {"wall": "#90E0EF", "floor": "#F4D58D", "accent": "#F72585", "sky": "#48CAE4"},
    "car_interior": {"wall": "#3D405B", "floor": "#2B2D42", "accent": "#E07A5F", "sky": "#8ECAE6"},
    "generic_interior": {"wall": "#E9EDC9", "floor": "#A3B18A", "accent": "#588157"},
    "generic_exterior": {"wall": "#8ECAE6", "floor": "#A7C957", "accent": "#F2E8CF", "sky": "#8ECAE6"},
}

BASE_MARKS = {"center": (0.0, 0.0), "left": (-1.3, 0.0), "right": (1.3, 0.0), "back": (0.0, 1.5), "front": (0.0, -1.2),
              "far_left": (-2.4, 0.6), "far_right": (2.4, 0.6), "offscreen_left": (-6.0, 0.0), "offscreen_right": (6.0, 0.0)}

# (type, x, y, rot_deg, extra)
KIT_DRESSING = {
    "living_room": [("rug", 0, 0.6, 0), ("sofa", 0, 2.25, 0), ("tv", -3.1, 0.9, -90), ("plant", 3.3, 2.5, 0), ("lamp", -1.7, 2.5, 0),
                    ("painting", -1.9, 2.92, 0), ("window", 1.9, 2.92, 0), ("door", 3.4, 2.9, 0)],
    "kitchen": [("counter", -0.4, 2.55, 0), ("stove", -2.3, 2.55, 0), ("fridge", 2.5, 2.5, 0), ("window", -0.4, 2.92, 0),
                ("table", 2.0, 0.4, 0), ("chair", 2.0, 1.1, 180), ("plant", -3.3, 2.4, 0)],
    "bedroom": [("bed", -1.9, 1.7, 0), ("rug", 0.3, 0.4, 0), ("lamp", -0.6, 2.6, 0), ("window", 1.4, 2.92, 0), ("painting", -1.9, 2.92, 0),
                ("plant", 3.2, 2.5, 0), ("door", 3.3, 2.9, 0)],
    "bathroom": [("toilet", -1.6, 2.55, 0), ("counter", 1.4, 2.6, 0, 0.55), ("painting", 1.4, 2.92, 0), ("plant", 3.3, 2.5, 0)],
    "office": [("desk", -1.7, 1.6, 0), ("computer", -1.7, 1.65, 0, 1.0, 0.76), ("chair", -1.7, 1.0, 180), ("desk", 1.7, 1.6, 0),
               ("computer", 1.7, 1.65, 0, 1.0, 0.76), ("chair", 1.7, 1.0, 180), ("shelf", 0, 2.75, 0), ("plant", 3.3, 2.5, 0),
               ("window", -2.7, 2.92, 0), ("window", 2.7, 2.92, 0)],
    "street": [("streetlight", -2.8, 1.2, 0),
               ("streetlight", 3.2, 1.2, 0), ("trash_can", 2.2, 1.1, 0), ("tree", -4.5, 1.5, 0), ("sign", 4.4, 1.2, 0), ("bench", -1.5, 1.4, 0)],
    "park": [("tree", -2.8, 2.8, 0), ("tree", 3.2, 3.4, 0), ("tree", 0.6, 6.5, 0), ("bush", -4.2, 1.2, 0), ("bush", 4.5, 1.8, 0),
             ("bench", 0.2, 2.3, 0), ("streetlight", -1.6, 2.4, 0), ("trash_can", 1.6, 2.4, 0)],
    "supermarket": [("shelf", -2.5, 2.7, 0), ("shelf", -1.25, 2.7, 0), ("shelf", 0.0, 2.7, 0), ("shelf", 1.25, 2.7, 0), ("shelf", 2.5, 2.7, 0),
                    ("shelf", -3.6, 1.2, 90), ("shelf", 3.6, 1.2, -90), ("shopping_cart", 1.9, 0.9, 30), ("box", -1.9, 1.6, 15), ("box", -2.2, 1.9, -10)],
    "studio_void": [],
    "restaurant": [("restaurant_table", -2.3, 1.0, 0), ("chair", -2.3, 1.6, 180), ("chair", -2.9, 0.6, -60), ("restaurant_table", 2.3, 1.0, 0),
                   ("chair", 2.3, 1.6, 180), ("chair", 2.9, 0.6, 60), ("restaurant_table", -1.0, 2.5, 0), ("chair", -1.6, 2.5, -90),
                   ("counter", 1.6, 2.6, 0, 0.9), ("cooking_pot", 1.2, 2.6, 0, 1.0, 0.83), ("menu_board", 3.3, 2.3, -20),
                   ("wine_glass", -2.1, 0.9, 0, 1.0, 0.78), ("plate_food", -2.45, 1.05, 0, 1.0, 0.78), ("wine_glass", 2.1, 0.9, 0, 1.0, 0.78),
                   ("plate_food", 2.45, 1.05, 0, 1.0, 0.78), ("plant", -3.4, 2.5, 0), ("window", -0.9, 2.92, 0)],
    "classroom": [("blackboard", 0.0, 2.92, 0), ("desk", -1.9, 2.1, 0), ("school_desk", -2.6, 0.2, 60), ("chair", -2.95, 0.0, -120),
                  ("school_desk", -2.6, 1.3, 60), ("school_desk", 2.6, 0.2, -60), ("chair", 2.95, 0.0, 120), ("school_desk", 2.6, 1.3, -60),
                  ("globe", -1.6, 2.1, 0, 1.0, 0.76), ("backpack", 2.2, -0.3, 30), ("window", 3.3, 2.92, 0), ("plant", -3.4, 2.5, 0)],
    "beach": [("palm_tree", -3.2, 2.5, 0), ("palm_tree", 3.6, 3.2, 40), ("parasol", 1.8, 1.4, 0), ("beach_towel", 1.4, 1.1, 10),
              ("beach_towel", -1.6, 1.6, -15), ("sandcastle", -0.9, 0.6, 0), ("cooler", 2.4, 1.6, 20), ("beach_ball", 0.9, 2.4, 0),
              ("lifeguard_tower", -4.0, 5.5, 15), ("surfboard", 3.0, 2.1, 30)],
    "car_interior": [],
    "generic_interior": [],
    "generic_exterior": [],
}

KIT_MARKS = {
    "living_room": {"couch": (0.0, 1.85), "tv": (-2.4, 0.9), "door": (3.4, 2.3), "window": (1.9, 2.3)},
    "kitchen": {"counter": (-0.4, 1.9), "stove": (-2.3, 1.9), "fridge": (2.5, 1.8), "table": (2.0, -0.3)},
    "bedroom": {"bed": (-1.9, 0.6), "door": (3.3, 2.3), "window": (1.4, 2.3)},
    "bathroom": {"toilet": (-1.6, 2.0), "sink": (1.4, 2.0)},
    "office": {"desk_left": (-1.7, 0.7), "desk_right": (1.7, 0.7), "shelf": (0.0, 2.2)},
    "street": {"sidewalk_left": (-1.5, 0.0), "sidewalk_right": (1.5, 0.0), "road": (0.0, 3.8), "bench": (-1.5, 0.9)},
    "park": {"bench": (0.2, 1.8), "tree": (-2.6, 2.0), "path": (0.0, 0.5)},
    "supermarket": {"aisle": (0.0, 1.6), "cart": (1.5, 0.0)},
    "studio_void": {},
    "restaurant": {"table_left": (-2.3, 0.4), "table_right": (2.3, 0.4), "kitchen_pass": (1.4, 1.9), "entrance": (3.3, 0.6)},
    "classroom": {"teacher": (0.0, 1.9), "blackboard": (0.0, 2.4), "desk_left": (-2.2, 0.6), "desk_right": (2.2, 0.6)},
    "beach": {"towel": (-1.6, 1.0), "parasol": (1.4, 0.8), "sandcastle": (-0.9, 0.0), "water_edge": (0.0, 5.5)},
    "car_interior": {"driver": (-0.42, 0.25), "passenger": (0.42, 0.25), "back_left": (-0.42, 1.15), "back_right": (0.42, 1.15)},
    "generic_interior": {},
    "generic_exterior": {},
}

INTERIOR = {"living_room", "kitchen", "bedroom", "bathroom", "office", "supermarket", "restaurant", "classroom", "generic_interior"}


# Style des surfaces : (motif du sol, motif des murs, couleur secondaire du sol | None, soubassement)
SURFACES = {
    "living_room": ("planks", "stripes", None, True),
    "kitchen": ("tiles", "noise", "#C4B28A", True),
    "bedroom": ("planks", "stripes", None, True),
    "bathroom": ("tiles", "tiles", "#B3C4CF", False),
    "office": ("noise", "noise", None, False),
    "supermarket": ("tiles", "noise", "#B5BCC4", False),
    "restaurant": ("planks", "noise", None, True),
    "classroom": ("planks", "noise", None, True),
}

# Objets muraux d'ambiance (mur du fond) : (type, x, z, largeur/paramètre)
WALL_DECOR = {
    "living_room": [("clock", 0.0, 2.45, 0), ("shelf", -3.0, 1.75, 0.9), ("poster", -0.95, 1.85, 0.45), ("poster", 0.95, 1.9, 0.38),
                    ("curtains", 1.9, 1.55, 1.3), ("pendant", 0.0, 1.2, 0)],
    "kitchen": [("cabinet", -2.3, 2.2, 1.2), ("cabinet", 1.25, 2.2, 1.0), ("clock", -0.4, 2.62, 0), ("shelf", -3.3, 1.55, 0.7),
                ("curtains", -0.4, 1.55, 1.3), ("pendant", 0.4, 1.0, 0), ("poster", 3.45, 1.9, 0.4)],
    "bedroom": [("poster", 0.1, 1.8, 0.5), ("poster", 2.7, 1.7, 0.4), ("shelf", -0.2, 2.35, 1.0), ("curtains", 1.4, 1.55, 1.3),
                ("pendant", 0.0, 1.0, 0)],
    "bathroom": [("shelf", -1.6, 1.5, 0.8), ("clock", 0.0, 2.3, 0), ("poster", -0.2, 1.6, 0.35)],
    "office": [("clock", 0.0, 2.55, 0), ("poster", -1.3, 1.75, 0.55), ("poster", 1.3, 1.75, 0.55), ("pendant", -1.7, 1.2, 0),
               ("pendant", 1.7, 1.2, 0)],
    "supermarket": [("pendant", -1.2, 0.5, 0), ("pendant", 1.2, 0.5, 0), ("pendant", -1.2, 2.2, 0), ("pendant", 1.2, 2.2, 0)],
    "restaurant": [("pendant", -2.3, 1.0, 0), ("pendant", 2.3, 1.0, 0), ("pendant", -1.0, 2.5, 0), ("shelf", 1.6, 2.0, 1.2),
                   ("poster", -2.4, 1.85, 0.5), ("poster", 3.1, 1.95, 0.4), ("clock", 0.4, 2.55, 0), ("curtains", -0.9, 1.55, 1.3)],
    "classroom": [("clock", 1.8, 2.6, 0), ("poster", -2.4, 1.8, 0.5), ("poster", 2.0, 1.75, 0.45), ("shelf", -3.0, 1.5, 0.8),
                  ("pendant", -1.2, 1.0, 0), ("pendant", 1.2, 1.0, 0)],
}

# Zones de petits objets posés : (x_min, x_max, y, hauteur de surface, nombre, types)
CLUTTER = {
    "kitchen": [(-1.45, 0.65, 2.45, 0.92, 6, ("jar", "bottle", "plates", "board", "bowl", "jar")), (1.6, 2.4, 0.4, 0.76, 2, ("bowl", "mug"))],
    "living_room": [],
    "office": [(-2.35, -1.25, 1.55, 0.76, 2, ("mug", "books")), (1.25, 2.35, 1.55, 0.76, 2, ("books", "mug"))],
    "bathroom": [(1.0, 1.8, 2.55, 0.5, 3, ("bottle", "jar", "bottle"))],
}
