"""Vocabulaire officiel du moteur. N'importe PAS bpy : utilisé aussi par les tests et le pipeline.

Les tests vérifient que ces listes sont identiques aux enums des schémas JSON :
toute capacité déclarée dans un contrat est réellement implémentée par le moteur.
"""

ENGINE_VERSION = "0.5.0"

HAIR_STYLES = ["none", "short", "spiky", "bowl", "mohawk", "bun", "long", "curly"]
TOPS = ["tshirt", "shirt", "hoodie", "suit", "dress", "tank"]
BOTTOMS = ["pants", "shorts", "skirt"]
ACCESSORIES = ["cap", "glasses", "sunglasses", "tie", "bowtie", "mustache", "beard", "chef_hat", "headband", "earrings", "crown"]
NOSES = ["round", "long", "pointy", "potato"]
EXPRESSIONS = ["neutral", "happy", "laugh", "sad", "angry", "shocked", "scared", "smug", "disgusted", "confused", "deadpan", "crying", "evil_grin", "love"]
ACTIONS = ["idle", "walk_to", "run_to", "turn_to", "look_at", "wave", "point", "shrug", "facepalm", "jump", "shocked_jump",
           "fall_back", "slip_fall", "cower", "stomp", "celebrate", "dance", "sit", "stand_up", "throw", "flail", "nod",
           "shake_head", "take_hit", "faint", "arms_crossed", "hands_on_hips", "lean_in", "talk_gesture"]
PROP_ACTIONS = ["attach", "detach", "appear", "disappear", "throw", "fall", "shake", "explode", "spin"]
FX = ["smoke_puff", "explosion", "sparkles", "impact_star", "sweat_drops", "question_marks", "hearts"]
KITS = ["living_room", "kitchen", "bedroom", "bathroom", "office", "street", "park", "supermarket", "studio_void",
        "restaurant", "classroom", "beach", "car_interior", "generic_interior", "generic_exterior"]
PROP_TYPES = ["sofa", "table", "chair", "tv", "fridge", "stove", "counter", "toaster", "plant", "lamp", "door", "window", "car",
              "tree", "bush", "bench", "desk", "computer", "phone", "mug", "bed", "toilet", "box", "trash_can", "cake", "sign",
              "pigeon", "cat", "frying_pan", "fire_extinguisher", "shopping_cart", "shelf", "rug", "streetlight", "building", "painting",
              "restaurant_table", "wine_glass", "plate_food", "menu_board", "cooking_pot", "school_desk", "blackboard", "backpack",
              "globe", "parasol", "beach_towel", "sandcastle", "palm_tree", "beach_ball", "surfboard", "cooler",
              "lifeguard_tower", "dog", "chicken", "duck", "rat", "fish", "cow", "guitar",
              "pizza", "burger", "trophy", "money_stack", "skateboard", "bucket", "custom", "composite"]
MOODS = ["day_warm", "day_cool", "night", "interior_warm", "office_flat", "dramatic", "spooky", "sunset"]
FRAMINGS = ["wide", "full", "medium", "medium_close", "close_up", "extreme_close_up", "two_shot", "over_shoulder", "insert"]
ANGLES = ["eye", "low", "high", "dutch", "top_down"]
MOVES = ["static", "push_in", "pull_out", "pan_left", "pan_right", "orbit_left", "orbit_right", "track_subject", "shake", "crash_zoom", "handheld"]
TRANSITIONS = ["cut", "whip", "smash_cut", "fade_black", "flash_white"]

ANIMALS = ["pigeon", "cat", "dog", "chicken", "duck", "rat", "fish", "cow"]
EXTERNAL_FORMATS = [".glb", ".gltf", ".obj"]
COMPOSITE_SHAPES = ["box", "ball", "cyl", "cone", "torus", "text"]
SURFACE_PATTERNS = ["planks", "tiles", "noise", "grass", "bricks", "wood", "stripes"]
BACKDROPS = ["skyline", "hills", "trees", "sea", "clouds"]
