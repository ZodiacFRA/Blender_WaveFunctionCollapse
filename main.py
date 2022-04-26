import sys
import bpy
import json
import time
import random
from pprint import pprint

GRID_SIZE = 2
MAX_CONSECUTIVE_OVERRIDES = 20


class App(object):
    def __init__(self):
        random.seed(42)
        self.deltaTime = 0.01
        self.endTime = time.time()

        self.modules = {}
        self.socket_types_count = 0
        self.load_modules_data("/home/seub/perso/Trackmania-WFC/path.json")
        print(f"{len(self.modules)} modules, {self.socket_types_count + 1} socket types")

        # Initialize map
        self.map = []
        for x in range(GRID_SIZE):
            self.map.append([] * GRID_SIZE)
            for y in range(GRID_SIZE):
                self.map[x].append([set([m for m in self.modules.values()])] *
                                GRID_SIZE)

        pprint(self.map)
        self.last_chosen_module = None
        self.overrides_count = 0
        self.consecutive_overrides_count = 0
        # Perform WFC on the map
        self.waveshift_function_collapse()
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
        for name, module in self.modules.items():
            # For each direction
            for direction, matching_cell_socket_types in enumerate(module.neighbors):
                # For each matching socket type (each direction can have multiple socket types)
                for matching_cell_socket_type in matching_cell_socket_types:
                    # Add all matching sockets
                    for b_name, b_module in self.modules.items():
                        b_socket_type = b_module.neighbors[self.get_opposite_direction(direction)]
                        if matching_cell_socket_type in b_socket_type:
                            self.create_link(module, direction, b_module)

    def create_link(self, nodeA, direction, nodeB):
        nodeA.create_link(nodeB, direction)
        # print('-'*20)
        # print(f"from {nodeA} to {nodeB} / {direction}")
        direction = self.get_opposite_direction(direction)
        # print(f"from {nodeB} to {nodeA} / {direction}")
        nodeB.create_link(nodeA, direction)

    def get_opposite_direction(self, dir): #perhaps here
        return (dir + 3) % 6

    def choose_module_from_possibilities(self, cell, possible_modules, type="lowest"):
        if type == "lowest":
            res = []
            lowest = GRID_SIZE * GRID_SIZE
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
# WFC functions
    def waveshift_function_collapse(self):
        while 1:
            print("in")
            self.handle_loop()
            # Update the display so we can see the algorithm working in real time
            # Get the next cell to update
            cell = self.get_minimal_entropy_cell()
            if cell is None:
                break
            module = self.choose_module_from_possibilities(cell, self.map[cell.x][cell.y][cell.z], "lowest")
            self.last_chosen_module = module
            module.count += 1
            self.map[cell.x][cell.y][cell.z] = {module}
            # Now propagate to neighbors
            self.update_possibilities(cell, 20)
            self.display_map()


    def update_possibilities(self, cell, depth):
        # End of recursion conditions
        # if depth == 0:
        #     return

        to_be_updated_neighbors = set()
       

        # Propagate the collapse to neighbor which had changes
        for neighbor in to_be_updated_neighbors:
            self.update_possibilities(neighbor, depth - 1)

    def update_neighbor(self, cell, neighbor, direction):
        out = set()
        possible_modules = set()
        cell_modules = self.map[cell.x][cell.y][cell.z]
        # For each possible module of the cell
        for cell_module in cell_modules:
            # Add the possibilities based on this direction
            for module in cell_module.links[direction]:
                possible_modules.add(module)
        # Remove impossible modules in the upper neighbor
        tmp = set()
        # For each possible module in the neighbor, remove impossible modules
        for neighbor_possible_module in self.map[neighbor.x][neighbor.y][neighbor.z]:
            if neighbor_possible_module in possible_modules:
                tmp.add(neighbor_possible_module)
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
        for z in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                for x in range(GRID_SIZE):
                    # Ignore already finished cells
                    if len(self.map[x][y][z]) < 2:
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
# Display functions
    def display_map(self):
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                for z in range(GRID_SIZE):
                    if len(self.map[x][y][z]) == 1:
                        module = list(self.map[x][y][z])[0]
                        bpy.data.objects[module.sprite_path].select_set(True)
                        new_obj = bpy.context.active_object.copy()
                        new_obj.location = new_obj.location + mathutils.Vector((x,y,z))
                        # self.display.blit(module.sprite, (x*TILE_SIZE, y*TILE_SIZE))

    def handle_loop(self):
        delta = time.time() - self.endTime
        if delta < self.deltaTime:
            time.sleep(self.deltaTime - delta)
        self.endTime = time.time()


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

        self.load_sprite(data["sprite_name"])

    def load_sprite(self, sprite_path):
        self.sprite = bpy.data.objects[sprite_path]
        # self.sprite = pygame.image.load(
        #     f"""./assets/{sprite_path}""")
        # # Transform it to a pygame friendly format (quicker drawing)
        # self.sprite.convert()
        # self.sprite = pygame.transform.scale(self.sprite,
        #                                     (tile_size, tile_size))
        # ALL PYGAME ROTATIONS ARE COUNTERCLOCKWISE
        # if self.rotation != 0:
        #     self.sprite = pygame.transform.rotate(self.sprite, self.rotation)
        # top = self.neighbors[0]
        # right = self.neighbors[1]
        # bottom = self.neighbors[2]
        # left = self.neighbors[3]
        # if self.rotation == 90:
        #     self.neighbors = [right, bottom, left, top]
        # elif self.rotation == 180:
        #     self.neighbors = [bottom, left, top, right]
        # elif self.rotation == 270:
        #     self.neighbors = [left, top, right, bottom]

    def create_link(self, nodeB, direction):
        self.links[direction].add(nodeB)

    def __repr__(self):
        return f"{self.name:<20} {self.count}"


class Position(object):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return f"x:{self.x} y:{self.y} z:{self.z}"


if __name__ == "__main__":
    print("="*20)
    app = App()