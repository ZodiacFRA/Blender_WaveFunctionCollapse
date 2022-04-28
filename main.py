import sys
import bpy
import json
import time
import random
import mathutils
from pprint import pprint

X_GRID_SIZE = 20
Y_GRID_SIZE = 20
Z_GRID_SIZE = 20
MAX_CONSECUTIVE_OVERRIDES = 20


class App(object):
    def __init__(self):
        seed = random.randint(0, 100)
        random.seed(seed)
        print("Seed:", seed)
        self.deltaTime = 0.0001
        self.endTime = time.time()

        self.modules = {}
        self.socket_types_count = 0
        self.load_modules_data("/home/seub/perso/Trackmania-WFC/path.json")
        print(f"{len(self.modules)} modules, {self.socket_types_count + 1} socket types")

        # Initialize map
        self.map = []
        for x in range(X_GRID_SIZE):
            tmpY = []
            for y in range(Y_GRID_SIZE):
                tmpZ = []
                for z in range(Z_GRID_SIZE):
                    # Add one single cell, z times
                    tmpZ.append(set([m for m in self.modules.values()]))
                # Add one single line, y times
                tmpY.append(tmpZ)
            # Add one single plane, x times
            self.map.append(tmpY)
        

        self.last_chosen_module = None
        self.overrides_count = 0
        self.consecutive_overrides_count = 0
        # Perform WFC on the map
        self.waveshift_function_collapse()
        self.display_map()
        pprint(list(self.modules.values()))
        print(f"{self.overrides_count} overrides")

#########################################
# Utility functions
    def load_modules_data(self, filepath):
        with open(filepath, "r") as f:
            modules_data = json.load(f)
        # Create all modules
        for module in modules_data:
            for directions in module["neighbors"]:
                for socket_type in directions:
                    if socket_type > self.socket_types_count:
                        self.socket_types_count = socket_type
            for rotation in module["rotations"]:
                name = f"""{module["module_name"]}_{rotation}"""
                self.modules[name] = Module(name, module, rotation)
        self.create_links()

    def create_links(self):
        # For each module
        for a_name, a_module in self.modules.items():
            # For each direction
            for direction, matching_cell_socket_types in enumerate(a_module.neighbors):
                # For each matching socket type (each direction can have multiple socket types)
                for a_socket_type in matching_cell_socket_types:
                    # Add all matching sockets
                    for b_name, b_module in self.modules.items():
                        b_socket_types = b_module.neighbors[self.get_opposite_direction(direction)]
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
#dum dee dum WFC functions
    def waveshift_function_collapse(self):
        while 1:
            self.handle_loop()
            # Update the display so we can see the algorithm working in real time
            # Get the next cell to update
            cell = self.get_minimal_entropy_cell()
            if cell is None:
                print("no cell found")
                break
            module = self.choose_module_from_possibilities(
                cell, self.map[cell.x][cell.y][cell.z], "lowest"
            )
            self.last_chosen_module = module
            module.count += 1
            # Assign cell
            self.map[cell.x][cell.y][cell.z] = {module}
            # self.duplicate_and_place_object(module.sprite_path, cell)
            # Now propagate to neighbors
            self.update_possibilities(cell, 20)

    def update_possibilities(self, cell, depth):
        # End of recursion conditions
        # if depth == 0:
        #     return
        to_be_updated_neighbors = set()
        # Top
        neighbor = Position(cell.x, cell.y, cell.z + 1)
        if cell.z < Z_GRID_SIZE - 1 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 0))
        # Bottom
        neighbor = Position(cell.x, cell.y, cell.z - 1)
        if cell.z > 0 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 3))
        # Front
        neighbor = Position(cell.x, cell.y - 1, cell.z)
        if cell.y > 0 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 4))
        # Back
        neighbor = Position(cell.x, cell.y + 1, cell.z)
        if cell.y < Y_GRID_SIZE - 1 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 1))
        # Left
        neighbor = Position(cell.x - 1, cell.y, cell.z)
        if cell.x > 0 and len(self.map[neighbor.x][neighbor.y][neighbor.z]) > 1:
            to_be_updated_neighbors.update(self.update_neighbor(cell, neighbor, 5))
        # Right
        neighbor = Position(cell.x + 1, cell.y, cell.z)
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
                        minimal_entropy_cells = [Position(x, y, z)]
                    # Add to the list of lowest entropy cells
                    elif len(self.map[x][y][z]) == minimal_entropy:
                        minimal_entropy_cells.append(Position(x, y, z))

        if len(minimal_entropy_cells) > 0:
            # Choose a random minimum entropy cell
            return random.choice(minimal_entropy_cells)
        return None

#########################################
# Blender functions
    def handle_loop(self):
        delta = time.time() - self.endTime
        if delta < self.deltaTime:
            time.sleep(self.deltaTime - delta)
        self.endTime = time.time()

    def duplicate_and_place_object(self, object_name, position):
        if object_name == 'Empty':
            return
        # the new object is created with the old object's data, which makes it "linked"
        my_new_obj = bpy.data.objects.new(f"{object_name}_{position}", bpy.data.objects[object_name].data)
        # now it's just an object ref and you can move it to an absolute position
        my_new_obj.location = (position.x * 2, position.y * 2, position.z * 2)
        # when you create a new object manually this way it's not part of any collection, add it to the active collection so you can actually see it in the viewport
        bpy.context.collection.objects.link(my_new_obj)
    
    def display_map(self):
        for x in range(X_GRID_SIZE):
            for y in range(Y_GRID_SIZE):
                for z in range(Z_GRID_SIZE):
                    pos = Position(x,y,z)
                    states = self.map[x][y][z]
                    if len(states) == 1:
                        self.duplicate_and_place_object(states.pop().sprite_path, pos)
                    else:
                        print(f"ignored: {pos} due to {len(states)}")

class Module(object):
    def __init__(self, name, data, rotation):
        self.count = 0
        self.name = name
        self.rotation = rotation
        self.self_attraction = data.get("self_attraction", 1)

        self.neighbors = data["neighbors"]
        self.links = []
        for i in range(6):
            self.links.append(set())

        # self.load_sprite(data["sprite_name"])
        self.sprite_path = data["sprite_name"]

    # def load_sprite(self, sprite_path):
    #     self.sprite = bpy.data.objects[sprite_path]
    
    #     if self.rotation != 0:
    #         self.sprite = pygame.transform.rotate(self.sprite, self.rotation)
    #     top = self.neighbors[0]
    #     right = self.neighbors[1]
    #     bottom = self.neighbors[2]
    #     left = self.neighbors[3]
    #     if self.rotation == 90:
    #         self.neighbors = [right, bottom, left, top]
    #     elif self.rotation == 180:
    #         self.neighbors = [bottom, left, top, right]
    #     elif self.rotation == 270:
    #         self.neighbors = [left, top, right, bottom]

    def create_link(self, nodeB, direction):
        #check if module already added
        self.links[direction].add(nodeB)

    def __repr__(self):
        # return f"{self.name} ({self.count} {self.links})"
        tmp1 = f"{self.name}\n"
        for index, possible_modules_for_this_direction in enumerate(self.links):
            tmp1 += f"\t{index}: "
            for possible_module in possible_modules_for_this_direction:
                tmp1 += f"{possible_module.name}, "
            tmp1 += '\n'
        return tmp1


class Position(object):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return f"x:{self.x} y:{self.y} z:{self.z}"


if __name__ == "__main__":
    print("\n"*200)
    print("="*20)
    print("="*20)
    app = App()
