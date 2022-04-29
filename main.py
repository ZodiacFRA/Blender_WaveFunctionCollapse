import bpy
import json
import time
import math
import random
from pprint import pprint
from mathutils import Matrix

X_GRID_SIZE = 8
Y_GRID_SIZE = 8
Z_GRID_SIZE = 8
MAX_CONSECUTIVE_OVERRIDES = 20

JSON_MODULES_DATA_PATH = "/home/zodiac/Code/Perso/Trackmania-WFC/path.json"
CELLS_MODIFICATIONS_HISTORY_PATH = "/home/zodiac/Code/Perso/Trackmania-WFC/output.txt"


class App(object):
    def __init__(self):
        clean_blender_scene()
        # Constants
        seed = random.randint(0, 100)
        random.seed(seed)
        print("Seed:", seed)
        self.deltaTime = 0.0001
        self.endTime = time.time()

        self.handle_modules_creation()
        self.handle_map_creation()
        # Creates a collection in which all created blocks will go
        create_blender_collection("Output")
        # Perform WFC on the map
        self.waveshift_function_collapse()
        self.log()

    def handle_modules_creation(self):
        # Creates a "Generated modules" collection where all the rotations
        # of all the modules (including 0, which does not actually rotates the object)
        # will go during modules data loading
        create_blender_collection("Generated modules")
        # Load all the modules data from the json
        self.modules = {}
        self.socket_types_count = 0
        self.load_modules_data(JSON_MODULES_DATA_PATH)
        self.create_links()
        print(f"{len(self.modules)} modules, {self.socket_types_count + 1} socket types")
        vlayer = bpy.context.scene.view_layers['View Layer']
        vlayer.layer_collection.children['Generated modules'].hide_viewport = True

        # Modules data recording
        self.last_chosen_module = None
        self.overrides_count = 0
        self.consecutive_overrides_count = 0
        self.impossible_positions_count = 0

    def handle_map_creation(self):
        # Initialize map
        self.map = []
        self.cells_modifications_history = {}
        for x in range(X_GRID_SIZE):
            tmpY = []
            for y in range(Y_GRID_SIZE):
                tmpZ = []
                for z in range(Z_GRID_SIZE):
                    # Add one single cell, z times
                    self.cells_modifications_history[Vector3(x, y, z).__repr__()] = []
                    tmpZ.append(set([m for m in self.modules.values()]))
                # Add one single line, y times
                tmpY.append(tmpZ)
            # Add one single plane, x times
            self.map.append(tmpY)

    def log(self):
        # Logging
        self.display_map()
        pprint(list(self.modules.values()))
        print(f"{self.overrides_count} overrides")
        print(f"{(self.impossible_positions_count/(X_GRID_SIZE * Y_GRID_SIZE * Z_GRID_SIZE) * 100):.2f}% ({self.impossible_positions_count}/{X_GRID_SIZE * Y_GRID_SIZE * Z_GRID_SIZE}) impossible positions")
        # Write cell modifications history to a text file
        with open(CELLS_MODIFICATIONS_HISTORY_PATH, 'w') as f:
            for cell_pos, modifications in self.cells_modifications_history.items():
                f.write(f"{cell_pos}\n")
                for modification in modifications:
                    f.write(f"\t{modification}\n")


#########################################
# Utility functions
    def load_modules_data(self, filepath):
        with open(filepath, "r") as f:
            modules_data = json.load(f)

        x_pos = 0
        # Create all modules
        for module in modules_data:
            # Only needed to get total socket_types_count
            for directions in module["sockets"]:
                for socket_type in directions:
                    if socket_type > self.socket_types_count:
                        self.socket_types_count = socket_type
            y_pos = 0
            # Create all the rotated meshes
            if module["rotations"][0] == -1:
                module["rotations"] = [idx for idx in range(23)]
            for rotation in module["rotations"]:
                name = f"""{module["module_name"]}_{rotation}"""
                self.modules[name] = Module(name, module, rotation, Vector3(x_pos, y_pos, 0))
                y_pos += 1

            x_pos += 1

    def create_links(self):
        # For each module
        for a_name, a_module in self.modules.items():
            # For each direction
            for direction, matching_cell_socket_types in enumerate(a_module.sockets):
                # For each matching socket type (each direction can have multiple socket types)
                for a_socket_type in matching_cell_socket_types:
                    # Add all matching sockets
                    for b_name, b_module in self.modules.items():
                        b_socket_types = b_module.sockets[self.get_opposite_direction(direction)]
                        if a_socket_type in b_socket_types:
                            self.create_link(a_module, direction, b_module)

    def create_link(self, nodeA, direction, nodeB):
        nodeA.create_link(nodeB, direction)
        direction = self.get_opposite_direction(direction)
        nodeB.create_link(nodeA, direction)

    def get_opposite_direction(self, dir): #perhaps here
        return (dir + 3) % 6

    def choose_module_from_possibilities(self, cell, possible_modules, type="lowest"):
        if type == "lowest":
            res = []
            lowest = X_GRID_SIZE * Y_GRID_SIZE * Z_GRID_SIZE
            for module in possible_modules:
                if module.count < lowest:
                    lowest = module.count
                    res = [module]
                elif module.count == lowest:
                    res.append(module)
        elif type == "override":
            res = list(possible_modules)
            if self.last_chosen_module and self.last_chosen_module in possible_modules:
                # print(self.last_chosen_module.self_attraction)
                if self.last_chosen_module.self_attraction:
                    self.overrides_count += 1
                    self.consecutive_overrides_count += 1
                    if self.consecutive_overrides_count < MAX_CONSECUTIVE_OVERRIDES:
                        return self.last_chosen_module
            self.consecutive_overrides_count = 0
        return random.choice(res)


#########################################
# WFC algorithm functions
    def waveshift_function_collapse(self):
        while 1:
            # Get the next cell to update
            cell = self.get_minimal_entropy_cell()
            if cell is None:
                break
            module = self.choose_module_from_possibilities(
                cell, self.map[cell.x][cell.y][cell.z], "lowest"
            )
            self.last_chosen_module = module
            module.count += 1
            # Assign cell
            self.cells_modifications_history[cell.__repr__()].append(f"Assigned {module} from {self.map[cell.x][cell.y][cell.z]} possible modules")
            self.map[cell.x][cell.y][cell.z] = {module}
            # duplicate_and_place_object(module.name, cell)
            # Now propagate to neighbors
            self.update_possibilities(cell, 20)

    def update_possibilities(self, cell, depth):
        # End of recursion conditions
        # if depth == 0:
        #     return
        to_be_updated_neighbors = set()
        # Top
        neighbor = Vector3(cell.x, cell.y, cell.z + 1)
        if cell.z < Z_GRID_SIZE - 1 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 0))
        # Bottom
        neighbor = Vector3(cell.x, cell.y, cell.z - 1)
        if cell.z > 0 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 3))
        # Front
        neighbor = Vector3(cell.x, cell.y - 1, cell.z)
        if cell.y > 0 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 4))
        # Back
        neighbor = Vector3(cell.x, cell.y + 1, cell.z)
        if cell.y < Y_GRID_SIZE - 1 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 1))
        # Left
        neighbor = Vector3(cell.x - 1, cell.y, cell.z)
        if cell.x > 0 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 5))
        # Right
        neighbor = Vector3(cell.x + 1, cell.y, cell.z)
        if cell.x < X_GRID_SIZE - 1 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 2))

        # Propagate the collapse to neighbor which had changes
        for neighbor in to_be_updated_neighbors:
            self.update_possibilities(neighbor, depth - 1)

    def update_neighbor(self, cell, neighbor, direction):
        out = set()
        a_possible_neighbors = set()
        cell_states = self.map[cell.x][cell.y][cell.z]
        # For each possible module of the cell
        for cell_state in cell_states:
            # Add the possibilities based on this direction
            for possible_neighbor in cell_state.links[direction]:
                a_possible_neighbors.add(possible_neighbor)
        ########
        # Remove impossible modules
        tmp = set()
        # For each possible module in the neighbor, remove impossible modules
        for neighbor_state in self.map[neighbor.x][neighbor.y][neighbor.z]:
            if neighbor_state in a_possible_neighbors:
                    tmp.add(neighbor_state)
        # Add the neighbor to the to-be-updated neighbors list if a change has been made
        if set(self.map[neighbor.x][neighbor.y][neighbor.z]) != tmp:
            self.cells_modifications_history[neighbor.__repr__()].append(f"Updated to {tmp} from {self.map[neighbor.x][neighbor.y][neighbor.z]}, because of {cell} with modules {cell_states}")
            self.map[neighbor.x][neighbor.y][neighbor.z] = tmp

            out.add(neighbor)
        return out

    def get_minimal_entropy_cell(self):
        """ Returns the cell with the lowest entropy of all, if multiple cells
        have the same entropy, choose one at random """
        minimal_entropy = len(self.modules)
        minimal_entropy_cells = []
        tmp_count = 0
        for x in range(X_GRID_SIZE):
            for y in range(Y_GRID_SIZE):
                for z in range(Z_GRID_SIZE):
                    # Ignore already finished cells
                    if len(self.map[x][y][z]) < 2:
                        tmp_count += 1
                        continue
                    # Lower entropy found
                    elif len(self.map[x][y][z]) < minimal_entropy:
                        minimal_entropy = len(self.map[x][y][z])
                        minimal_entropy_cells = [Vector3(x, y, z)]
                    # Add to the list of lowest entropy cells
                    elif len(self.map[x][y][z]) == minimal_entropy:
                        minimal_entropy_cells.append(Vector3(x, y, z))

        if len(minimal_entropy_cells) > 0:
            # Choose a random minimum entropy cell
            return random.choice(minimal_entropy_cells)
        return None

#########################################
# Blender functions
    def display_map(self):
        for x in range(X_GRID_SIZE):
            for y in range(Y_GRID_SIZE):
                for z in range(Z_GRID_SIZE):
                    pos = Vector3(x,y,z)
                    states = self.map[x][y][z]
                    states_count = len(states)
                    if states_count == 1:
                        duplicate_and_place_object(states.pop().name, pos)
                    elif states_count == 0:
                        self.impossible_positions_count += 1
                    elif states_count > 1:
                        print(f"ignored: {pos} due to cell not collapsed (states: {states})")

## Non part of the class
def clean_blender_scene():
    """
    - The scene is supposed to have a "Modules" collection, which will be left
    untouched
    - All other collections will be deleted
    - Purge orphan data
    """
    for collection in bpy.data.collections:
        if collection.name != "Modules":
            # Delete all the objects
            for obj in collection.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(collection)
    # Purge orphan data
    for block in bpy.data.objects:
        if block.users == 0:
            bpy.data.objects.remove(block)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.textures:
        if block.users == 0:
            bpy.data.textures.remove(block)
    for block in bpy.data.images:
        if block.users == 0:
            bpy.data.images.remove(block)


def create_blender_collection(collection_name):
    collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(collection)


def duplicate_and_place_object(object_name, position):
    if not object_name:
        return
    # the new object is created with the old object's data, which makes it "linked"
    new_obj = bpy.data.objects.new(f"{object_name}_{position}", bpy.data.objects[object_name].data)
    # now it's just an object ref and you can move it to an absolute position
    new_obj.location = (position.x * 2, position.y * 2, position.z * 2)
    # when you create a new object manually this way it's not part of any collection, add it to the active collection so you can actually see it in the viewport
    bpy.data.collections['Output'].objects.link(new_obj)


def blender_rotate(ob, rotation):
    ob.rotation_euler[0] = math.radians(rotation.x)
    ob.rotation_euler[1] = math.radians(rotation.y)
    ob.rotation_euler[2] = math.radians(rotation.z)
    bpy.data.objects[ob.name].select_set(True)
    bpy.ops.object.transform_apply(rotation=True)
    bpy.data.objects[ob.name].select_set(False)

ROTATIONS = [
"",
"X",
"Y",
"XX",
"XY",
"YX",
"YY",
"XXX",
"XXY",
"XYX",
"XYY",
"YXX",
"YYX",
"YYY",
"XXXY",
"XXYX",
"XXYY",
"XYXX",
"XYYY",
"YXXX",
"YYYX",
"XXXYX",
"XYXXX",
"XYYYX"
]

class Module(object):
    def __init__(self, name, data, rotation, mesh_position):
        self.count = 0
        self.name = name
        self.rotation = rotation
        self.self_attraction = data.get("self_attraction", 1)

        self.sockets = data["sockets"].copy()
        self.links = []
        for i in range(6):
            self.links.append(set())

        self.original_scene_object_name = data["scene_object_name"]
        self.create_transformed_object(rotation, mesh_position)

    def create_transformed_object(self, rotation, mesh_position):
        """ Mesh position is only needed to neatly present all the generated meshes
        it has no impact on anything else """
        # The name already contains the original object name + the rotation idx
        # Duplicate the object AND its data
        # - We don't want the underlying mesh to be the same, otherwise the
        # rotations won't work
        if bpy.data.objects[self.original_scene_object_name].data is not None:
            new_obj = bpy.data.objects.new(
                f"{self.name}",
                bpy.data.objects[self.original_scene_object_name].data.copy()
            )
        else:  # Needed for empty objects
            new_obj = bpy.data.objects.new(
                f"{self.name}",
                bpy.data.objects[self.original_scene_object_name].data
            )
        # Link to collection
        bpy.data.collections['Generated modules'].objects.link(new_obj)
        # Rotate
        x_rotation = Vector3(90, 0, 0)
        y_rotation = Vector3(0, 90, 0)

        rotations_order = ROTATIONS[rotation]
        # Apply each single transformation individually
        # And swap the sockets to their new direction
        for rotation_axis in rotations_order:
            if rotation_axis == "X":
                blender_rotate(new_obj, x_rotation)
                self.rotate_sockets(rotation_axis)
            elif rotation_axis == "Y":
                blender_rotate(new_obj, y_rotation)
                self.rotate_sockets(rotation_axis)
            else:
                print("UNKNOWN ROTATION:", rotation_axis)

        # Translate
        new_obj.location = (mesh_position.x * 4, mesh_position.y * 4, mesh_position.z * 4)

    def rotate_sockets(self, rotation_axis):
        i0 = self.sockets[0]
        i1 = self.sockets[1]
        i2 = self.sockets[2]
        i3 = self.sockets[3]
        i4 = self.sockets[4]
        i5 = self.sockets[5]
        if rotation_axis == "X":
            self.sockets[0] = i1
            self.sockets[1] = i3
            self.sockets[3] = i4
            self.sockets[4] = i0
        elif rotation_axis == "Y":
            self.sockets[0] = i5
            self.sockets[2] = i0
            self.sockets[3] = i2
            self.sockets[5] = i3

    def create_link(self, nodeB, direction):
        self.links[direction].add(nodeB)

    def __repr__(self):
        return f"{self.name:<25}{self.count}"

        # DEBUG: To display links

        # tmp1 = f"\n{'-'*10} - {self.name}\n"
        # for index, possible_modules_for_this_direction in enumerate(self.links):
        #     tmp1 += f"\t{index}: "
        #     for possible_module in possible_modules_for_this_direction:
        #         tmp1 += f"{possible_module.name}, "
        #     tmp1 += '\n'
        # return tmp1

        # DEBUG: To display sockets

        # tmp1 = f"\n{'-'*2} - {self.name}\n"
        # for index, sockets in enumerate(self.sockets):
        #     tmp1 += f"\t{index}: "
        #     for socket in sockets:
        #         tmp1 += f"{socket}, "
        #     tmp1 += '\n'
        # return tmp1


class Vector3(object):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return f"{self.x}/{self.y}/{self.z}"


if __name__ == "__main__":
    print("\n"*200)
    print("="*20)
    print("="*20)
    app = App()
